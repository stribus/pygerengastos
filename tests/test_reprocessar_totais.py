"""Testes do script scripts/reprocessar_totais_nfce.py."""

import importlib.util
import shutil
from decimal import Decimal
from pathlib import Path

from src.database import carregar_nota, conexao, salvar_nota
from src.scrapers import receita_rs

RAIZ = Path(__file__).resolve().parents[1]
FIXTURE_TABULAR = RAIZ / "tests" / "fixtures" / "nfce_tabular_com_desconto.html"
CHAVE_TABULAR = "43251193015006002590651030000000010000000010"

_spec = importlib.util.spec_from_file_location(
    "reprocessar_totais_nfce", RAIZ / "scripts" / "reprocessar_totais_nfce.py"
)
script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(script)


def _preparar(tmp_path):
    """Banco com a nota gravada correta e pasta com o HTML dela."""
    pasta_html = tmp_path / "raw"
    pasta_html.mkdir()
    shutil.copy(FIXTURE_TABULAR, pasta_html / f"nfce_{CHAVE_TABULAR}.html")
    db_path = tmp_path / "test.sqlite3"
    nota = receita_rs.parse_nota(FIXTURE_TABULAR.read_text(encoding="utf-8"), CHAVE_TABULAR)
    salvar_nota(nota, db_path=db_path)
    return pasta_html, db_path


def test_simulacao_nao_grava_e_aplicar_corrige(tmp_path):
    """Sem --aplicar só reporta; com --aplicar corrige; depois disso não há divergência."""
    pasta_html, db_path = _preparar(tmp_path)
    with conexao(db_path) as con:
        con.execute("UPDATE notas SET valor_total = '1067.44', desconto = NULL, valor_pago = NULL")
        con.execute("DELETE FROM pagamentos")

    lidos, alteradas = script.reprocessar(pasta_html, db_path, aplicar=False)
    assert (lidos, alteradas) == (1, [CHAVE_TABULAR])
    assert carregar_nota(CHAVE_TABULAR, db_path=db_path).valor_total == Decimal("1067.44")

    script.reprocessar(pasta_html, db_path, aplicar=True)
    assert carregar_nota(CHAVE_TABULAR, db_path=db_path).valor_total == Decimal("1014.52")

    assert script.reprocessar(pasta_html, db_path, aplicar=False) == (1, [])


def test_detecta_pagamento_alterado_com_mesma_quantidade(tmp_path):
    """Forma de pagamento com valor errado é detectada mesmo sem mudar a quantidade."""
    pasta_html, db_path = _preparar(tmp_path)
    with conexao(db_path) as con:
        con.execute("UPDATE pagamentos SET valor = '1.00' WHERE valor = 400")

    _, alteradas = script.reprocessar(pasta_html, db_path, aplicar=True)

    assert alteradas == [CHAVE_TABULAR]
    valores = sorted(p.valor for p in carregar_nota(CHAVE_TABULAR, db_path=db_path).pagamentos)
    assert valores == [Decimal("400.00"), Decimal("614.52")]
