"""Integração com a Groq API para classificar automaticamente itens inéditos."""

from __future__ import annotations

from typing import Iterable, Sequence

from src.database import (
	ItemParaClassificacao,
	listar_categorias,
	listar_itens_para_classificacao,
	registrar_classificacao_itens,
)

from .groq import ClassificacaoResultado, GroqClassifier

__all__ = [
	"ClassificacaoResultado",
	"GroqClassifier",
	"classificar_itens_pendentes",
]


def classificar_itens_pendentes(
	*,
	limit: int = 25,
	confirmar: bool = False,
	db_path: str | None = None,
	classifier: GroqClassifier | None = None,
	model: str | None = None,
	temperature: float | None = None,
) -> list[ClassificacaoResultado]:
	"""Busca itens sem categoria, envia para a Groq e persiste o resultado."""

	itens = listar_itens_para_classificacao(limit=limit, db_path=db_path)
	if not itens:
		return []

	categorias = [categoria.nome for categoria in listar_categorias(db_path=db_path)]

	if classifier is None:
		# Garantir que o prompt sempre receba as categorias conhecidas
		if model is not None and temperature is not None:
			classifier = GroqClassifier(model=model, temperature=temperature, categorias=categorias)
		elif model is not None:
			classifier = GroqClassifier(model=model, categorias=categorias)
		elif temperature is not None:
			classifier = GroqClassifier(temperature=temperature, categorias=categorias)
		else:
			classifier = GroqClassifier(categorias=categorias)

	resultados = classifier.classificar_itens(itens)
	_salvar_resultados(resultados, confirmar=confirmar, db_path=db_path)
	return resultados


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
