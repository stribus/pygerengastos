from pathlib import Path

import pytest

from src.database import (
    carregar_nota,
    conexao,
    inicializar_banco,
    listar_categorias,
    listar_itens_para_revisao,
    listar_itens_para_classificacao,
    listar_itens_padronizados,
    listar_notas,
    listar_revisoes_manuais,
    limpar_categorias_confirmadas,
    limpar_classificacoes_completas,
    normalizar_produto_descricao,
    registrar_classificacao_itens,
    registrar_revisoes_manuais,
    seed_categorias_csv,
    salvar_nota,
)
from src.scrapers import receita_rs

FIXTURE_PATH = Path(__file__).resolve().parents[1] / ".github" / "xmlexemplo.xml"
CHAVE = "43251193015006003562651350005430861685582449"


def _nota_exemplo():
    html = FIXTURE_PATH.read_text(encoding="utf-8")
    return receita_rs.parse_nota(html, CHAVE)


def test_salvar_e_carregar_nota(tmp_path):
    db_path = tmp_path / "test.sqlite3"
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
    db_path = tmp_path / "test.sqlite3"
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
	db_path = tmp_path / "test.sqlite3"
	nota = _nota_exemplo()

	salvar_nota(nota, db_path=db_path)
	itens = listar_itens_para_classificacao(db_path=db_path, limit=100)

	assert len(itens) == len(nota.itens)
	primeiro = itens[0]
	assert primeiro.descricao == nota.itens[0].descricao
	assert primeiro.categoria_sugerida is None


def test_listar_itens_para_revisao_filtra_pendentes(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()

    salvar_nota(nota, db_path=db_path)
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentos",
                "origem": "teste",
                "modelo": "pytest",
            }
        ],
        db_path=db_path,
        confirmar=True,
    )

    itens_todos = listar_itens_para_revisao(CHAVE, db_path=db_path)
    itens_pendentes = listar_itens_para_revisao(CHAVE, somente_pendentes=True, db_path=db_path)

    assert len(itens_todos) == len(nota.itens)
    assert len(itens_pendentes) == len(nota.itens) - 1
    assert all(item.categoria_confirmada is None for item in itens_pendentes)


