"""Tamanho pela IA no fluxo de classificação e no script scripts/preencher_tamanhos.py."""
from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

from src.classifiers import ClassificacaoResultado, classificar_itens_pendentes
from src.classifiers.llm_classifier import LLMClassifier
from src.database import listar_itens_para_revisao, salvar_nota
from src.scrapers.receita_rs import NotaFiscal, NotaItem

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("preencher_tamanhos", RAIZ / "scripts" / "preencher_tamanhos.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)

CHAVE = "5" * 44
OUTRA = "6" * 44


def _importar(db_path, chave, descricoes):
	itens = [
		NotaItem(descricao=d, codigo=None, quantidade=Decimal("1"), unidade=u,
		         valor_unitario=Decimal("10"), valor_total=Decimal("10"))
		for d, u in descricoes
	]
	salvar_nota(NotaFiscal(chave_acesso=chave, emissao="10/05/2025 10:00:00", itens=itens), db_path=db_path)


def _tamanhos(db_path, chave):
	return [(i.descricao, i.tamanho, i.tamanho_fonte) for i in listar_itens_para_revisao(chave, db_path=db_path)]


class FakeLLM(LLMClassifier):  # type: ignore[misc]
	"""Classifica tudo como Bebidas e responde tamanhos a partir de um dicionário por descrição."""

	def __init__(self, tamanhos: dict[str, str | None]):  # pylint: disable=super-init-not-called
		self.model = "fake"
		self.itens_nao_classificados = []
		self.tamanhos = tamanhos
		self.pedidos_tamanho: list[str] = []

	def classificar_itens(self, itens, *, model_priority=None, progress_callback=None):
		return [
			ClassificacaoResultado(chave_acesso=i.chave_acesso, sequencia=i.sequencia, categoria="Bebidas",
			                       modelo="fake", tamanho=self.tamanhos.get(i.descricao))
			for i in itens
		]

	def sugerir_tamanhos(self, itens, *, model_priority=None):
		self.pedidos_tamanho.extend(i.descricao for i in itens)
		return {
			(i.chave_acesso, i.sequencia): self.tamanhos[i.descricao]
			for i in itens
			if self.tamanhos.get(i.descricao)
		}


@pytest.fixture
def db_path(tmp_path):
	db_path = tmp_path / "t.db"
	_importar(db_path, CHAVE, [
		("CHOPP TRADICIONAL TU", "UNID"),  # sem tamanho
		("AGUA SARANDI C/GAS 2L", "UNID"),  # tamanho na descrição
		("PAO FRANCES KG", "KG"),  # vendido por peso
	])
	return db_path


def _match_cache(descricao, top_k=1):
	return [{"score": 1.0, "categoria": "Bebidas", "nome_base": "Bebida", "descricao_original": descricao}]


def test_item_classificado_pela_ia_recebe_o_tamanho(db_path):
	fake = FakeLLM({"CHOPP TRADICIONAL TU": "1L"})
	with patch("src.classifiers.buscar_produtos_semelhantes", return_value=[]):
		classificar_itens_pendentes(classifier=cast(LLMClassifier, fake), db_path=db_path)

	assert _tamanhos(db_path, CHAVE)[0] == ("CHOPP TRADICIONAL TU", "1L", "ia")
	assert fake.pedidos_tamanho == []  # a classificação já trouxe o tamanho


def test_item_do_cache_sem_tamanho_vai_para_a_chamada_extra(db_path):
	fake = FakeLLM({"CHOPP TRADICIONAL TU": "1L"})
	with patch("src.classifiers.buscar_produtos_semelhantes", side_effect=_match_cache):
		classificar_itens_pendentes(classifier=cast(LLMClassifier, fake), db_path=db_path)

	# só o item sem tamanho na descrição e vendido por unidade é perguntado
	assert fake.pedidos_tamanho == ["CHOPP TRADICIONAL TU"]
	assert _tamanhos(db_path, CHAVE)[0] == ("CHOPP TRADICIONAL TU", "1L", "ia")
	assert _tamanhos(db_path, CHAVE)[1][1:] == (None, None)


def test_falha_na_chamada_extra_nao_impede_a_classificacao(db_path):
	fake = FakeLLM({})

	def falhar(itens, *, model_priority=None):
		raise RuntimeError("API fora do ar")

	fake.sugerir_tamanhos = falhar  # type: ignore[method-assign]
	with patch("src.classifiers.buscar_produtos_semelhantes", side_effect=_match_cache):
		resultados = classificar_itens_pendentes(classifier=cast(LLMClassifier, fake), db_path=db_path)

	assert len(resultados) == 3


# ---------------------------------------------------------------------------
# scripts/preencher_tamanhos.py
# ---------------------------------------------------------------------------

def test_simulacao_lista_descricoes_sem_chamar_a_ia(db_path):
	_importar(db_path, OUTRA, [("CHOPP TRADICIONAL TU", "UNID"), ("CERVEJA SPATEN PURO", "UNID")])
	fake = FakeLLM({})

	relatorio = script.preencher(db_path, aplicar=False, classifier=fake)

	assert relatorio["descricoes"] == ["CERVEJA SPATEN PURO", "CHOPP TRADICIONAL TU"]
	assert relatorio["itens"] == 3
	assert fake.pedidos_tamanho == []
	assert _tamanhos(db_path, OUTRA)[0][1] is None


def test_aplicar_pergunta_uma_vez_por_descricao_e_propaga(db_path):
	_importar(db_path, OUTRA, [("CHOPP TRADICIONAL TU", "UNID"), ("CERVEJA SPATEN PURO", "UNID")])
	fake = FakeLLM({"CHOPP TRADICIONAL TU": "1L"})

	relatorio = script.preencher(db_path, aplicar=True, classifier=fake)

	assert sorted(fake.pedidos_tamanho) == ["CERVEJA SPATEN PURO", "CHOPP TRADICIONAL TU"]
	assert relatorio["preenchidas"] == {"CHOPP TRADICIONAL TU": "1L"}
	assert relatorio["sem_resposta"] == ["CERVEJA SPATEN PURO"]
	assert _tamanhos(db_path, CHAVE)[0][1:] == ("1L", "ia")
	assert _tamanhos(db_path, OUTRA)[0][1:] == ("1L", "ia")
