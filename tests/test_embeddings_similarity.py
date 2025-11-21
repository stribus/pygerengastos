from pathlib import Path

import pytest

from src.classifiers import embeddings
from src.database import _buscar_produto_por_descricao_similaridade, _criar_produto, conexao


def _setup_produto_temporario(db_path: Path) -> int:
    with conexao(db_path=db_path) as con:
        produto = _criar_produto(con, "Produto Semelhante", "Marca A")
    assert produto.id is not None
    return produto.id


def test_busca_produto_semelhante_utiliza_embeddings(monkeypatch, tmp_path):
    db_path = tmp_path / "test.duckdb"
    produto_id = _setup_produto_temporario(db_path)

    def _fake_busca(descricao: str, top_k: int = 3):
        return [
            {
                "produto_id": str(produto_id),
                "score": 0.95,
            }
        ]

    monkeypatch.setattr(embeddings, "buscar_produtos_semelhantes", _fake_busca)

    with conexao(db_path=db_path) as con:
        encontrado = _buscar_produto_por_descricao_similaridade(con, "descrição qualquer")

    assert encontrado is not None
    assert encontrado.id == produto_id


def test_busca_produto_semelhante_ignora_similaridade_baixa(monkeypatch, tmp_path):
    db_path = tmp_path / "test.duckdb"
    produto_id = _setup_produto_temporario(db_path)

    def _fake_busca(descricao: str, top_k: int = 3):
        return [
            {
                "produto_id": str(produto_id),
                "score": 0.3,
            }
        ]

    monkeypatch.setattr(embeddings, "buscar_produtos_semelhantes", _fake_busca)

    with conexao(db_path=db_path) as con:
        encontrado = _buscar_produto_por_descricao_similaridade(con, "descrição qualquer")

    assert encontrado is None
