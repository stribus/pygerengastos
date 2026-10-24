"""Testes das consultas que alimentam a Home (KPIs, resumo mensal e categorias)."""

from decimal import Decimal

import pytest

from src.database import (
	conexao,
	inicializar_banco,
	obter_gastos_por_categoria,
	obter_kpis_gerais,
	obter_resumo_mensal,
	salvar_nota,
)
from src.scrapers.receita_rs import NotaFiscal, NotaItem


def _nota(chave_digito: str, emissao: str, itens: list[tuple[str, Decimal]]) -> NotaFiscal:
	"""Cria nota com itens (descricao, valor_total) de quantidade 1."""
	nota_itens = [
		NotaItem(
			descricao=descricao,
			codigo=None,
			quantidade=Decimal("1"),
			unidade="UN",
			valor_unitario=valor,
			valor_total=valor,
		)
		for descricao, valor in itens
	]
	total = sum((item.valor_total for item in nota_itens), Decimal("0"))
	return NotaFiscal(
		chave_acesso=chave_digito * 44,
		emitente_nome="Mercado Teste",
		emissao=emissao,
		itens=nota_itens,
		valor_total=total,
	)


@pytest.fixture
def db_home(tmp_path):
	"""Banco com notas em jan/2025 (2 notas) e fev/2025 (1 nota).

	Itens confirmados: ARROZ (Alimentos, jan), SABAO (Limpeza, jan) e
	FEIJAO (Alimentos, fev). O DETERGENTE de fev fica só com sugestão.
	"""
	db_path = tmp_path / "home.db"
	inicializar_banco(db_path=db_path)

	salvar_nota(_nota("1", "10/01/2025 10:00:00", [("ARROZ", Decimal("20.00"))]), db_path=db_path)
	salvar_nota(_nota("2", "25/01/2025 18:30:00", [("SABAO", Decimal("5.50"))]), db_path=db_path)
	salvar_nota(
		_nota("3", "03/02/2025 09:15:00", [("FEIJAO", Decimal("8.00")), ("DETERGENTE", Decimal("3.25"))]),
		db_path=db_path,
	)

	with conexao(db_path) as con:
		for chave, seq, categoria in [
			("1" * 44, 1, "Alimentos"),
			("2" * 44, 1, "Limpeza"),
			("3" * 44, 1, "Alimentos"),
		]:
			con.execute(
				"UPDATE itens SET categoria_confirmada = ? WHERE chave_acesso = ? AND sequencia = ?",
				[categoria, chave, seq],
			)
		con.execute(
			"UPDATE itens SET categoria_sugerida = 'Limpeza' WHERE chave_acesso = ? AND sequencia = 2",
			["3" * 44],
		)

	return db_path


def test_resumo_mensal_agrupa_por_mes(db_home):
	"""Cada mês vira uma linha "YYYY-MM", do mais recente para o mais antigo.

	Regressão: strftime com argumentos invertidos e CAST AS DATE devolvia NULL,
	somando todas as notas numa única linha com mes=None.
	"""
	resumo = obter_resumo_mensal(db_path=db_home)

	assert resumo == [
		{"mes": "2025-02", "total": 11.25},
		{"mes": "2025-01", "total": 25.50},
	]


def test_gastos_por_categoria_filtra_por_mes(db_home):
	"""O filtro mes_iso considera apenas os itens confirmados daquele mês."""
	janeiro = obter_gastos_por_categoria(mes_iso="2025-01", db_path=db_home)
	fevereiro = obter_gastos_por_categoria(mes_iso="2025-02", db_path=db_home)

	assert janeiro == [
		{"categoria": "Alimentos", "total": 20.00},
		{"categoria": "Limpeza", "total": 5.50},
	]
	assert fevereiro == [{"categoria": "Alimentos", "total": 8.00}]


def test_gastos_por_categoria_sem_filtro_usa_so_confirmadas(db_home):
	"""Sem filtro, soma o histórico confirmado; a sugestão pendente fica de fora."""
	gastos = obter_gastos_por_categoria(db_path=db_home)

	assert gastos == [
		{"categoria": "Alimentos", "total": 28.00},
		{"categoria": "Limpeza", "total": 5.50},
	]


def test_kpis_informam_valor_dos_itens_pendentes(db_home):
	"""Os KPIs trazem quantidade e valor dos itens ainda não confirmados.

	A Home usa esses números para avisar o que está fora do painel de categorias.
	"""
	kpis = obter_kpis_gerais(db_path=db_home)

	assert kpis["total_notas"] == 3
	assert kpis["total_gasto"] == Decimal("36.75")
	assert kpis["itens_pendentes"] == 1
	assert kpis["total_pendente"] == Decimal("3.25")
