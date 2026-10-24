"""Testes da métrica de similaridade do cache semântico (Chroma)."""
from __future__ import annotations

import logging

import chromadb
import numpy as np
import pytest

from src.classifiers import embeddings


@pytest.fixture
def chroma_temporario(tmp_path, monkeypatch):
	"""Aponta o cache semântico para um diretório temporário e isola o cliente."""
	monkeypatch.setattr(embeddings, "_CHROMA_PERSIST_DIR", tmp_path / "chroma")
	monkeypatch.setattr(embeddings, "_espacos_avisados", set())
	embeddings._chroma_client = None
	yield tmp_path / "chroma"
	embeddings._chroma_client = None


def _cosseno(texto_a: str, texto_b: str) -> float:
	a = np.array(embeddings.gerar_embedding(texto_a))
	b = np.array(embeddings.gerar_embedding(texto_b))
	return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


@pytest.mark.parametrize(
	("distancia", "espaco", "esperado"),
	[
		(0.1338, "cosine", 0.8662),  # distância cosseno = 1 − cos
		(0.2676, "l2", 0.8662),  # L2² de vetores unitários = 2 − 2·cos
		(0.2000, "ip", 0.8000),  # produto interno: distância = 1 − <a, b>
		(1.4000, "cosine", 0.0),  # vetores opostos não geram score negativo
	],
)
def test_distancia_para_similaridade_por_metrica(distancia, espaco, esperado):
	assert embeddings._distancia_para_similaridade(distancia, espaco) == pytest.approx(esperado)


def test_colecao_nova_declara_metrica_cosseno(chroma_temporario):
	"""A métrica não pode depender do padrão da biblioteca: é declarada na criação."""
	colecao = embeddings._get_collection()

	assert embeddings._espaco_da_colecao(colecao) == "cosine"


def test_score_retornado_e_o_cosseno(chroma_temporario):
	"""O score de buscar_produtos_semelhantes é a similaridade de cosseno real."""
	embeddings.upsert_descricao_embedding("SCOXA FGO SADIA IQF 1KG", nome_base="Sobrecoxa", categoria="Carnes")

	resultado = embeddings.buscar_produtos_semelhantes("SCOXA FGO SEARA IQF 1KG", top_k=1)

	assert resultado[0]["score"] == pytest.approx(
		_cosseno("SCOXA FGO SEARA IQF 1KG", "SCOXA FGO SADIA IQF 1KG"), abs=1e-4
	)


def test_colecao_antiga_em_l2_continua_devolvendo_cosseno(chroma_temporario, caplog):
	"""Coleção criada com outra métrica (ex.: Chroma 0.x usava L2) mantém o score correto e avisa."""
	cliente = chromadb.PersistentClient(path=str(chroma_temporario))
	cliente.create_collection(
		name=embeddings._CHROMA_COLLECTION_NAME,
		embedding_function=embeddings._get_embedding_function(),
		configuration={"hnsw": {"space": "l2"}},
	)
	del cliente
	embeddings.upsert_descricao_embedding("CERV BUDWEISER 990ML", nome_base="Cerveja", categoria="Bebidas")

	with caplog.at_level(logging.WARNING):
		resultado = embeddings.buscar_produtos_semelhantes("CERV BUDWEISER 473ML", top_k=1)

	assert resultado[0]["score"] == pytest.approx(
		_cosseno("CERV BUDWEISER 473ML", "CERV BUDWEISER 990ML"), abs=1e-4
	)
	assert any("l2" in registro.getMessage() for registro in caplog.records)


def test_limiar_unico_compartilhado_pelo_cache_e_pelo_banco():
	"""O limiar mínimo de similaridade vive num só lugar."""
	from src import database

	assert embeddings.SIMILARIDADE_MINIMA == pytest.approx(0.82)
	assert not hasattr(database, "_SIMILARIDADE_MINIMA")
