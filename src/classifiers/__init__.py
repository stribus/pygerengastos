"""Integração com modelos Gemini via LiteLLM para classificar itens."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from src.database import (
	ItemParaClassificacao,
	listar_categorias,
	listar_itens_para_classificacao,
	registrar_classificacao_itens,
	obter_categoria_de_produto,
	limpar_categorias_confirmadas,
	limpar_classificacoes_completas,
)

from src.logger import setup_logging
from .llm_classifier import ClassificacaoResultado, LLMClassifier
from .embeddings import buscar_produtos_semelhantes

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
	"""Busca itens sem categoria, envia para o LLM configurado e persiste o resultado.

	Args:
		incluir_confirmados: Se True, busca todos os itens da nota, incluindo os já confirmados.
		limpar_confirmadas_antes: Se True, limpa as classificações existentes antes de reprocessar.
		forcar_llm: Se True, pula a etapa de busca semântica via Chroma e força
		           classificação via LLM para todos os itens.
	"""

	# Se solicitado, limpar todas as classificações antes de reprocessar
	if limpar_confirmadas_antes and chave_acesso:
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
					progress_callback(f"Limpas {num_limpos} classificações anteriores (modo full reset).")
		else:
			# Modo parcial: limpar categorias (confirmadas e sugeridas), mas preservar produtos
			num_limpos = limpar_categorias_confirmadas(chave_acesso, db_path=db_path)
			if num_limpos > 0:
				logger.info(
					"Resetadas %s categorias (confirmadas e sugeridas) para a nota %s antes de reprocessar.",
					num_limpos,
					chave_acesso,
				)
				if progress_callback:
					progress_callback(f"Limpas {num_limpos} categorias (confirmadas e sugeridas).")

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

			# Se encontrou algo com alta confiança (>= 0.82)
			if match and (match.get("score") or 0.0) >= 0.82:
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
							produto_marca=match.get("marca_base"),
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

		categorias = [categoria.nome for categoria in listar_categorias(db_path=db_path)]

		if classifier is None:
			# Garantir que o prompt sempre receba as categorias conhecidas
			if model is not None and temperature is not None:
				classifier = LLMClassifier(model=model, temperature=temperature, categorias=categorias)
			elif model is not None:
				classifier = LLMClassifier(model=model, categorias=categorias)
			elif temperature is not None:
				classifier = LLMClassifier(temperature=temperature, categorias=categorias)
			else:
				classifier = LLMClassifier(categorias=categorias)

		logger.info(f"Enviando {len(itens_para_llm)} itens para a API do LLM configurado.")
		resultados_llm = classifier.classificar_itens(
			itens_para_llm,
			model_priority=model_priority,
			progress_callback=progress_callback,
		)
		resultados_finais.extend(resultados_llm)
	else:
		if progress_callback:
			progress_callback("Nenhum item necessita classificação via LLM.")

	_salvar_resultados(resultados_finais, confirmar=confirmar, db_path=db_path)
	logger.info(f"Classificação concluída. {len(resultados_finais)} itens processados.")
	return resultados_finais


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
		}
		for resultado in resultados
	]
	if dados:
		registrar_classificacao_itens(dados, confirmar=confirmar, db_path=db_path)
