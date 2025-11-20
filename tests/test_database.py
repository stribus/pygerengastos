from pathlib import Path

from src.database import carregar_nota, inicializar_banco, listar_notas, salvar_nota
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
