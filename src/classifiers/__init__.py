"""Integração com modelos Gemini via LiteLLM para classificar itens."""

from __future__ import annotations

import re
import unicodedata
from typing import Callable, Iterable, Sequence

from src.database import (
	ItemParaClassificacao,
	listar_categorias,
	listar_itens_para_classificacao,
	registrar_classificacao_itens,
	obter_categoria_de_produto,
	limpar_categorias_para_reclassificacao,
	limpar_classificacoes_completas,
)

from src.logger import setup_logging
from src.medidas import extrair_tamanho, normalizar_unidade
from .llm_classifier import ClassificacaoResultado, LLMClassifier
from .embeddings import SIMILARIDADE_MINIMA, buscar_produtos_semelhantes

logger = setup_logging("classifiers")

__all__ = [
	"ClassificacaoResultado",
	"LLMClassifier",
	"classificar_itens_pendentes",
]


def classificar_itens_pendentes(
	*,
	limit: int = 25,
	confirmar: bool = False,
	db_path: str | None = None,
	classifier: LLMClassifier | None = None,
	model: str | None = None,
	temperature: float | None = None,
	chave_acesso: str | None = None,
	model_priority: Sequence[str] | None = None,
	progress_callback: Callable[[str], None] | None = None,
	incluir_confirmados: bool = False,
	limpar_confirmadas_antes: bool = False,
	forcar_llm: bool = False,
) -> list[ClassificacaoResultado]:
	"""Busca itens pendentes de classificação, aplica classificação híbrida e persiste o resultado.

	A ordem do pipeline é:
	1. (Opcional) Limpeza de classificações anteriores da nota (`limpar_confirmadas_antes`)
	2. Busca semântica via ChromaDB (cache de produtos) – exceto se `forcar_llm=True`
	3. Fallback para LLM (via `LLMClassifier`) para itens ainda não classificados

	Args:
		limit: Número máximo de itens a processar em uma execução.
		confirmar: Se True, grava a categoria como confirmada (além de sugerida) ao salvar
			resultados no banco.
		db_path: Caminho opcional para o arquivo SQLite a ser usado. Se None, usa o padrão
			definido em `src.database`.
		classifier: Instância pré-configurada de `LLMClassifier`. Se não for fornecida,
			uma nova instância será criada com base em `model`, `temperature` e nas
			categorias conhecidas do banco.
		model: Identificador do modelo LLM a ser usado pelo `LLMClassifier` (ex.: Gemini).
			Usado apenas se `classifier` não for informado.
		temperature: Temperatura a ser usada nas chamadas ao LLM. Usado apenas se
			`classifier` não for informado.
		chave_acesso: Se informado, limita a classificação aos itens de uma única NFC-e
			(identificada pela chave de acesso). Também é usado para controlar a limpeza
			de classificações anteriores.
		model_priority: Lista de IDs de modelos em ordem de preferência, passada para
			`LLMClassifier.classificar_itens` para controlar o fallback entre modelos.
		progress_callback: Função opcional chamada em diferentes etapas do processo
			(recebe uma string de status), útil para atualizar a UI (ex.: Streamlit).
		incluir_confirmados: Se True, também inclui itens que já possuem categoria
			confirmada para reclassificação. Se False, processa apenas itens sem
			categoria (pendentes).
		limpar_confirmadas_antes: Se True e `chave_acesso` for fornecida, remove as
			categorias confirmadas da nota antes de reprocessar. Em modo normal (com
			`forcar_llm=False`), apenas as categorias confirmadas são limpas.
		forcar_llm: Se True, pula totalmente a etapa de busca semântica via Chroma e
			força classificação via LLM para todos os itens. Quando combinado com
			`limpar_confirmadas_antes=True`, ativa o modo "full reset", limpando todas
			as classificações (confirmadas ou não, incluindo vínculo de produto) antes
			de reclassificar a nota via LLM.

	Returns:
		list[ClassificacaoResultado]: Lista com os resultados de classificação
		(semântica e/ou via LLM) para cada item processado.
	"""

	# Se solicitado, limpar todas as classificações antes de reprocessar
	if limpar_confirmadas_antes:
		if not chave_acesso:
			# Evitar comportamento silencioso quando a flag é True mas não há chave definida
			logger.warning(
				"Solicitado 'limpar_confirmadas_antes=True', mas nenhuma 'chave_acesso' foi informada. "
				"Nenhuma classificação anterior será limpa."
			)
			if progress_callback:
				progress_callback(
					"Aviso: solicitado limpar classificações anteriores, mas nenhuma chave da nota foi informada. "
					"Nenhuma limpeza foi realizada."
				)
		else:
			if forcar_llm:
				# Modo full reset: limpar tudo (categorias + produtos)
				num_limpos = limpar_classificacoes_completas(chave_acesso, db_path=db_path)
				if num_limpos > 0:
					logger.info(
						"Resetadas TODAS as classificações (%s itens) da nota %s antes de reprocessar com LLM.",
						num_limpos,
						chave_acesso,
					)
					if progress_callback:
						progress_callback(
							f"Limpas {num_limpos} classificações anteriores (modo full reset)."
						)
			else:
				# Modo parcial: devolve os itens confirmados à fila de reclassificação
				# (zera sugerida e confirmada), preservando produto_id e embeddings
				num_limpos = limpar_categorias_para_reclassificacao(chave_acesso, db_path=db_path)
				if num_limpos > 0:
					logger.info(
						"Resetadas %s categorias confirmadas para a nota %s antes de reprocessar.",
						num_limpos,
						chave_acesso,
					)
					if progress_callback:
						progress_callback(f"Limpas {num_limpos} categorias confirmadas.")

	itens = listar_itens_para_classificacao(
		limit=limit,
		chave_acesso=chave_acesso,
		db_path=db_path,
		incluir_confirmados=incluir_confirmados,
		apenas_sem_categoria=not incluir_confirmados,  # Se incluindo confirmados, não filtrar por categoria_sugerida
	)
	if not itens:
		if chave_acesso:
			logger.info("Nenhum item pendente encontrado para a nota %s.", chave_acesso)
		else:
			logger.info("Nenhum item pendente de classificação.")
		return []

	if chave_acesso:
		logger.info("Iniciando classificação de %s itens para a nota %s.", len(itens), chave_acesso)
	else:
		logger.info(f"Iniciando classificação de {len(itens)} itens.")

	if progress_callback:
		progress_callback(f"Iniciando classificação de {len(itens)} itens...")

	resultados_finais: list[ClassificacaoResultado] = []
	itens_para_llm: list[ItemParaClassificacao] = []

	# 1. Tentar classificação semântica via Chroma (apenas se não forcar LLM)
	if forcar_llm:
		logger.info("Modo forçar LLM ativado: pulando busca semântica via Chroma.")
		if progress_callback:
			progress_callback("Modo LLM-only ativado: todos os itens serão reclassificados pela IA.")
		itens_para_llm = list(itens)
	else:
		if progress_callback:
			progress_callback("Buscando classificações em cache semântico...")

		for item in itens:
			matches = buscar_produtos_semelhantes(item.descricao, top_k=1)
			match = matches[0] if matches else None

			# Se encontrou algo com alta confiança (similaridade de cosseno >= SIMILARIDADE_MINIMA)
			if match and (match.get("score") or 0.0) >= SIMILARIDADE_MINIMA:
				categoria = match.get("categoria")
				# Só usa se categoria estiver preenchida
				if categoria and categoria.strip():
					logger.debug(f"Match semântico encontrado para '{item.descricao}': {categoria} (score: {match.get('score')})")
					resultados_finais.append(
						ClassificacaoResultado(
							chave_acesso=item.chave_acesso,
							sequencia=item.sequencia,
							categoria=categoria,
							confianca=match.get("score"),
							origem="chroma-cache",
							modelo="all-MiniLM-L6-v2",
							observacoes=f"Match semântico com descrição: {match.get('descricao_original', '')}",
							produto_nome=match.get("nome_base"),
							produto_marca=_marca_confiavel(match, item.descricao),
							produto_id=match.get("produto_id"),
						)
					)
					continue

			# Se não encontrou ou confiança baixa, vai para o LLM
			itens_para_llm.append(item)

		if progress_callback and resultados_finais:
			progress_callback(f"{len(resultados_finais)} item(ns) classificado(s) via cache semântico.")

	# 2. Processar itens restantes com o LLM
	if itens_para_llm:
		if progress_callback:
			progress_callback(f"Preparando {len(itens_para_llm)} item(ns) para classificação via LLM...")

		if classifier is None:
			classifier = _criar_classifier(model, temperature, db_path)

		logger.info(f"Enviando {len(itens_para_llm)} itens para a API do LLM configurado.")
		resultados_llm = classifier.classificar_itens(
			itens_para_llm,
			model_priority=model_priority,
			progress_callback=progress_callback,
		)
		resultados_finais.extend(resultados_llm)

		nao_classificados = getattr(classifier, "itens_nao_classificados", None) or []
		if nao_classificados:
			mensagem = (
				f"{len(nao_classificados)} item(ns) ficaram sem classificação após tentar "
				"todos os modelos; revise-os na aba de análise."
			)
			logger.warning(mensagem)
			if progress_callback:
				progress_callback(mensagem)
	else:
		if progress_callback:
			progress_callback("Nenhum item necessita classificação via LLM.")

	# 3. Tamanho da embalagem para os itens do cache semântico, que não passaram
	# pela IA: só os vendidos por unidade e sem tamanho na descrição
	itens_por_chave = {(item.chave_acesso, item.sequencia): item for item in itens}
	sem_tamanho = [
		(resultado, itens_por_chave[(resultado.chave_acesso, resultado.sequencia)])
		for resultado in resultados_finais
		if resultado.origem == "chroma-cache"
		and _precisa_tamanho(itens_por_chave.get((resultado.chave_acesso, resultado.sequencia)))
	]
	if sem_tamanho:
		if classifier is None:
			classifier = _criar_classifier(model, temperature, db_path)
		if progress_callback:
			progress_callback(f"Buscando o tamanho da embalagem de {len(sem_tamanho)} item(ns) via IA...")
		try:
			tamanhos = classifier.sugerir_tamanhos(
				[item for _, item in sem_tamanho], model_priority=model_priority
			)
		except Exception as exc:  # noqa: BLE001 - o tamanho nunca bloqueia a classificação
			logger.warning("Não foi possível obter o tamanho das embalagens: %s", exc)
			tamanhos = {}
		for resultado, item in sem_tamanho:
			resultado.tamanho = tamanhos.get((item.chave_acesso, item.sequencia))

	_salvar_resultados(resultados_finais, confirmar=confirmar, db_path=db_path)
	logger.info(f"Classificação concluída. {len(resultados_finais)} itens processados.")
	return resultados_finais


