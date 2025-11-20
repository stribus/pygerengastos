from decimal import Decimal
from pathlib import Path

from src.scrapers import receita_rs

FIXTURE_PATH = Path(__file__).resolve().parents[1] / ".github" / "xmlexemplo.xml"
CHAVE = "43251193015006003562651350005430861685582449"


def _load_html() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_parse_nota_totais_e_pagamentos():
    nota = receita_rs.parse_nota(_load_html(), CHAVE)

    assert nota.total_itens == 65
    assert nota.valor_total == Decimal("1069.31")
    assert nota.valor_pago == Decimal("1069.31")

    formas = [pag.forma for pag in nota.pagamentos]
    assert "Cartão de Débito" in formas
    assert "Vale Alimentação" in formas

    debito = next(filter(lambda p: p.forma == "Cartão de Débito", nota.pagamentos))
    alimentacao = next(filter(lambda p: p.forma == "Vale Alimentação", nota.pagamentos))

    assert debito.valor == Decimal("719.31")
    assert alimentacao.valor == Decimal("350.00")


def test_parse_primeiro_item_e_emitente():
    nota = receita_rs.parse_nota(_load_html(), CHAVE)

    assert nota.emitente_nome == "COMPANHIA ZAFFARI COMERCIO E INDUSTRIA"
    assert nota.emitente_cnpj == "93.015.006/0035-62"
    assert len(nota.itens) == 65

    primeiro = nota.itens[0]
    assert primeiro.descricao == "SCOXA FGO LAR IQF 1KG"
    assert primeiro.valor_total == Decimal("16.90")
    assert primeiro.valor_unitario == Decimal("16.90") or primeiro.valor_unitario == Decimal("16.9")
    
def test_buscar_nota():
    nota = receita_rs.buscar_nota(CHAVE)

    assert nota.chave_acesso == CHAVE
    assert nota.emitente_nome == "COMPANHIA ZAFFARI COMERCIO E INDUSTRIA"
