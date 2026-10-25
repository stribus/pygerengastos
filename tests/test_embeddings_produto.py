"""Testes do vínculo entre embeddings (cache semântico) e o produto canônico."""
from __future__ import annotations

from decimal import Decimal

import pytest

import src.classifiers as classifiers
from src.classifiers import embeddings
from src.database import _criar_produto, conexao, consolidar_produtos, registrar_classificacao_itens, salvar_nota
from src.scrapers.receita_rs import NotaFiscal, NotaItem


def _salvar(db_path, chave_digito: str, descricoes: list[str]) -> str:
	chave = chave_digito * 44
	itens = [
		NotaItem(descricao=d, codigo=None, quantidade=Decimal("1"), unidade="UN",
		         valor_unitario=Decimal("10"), valor_total=Decimal("10"))
		for d in descricoes
	]
	salvar_nota(NotaFiscal(chave_acesso=chave, emissao="10/01/2025 10:00:00", itens=itens), db_path=db_path)
	return chave


@pytest.fixture
def upserts(monkeypatch):
	"""Captura as chamadas a upsert_descricao_embedding sem tocar no Chroma."""
	import src.database as database

	chamadas: list[dict] = []
	monkeypatch.setattr(embeddings, "upsert_descricao_embedding", lambda **kw: chamadas.append(kw))
	monkeypatch.setattr(database, "_registrar_embeddings_para_produto", lambda produto: None)
	return chamadas


def test_embedding_da_classificacao_guarda_produto_id_e_nome_canonico(tmp_path, upserts):
	"""Regressão: o embedding era gravado com produto_id=None e com o nome sugerido pelo LLM."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		chopp = _criar_produto(con, "Chopp", "Tupiniquim")
	chave = _salvar(db_path, "1", ["CHOPP BAIRRISTA PET 1L"])

	registrar_classificacao_itens(
		[{"chave_acesso": chave, "sequencia": 1, "categoria": "Bebidas",
		  "produto_nome": "chopp pilsen", "produto_marca": "Bairrista", "produto_id": chopp.id}],
		db_path=db_path,
	)

	assert upserts[-1]["descricao_original"] == "CHOPP BAIRRISTA PET 1L"
	assert upserts[-1]["produto_id"] == chopp.id
	assert upserts[-1]["nome_base"] == "Chopp"
	assert upserts[-1]["marca_base"] == "Bairrista"


def test_consolidacao_repassa_o_nome_final_aos_embeddings(tmp_path, monkeypatch):
	"""Os embeddings do produto consolidado precisam do id E do nome novos."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		destino = _criar_produto(con, "Coxa Frango", None)
		origem = _criar_produto(con, "Sobrecoxa", None)
	chamadas = []
	monkeypatch.setattr(
		embeddings, "atualizar_produto_id_embeddings",
		lambda antigo, novo, nome_base=None: chamadas.append((antigo, novo, nome_base)) or 0,
	)

	consolidar_produtos(origem.id, destino.id, nome_final="Coxa e Sobrecoxa", db_path=db_path)

	assert chamadas == [(origem.id, destino.id, "Coxa e Sobrecoxa")]


@pytest.fixture
def chroma_temporario(tmp_path, monkeypatch):
	monkeypatch.setattr(embeddings, "_CHROMA_PERSIST_DIR", tmp_path / "chroma")
	embeddings._chroma_client = None
	yield
	embeddings._chroma_client = None


def test_atualizar_embeddings_troca_produto_e_nome_da_origem_e_do_destino(chroma_temporario):
	"""Após consolidar, o cache devolve o produto e o nome novos para as duas descrições."""
	embeddings.upsert_descricao_embedding("SCOXA FGO SADIA IQF 1KG", "Coxa Frango", "Sadia", "Carnes", produto_id=10)
	embeddings.upsert_descricao_embedding("SOBRECOXAS TEMP AVE", "Sobrecoxa", None, "Carnes", produto_id=20)

	atualizados = embeddings.atualizar_produto_id_embeddings(20, 10, nome_base="Coxa e Sobrecoxa")

	assert atualizados == 2
	metadados = embeddings._get_collection().get(include=["metadatas"])["metadatas"]
	assert sorted((m["produto_id"], m["nome_base"], m["marca_base"]) for m in metadados) == [
		("10", "Coxa e Sobrecoxa", ""),
		("10", "Coxa e Sobrecoxa", "Sadia"),
	]


class _LLMQueNaoDeveSerChamado:
	itens_nao_classificados: list = []

	def classificar_itens(self, itens, **kwargs):
		raise AssertionError("o item deveria ter sido resolvido pelo cache semântico")


@pytest.mark.parametrize(
	("descricao", "score", "marca_esperada"),
	[
		("SCOXA FGO SEARA IQF 1KG", 0.95, None),  # vizinho é Sadia: marca não pode ser herdada
		("SCOXA FGO SADIA IQF 1KG", 0.95, "Sadia"),  # marca aparece na descrição
		("SCOXA SADIA 1K", 0.995, "Sadia"),  # descrição praticamente idêntica
	],
)
def test_cache_semantico_usa_produto_id_e_so_herda_marca_confiavel(
	tmp_path, monkeypatch, upserts, descricao, score, marca_esperada
):
	"""Regressão: "SCOXA FGO SEARA IQF 1KG" foi gravado com a marca Sadia do vizinho."""
	db_path = tmp_path / "t.db"
	with conexao(db_path) as con:
		coxa = _criar_produto(con, "Coxa Frango", None)
	chave = _salvar(db_path, "2", [descricao])
	monkeypatch.setattr(
		classifiers, "buscar_produtos_semelhantes",
		lambda texto, top_k=1: [{"score": score, "categoria": "Carnes", "nome_base": "Coxa Frango",
		                        "marca_base": "Sadia", "produto_id": coxa.id,
		                        "descricao_original": "SCOXA FGO SADIA IQF 1KG"}],
	)

	resultados = classifiers.classificar_itens_pendentes(
		classifier=_LLMQueNaoDeveSerChamado(), db_path=db_path, limit=1
	)

	assert resultados[0].produto_id == coxa.id
	assert resultados[0].produto_marca == marca_esperada
	with conexao(db_path) as con:
		assert con.execute("SELECT produto_id, produto_marca FROM itens").fetchone() == (coxa.id, marca_esperada)