def test_seed_categorias_csv_insere_sem_duplicar(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    csv_path = tmp_path / "categorias.csv"
    csv_path.write_text("Grupo,Categoria\nGrupo A,Cat 1\nGrupo A,Cat 2\n", encoding="utf-8")

    inseridos = seed_categorias_csv(csv_path, db_path=db_path)
    assert inseridos == 2
    # rodar novamente não deve duplicar
    inseridos_segunda = seed_categorias_csv(csv_path, db_path=db_path)
    assert inseridos_segunda == 0

    categorias = listar_categorias(db_path=db_path, apenas_ativos=False)
    assert len(categorias) == 2
    assert categorias[0].grupo == "Grupo A"


def test_normalizar_produto_descricao_detecta_marca_e_remove_unidade():
    nome, marca = normalizar_produto_descricao("ARROZ INTEGRAL TIO JOAO 5KG")
    assert nome == "Arroz Integral"
    assert marca == "Tio João"

    nome_sem_marca, marca_sem = normalizar_produto_descricao("Detergente Líquido Neutro 500ml")
    assert nome_sem_marca == "Detergente Líquido Neutro"
    assert marca_sem is None


def test_salvar_nota_cria_produtos_e_aliases(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    with conexao(db_path) as con:
        item_row = con.execute(
            """
            SELECT descricao, produto_id, produto_nome, produto_marca
            FROM itens
            LIMIT 1
            """
        ).fetchone()
        assert item_row is not None
        descricao, produto_id, produto_nome, produto_marca = item_row
        assert produto_id is not None
        normalizado_nome, normalizado_marca = normalizar_produto_descricao(descricao)
        assert produto_nome == normalizado_nome
        assert produto_marca == normalizado_marca

        produtos_total_row = con.execute("SELECT COUNT(*) FROM produtos").fetchone()
        aliases_total_row = con.execute("SELECT COUNT(*) FROM aliases_produtos").fetchone()

    assert produtos_total_row is not None
    assert aliases_total_row is not None
    assert produtos_total_row[0] >= 1
    assert aliases_total_row[0] >= 1
def test_registrar_classificacao_itens_atualiza_tabelas(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "confianca": 0.93,
                "origem": "gemini-litellm",
                "modelo": "teste",
                "observacoes": "classificação automática",
                "resposta_json": "{}",
                "confirmar": True,
                "produto_nome": "Arroz Integral",
                "produto_marca": "Tio João",
            }
        ],
        db_path=db_path,
    )

    with conexao(db_path) as con:
        item_row = con.execute(
            """
            SELECT categoria_sugerida, categoria_confirmada, fonte_classificacao, confianca_classificacao,
                produto_id, produto_nome, produto_marca
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
    assert item_row[2] == "gemini-litellm"
    assert pytest.approx(float(item_row[3]), rel=1e-3) == 0.93
    assert item_row[4] is not None
    assert item_row[5] == "Arroz Integral"
    assert item_row[6] == "Tio João"
    assert registros_historico == 1


def test_registrar_revisoes_manuais_salva_historico(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    registros = [
        {
            "chave_acesso": CHAVE,
            "sequencia": 1,
            "categoria": "higiene",
            "produto_nome": "Sabonete",
            "produto_marca": "Marca X",
            "observacoes": "ajuste manual",
        }
    ]

    registrar_revisoes_manuais(
        registros,
        confirmar=True,
        usuario="ana",
        observacoes_padrao="confirmação",
        db_path=db_path,
    )

    with conexao(db_path) as con:
        item_row = con.execute(
            """
            SELECT categoria_confirmada, produto_nome, produto_marca
            FROM itens
            WHERE chave_acesso = ? AND sequencia = 1
            """,
            [CHAVE],
        ).fetchone()
        revisoes_total = con.execute(
            "SELECT COUNT(*) FROM revisoes_manuais WHERE chave_acesso = ?",
            [CHAVE],
        ).fetchone()

    assert item_row is not None
    assert item_row[0] == "higiene"
    assert item_row[1] == "Sabonete"
    assert item_row[2] == "Marca X"
    assert revisoes_total is not None and revisoes_total[0] == 1

    historico = listar_revisoes_manuais(CHAVE, db_path=db_path)
    assert historico
    registro_hist = historico[0]
    assert registro_hist.usuario == "ana"
    assert registro_hist.confirmado is True
    assert registro_hist.observacoes == "ajuste manual"


def test_listar_itens_padronizados_retorna_dimensoes(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    itens = listar_itens_padronizados(db_path=db_path, limit=10)
    assert itens
    item = itens[0]
    assert item.estabelecimento_nome == nota.emitente_nome
    assert item.estabelecimento_cnpj == nota.emitente_cnpj
    assert item.data_emissao is not None
    assert item.ano is None or item.ano >= 2000
    assert item.categoria is None
    assert item.quantidade == nota.itens[0].quantidade
    assert item.valor_total == nota.itens[0].valor_total


def test_limpar_categorias_confirmadas_atualiza_rows_corretos(tmp_path):
    """Testa se limpar_categorias_confirmadas atualiza o número correto de rows."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Confirmar categorias em alguns itens (não todos)
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "origem": "teste",
                "modelo": "pytest",
            },
            {
                "chave_acesso": CHAVE,
                "sequencia": 2,
                "categoria": "higiene",
                "origem": "teste",
                "modelo": "pytest",
            },
        ],
        db_path=db_path,
        confirmar=True,
    )

    # Limpar categorias confirmadas
    rows_atualizadas = limpar_categorias_confirmadas(CHAVE, db_path=db_path)

    # Deve ter atualizado exatamente 2 rows (os que tinham categoria_confirmada)
    assert rows_atualizadas == 2


