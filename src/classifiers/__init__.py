"""Integração com modelos Gemini via LiteLLM para classificar itens."""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from src.database import (
	ItemParaClassificacao,
	listar_categorias,
	listar_itens_para_classificacao,
	registrar_classificacao_itens,
	obter_categoria_de_produto,
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
) -> list[ClassificacaoResultado]:
	"""Busca itens sem categoria, envia para o LLM configurado e persiste o resultado."""

	itens = listar_itens_para_classificacao(
		limit=limit,
		chave_acesso=chave_acesso,
		db_path=db_path,
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
	resultados_finais: list[ClassificacaoResultado] = []
	itens_para_llm: list[ItemParaClassificacao] = []

	# 1. Tentar classificação semântica via Chroma
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

	# 2. Processar itens restantes com o LLM
	if itens_para_llm:
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
