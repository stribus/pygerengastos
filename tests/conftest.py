"""Configuração compartilhada dos testes."""
from __future__ import annotations

import pytest


def pytest_configure(config):
	config.addinivalue_line(
		"markers",
		"chroma_padrao: o teste precisa do caminho padrão de data/chroma (não isolar)",
	)


@pytest.fixture(autouse=True)
def isolar_chroma(request, tmp_path, monkeypatch):
	"""Aponta o cache semântico (Chroma) para um diretório temporário em todo teste.

	Sem isso, salvar_nota, registrar_classificacao_itens e consolidar_produtos
	gravavam no data/chroma real do projeto, poluindo o cache usado pelo app com
	descrições, categorias e produto_ids de bancos temporários de teste.
	"""
	if request.node.get_closest_marker("chroma_padrao"):
		yield
		return

	from src.classifiers import embeddings

	monkeypatch.setattr(embeddings, "_CHROMA_PERSIST_DIR", tmp_path / "chroma_isolado")
	monkeypatch.setattr(embeddings, "_chroma_client", None)
	yield
	embeddings._chroma_client = None