def test_limpar_categorias_confirmadas_limpa_apenas_campos_corretos(tmp_path):
    """Testa se limpar_categorias_confirmadas limpa apenas categoria_confirmada e categoria_confirmada_id."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Classificar e confirmar item com todos os campos preenchidos
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "confianca": 0.95,
                "origem": "gemini-litellm",
                "modelo": "teste",
                "confirmar": True,
                "produto_nome": "Arroz",
                "produto_marca": "Tio João",
            }
        ],
        db_path=db_path,
    )

    # Capturar estado antes da limpeza
    with conexao(db_path) as con:
        before = con.execute(
            """
            SELECT categoria_sugerida, categoria_confirmada, produto_id,
                   produto_nome, produto_marca, fonte_classificacao, confianca_classificacao
            FROM itens
            WHERE chave_acesso = ? AND sequencia = 1
            """,
            [CHAVE],
        ).fetchone()

    # Limpar categorias confirmadas
    limpar_categorias_confirmadas(CHAVE, db_path=db_path)

    # Verificar estado após limpeza
    with conexao(db_path) as con:
        after = con.execute(
            """
            SELECT categoria_sugerida, categoria_confirmada, produto_id,
                   produto_nome, produto_marca, fonte_classificacao, confianca_classificacao
            FROM itens
            WHERE chave_acesso = ? AND sequencia = 1
            """,
            [CHAVE],
        ).fetchone()

    # categoria_confirmada deve ser NULL
    assert after[1] is None

    # Outros campos NÃO devem ser afetados
    assert after[0] == before[0]  # categoria_sugerida
    assert after[2] == before[2]  # produto_id
    assert after[3] == before[3]  # produto_nome
    assert after[4] == before[4]  # produto_marca
    assert after[5] == before[5]  # fonte_classificacao
    assert after[6] == before[6]  # confianca_classificacao


def test_limpar_categorias_confirmadas_atualiza_timestamp(tmp_path):
    """Testa se limpar_categorias_confirmadas atualiza o atualizado_em timestamp."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Confirmar categoria
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "origem": "teste",
                "modelo": "pytest",
            }
        ],
        db_path=db_path,
        confirmar=True,
    )

    # Capturar timestamp antes da limpeza
    with conexao(db_path) as con:
        timestamp_antes = con.execute(
            "SELECT atualizado_em FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE],
        ).fetchone()[0]

    # Aguardar um momento para garantir que o timestamp mude
    import time
    time.sleep(0.1)

    # Limpar categorias confirmadas
    limpar_categorias_confirmadas(CHAVE, db_path=db_path)

    # Verificar timestamp após limpeza
    with conexao(db_path) as con:
        timestamp_depois = con.execute(
            "SELECT atualizado_em FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE],
        ).fetchone()[0]

    # Timestamp deve ter sido atualizado
    assert timestamp_depois > timestamp_antes


def test_limpar_categorias_confirmadas_filtra_por_chave_acesso(tmp_path):
    """Testa se limpar_categorias_confirmadas filtra corretamente por chave_acesso."""
    db_path = tmp_path / "test.sqlite3"
    nota1 = _nota_exemplo()
    salvar_nota(nota1, db_path=db_path)

    # Criar uma segunda nota com chave diferente
    CHAVE2 = "43251193015006003562651350005430861685582450"
    nota2 = _nota_exemplo()
    nota2.chave_acesso = CHAVE2
    salvar_nota(nota2, db_path=db_path)

    # Confirmar categorias em ambas as notas
    registrar_classificacao_itens(
        [
            {"chave_acesso": CHAVE, "sequencia": 1, "categoria": "alimentacao", "origem": "teste", "modelo": "pytest"},
            {"chave_acesso": CHAVE2, "sequencia": 1, "categoria": "higiene", "origem": "teste", "modelo": "pytest"},
        ],
        db_path=db_path,
        confirmar=True,
    )

    # Limpar apenas a primeira nota
    limpar_categorias_confirmadas(CHAVE, db_path=db_path)

    # Verificar que apenas a primeira nota foi limpa
    with conexao(db_path) as con:
        categoria_nota1 = con.execute(
            "SELECT categoria_confirmada FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE],
        ).fetchone()[0]
        categoria_nota2 = con.execute(
            "SELECT categoria_confirmada FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE2],
        ).fetchone()[0]

    assert categoria_nota1 is None  # Limpa
    assert categoria_nota2 == "higiene"  # Não afetada


def test_limpar_categorias_confirmadas_sem_itens_confirmados(tmp_path):
    """Testa comportamento quando não há itens com categoria_confirmada."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Não confirmar nenhuma categoria, apenas sugerir
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "origem": "teste",
                "modelo": "pytest",
            }
        ],
        db_path=db_path,
        confirmar=False,  # Apenas sugestão
    )

    # Limpar categorias confirmadas (não há nenhuma)
    rows_atualizadas = limpar_categorias_confirmadas(CHAVE, db_path=db_path)

    # Nenhuma row deve ser atualizada
    assert rows_atualizadas == 0


def test_limpar_classificacoes_completas_atualiza_rows_corretos(tmp_path):
    """Testa se limpar_classificacoes_completas atualiza o número correto de rows."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Classificar todos os itens
    num_itens = len(nota.itens)
    registros = [
        {
            "chave_acesso": CHAVE,
            "sequencia": i + 1,
            "categoria": "alimentacao",
            "origem": "teste",
            "modelo": "pytest",
        }
        for i in range(num_itens)
    ]
    registrar_classificacao_itens(registros, db_path=db_path, confirmar=True)

    # Limpar todas as classificações
    rows_atualizadas = limpar_classificacoes_completas(CHAVE, db_path=db_path)

    # Deve ter atualizado todos os itens da nota
    assert rows_atualizadas == num_itens


