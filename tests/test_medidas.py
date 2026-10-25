"""Testes de src/medidas.py: unidade de venda, tamanho da embalagem e medida base."""
from __future__ import annotations

import pytest

from src.medidas import extrair_tamanho, medida_base, normalizar_unidade, tamanho_detectado


@pytest.mark.parametrize(
	"unidade, esperado",
	[
		("UN", "UN"), ("UNID", "UN"), ("UND9", "UN"), ("PC", "UN"), ("PACOTE", "UN"),
		("KG", "KG"), ("KG9", "KG"), ("kg", "KG"),
		("L", "L"), ("LT", "L"),
		("CX", "CX"), ("CXA1", "CX"), ("CAIXA", "CX"),
		(None, "UN"), ("", "UN"),
	],
)
def test_normalizar_unidade(unidade, esperado):
	assert normalizar_unidade(unidade) == esperado


@pytest.mark.parametrize(
	"descricao, esperado",
	[
		("ALHO PLANALTO 200G", (0.2, "KG")),
		("SCOXA FGO SEARA IQF 1KG", (1.0, "KG")),
		("AGUA DA PEDRA 2L C G", (2.0, "L")),
		("AGUA DA PEDRA 500ML", (0.5, "L")),
		("MM LAVA ROUPAS 5LTS", (5.0, "L")),
		("QUEIJO 1,5KG", (1.5, "KG")),
		("BISCOITO 200GR", (0.2, "KG")),
		# multipack: 6 latas de 350 ml
		("CERVEJA 6X350ML", (2.1, "L")),
		("SABONETE 85G C/3", (0.255, "KG")),
		# vários tamanhos: vale o maior (a embalagem, não a porção)
		("IOG NESTLE 10G P 120G", (0.12, "KG")),
		# vírgula perdida na nota: "1 5L" é 1,5 L
		("AGUA DA PEDRA 1 5L S", (1.5, "L")),
		# "L+P-" é promoção (leve mais, pague menos), não litro
		("CR D ORAL-B 3D WHIT 70G C/3 L+P-", (0.21, "KG")),
		# "K" no fim de descrição cortada é quilo ("1KG" truncado)
		("CARVAO PAVE CARBO 3K", (3.0, "KG")),
		("NHOQUE TALHATELLI 1K", (1.0, "KG")),
		# tamanho colado na contagem: 2 tubos de 90 g
		("CR+GEL D SENSODYNE 90GC/2PROM", (0.18, "KG")),
	],
)
def test_extrair_tamanho(descricao, esperado):
	valor, unidade = extrair_tamanho(descricao)
	assert unidade == esperado[1]
	assert valor == pytest.approx(esperado[0])


@pytest.mark.parametrize(
	"descricao",
	[
		"CERVEJA SPATEN PURO",  # descrição truncada, sem tamanho
		"DIPIRONA 500MG",  # miligrama é dose, não embalagem
		"FILTRO DE PAPEL120UN",
		"OVO BRANCO EXTRA C/30",  # contagem sem tamanho
		"PROT INTIMUS A.BAC C/80L+P-",  # 80 unidades, não 80 litros
		"CERVEJA LATAO",
		"PAPEL 4K PLUS",  # "K" no meio da descrição não é quilo
		"",
		None,
	],
)
def test_extrair_tamanho_sem_tamanho(descricao):
	assert extrair_tamanho(descricao) is None


def test_medida_base_vendido_por_peso_mantem_quantidade():
	assert medida_base(0.368, "KG9", "LING.SUINA BORRUSSIA 1KG") == (0.368, "KG")


def test_medida_base_unidade_com_tamanho_vira_peso_ou_volume():
	qtd, unidade = medida_base(2, "UNID", "CERV BUDWEISER 473ML")
	assert unidade == "L"
	assert qtd == pytest.approx(0.946)


def test_medida_base_sem_tamanho_fica_na_unidade_de_venda():
	assert medida_base(1, "UNID", "CERVEJA SPATEN PURO") == (1, "UN")
	assert medida_base(1, "CXA1", "CERVEJA SPATEN") == (1, "CX")


def test_medida_base_tamanho_informado_vale_sobre_a_descricao():
	"""Tamanho digitado na revisão completa a descrição truncada pelo mercado."""
	assert medida_base(2, "UNID", "CHOPP TRADICIONAL TU", "1L") == (2.0, "L")
	qtd, unidade = medida_base(1, "UN", "CERVEJA 350ML", "473 ml")
	assert (round(qtd, 3), unidade) == (0.473, "L")


@pytest.mark.parametrize(
	"descricao, esperado",
	[
		("AGUA SARANDI C/GAS 2L", "2L"),
		("OLEO LILAS CANOLA 900ML", "900ML"),
		("SALG MEGA MILHO SABOR QUEIJO 140G", "140G"),
		("ARROZ PIEMONT BCO T1 1KG", "1KG"),
		("CERVEJA 6X350ML", "2,1L"),
		("PAO FRANCES KG", ""),
		("CERVEJA SPATEN PURO", ""),
	],
)
def test_tamanho_detectado_para_exibir(descricao, esperado):
	"""O texto exibido volta ao mesmo tamanho quando lido de novo."""
	texto = tamanho_detectado(descricao)
	assert texto == esperado
	if texto:
		valor, unidade = extrair_tamanho(texto)
		assert unidade == extrair_tamanho(descricao)[1]
		assert valor == pytest.approx(extrair_tamanho(descricao)[0])


@pytest.mark.parametrize(
	"descricao, esperado",
	[
		("AGUA SARANDI C/GAS 2L", "2L"),
		("OLEO LILAS CANOLA 900ML", "900ML"),
		("SALG MEGA MILHO SABOR QUEIJO 140G", "140G"),
		("ARROZ PIEMONT BCO T1 1KG", "1KG"),
		("CERVEJA 6X350ML", "2,1L"),
		("PAO FRANCES KG", ""),
		("CERVEJA SPATEN PURO", ""),
	],
)
def test_tamanho_detectado_para_exibir(descricao, esperado):
	"""O texto exibido volta ao mesmo tamanho quando lido de novo."""
	texto = tamanho_detectado(descricao)
	assert texto == esperado
	if texto:
		valor, unidade = extrair_tamanho(texto)
		assert unidade == extrair_tamanho(descricao)[1]
		assert valor == pytest.approx(extrair_tamanho(descricao)[0])
