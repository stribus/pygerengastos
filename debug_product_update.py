from pathlib import Path

from src.scrapers import receita_rs
from src.database import conexao, registrar_classificacao_itens, salvar_nota

FIXTURE_PATH = Path(__file__).resolve().parent / ".github" / "xmlexemplo.xml"
CHAVE = "43251193015006003562651350005430861685582449"

nota = receita_rs.parse_nota(FIXTURE_PATH.read_text(encoding="utf-8"), CHAVE)
root_db = Path(__file__).resolve().parents[1] / "debug_duckdb.db"
if root_db.exists():
    root_db.unlink()
salvar_nota(nota, db_path=root_db)
registrar_classificacao_itens(
    [
        {
            "chave_acesso": CHAVE,
            "sequencia": 1,
            "categoria": "alimentacao",
            "produto_nome": "Arroz Integral",
            "produto_marca": "Tio João",
            "resposta_json": "{}",
        }
    ],
    db_path=root_db,
)

with conexao(db_path=root_db) as con:
    item = con.execute(
        """
        SELECT produto_id, produto_nome, produto_marca
        FROM itens
        WHERE chave_acesso = ? AND sequencia = 1
        """,
        [CHAVE],
    ).fetchone()
    produtos = con.execute("SELECT id, nome_base, marca_base FROM produtos").fetchall()

print("item", item)
print("produtos", produtos)