def test_limpar_classificacoes_completas_limpa_todos_campos(tmp_path):
    """Testa se limpar_classificacoes_completas limpa todos os campos de classificação e produto."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Classificar com todos os campos preenchidos
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "confianca": 0.95,
                "origem": "gemini-litellm",
                "modelo": "teste",
                "confirmar": True,
                "produto_nome": "Arroz",
                "produto_marca": "Tio João",
            }
        ],
        db_path=db_path,
    )

    # Limpar todas as classificações
    limpar_classificacoes_completas(CHAVE, db_path=db_path)

    # Verificar que todos os campos foram limpos
    with conexao(db_path) as con:
        row = con.execute(
            """
            SELECT categoria_sugerida, categoria_confirmada, produto_id,
                   produto_nome, produto_marca, fonte_classificacao, confianca_classificacao
            FROM itens
            WHERE chave_acesso = ? AND sequencia = 1
            """,
            [CHAVE],
        ).fetchone()

    # Todos os campos devem ser NULL
    assert all(campo is None for campo in row)


def test_limpar_classificacoes_completas_atualiza_timestamp(tmp_path):
    """Testa se limpar_classificacoes_completas atualiza o atualizado_em timestamp."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Classificar item
    registrar_classificacao_itens(
        [
            {
                "chave_acesso": CHAVE,
                "sequencia": 1,
                "categoria": "alimentacao",
                "origem": "teste",
                "modelo": "pytest",
            }
        ],
        db_path=db_path,
        confirmar=True,
    )

    # Capturar timestamp antes da limpeza
    with conexao(db_path) as con:
        timestamp_antes = con.execute(
            "SELECT atualizado_em FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE],
        ).fetchone()[0]

    # Aguardar um momento para garantir que o timestamp mude
    import time
    time.sleep(0.1)

    # Limpar todas as classificações
    limpar_classificacoes_completas(CHAVE, db_path=db_path)

    # Verificar timestamp após limpeza
    with conexao(db_path) as con:
        timestamp_depois = con.execute(
            "SELECT atualizado_em FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE],
        ).fetchone()[0]

    # Timestamp deve ter sido atualizado
    assert timestamp_depois > timestamp_antes


def test_limpar_classificacoes_completas_filtra_por_chave_acesso(tmp_path):
    """Testa se limpar_classificacoes_completas filtra corretamente por chave_acesso."""
    db_path = tmp_path / "test.sqlite3"
    nota1 = _nota_exemplo()
    salvar_nota(nota1, db_path=db_path)

    # Criar uma segunda nota com chave diferente
    CHAVE2 = "43251193015006003562651350005430861685582450"
    nota2 = _nota_exemplo()
    nota2.chave_acesso = CHAVE2
    salvar_nota(nota2, db_path=db_path)

    # Classificar ambas as notas
    registrar_classificacao_itens(
        [
            {"chave_acesso": CHAVE, "sequencia": 1, "categoria": "alimentacao", "origem": "teste", "modelo": "pytest"},
            {"chave_acesso": CHAVE2, "sequencia": 1, "categoria": "higiene", "origem": "teste", "modelo": "pytest"},
        ],
        db_path=db_path,
        confirmar=True,
    )

    # Limpar apenas a primeira nota
    limpar_classificacoes_completas(CHAVE, db_path=db_path)

    # Verificar que apenas a primeira nota foi limpa
    with conexao(db_path) as con:
        categoria_nota1 = con.execute(
            "SELECT categoria_sugerida, categoria_confirmada FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE],
        ).fetchone()
        categoria_nota2 = con.execute(
            "SELECT categoria_sugerida, categoria_confirmada FROM itens WHERE chave_acesso = ? AND sequencia = 1",
            [CHAVE2],
        ).fetchone()

    assert all(campo is None for campo in categoria_nota1)  # Limpa
    assert categoria_nota2[0] == "higiene"  # Não afetada
    assert categoria_nota2[1] == "higiene"  # Não afetada


def test_limpar_classificacoes_completas_sem_classificacoes(tmp_path):
    """Testa comportamento quando não há classificações para limpar."""
    db_path = tmp_path / "test.sqlite3"
    nota = _nota_exemplo()
    salvar_nota(nota, db_path=db_path)

    # Não classificar nenhum item

    # Limpar classificações (não há nenhuma)
    rows_atualizadas = limpar_classificacoes_completas(CHAVE, db_path=db_path)

    # Ainda deve atualizar todos os itens (mesmo que já estejam NULL)
    # porque a query não filtra por campos NOT NULL
    assert rows_atualizadas == len(nota.itens)