def _criar_classifier(
	model: str | None, temperature: float | None, db_path: str | None
) -> LLMClassifier:
	# Garantir que o prompt sempre receba as categorias conhecidas
	categorias = [categoria.nome for categoria in listar_categorias(db_path=db_path)]
	if model is not None and temperature is not None:
		return LLMClassifier(model=model, temperature=temperature, categorias=categorias)
	if model is not None:
		return LLMClassifier(model=model, categorias=categorias)
	if temperature is not None:
		return LLMClassifier(temperature=temperature, categorias=categorias)
	return LLMClassifier(categorias=categorias)


def _precisa_tamanho(item: ItemParaClassificacao | None) -> bool:
	"""Item vendido por unidade, sem tamanho na descrição nem já informado."""
	return (
		item is not None
		and not item.tamanho
		and normalizar_unidade(item.unidade) not in ("KG", "L")
		and extrair_tamanho(item.descricao) is None
	)


# Acima disso, a descrição é praticamente igual à indexada e a marca pode ser herdada
_SCORE_DESCRICAO_IDENTICA = 0.99


def _normalizar_para_comparacao(texto: str) -> str:
	sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
	return " ".join(re.sub(r"[^A-Za-z0-9]+", " ", sem_acento).upper().split())


def _marca_confiavel(match: dict, descricao: str) -> str | None:
	"""Marca do match semântico, só quando ela vale para a descrição do item.

	O vizinho mais próximo pode ser de outra marca ("SCOXA FGO SEARA" casa com
	"SCOXA FGO SADIA"). A marca é herdada se a descrição for praticamente igual
	à indexada ou se a marca aparecer na própria descrição; senão fica vazia
	para o LLM ou a revisão manual preencherem.
	"""
	marca = (match.get("marca_base") or "").strip()
	if not marca:
		return None
	if (match.get("score") or 0.0) >= _SCORE_DESCRICAO_IDENTICA:
		return marca
	marca_norm = _normalizar_para_comparacao(marca)
	descricao_norm = f" {_normalizar_para_comparacao(descricao or '')} "
	return marca if marca_norm and f" {marca_norm} " in descricao_norm else None


def _salvar_resultados(
	resultados: Iterable[ClassificacaoResultado],
	*,
	confirmar: bool,
	db_path: str | None,
) -> None:
	dados = [
		{
			"chave_acesso": resultado.chave_acesso,
			"sequencia": resultado.sequencia,
			"categoria": resultado.categoria,
			"confianca": resultado.confianca,
			"origem": resultado.origem,
			"modelo": resultado.modelo,
			"observacoes": resultado.observacoes,
			"resposta_json": resultado.resposta_json,
			"produto_nome": resultado.produto_nome,
			"produto_marca": resultado.produto_marca,
			"produto_id": resultado.produto_id,
			"tamanho": resultado.tamanho,
		}
		for resultado in resultados
	]
	if dados:
		registrar_classificacao_itens(dados, confirmar=confirmar, db_path=db_path)
