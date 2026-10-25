"""Unidade de venda, tamanho da embalagem e medida base dos itens da NFC-e.

Os relatórios de preço comparam compras do mesmo produto em embalagens
diferentes (pacote de 500 g, bandeja de 1 kg, peso na balança). Para isso, cada
compra é convertida para uma medida base: quilo (KG) ou litro (L) quando o peso
ou volume é conhecido, ou a própria unidade de venda (UN, CX) quando não é.
"""

from __future__ import annotations

import re

_UNIDADES_VENDA = {
	"UN": "UN", "UNID": "UN", "UND": "UN", "UNIDADE": "UN",
	"PC": "UN", "PCT": "UN", "PACOTE": "UN",
	"KG": "KG",
	"L": "L", "LT": "L",
	"CX": "CX", "CXA": "CX", "CAIXA": "CX",
}

# Número + unidade de peso/volume, com multiplicador opcional ("6X350ML").
# MG fica de fora (dose de medicamento, não embalagem); número depois de "/"
# é contagem ("C/80"), e "1 5L" é 1,5 L com a vírgula perdida na nota.
_TAMANHO = re.compile(
	r"(?<![\d.,/])(?:(\d+)\s*X\s*)?(\d+(?:[.,]\d+| \d(?=L))?)\s*(KG|GR|G|ML|LTS|LT|L)(?![A-Z])",
	re.IGNORECASE,
)
# "C/3": embalagem com 3 unidades do tamanho indicado
_CONTEM = re.compile(r"\bC/\s*(\d+)\b", re.IGNORECASE)
_PARA_BASE = {
	"KG": (1.0, "KG"), "GR": (0.001, "KG"), "G": (0.001, "KG"),
	"ML": (0.001, "L"), "LTS": (1.0, "L"), "LT": (1.0, "L"), "L": (1.0, "L"),
}


def normalizar_unidade(unidade: str | None) -> str:
	"""Unidade de venda da NFC-e em UN, KG, L ou CX ("UND9" → UN, "KG9" → KG).

	Os mercados acrescentam dígitos ao código ("UND9", "CXA1"); eles são
	ignorados. Unidade vazia vale UN; código desconhecido volta em maiúsculas.
	"""
	codigo = re.sub(r"\d+$", "", (unidade or "").strip().upper())
	if not codigo:
		return "UN"
	return _UNIDADES_VENDA.get(codigo, codigo)


def extrair_tamanho(descricao: str | None) -> tuple[float, str] | None:
	"""Tamanho da embalagem na descrição, em KG ou L, ou None se não houver.

	"ALHO PLANALTO 200G" → (0.2, "KG"); "CERVEJA 6X350ML" → (2.1, "L");
	"SABONETE 85G C/3" → (0.255, "KG"). Com vários tamanhos, vale o maior
	("IOG 10G P 120G" → 0,12 kg): o menor costuma ser a porção.
	"""
	if not descricao:
		return None

	tamanhos = []
	for multiplicador, numero, unidade in _TAMANHO.findall(descricao):
		fator, unidade_base = _PARA_BASE[unidade.upper()]
		valor = float(numero.replace(",", ".").replace(" ", ".")) * fator * int(multiplicador or 1)
		tamanhos.append((valor, unidade_base))
	if not tamanhos:
		return None

	valor, unidade_base = max(tamanhos)
	contem = _CONTEM.search(descricao)
	if contem:
		valor *= int(contem.group(1))
	return valor, unidade_base


def medida_base(
	quantidade: float,
	unidade: str | None,
	descricao: str | None,
	tamanho_informado: str | None = None,
) -> tuple[float, str]:
	"""Quantidade comprada na medida base: (quantidade, "KG"|"L"|"UN"|"CX").

	Vendido por peso ou volume: a quantidade já está em KG/L. Vendido por
	unidade com tamanho conhecido: quantidade × tamanho. Sem tamanho: a
	quantidade fica na unidade de venda. O ``tamanho_informado`` na revisão
	("473ml") vale sobre o da descrição, que o mercado às vezes trunca.
	"""
	unidade_venda = normalizar_unidade(unidade)
	if unidade_venda in ("KG", "L"):
		return quantidade, unidade_venda

	tamanho = extrair_tamanho(tamanho_informado) or extrair_tamanho(descricao)
	if tamanho is None:
		return quantidade, unidade_venda
	return quantidade * tamanho[0], tamanho[1]
