"""Tamanho da embalagem informado na revisão manual (descrições truncadas)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.database import (
	_criar_produto,
	conexao,
	listar_itens_para_revisao,
	obter_compras_fora_da_unidade,
	obter_custos_unitarios_mensais,
	registrar_revisoes_manuais,
	salvar_nota,
)
from src.scrapers.receita_rs import NotaFiscal, NotaItem

CHAVE = "7" * 44


@pytest.fixture
def db_path(tmp_path):
	"""Chopp de 1 L com tamanho na descrição e um com a descrição truncada."""
	db_path = tmp_path / "t.db"
	itens = [
		NotaItem(descricao="CHOPP TUPINIQUIM PILSEN 1L", codigo=None, quantidade=Decimal("2"),
		         unidade="UN", valor_unitario=Decimal("11"), valor_total=Decimal("22")),
		NotaItem(descricao="CHOPP TRADICIONAL TU", codigo=None, quantidade=Decimal("1"),
		         unidade="UNID", valor_unitario=Decimal("10"), valor_total=Decimal("10")),
	]
	salvar_nota(NotaFiscal(chave_acesso=CHAVE, emissao="10/05/2025 10:00:00", itens=itens), db_path=db_path)
	with conexao(db_path) as con:
		produto = _criar_produto(con, "Chopp", None)
		con.execute("UPDATE itens SET produto_id = ?, produto_nome = ?", [produto.id, produto.nome_base])
	return db_path


def _revisar(db_path, tamanho):
	registrar_revisoes_manuais(
		[{"chave_acesso": CHAVE, "sequencia": 2, "categoria": "Bebidas",
		  "produto_nome": "Chopp", "tamanho": tamanho}],
		db_path=db_path,
	)


def test_sem_tamanho_a_compra_fica_fora(db_path):
	assert obter_compras_fora_da_unidade(["Chopp"], db_path=db_path) == {"Chopp": 1}


def test_tamanho_informado_inclui_a_compra_no_preco_por_litro(db_path):
	_revisar(db_path, "2l")

	custos = obter_custos_unitarios_mensais(["Chopp"], db_path=db_path)

	# (22 + 10) / (2 x 1 L + 1 x 2 L)
	assert custos[0]["custo_unitario_medio"] == pytest.approx(8.0)
	assert obter_compras_fora_da_unidade(["Chopp"], db_path=db_path) == {}
	assert listar_itens_para_revisao(CHAVE, db_path=db_path)[1].tamanho == "2L"


def test_tamanho_vazio_remove_o_informado(db_path):
	_revisar(db_path, "2l")
	_revisar(db_path, "")

	assert listar_itens_para_revisao(CHAVE, db_path=db_path)[1].tamanho is None


def test_tamanho_invalido_e_recusado(db_path):
	with pytest.raises(ValueError, match="Tamanho"):
		_revisar(db_path, "grande")

	assert listar_itens_para_revisao(CHAVE, db_path=db_path)[1].tamanho is None


def test_tamanho_nao_e_gravado_se_a_confirmacao_falha(db_path):
	"""Item sem categoria barra a confirmação; o tamanho do outro item não fica gravado pela metade."""
	with pytest.raises(ValueError, match="Categoria"):
		registrar_revisoes_manuais(
			[
				{"chave_acesso": CHAVE, "sequencia": 2, "categoria": "Bebidas", "tamanho": "2l"},
				{"chave_acesso": CHAVE, "sequencia": 1, "categoria": None},
			],
			confirmar=True,
			db_path=db_path,
		)

	assert listar_itens_para_revisao(CHAVE, db_path=db_path)[1].tamanho is None


def test_tamanho_nao_e_gravado_se_a_classificacao_falha(db_path, monkeypatch):
	import src.database as database

	def falhar(*args, **kwargs):
		raise RuntimeError("falha ao classificar")

	monkeypatch.setattr(database, "registrar_classificacao_itens", falhar)
	with pytest.raises(RuntimeError):
		_revisar(db_path, "2l")

	assert listar_itens_para_revisao(CHAVE, db_path=db_path)[1].tamanho is None


def test_tamanho_e_gravado_em_rascunho_sem_categoria(db_path):
	registrar_revisoes_manuais(
		[{"chave_acesso": CHAVE, "sequencia": 2, "categoria": None, "tamanho": "2l"}],
		db_path=db_path,
	)

	assert listar_itens_para_revisao(CHAVE, db_path=db_path)[1].tamanho == "2L"
