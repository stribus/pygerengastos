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
	registrar_classificacao_itens,
	registrar_revisoes_manuais,
	salvar_nota,
)
from src.scrapers.receita_rs import NotaFiscal, NotaItem
from src.ui.analise import _converter_registros, _montar_editor

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


# ---------------------------------------------------------------------------
# Origem do tamanho (usuário x IA), propagação por descrição e herança
# ---------------------------------------------------------------------------

OUTRA_CHAVE = "8" * 44


def _importar(db_path, chave, descricoes, unidade="UNID"):
	itens = [
		NotaItem(descricao=d, codigo=None, quantidade=Decimal("1"), unidade=unidade,
		         valor_unitario=Decimal("10"), valor_total=Decimal("10"))
		for d in descricoes
	]
	salvar_nota(NotaFiscal(chave_acesso=chave, emissao="10/06/2025 10:00:00", itens=itens), db_path=db_path)


def _tamanhos(db_path, chave):
	return [(i.tamanho, i.tamanho_fonte) for i in listar_itens_para_revisao(chave, db_path=db_path)]


def _classificar_com_tamanho(db_path, chave, sequencia, tamanho):
	registrar_classificacao_itens(
		[{"chave_acesso": chave, "sequencia": sequencia, "categoria": "Bebidas", "tamanho": tamanho}],
		db_path=db_path,
	)


def test_tamanho_do_usuario_vale_para_a_mesma_descricao_em_outras_notas(db_path):
	_importar(db_path, OUTRA_CHAVE, ["CHOPP TRADICIONAL TU", "CERVEJA SPATEN PURO"])

	_revisar(db_path, "2l")

	assert _tamanhos(db_path, CHAVE)[1] == ("2L", "usuario")
	assert _tamanhos(db_path, OUTRA_CHAVE) == [("2L", "usuario"), (None, None)]


def test_nota_importada_depois_herda_o_tamanho_da_mesma_descricao(db_path):
	_revisar(db_path, "2l")

	_importar(db_path, OUTRA_CHAVE, ["CHOPP TRADICIONAL TU"])

	assert _tamanhos(db_path, OUTRA_CHAVE) == [("2L", "usuario")]


def test_tamanho_da_ia_e_gravado_e_propagado(db_path):
	_importar(db_path, OUTRA_CHAVE, ["CHOPP TRADICIONAL TU"])

	_classificar_com_tamanho(db_path, CHAVE, 2, "1l")

	assert _tamanhos(db_path, CHAVE)[1] == ("1L", "ia")
	assert _tamanhos(db_path, OUTRA_CHAVE) == [("1L", "ia")]


def test_ia_nao_sobrescreve_o_usuario(db_path):
	_revisar(db_path, "2l")

	_classificar_com_tamanho(db_path, CHAVE, 2, "1l")

	assert _tamanhos(db_path, CHAVE)[1] == ("2L", "usuario")


def test_usuario_corrige_o_palpite_da_ia(db_path):
	_classificar_com_tamanho(db_path, CHAVE, 2, "1l")

	_revisar(db_path, "2l")

	assert _tamanhos(db_path, CHAVE)[1] == ("2L", "usuario")


def test_ia_e_ignorada_quando_a_descricao_ja_tem_tamanho(db_path):
	_classificar_com_tamanho(db_path, CHAVE, 1, "5l")

	assert _tamanhos(db_path, CHAVE)[0] == (None, None)


def test_ia_e_ignorada_para_item_vendido_por_peso(db_path):
	_importar(db_path, OUTRA_CHAVE, ["PAO FRANCES KG"], unidade="KG")

	_classificar_com_tamanho(db_path, OUTRA_CHAVE, 1, "1kg")

	assert _tamanhos(db_path, OUTRA_CHAVE) == [(None, None)]


# ---------------------------------------------------------------------------
# Tela de análise: exibição e o que volta para o banco
# ---------------------------------------------------------------------------

def test_editor_mostra_o_tamanho_da_nota_e_a_origem(db_path):
	_importar(db_path, OUTRA_CHAVE, ["AGUA SARANDI C/GAS 2L", "CHOPP TRADICIONAL TU", "PAO FRANCES KG"])
	_classificar_com_tamanho(db_path, OUTRA_CHAVE, 2, "1l")

	df = _montar_editor(listar_itens_para_revisao(OUTRA_CHAVE, db_path=db_path))

	assert df["tamanho"].tolist() == ["2L", "1L", ""]
	assert df["origem_tamanho"].tolist() == ["nota", "IA", ""]


def test_editor_so_envia_o_tamanho_alterado(db_path):
	_importar(db_path, OUTRA_CHAVE, ["AGUA SARANDI C/GAS 2L", "CHOPP TRADICIONAL TU", "CERVEJA SPATEN PURO"])
	df_base = _montar_editor(listar_itens_para_revisao(OUTRA_CHAVE, db_path=db_path))
	df_editado = df_base.copy()
	df_editado.loc[0, "tamanho"] = "2 l"  # igual ao da descrição
	df_editado.loc[1, "tamanho"] = "1l"  # novo

	registros = _converter_registros(df_editado, OUTRA_CHAVE, None, df_base)

	assert registros[0]["tamanho"] == ""  # não grava o que a descrição já informa
	assert registros[1]["tamanho"] == "1l"
	assert "tamanho" not in registros[2]  # não mexeu
