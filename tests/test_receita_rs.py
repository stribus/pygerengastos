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


# ---------------------------------------------------------------------------
# Totais, descontos e pagamentos
# ---------------------------------------------------------------------------

FIXTURE_TABULAR = Path(__file__).resolve().parent / "fixtures" / "nfce_tabular_com_desconto.html"
# Chave e CPF da fixture são fictícios (HTML real anonimizado)
CHAVE_TABULAR = "43251193015006002590651030000000010000000010"


def test_layout_tabular_desconta_valor_total_e_le_pagamentos():
	"""Layout tabular (NFCDetalhe_Item): valor da nota é o líquido, já com desconto.

	Regressão: sem #totalNota, o parser somava os itens (bruto), ignorava o
	desconto e não lia nenhuma forma de pagamento.
	"""
	nota = receita_rs.parse_nota(FIXTURE_TABULAR.read_text(encoding="utf-8"), CHAVE_TABULAR)

	assert sum(item.valor_total for item in nota.itens) == Decimal("1067.44")
	assert nota.desconto == Decimal("52.92")
	assert nota.valor_total == Decimal("1014.52")
	assert sorted(pag.valor for pag in nota.pagamentos) == [Decimal("400.00"), Decimal("614.52")]
	assert nota.valor_pago == Decimal("1014.52")


def test_layout_moderno_nao_trata_total_desconto_e_troco_como_pagamento():
	"""No layout com #totalNota, só as linhas após "Forma de pagamento" são pagamentos."""
	html = _load_html().replace(
		'<div id="linhaTotal" class="linhaShade"><label>Valor a pagar R$:</label>',
		'<div id="linhaTotal"><label>Valor total R$:</label><span class="totalNumb">1.100,00</span></div>'
		'<div id="linhaTotal"><label>Descontos R$:</label><span class="totalNumb">30,69</span></div>'
		'<div id="linhaTotal" class="linhaShade"><label>Valor a pagar R$:</label>',
	).replace(
		'<div id="linhaTotal" /><div id="linhaTotal" class="spcTop">',
		'<div id="linhaTotal"><label>Troco R$:</label><span class="totalNumb">0,00</span></div>'
		'<div id="linhaTotal" /><div id="linhaTotal" class="spcTop">',
	)
	assert "Descontos R$:" in html and "Troco R$:" in html

	nota = receita_rs.parse_nota(html, CHAVE)

	assert nota.valor_total == Decimal("1069.31")
	assert nota.desconto == Decimal("30.69")
	assert sorted(pag.forma for pag in nota.pagamentos) == ["Cartão de Débito", "Vale Alimentação"]
	assert nota.valor_pago == Decimal("1069.31")


def test_layout_moderno_sem_linha_de_desconto_fica_none():
	"""Fixture original não tem linha de desconto: desconto fica None e o resto não muda."""
	nota = receita_rs.parse_nota(_load_html(), CHAVE)

	assert nota.desconto is None
	assert nota.valor_total == Decimal("1069.31")
