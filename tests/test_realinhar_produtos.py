"""Testes do script scripts/realinhar_produtos.py."""
from __future__ import annotations

import importlib.util
from decimal import Decimal
from pathlib import Path

from src.classifiers import embeddings
from src.database import _criar_produto, conexao, salvar_nota
from src.scrapers.receita_rs import NotaFiscal, NotaItem

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("realinhar_produtos", RAIZ / "scripts" / "realinhar_produtos.py")
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _banco(tmp_path):
	"""Banco com duplicatas por nome, nomes desalinhados, um órfão e cache poluído.

	- "Cerveja"/Spaten (1 item) e "cerveja "/Budweiser (2 itens): mesmo produto.
	- O item 3 está no produto Budweiser, mas gravado como "Cerv Budweiser".
	- O item 4 aponta para um produto que não existe mais.
	"""
	db_path = tmp_path / "t.db"
	descricoes = ["CERVEJA SPATEN 473ML", "CERV BUDWEISER 473ML", "CERV BUDWEISER 990ML", "LEITE CONDENSADO 395G"]
	itens = [
		NotaItem(descricao=d, codigo=None, quantidade=Decimal("1"), unidade="UN",
		         valor_unitario=Decimal("5"), valor_total=Decimal("5"))
		for d in descricoes
	]
	salvar_nota(NotaFiscal(chave_acesso="8" * 44, emissao="10/01/2025 10:00:00", itens=itens), db_path=db_path)
	with conexao(db_path) as con:
		# Órfãos só existem no banco real porque as FKs já estiveram desligadas
		con.execute("PRAGMA foreign_keys = OFF")
		spaten = _criar_produto(con, "Cerveja", "Spaten")
		budweiser = _criar_produto(con, "cerveja ", "Budweiser")
		atualizar = "UPDATE itens SET produto_id = ?, produto_nome = ?, produto_marca = ?, categoria_confirmada = ? WHERE sequencia = ?"
		con.execute(atualizar, [spaten.id, "Cerveja", "Spaten", "Cervejas", 1])
		con.execute(atualizar, [budweiser.id, "cerveja ", "Budweiser", "Cervejas", 2])
		con.execute(atualizar, [budweiser.id, "Cerv Budweiser", "Budweiser", "Cervejas", 3])
		con.execute(atualizar, [999999, "Leite Condensado", None, "Laticínios", 4])
		# Produto criado pela importação a partir da descrição (o alias aponta para ele)
		leite_id = con.execute(
			"SELECT produto_id FROM aliases_produtos WHERE texto_original = 'LEITE CONDENSADO 395G'"
		).fetchone()[0]
	return db_path, spaten.id, budweiser.id, leite_id


def _itens(db_path):
	with conexao(db_path) as con:
		return con.execute("SELECT sequencia, produto_id, produto_nome, produto_marca FROM itens ORDER BY sequencia").fetchall()


def test_simulacao_nao_altera_nada(tmp_path):
	db_path, spaten, budweiser, _ = _banco(tmp_path)
	antes = _itens(db_path)

	relatorio = script.realinhar(db_path, aplicar=False)

	assert _itens(db_path) == antes
	assert [(destino, origens) for destino, origens, _ in relatorio["fusoes"]] == [(budweiser, [spaten])]
	assert relatorio["orfaos"] == 1


def test_funde_produtos_de_mesmo_nome_no_que_tem_mais_itens(tmp_path):
	"""Produto = nome: "Cerveja" e "cerveja " viram um só (o destino é o que tem mais itens)."""
	db_path, spaten, budweiser, _ = _banco(tmp_path)

	relatorio = script.realinhar(db_path, aplicar=True)

	assert [(destino, origens) for destino, origens, _ in relatorio["fusoes"]] == [(budweiser, [spaten])]
	with conexao(db_path) as con:
		assert con.execute("SELECT COUNT(*) FROM produtos WHERE id = ?", [spaten]).fetchone()[0] == 0
	assert {pid for _, pid, _, _ in _itens(db_path)[:3]} == {budweiser}


def test_alinha_nome_dos_itens_e_preserva_a_marca(tmp_path):
	"""O nome do produto destino é aparado (sem espaço sobrando) e os itens o recebem."""
	db_path, _, budweiser, _ = _banco(tmp_path)

	script.realinhar(db_path, aplicar=True)

	assert _itens(db_path)[:3] == [
		(1, budweiser, "cerveja", "Spaten"),
		(2, budweiser, "cerveja", "Budweiser"),
		(3, budweiser, "cerveja", "Budweiser"),
	]


def test_item_orfao_e_religado_pelo_alias_da_descricao(tmp_path):
	db_path, _, _, leite_id = _banco(tmp_path)

	script.realinhar(db_path, aplicar=True)

	assert _itens(db_path)[3] == (4, leite_id, "Leite Condensado", None)


def test_cache_poluido_e_limpo_e_itens_reais_reindexados(tmp_path):
	"""Remove entradas com categoria que não correspondem a item real; reindexa os itens."""
	db_path, _, budweiser, _ = _banco(tmp_path)
	embeddings.upsert_descricao_embedding("SAB PHEBO GLIC ROSAS 90G", "Sab Phebo", None, "alimentacao", produto_id=2)
	embeddings.upsert_descricao_embedding("CERV BUDWEISER 990ML", "Cerv Budweiser", "Budweiser", "alimentacao", produto_id=5)

	relatorio = script.realinhar(db_path, aplicar=True)

	dados = embeddings._get_collection().get(include=["metadatas", "documents"])
	por_doc = dict(zip(dados["documents"], dados["metadatas"]))
	assert "SAB PHEBO GLIC ROSAS 90G" not in por_doc
	assert por_doc["CERV BUDWEISER 990ML"]["produto_id"] == str(budweiser)
	assert por_doc["CERV BUDWEISER 990ML"]["nome_base"] == "cerveja"
	assert por_doc["CERV BUDWEISER 990ML"]["categoria"] == "Cervejas"
	assert relatorio["embeddings_removidos"] >= 1
	assert relatorio["embeddings_reindexados"] == 4


def test_segunda_execucao_nao_encontra_mais_nada(tmp_path):
	db_path, *_ = _banco(tmp_path)
	script.realinhar(db_path, aplicar=True)

	relatorio = script.realinhar(db_path, aplicar=False)

	assert relatorio["fusoes"] == []
	assert relatorio["nomes_desalinhados"] == 0
	assert relatorio["orfaos"] == 0
	assert relatorio["embeddings_a_remover"] == 0
