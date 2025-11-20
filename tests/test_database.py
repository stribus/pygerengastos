from pathlib import Path

import pytest

from src.database import (
    carregar_nota,
    conexao,
    inicializar_banco,
    listar_itens_para_classificacao,
    listar_notas,
    registrar_classificacao_itens,
    salvar_nota,
)
from src.scrapers import receita_rs

FIXTURE_PATH = Path(__file__).resolve().parents[1] / ".github" / "xmlexemplo.xml"
CHAVE = "43251193015006003562651350005430861685582449"


def _nota_exemplo():
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    return receita_rs.parse_nota(html, CHAVE)


def test_salvar_e_carregar_nota(tmp_path):
    db_path = tmp_path / "test.duckdb"
    nota = _nota_exemplo()

    salvar_nota(nota, db_path=db_path)

    conn = inicializar_banco(db_path=db_path)
    try:
        total_notas_row = conn.execute("SELECT COUNT(*) FROM notas").fetchone()
        total_itens_row = conn.execute("SELECT COUNT(*) FROM itens").fetchone()
        total_pag_row = conn.execute("SELECT COUNT(*) FROM pagamentos").fetchone()
    finally:
        conn.close()

    assert total_notas_row is not None
    assert total_itens_row is not None
    assert total_pag_row is not None

    total_notas = total_notas_row[0]
    total_itens = total_itens_row[0]
    total_pag = total_pag_row[0]

    assert total_notas == 1
    assert total_itens == len(nota.itens)
    assert total_pag == len(nota.pagamentos)

    carregada = carregar_nota(CHAVE, db_path=db_path)
    assert carregada is not None
    assert carregada.valor_total == nota.valor_total
    assert len(carregada.itens) == len(nota.itens)
    assert len(carregada.pagamentos) == len(nota.pagamentos)


def test_listar_notas_retorna_resumo(tmp_path):
    db_path = tmp_path / "test.duckdb"
    nota = _nota_exemplo()

    salvar_nota(nota, db_path=db_path)

    resumos = listar_notas(db_path=db_path)
    assert len(resumos) == 1
    resumo = resumos[0]

    assert resumo["chave_acesso"] == CHAVE
    assert resumo["valor_total"] == nota.valor_total
    assert resumo["total_itens"] == nota.total_itens
    assert resumo["emitente_nome"] == nota.emitente_nome


def test_listar_itens_para_classificacao_retorna_itens(tmp_path):
	db_path = tmp_path / "test.duckdb"
	nota = _nota_exemplo()

	salvar_nota(nota, db_path=db_path)
	itens = listar_itens_para_classificacao(db_path=db_path, limit=100)

	assert len(itens) == len(nota.itens)
	primeiro = itens[0]
	assert primeiro.descricao == nota.itens[0].descricao
	assert primeiro.categoria_sugerida is None
def test_registrar_classificacao_itens_atualiza_tabelas(tmp_path):
    db_path = tmp_path / "test.duckdb"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "confianca": 0.93,
                "origem": "groq",
                "modelo": "teste",
                "observacoes": "classificação automática",
                "resposta_json": "{}",
                "confirmar": True,
            }
        ],
        db_path=db_path,
    )

    with conexao(db_path) as con:
        item_row = con.execute(
            """
            SELECT categoria_sugerida, categoria_confirmada, fonte_classificacao, confianca_classificacao
            FROM itens
            WHERE chave_acesso = ? AND sequencia = 1
            """,
            [CHAVE],
        ).fetchone()
        registros_historico_row = con.execute(
            "SELECT COUNT(*) FROM classificacoes_historico WHERE chave_acesso = ?",
            [CHAVE],
        ).fetchone()

    assert registros_historico_row is not None
    registros_historico = registros_historico_row[0]

    assert item_row is not None
    assert item_row[0] == "alimentacao"
    assert item_row[1] == "alimentacao"
    assert item_row[2] == "groq"
    assert pytest.approx(float(item_row[3]), rel=1e-3) == 0.93
    assert registros_historico == 1
