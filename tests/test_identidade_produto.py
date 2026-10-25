"""Testes da identidade do produto: produto = nome (sem caixa); marca fica no item."""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.database import (
	_criar_produto,
	conexao,
	registrar_classificacao_itens,
	salvar_nota,
)
from src.scrapers.receita_rs import NotaFiscal, NotaItem


@pytest.fixture(autouse=True)
def _sem_embeddings(monkeypatch):
	"""Os testes de identidade não precisam do Chroma nem do modelo."""
	import src.database as database

	monkeypatch.setattr(database, "_registrar_embeddings_para_produto", lambda produto: None)
	monkeypatch.setattr(database, "_atualizar_embeddings_pos_classificacao", lambda dados, con: None)


def _salvar(db_path, chave_digito: str, descricoes: list[str]) -> str:
	chave = chave_digito * 44
	itens = [
		NotaItem(descricao=d, codigo=None, quantidade=Decimal("1"), unidade="UN",
		         valor_unitario=Decimal("10"), valor_total=Decimal("10"))
		for d in descricoes
	]
	salvar_nota(NotaFiscal(chave_acesso=chave, emissao="10/01/2025 10:00:00", itens=itens), db_path=db_path)
	return chave


def _classificar(db_path, chave: str, seq: int, nome: str, marca: str | None, **extra) -> None:
	registrar_classificacao_itens(
		[{"chave_acesso": chave, "sequencia": seq, "categoria": "Bebidas",
		  "produto_nome": nome, "produto_marca": marca, **extra}],
		db_path=db_path,
	)


def _item(db_path, chave: str, seq: int) -> tuple:
	with conexao(db_path) as con:
		return con.execute(
			"SELECT produto_id, produto_nome, produto_marca FROM itens WHERE chave_acesso = ? AND sequencia = ?",
			[chave, seq],
		).fetchone()


def _produtos_com_nome(db_path, nome: str) -> int:
	with conexao(db_path) as con:
		return con.execute("SELECT COUNT(*) FROM produtos WHERE lower(nome_base) = lower(?)", [nome]).fetchone()[0]


def test_nome_existente_com_outra_marca_reusa_o_produto(tmp_path):
	"""Regressão: "Chopp / Bairrista" criava um produto novo e desfazia a consolidação."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		chopp = _criar_produto(con, "Chopp", "Tupiniquim")
	chave = _salvar(db_path, "1", ["CHOPP BAIRRISTA PET 1L"])

	_classificar(db_path, chave, 1, "chopp", "Bairrista")

	assert _item(db_path, chave, 1) == (chopp.id, "Chopp", "Bairrista")
	assert _produtos_com_nome(db_path, "Chopp") == 1


def test_varios_produtos_com_mesmo_nome_prefere_a_mesma_marca(tmp_path):
	"""Duplicatas antigas por marca: o item vai para a de mesma marca, se existir."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		_criar_produto(con, "Cerveja", "Spaten")
		budweiser = _criar_produto(con, "Cerveja", "Budweiser")
	chave = _salvar(db_path, "2", ["CERV BUDWEISER 473ML"])

	_classificar(db_path, chave, 1, "Cerveja", "budweiser")

	assert _item(db_path, chave, 1)[0] == budweiser.id


def test_nome_novo_cria_produto(tmp_path):
	db_path = tmp_path / "t.db"
	chave = _salvar(db_path, "3", ["KOMBUCHA GENGIBRE 300ML"])

	_classificar(db_path, chave, 1, "Kombucha", "Tao")

	produto_id, nome, marca = _item(db_path, chave, 1)
	assert (nome, marca) == ("Kombucha", "Tao")
	assert _produtos_com_nome(db_path, "Kombucha") == 1


def test_produto_id_informado_pelo_cache_e_respeitado(tmp_path):
	"""O match semântico traz o produto_id: ele vale mesmo se o nome sugerido divergir."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		agua = _criar_produto(con, "Água c/gás 2L", "Água da Pedra")
	chave = _salvar(db_path, "4", ["AGUA DA PEDRA 2L C G"])

	_classificar(db_path, chave, 1, "Água Mineral com gás", None, produto_id=agua.id)

	assert _item(db_path, chave, 1) == (agua.id, "Água c/gás 2L", None)
	assert _produtos_com_nome(db_path, "Água Mineral com gás") == 0


def test_descricao_passa_a_apontar_para_o_produto_escolhido(tmp_path):
	"""Depois da classificação, uma nova nota com a mesma descrição já entra no produto certo."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		chopp = _criar_produto(con, "Chopp", "Tupiniquim")
	chave = _salvar(db_path, "5", ["CHOPP STIER PILSEN P"])
	_classificar(db_path, chave, 1, "Chopp", "Stier")

	outra = _salvar(db_path, "6", ["CHOPP STIER PILSEN P"])

	assert _item(db_path, outra, 1)[0] == chopp.id


# ---------------------------------------------------------------------------
# Consolidação: nome unificado nos itens da origem E do destino; marca preservada
# ---------------------------------------------------------------------------

def _produto_do_item(db_path, chave: str, seq: int) -> int:
	return _item(db_path, chave, seq)[0]


def _preparar_consolidacao(db_path):
	"""Destino "Coxa Frango" com item gravado como "Coxa de Frango" (dado real) e origem "Sobrecoxa"."""
	chave = _salvar(db_path, "7", ["SCOXA FGO SADIA IQF 1KG", "SOBRECOXAS TEMP AVE"])
	with conexao(db_path) as con:
		destino = _criar_produto(con, "Coxa Frango", "Lar")
		origem = _criar_produto(con, "Sobrecoxa", None)
		con.execute(
			"UPDATE itens SET produto_id = ?, produto_nome = 'Coxa de Frango', produto_marca = 'Sadia' WHERE sequencia = 1",
			[destino.id],
		)
		con.execute(
			"UPDATE itens SET produto_id = ?, produto_nome = 'Sobrecoxa', produto_marca = NULL WHERE sequencia = 2",
			[origem.id],
		)
	return chave, origem.id, destino.id


def test_consolidacao_unifica_nome_dos_itens_do_destino_tambem(tmp_path):
	"""Regressão: só os itens da origem eram renomeados; os do destino ficavam com o nome antigo."""
	from src.database import consolidar_produtos

	db_path = tmp_path / "t.db"
	chave, origem, destino = _preparar_consolidacao(db_path)

	consolidar_produtos(origem, destino, db_path=db_path)

	assert _item(db_path, chave, 1) == (destino, "Coxa Frango", "Sadia")
	assert _item(db_path, chave, 2) == (destino, "Coxa Frango", None)


def test_consolidacao_com_nome_final_usa_o_nome_efetivamente_gravado(tmp_path):
	"""Com conflito, o produto recebe sufixo "(1)": os itens devem receber esse mesmo nome."""
	from src.database import consolidar_produtos

	db_path = tmp_path / "t.db"
	chave, origem, destino = _preparar_consolidacao(db_path)
	with conexao(db_path) as con:
		_criar_produto(con, "Coxa de Frango", "Lar")  # força o sufixo no destino

	resultado = consolidar_produtos(origem, destino, nome_final="Coxa de Frango", db_path=db_path)

	assert resultado["nome_final_usado"] == "Coxa de Frango (1)"
	assert _item(db_path, chave, 1)[1] == "Coxa de Frango (1)"
	assert _item(db_path, chave, 2)[1] == "Coxa de Frango (1)"


def test_consolidacao_conta_apenas_itens_migrados_da_origem(tmp_path):
	from src.database import consolidar_produtos

	db_path = tmp_path / "t.db"
	_, origem, destino = _preparar_consolidacao(db_path)

	resultado = consolidar_produtos(origem, destino, db_path=db_path)

	assert resultado["itens_migrados"] == 1


def test_historico_registra_o_nome_efetivamente_gravado(tmp_path):
	from src.database import consolidar_produtos

	db_path = tmp_path / "t.db"
	_, origem, destino = _preparar_consolidacao(db_path)
	with conexao(db_path) as con:
		_criar_produto(con, "Coxa de Frango", "Lar")

	consolidar_produtos(origem, destino, nome_final="Coxa de Frango", db_path=db_path)

	with conexao(db_path) as con:
		nome = con.execute("SELECT nome_destino FROM consolidacoes_historico").fetchone()[0]
	assert nome == "Coxa de Frango (1)"
