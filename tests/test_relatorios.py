"""Testes para funções de relatórios com fixtures determinísticas."""

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from src.database import (
    conexao,
    inicializar_banco,
    _criar_produto,
    obter_compras_fora_da_unidade,
    obter_top_produtos_por_gasto,
    obter_custos_unitarios_mensais,
    obter_meses_com_notas,
    obter_quantidades_mensais_produtos,
    obter_unidades_produtos,
    salvar_nota,
    seed_categorias_csv,
)
from src.scrapers.receita_rs import NotaFiscal, NotaItem, Pagamento
from src.ui.relatorios import (
    _aplicar_backfill,
    _calcular_cesta_basica_personalizada,
    _calcular_inflacao_acumulada,
    _calcular_inflacao_media,
    _calcular_variacao_percentual,
    _eh_unidade_fracionavel,
    _gerar_meses_periodo,
    _identificar_produtos_regulares,
    _montar_series_inflacao,
    _montar_tabela_composicao_cesta,
    _periodo_padrao,
    _preencher_meses_faltantes,
    _quantidades_fixas_cesta,
)


def _criar_nota_teste(
    chave: str,
    emissao_data: str,
    itens: list[tuple[str, Decimal, Decimal, str]],
) -> NotaFiscal:
    """Cria uma nota fiscal de teste com itens customizados.
    
    Args:
        chave: Chave de acesso da nota
        emissao_data: Data de emissão no formato ISO (YYYY-MM-DD)
        itens: Lista de tuplas (descricao, valor_unitario, quantidade, unidade)
    """
    nota_itens = [
        NotaItem(
            descricao=desc,
            codigo=None,
            valor_unitario=val_unit,
            quantidade=qtd,
            valor_total=val_unit * qtd,
            unidade=unid,
        )
        for desc, val_unit, qtd, unid in itens
    ]
    
    valor_total = sum(item.valor_total for item in nota_itens)
    
    # Convert YYYY-MM-DD to DD/MM/YYYY format expected by database
    data_obj = datetime.fromisoformat(emissao_data)
    emissao_texto = data_obj.strftime("%d/%m/%Y 10:00:00")
    
    return NotaFiscal(
        chave_acesso=chave,
        emitente_nome="Mercado Teste Ltda",
        emitente_cnpj="12.345.678/0001-90",
        emitente_endereco="Rua Teste, 123",
        numero="12345",
        serie="1",
        emissao=emissao_texto,
        total_itens=len(nota_itens),
        valor_total=valor_total,
        valor_pago=valor_total,
        tributos=Decimal("0"),
        itens=nota_itens,
        pagamentos=[
            Pagamento(forma="Dinheiro", valor=valor_total)
        ],
    )


@pytest.fixture
def db_com_dados_teste(tmp_path):
    """Cria banco temporário com dados de teste para relatórios."""
    db_path = tmp_path / "test_relatorios.db"
    
    # Inicializar banco e seed de categorias
    inicializar_banco(db_path=db_path)
    csv_path = tmp_path / "categorias.csv"
    csv_path.write_text(
        "Grupo,Categoria\n"
        "Alimentação,Alimentos\n"
        "Limpeza,Produtos de Limpeza\n",
        encoding="utf-8"
    )
    seed_categorias_csv(csv_path, db_path=db_path)
    
    # Criar 3 notas com produtos repetidos em meses diferentes
    base_date = datetime(2025, 1, 15)
    
    # Nota 1: Janeiro 2025
    nota1 = _criar_nota_teste(
        "11111111111111111111111111111111111111111111",
        base_date.date().isoformat(),
        [
            ("ARROZ BRANCO 5KG", Decimal("25.00"), Decimal("2"), "UN"),
            ("FEIJAO PRETO 1KG", Decimal("8.00"), Decimal("3"), "UN"),
            ("DETERGENTE NEUTRO 500ML", Decimal("2.50"), Decimal("5"), "UN"),
        ],
    )
    
    # Nota 2: Fevereiro 2025 (preços diferentes)
    nota2 = _criar_nota_teste(
        "22222222222222222222222222222222222222222222",
        (base_date + timedelta(days=31)).date().isoformat(),
        [
            ("ARROZ BRANCO 5KG", Decimal("27.00"), Decimal("1"), "UN"),
            ("FEIJAO PRETO 1KG", Decimal("8.50"), Decimal("2"), "UN"),
            ("SABAO EM PO 1KG", Decimal("15.00"), Decimal("1"), "UN"),
        ],
    )
    
    # Nota 3: Março 2025
    nota3 = _criar_nota_teste(
        "33333333333333333333333333333333333333333333",
        (base_date + timedelta(days=62)).date().isoformat(),
        [
            ("ARROZ BRANCO 5KG", Decimal("26.00"), Decimal("2"), "UN"),
            ("DETERGENTE NEUTRO 500ML", Decimal("2.80"), Decimal("3"), "UN"),
        ],
    )
    
    # Salvar notas no banco
    for nota in [nota1, nota2, nota3]:
        salvar_nota(nota, db_path=db_path)
    
    return db_path


def test_obter_top_produtos_por_gasto(db_com_dados_teste):
    """Ranking por gasto: quantidades em unidades diferentes não são comparáveis."""
    top_produtos = obter_top_produtos_por_gasto(
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        top_n=10,
        db_path=db_com_dados_teste,
    )

    assert [p["produto_nome"] for p in top_produtos] == [
        "Arroz Branco", "Feijao Preto", "Detergente Neutro", "Sabao Po",
    ]
    # Arroz: 2x25 + 1x27 + 2x26
    assert top_produtos[0]["gasto_total"] == pytest.approx(129.0)
    assert all(p["produto_id"] for p in top_produtos)


def test_obter_top_produtos_com_filtro_data(db_com_dados_teste):
    """Testa filtro de período no ranking de produtos."""
    top_jan = obter_top_produtos_por_gasto(
        data_inicio="2025-01-01",
        data_fim="2025-01-31",
        top_n=10,
        db_path=db_com_dados_teste,
    )

    # Apenas 3 produtos em janeiro
    assert len(top_jan) == 3
    assert top_jan[0]["produto_nome"] == "Arroz Branco"
    assert top_jan[0]["gasto_total"] == pytest.approx(50.0)


def test_obter_top_produtos_com_limit(db_com_dados_teste):
    """Testa limite de resultados no ranking."""
    top_2 = obter_top_produtos_por_gasto(
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        top_n=2,
        db_path=db_com_dados_teste,
    )

    assert len(top_2) == 2


def test_obter_custos_unitarios_mensais(db_com_dados_teste):
    """Testa cálculo de custos unitários médios mensais."""
    db_path = db_com_dados_teste
    
    # Usar nomes normalizados (sem acentos) como retornado pelo banco
    produtos = ["Arroz Branco", "Feijao Preto"]
    custos = obter_custos_unitarios_mensais(
        produtos,
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        db_path=db_path,
    )
    
    # Deve ter registros para ambos os produtos
    assert len(custos) > 0
    
    # Separar por produto
    custos_arroz = [c for c in custos if c["produto_nome"] == "Arroz Branco"]
    custos_feijao = [c for c in custos if c["produto_nome"] == "Feijao Preto"]
    
    # Arroz aparece em 3 meses
    assert len(custos_arroz) == 3
    
    # Feijao aparece em 2 meses
    assert len(custos_feijao) == 2
    
    # Verificar estrutura dos registros
    primeiro_custo = custos[0]
    assert "produto_nome" in primeiro_custo
    assert "ano_mes" in primeiro_custo
    assert "custo_unitario_medio" in primeiro_custo
    
    # Verificar formato ano_mes (YYYY-MM)
    assert len(primeiro_custo["ano_mes"]) == 7
    assert primeiro_custo["ano_mes"].count("-") == 1


def test_obter_custos_unitarios_lista_vazia(db_com_dados_teste):
    """Testa comportamento com lista vazia de produtos."""
    db_path = db_com_dados_teste
    
    custos = obter_custos_unitarios_mensais(
        [],
        data_inicio="2025-01-01",
        data_fim="2025-12-31",
        db_path=db_path,
    )
    
    assert custos == []


def test_obter_custos_unitarios_calcula_media_ponderada(db_com_dados_teste):
    """Testa se o custo médio é calculado corretamente (ponderado por quantidade)."""
    db_path = db_com_dados_teste
    
    # Arroz em Janeiro: 2 pacotes de 5 kg a 25.00 = R$ 5,00/kg
    custos_arroz_jan = obter_custos_unitarios_mensais(
        ["Arroz Branco"],
        data_inicio="2025-01-01",
        data_fim="2025-01-31",
        db_path=db_path,
    )
    
    assert len(custos_arroz_jan) == 1
    assert custos_arroz_jan[0]["ano_mes"] == "2025-01"
    assert abs(custos_arroz_jan[0]["custo_unitario_medio"] - 5.00) < 0.01


def test_obter_unidades_produtos(db_com_dados_teste):
    """Testa mapeamento de produtos para unidades mais comuns."""
    db_path = db_com_dados_teste
    
    # Usar nomes normalizados (sem acentos)
    produtos = ["Arroz Branco", "Feijao Preto", "Detergente Neutro"]
    unidades = obter_unidades_produtos(produtos, db_path=db_path)
    
    # Deve retornar unidade para cada produto
    assert len(unidades) == 3
    
    # Vendidos por unidade, mas com o tamanho na descrição: medida base KG/L
    assert unidades["Arroz Branco"] == "KG"
    assert unidades["Feijao Preto"] == "KG"
    assert unidades["Detergente Neutro"] == "L"


def test_obter_unidades_produtos_lista_vazia(db_com_dados_teste):
    """Testa comportamento com lista vazia de produtos."""
    db_path = db_com_dados_teste
    
    unidades = obter_unidades_produtos([], db_path=db_path)
    
    assert unidades == {}


def test_obter_unidades_produtos_inexistentes(db_com_dados_teste):
    """Testa comportamento com produtos que não existem no banco."""
    db_path = db_com_dados_teste
    
    unidades = obter_unidades_produtos(
        ["Produto Inexistente", "Outro Inexistente"],
        db_path=db_path,
    )
    
    assert unidades == {}


# ---------------------------------------------------------------------------
# Preço por medida (R$/kg, R$/L) e unidade dominante
# ---------------------------------------------------------------------------

def _banco_um_produto(tmp_path, compras):
    """Banco com um único produto "Coxa Frango"; compras = (data, descricao, preco, qtd, unidade)."""
    db_path = tmp_path / "medida.db"
    inicializar_banco(db_path=db_path)
    for i, (data, descricao, preco, qtd, unidade) in enumerate(compras):
        nota = _criar_nota_teste(str(i) * 44, data, [(descricao, Decimal(preco), Decimal(qtd), unidade)])
        salvar_nota(nota, db_path=db_path)
    with conexao(db_path) as con:
        produto = _criar_produto(con, "Coxa Frango", None)
        con.execute("UPDATE itens SET produto_id = ?, produto_nome = ?", [produto.id, produto.nome_base])
    return db_path


def test_peso_na_balanca_e_pacote_com_tamanho_formam_a_mesma_serie(tmp_path):
    """Coxa a granel (KG) e pacote de 1 kg (UN) viram a mesma série em R$/kg."""
    db_path = _banco_um_produto(tmp_path, [
        ("2025-01-10", "COXA FRANGO", "9.39", "1.5", "KG"),
        ("2025-04-10", "SCOXA FGO SEARA IQF 1KG", "15.80", "1", "UN"),
    ])

    custos = obter_custos_unitarios_mensais(["Coxa Frango"], db_path=db_path)

    assert [(c["ano_mes"], round(c["custo_unitario_medio"], 2)) for c in custos] == [
        ("2025-01", 9.39), ("2025-04", 15.80),
    ]
    assert obter_unidades_produtos(["Coxa Frango"], db_path=db_path) == {"Coxa Frango": "KG"}


def test_custo_unitario_sem_divisao_inteira(tmp_path):
    """Valores e quantidades inteiros não truncam o preço (7 / 2 = 3,50, não 3)."""
    db_path = _banco_um_produto(tmp_path, [("2025-01-10", "COXA FRANGO", "3.50", "2", "UN")])

    custos = obter_custos_unitarios_mensais(["Coxa Frango"], db_path=db_path)

    assert custos[0]["custo_unitario_medio"] == pytest.approx(3.5)


def test_compras_em_outra_unidade_ficam_fora_e_sao_contadas(tmp_path):
    """Só a unidade base com mais gasto entra na série; as demais são contadas."""
    db_path = _banco_um_produto(tmp_path, [
        ("2025-01-10", "COXA FRANGO", "10.00", "3", "KG"),
        ("2025-02-10", "COXA FRANGO", "11.00", "2", "KG"),
        ("2025-02-20", "COXA FRANGO BANDEJA", "12.00", "1", "UN"),  # sem tamanho
    ])

    custos = obter_custos_unitarios_mensais(["Coxa Frango"], db_path=db_path)
    quantidades = obter_quantidades_mensais_produtos(["Coxa Frango"], db_path=db_path)

    assert [round(c["custo_unitario_medio"], 2) for c in custos] == [10.0, 11.0]
    assert [q["quantidade_total"] for q in quantidades] == [3.0, 2.0]
    assert obter_compras_fora_da_unidade(["Coxa Frango"], db_path=db_path) == {"Coxa Frango": 1}


# ---------------------------------------------------------------------------
# Helpers para montar entradas dos testes de cálculo
# ---------------------------------------------------------------------------

def _df_precos(valores, dtype=None) -> pd.DataFrame:
    """Cria DataFrame de série mensal a partir de uma lista de preços."""
    meses = [f"2025-{m:02d}" for m in range(1, len(valores) + 1)]
    serie = pd.Series(valores, dtype=dtype) if dtype else pd.Series(valores)
    return pd.DataFrame({"ano_mes": meses, "custo_unitario_medio": serie})


def _qtd(produto: str, mes: str, qtd: float) -> dict:
    """Registro no formato de obter_quantidades_mensais_produtos."""
    return {"produto_nome": produto, "ano_mes": mes, "quantidade_total": qtd}


MESES_6 = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06"]


# ---------------------------------------------------------------------------
# _calcular_variacao_percentual / _calcular_inflacao_acumulada (funções reais)
# ---------------------------------------------------------------------------

def test_variacao_percentual():
    """Variação percentual básica, com guardas para zero, None e NaN."""
    assert abs(_calcular_variacao_percentual(100.0, 110.0) - 10.0) < 0.01
    assert abs(_calcular_variacao_percentual(100.0, 90.0) - (-10.0)) < 0.01
    assert _calcular_variacao_percentual(0.0, 100.0) == 0.0
    assert _calcular_variacao_percentual(None, 100.0) == 0.0
    assert _calcular_variacao_percentual(float("nan"), 100.0) == 0.0


def test_inflacao_acumulada_serie_completa():
    """Série sem lacunas: [100, 110, 121] -> [0%, 10%, 21%]."""
    inflacao = _calcular_inflacao_acumulada(_df_precos([100.0, 110.0, 121.0]))

    assert abs(inflacao[0] - 0.0) < 0.01
    assert abs(inflacao[1] - 10.0) < 0.01
    assert abs(inflacao[2] - 21.0) < 0.01


def test_inflacao_acumulada_precos_constantes():
    """Preços constantes: inflação 0% em todos os meses."""
    inflacao = _calcular_inflacao_acumulada(_df_precos([100.0, 100.0, 100.0]))

    assert all(v is not None and abs(v) < 0.01 for v in inflacao)


def test_inflacao_acumulada_nan_a_esquerda():
    """Cenário da regressão do commit 1fdd053: produto entra no meio do período.

    NaN nos meses iniciais deve resultar em None (linha ausente no gráfico) e a
    acumulação começa em 0% no primeiro mês com preço — sem propagar NaN.
    """
    nan = float("nan")
    inflacao = _calcular_inflacao_acumulada(_df_precos([nan, nan, 100.0, 110.0]))

    assert inflacao[0] is None
    assert inflacao[1] is None
    assert abs(inflacao[2] - 0.0) < 0.01
    assert abs(inflacao[3] - 10.0) < 0.01


def test_inflacao_acumulada_gap_interior():
    """Lacuna no meio da série: compõe sobre o último preço válido."""
    inflacao = _calcular_inflacao_acumulada(_df_precos([100.0, float("nan"), 110.0]))

    assert abs(inflacao[0] - 0.0) < 0.01
    assert inflacao[1] is None
    assert abs(inflacao[2] - 10.0) < 0.01


def test_inflacao_acumulada_todos_nan():
    """Série inteira sem dados: tudo None."""
    nan = float("nan")
    inflacao = _calcular_inflacao_acumulada(_df_precos([nan, nan, nan]))

    assert inflacao == [None, None, None]


def test_inflacao_acumulada_none_literal_equivale_nan():
    """Coluna object com None literal produz o mesmo resultado que NaN float."""
    inflacao = _calcular_inflacao_acumulada(
        _df_precos([None, 100.0, 110.0], dtype=object)
    )

    assert inflacao[0] is None
    assert abs(inflacao[1] - 0.0) < 0.01
    assert abs(inflacao[2] - 10.0) < 0.01


def test_inflacao_acumulada_df_vazio():
    """DataFrame vazio retorna lista vazia."""
    df_vazio = pd.DataFrame(columns=["ano_mes", "custo_unitario_medio"])
    assert _calcular_inflacao_acumulada(df_vazio) == []


# ---------------------------------------------------------------------------
# _preencher_meses_faltantes
# ---------------------------------------------------------------------------

def test_preencher_meses_faltantes_denso_com_ffill():
    """Todos os produtos aparecem em todos os meses; ffill após a 1ª compra."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-03", "custo_unitario_medio": 12.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "custo_unitario_medio": 5.0},
    ]
    df = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-03-31")

    assert len(df) == 6  # 2 produtos x 3 meses

    serie_a = df[df["produto_nome"] == "A"].sort_values("ano_mes")
    assert serie_a["custo_unitario_medio"].tolist() == [10.0, 10.0, 12.0]

    serie_b = df[df["produto_nome"] == "B"].sort_values("ano_mes")
    valores_b = serie_b["custo_unitario_medio"].tolist()
    assert pd.isna(valores_b[0])  # antes da 1ª compra: sem preço
    assert valores_b[1] == 5.0
    assert valores_b[2] == 5.0  # forward fill


# ---------------------------------------------------------------------------
# _eh_unidade_fracionavel / _identificar_produtos_regulares (nova regra)
# ---------------------------------------------------------------------------

def test_eh_unidade_fracionavel():
    assert _eh_unidade_fracionavel("KG")
    assert _eh_unidade_fracionavel("kg")
    assert _eh_unidade_fracionavel("L")
    assert not _eh_unidade_fracionavel("UN")
    assert not _eh_unidade_fracionavel(None)  # default UN


def test_regular_unitario_meses_alternados():
    """UN com compra em m1/m3/m5: nunca 2 meses seguidos sem compra -> regular."""
    quantidades = [_qtd("A", m, 1) for m in ["2025-01", "2025-03", "2025-05"]]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6
    )
    assert regulares == ["A"]


def test_nao_regular_lacuna_dois_meses():
    """Compras em m1/m4/m6 deixam m2+m3 vazios (lacuna dupla) -> não regular."""
    quantidades = [_qtd("A", m, 1) for m in ["2025-01", "2025-04", "2025-06"]]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6
    )
    assert regulares == []


def test_nao_regular_borda_inicial():
    """Compras apenas de m3 em diante: m1+m2 vazios -> não regular."""
    quantidades = [_qtd("A", m, 1) for m in ["2025-03", "2025-04", "2025-05", "2025-06"]]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6
    )
    assert regulares == []


def test_nao_regular_borda_final():
    """Compras apenas até m4: m5+m6 vazios -> não regular."""
    quantidades = [_qtd("A", m, 1) for m in ["2025-01", "2025-02", "2025-03", "2025-04"]]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6
    )
    assert regulares == []


def test_unitario_quantidade_fracionaria_nao_conta():
    """Para produto UN, mês com quantidade < 1 não conta como compra."""
    quantidades = [
        _qtd("A", "2025-01", 1),
        _qtd("A", "2025-02", 0.5),  # não conta: cria lacuna dupla com m3
        _qtd("A", "2025-04", 1),
        _qtd("A", "2025-05", 1),
        _qtd("A", "2025-06", 1),
    ]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6
    )
    assert regulares == []


def test_fracionavel_media_abaixo_do_limite():
    """KG comprado todo mês, mas média mensal 0.05 <= 0.1 -> não regular."""
    quantidades = [_qtd("A", m, 0.05) for m in MESES_6]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "KG"}, MESES_6
    )
    assert regulares == []


def test_fracionavel_media_acima_do_limite():
    """KG com 0.3 em m1/m3/m5 (média 0.15 > 0.1, sem lacuna dupla) -> regular."""
    quantidades = [_qtd("A", m, 0.3) for m in ["2025-01", "2025-03", "2025-05"]]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "KG"}, MESES_6
    )
    assert regulares == ["A"]


def test_janela_menor_que_seis_meses():
    """Período de 3 meses usa o período inteiro como janela."""
    meses_3 = ["2025-01", "2025-02", "2025-03"]
    # UN com compra em m1 e m3 (m2 vazio, sem lacuna dupla) -> regular
    quantidades = [_qtd("A", "2025-01", 1), _qtd("A", "2025-03", 1)]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, meses_3
    )
    assert regulares == ["A"]

    # Fracionável: média calculada sobre 3 meses (0.6 / 3 = 0.2 > 0.1) -> regular
    quantidades_kg = [_qtd("B", "2025-01", 0.3), _qtd("B", "2025-03", 0.3)]
    regulares_kg = _identificar_produtos_regulares(
        quantidades_kg, ["B"], {"B": "KG"}, meses_3
    )
    assert regulares_kg == ["B"]


def test_produto_sem_compra_na_janela():
    """Produto do top-10 com compras apenas antes dos últimos 6 meses -> não regular."""
    meses_12 = _gerar_meses_periodo("2024-07-01", "2025-06-30")
    # Compras apenas em 2024 (fora da janela 2025-01..2025-06)
    quantidades = [_qtd("A", m, 5) for m in ["2024-07", "2024-08", "2024-09"]]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, meses_12
    )
    assert regulares == []


def test_produto_sem_unidade_no_dict_usa_default_un():
    """Produto ausente do dict de unidades é tratado como UN (qtd >= 1)."""
    # 0.5 todo mês: como UN, nenhum mês conta -> não regular
    # (se fosse tratado como fracionável, seria regular: média 0.5 > 0.1)
    quantidades = [_qtd("A", m, 0.5) for m in MESES_6]

    regulares = _identificar_produtos_regulares(quantidades, ["A"], {}, MESES_6)
    assert regulares == []


def test_regularidade_preserva_ordem_do_top():
    """A lista de regulares preserva a ordem dos produtos informados."""
    quantidades = [_qtd(p, m, 1) for p in ["B", "A"] for m in MESES_6]

    regulares = _identificar_produtos_regulares(
        quantidades, ["B", "A"], {"B": "UN", "A": "UN"}, MESES_6
    )
    assert regulares == ["B", "A"]


def test_regularidade_com_dados_do_banco(db_com_dados_teste):
    """Integração: saídas reais do banco alimentam a regra sem adaptação."""
    db_path = db_com_dados_teste
    produtos = ["Arroz Branco", "Feijao Preto", "Detergente Neutro"]

    quantidades = obter_quantidades_mensais_produtos(
        produtos,
        data_inicio="2025-01-01",
        data_fim="2025-03-31",
        db_path=db_path,
    )
    unidades = obter_unidades_produtos(produtos, db_path=db_path)
    meses = _gerar_meses_periodo("2025-01-01", "2025-03-31")

    regulares = _identificar_produtos_regulares(quantidades, produtos, unidades, meses)

    # Arroz: compras em jan/fev/mar -> regular
    # Feijao: jan/fev (m3 vazio na borda, lacuna simples) -> regular
    # Detergente: jan/mar (m2 vazio, lacuna simples) -> regular
    assert regulares == ["Arroz Branco", "Feijao Preto", "Detergente Neutro"]


# ---------------------------------------------------------------------------
# Regularidade x meses sem nota importada (lacuna de coleta != de consumo)
# ---------------------------------------------------------------------------

def test_mes_sem_nota_nao_penaliza_regularidade():
    """Lacuna de coleta não desqualifica: 03 e 04 não tiveram nota importada.

    Sem o filtro, os dois meses vazios seguidos derrubariam o produto — foi o que
    esvaziava a lista de regulares e deixava a inflação média achatada em 0%.
    """
    quantidades = [_qtd("A", m, 2) for m in ["2025-01", "2025-02", "2025-05", "2025-06"]]

    # Sem informar meses ativos: 03 e 04 contam como lacuna dupla -> não regular
    assert _identificar_produtos_regulares(quantidades, ["A"], {"A": "UN"}, MESES_6) == []

    # Informando que 03 e 04 não tiveram nota: janela vira [01, 02, 05, 06]
    regulares = _identificar_produtos_regulares(
        quantidades,
        ["A"],
        {"A": "UN"},
        MESES_6,
        meses_com_notas=["2025-01", "2025-02", "2025-05", "2025-06"],
    )
    assert regulares == ["A"]


def test_lacuna_real_ainda_desqualifica():
    """Mês ativo (com nota importada) e sem compra continua contando contra."""
    # Comprou só nas bordas; 02..05 tiveram notas, mas nenhuma compra do produto
    quantidades = [_qtd("A", "2025-01", 2), _qtd("A", "2025-06", 2)]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6, meses_com_notas=MESES_6
    )
    assert regulares == []


def test_janela_conta_apenas_meses_ativos():
    """A janela de 6 meses é medida em meses ativos, e o divisor acompanha.

    Com apenas 2 meses ativos, a média do fracionável é 0.6/2 = 0.3 (> 0.1).
    Se a janela ainda fosse de 6 meses de calendário, seria 0.6/6 = 0.1 e o
    produto não passaria.
    """
    meses_12 = _gerar_meses_periodo("2025-01-01", "2025-12-31")
    quantidades = [_qtd("A", "2025-11", 0.3), _qtd("A", "2025-12", 0.3)]

    regulares = _identificar_produtos_regulares(
        quantidades,
        ["A"],
        {"A": "KG"},
        meses_12,
        meses_com_notas=["2025-11", "2025-12"],
    )
    assert regulares == ["A"]

    # Sem o filtro, a janela pega 07..12 e a média cai para o limite -> fora
    assert _identificar_produtos_regulares(quantidades, ["A"], {"A": "KG"}, meses_12) == []


def test_meses_com_notas_none_preserva_comportamento():
    """meses_com_notas=None equivale a omitir o parâmetro."""
    quantidades = [_qtd("A", m, 1) for m in MESES_6]

    sem_param = _identificar_produtos_regulares(quantidades, ["A"], {"A": "UN"}, MESES_6)
    com_none = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6, meses_com_notas=None
    )
    assert sem_param == com_none == ["A"]


def test_nenhum_mes_ativo_no_periodo():
    """Período sem nenhuma nota importada não produz regulares."""
    quantidades = [_qtd("A", m, 5) for m in MESES_6]

    regulares = _identificar_produtos_regulares(
        quantidades, ["A"], {"A": "UN"}, MESES_6, meses_com_notas=[]
    )
    assert regulares == []


def test_obter_meses_com_notas(db_com_dados_teste):
    """Retorna os meses com nota importada, ordenados e sem repetição."""
    meses = obter_meses_com_notas(db_path=db_com_dados_teste)
    assert meses == ["2025-01", "2025-02", "2025-03"]


def test_obter_meses_com_notas_respeita_periodo(db_com_dados_teste):
    """Filtro de período restringe os meses retornados."""
    meses = obter_meses_com_notas(
        data_inicio="2025-02-01",
        data_fim="2025-02-28",
        db_path=db_com_dados_teste,
    )
    assert meses == ["2025-02"]


# ---------------------------------------------------------------------------
# _calcular_inflacao_media (base dos agregados e fallback)
# ---------------------------------------------------------------------------

def test_inflacao_media_ignora_nan_dos_produtos():
    """A média de cada mês usa apenas os produtos com dado naquele mês."""
    nan = float("nan")
    series = {"A": [0.0, 10.0, 20.0], "B": [nan, 20.0, 40.0]}

    media = _calcular_inflacao_media(series, ["A", "B"], 3)

    assert abs(media[0] - 0.0) < 0.01   # só A tem dado
    assert abs(media[1] - 15.0) < 0.01  # (10 + 20) / 2
    assert abs(media[2] - 30.0) < 0.01  # (20 + 40) / 2


def test_inflacao_media_mes_sem_dado_vira_nan():
    """Mês sem nenhum produto com dado é NaN, não 0.0.

    Regressão do sintoma relatado: o antigo preenchimento com 0.0 desenhava uma
    linha reta em 0% indistinguível de inflação real nula.
    """
    nan = float("nan")
    series = {"A": [nan, 10.0]}

    media = _calcular_inflacao_media(series, ["A"], 2)

    assert pd.isna(media[0])
    assert abs(media[1] - 10.0) < 0.01


def test_inflacao_media_sem_produtos_nao_vira_serie_zero():
    """Sem produtos na base, a média é toda NaN — nunca uma constante 0.0."""
    media = _calcular_inflacao_media({}, [], 3)

    assert len(media) == 3
    assert all(pd.isna(v) for v in media)


def test_fallback_usa_todos_os_produtos_com_preco():
    """Fallback da tela: sem regulares, a média sai de 0% usando todo o top.

    Reproduz o cenário real (nenhum produto regular no período) e confirma que a
    base alternativa gera uma curva de verdade, não uma linha achatada.
    """
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-02", "custo_unitario_medio": 12.0},
        {"produto_nome": "B", "ano_mes": "2025-01", "custo_unitario_medio": 20.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "custo_unitario_medio": 26.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-02-28")
    df_completo = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-02-28")

    # Base do fallback: todos os produtos com preço conhecido
    df_backfilled = _aplicar_backfill(df_completo, ["A", "B"], meses)
    series = _montar_series_inflacao(df_backfilled, ["A", "B"], meses)
    media = _calcular_inflacao_media(series, ["A", "B"], len(meses))

    assert abs(media[0] - 0.0) < 0.01    # base
    assert abs(media[1] - 25.0) < 0.01   # (20% + 30%) / 2
    assert media != [0.0] * len(meses)


# ---------------------------------------------------------------------------
# _aplicar_backfill / cesta básica / alinhamento
# ---------------------------------------------------------------------------

def test_aplicar_backfill_preenche_meses_iniciais():
    """Meses anteriores à 1ª compra recebem o primeiro preço conhecido."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-03", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-04", "custo_unitario_medio": 12.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-04-30")
    df_completo = _preencher_meses_faltantes(custos, ["A"], "2025-01-01", "2025-04-30")

    df_backfilled = _aplicar_backfill(df_completo, ["A"], meses)
    serie = df_backfilled.sort_values("ano_mes")["custo_unitario_medio"].tolist()

    assert serie == [10.0, 10.0, 10.0, 12.0]


def test_cesta_com_backfill_sem_salto_de_composicao():
    """Produto entrando no meio do período não gera degrau no custo da cesta."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-02", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-03", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-04", "custo_unitario_medio": 10.0},
        {"produto_nome": "B", "ano_mes": "2025-03", "custo_unitario_medio": 50.0},
        {"produto_nome": "B", "ano_mes": "2025-04", "custo_unitario_medio": 50.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-04-30")
    df_completo = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-04-30")

    df_backfilled = _aplicar_backfill(df_completo, ["A", "B"], meses)
    df_cesta = _calcular_cesta_basica_personalizada(df_backfilled, ["A", "B"], {"A": 1.0, "B": 1.0})

    custos_cesta = df_cesta.sort_values("ano_mes")["custo_cesta"].tolist()
    assert custos_cesta == [60.0, 60.0, 60.0, 60.0]  # sem degrau quando B "entra"

    inflacao_cesta = _calcular_inflacao_acumulada(df_cesta, coluna_valor="custo_cesta")
    assert all(v is not None and abs(v) < 0.01 for v in inflacao_cesta)


def test_inflacao_zero_em_meses_backfilled():
    """Nos meses retro-preenchidos o produto contribui com 0% de inflação."""
    custos = [
        {"produto_nome": "B", "ano_mes": "2025-03", "custo_unitario_medio": 50.0},
        {"produto_nome": "B", "ano_mes": "2025-04", "custo_unitario_medio": 55.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-04-30")
    df_completo = _preencher_meses_faltantes(custos, ["B"], "2025-01-01", "2025-04-30")
    df_backfilled = _aplicar_backfill(df_completo, ["B"], meses)

    series = _montar_series_inflacao(df_backfilled, ["B"], meses)

    assert abs(series["B"][0] - 0.0) < 0.01
    assert abs(series["B"][1] - 0.0) < 0.01
    assert abs(series["B"][2] - 0.0) < 0.01
    assert abs(series["B"][3] - 10.0) < 0.01


def test_backfill_e_cesta_sem_produtos_regulares():
    """Sem produtos regulares: DataFrames vazios com colunas corretas."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-02-28")
    df_completo = _preencher_meses_faltantes(custos, ["A"], "2025-01-01", "2025-02-28")

    df_backfilled = _aplicar_backfill(df_completo, [], meses)
    assert df_backfilled.empty
    assert list(df_backfilled.columns) == ["ano_mes", "produto_nome", "custo_unitario_medio"]

    df_cesta = _calcular_cesta_basica_personalizada(df_completo, [], {})
    assert df_cesta.empty
    assert list(df_cesta.columns) == ["ano_mes", "custo_cesta"]


def test_alinhamento_com_meses_ordenados():
    """Produto iniciando em m2: série alinhada tem NaN em m1 e 0% exatamente em m2."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-02", "custo_unitario_medio": 100.0},
        {"produto_nome": "A", "ano_mes": "2025-03", "custo_unitario_medio": 110.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-04-30")
    df_completo = _preencher_meses_faltantes(custos, ["A"], "2025-01-01", "2025-04-30")

    series = _montar_series_inflacao(df_completo, ["A"], meses)
    serie_a = series["A"]

    assert len(serie_a) == len(meses)
    assert pd.isna(serie_a[meses.index("2025-01")])
    assert abs(serie_a[meses.index("2025-02")] - 0.0) < 0.01
    assert abs(serie_a[meses.index("2025-03")] - 10.0) < 0.01
    assert abs(serie_a[meses.index("2025-04")] - 10.0) < 0.01  # ffill mantém preço


# ---------------------------------------------------------------------------
# _montar_tabela_composicao_cesta (tabela "Composição da Cesta Básica")
# ---------------------------------------------------------------------------

def test_composicao_cesta_inclui_produtos_do_fallback():
    """No fallback (nenhum regular), a tabela usa os mesmos produtos do gráfico.

    Regressão: o preço médio era filtrado por `produtos_regulares`, vazio no
    fallback; o merge com as quantidades saía vazio e o total virava R$ 0,00.
    """
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "B", "ano_mes": "2025-01", "custo_unitario_medio": 4.0},
    ]
    quantidades = [
        {"produto_nome": "A", "ano_mes": "2025-01", "quantidade_total": 2.0},
        {"produto_nome": "B", "ano_mes": "2025-01", "quantidade_total": 3.0},
    ]
    df_completo = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-01-31")

    tabela = _montar_tabela_composicao_cesta(
        quantidades, custos, df_completo, ["A", "B"], {"A": "UN", "B": "UN"}
    )

    assert sorted(tabela["Produto"]) == ["A", "B"]
    assert abs(tabela["Custo no Último Mês"].sum() - (2 * 10.0 + 3 * 4.0)) < 0.01


def test_composicao_cesta_sem_quantidades_retorna_vazio():
    """Sem quantidades para os produtos da cesta, a tabela sai vazia."""
    custos = [{"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0}]
    df_completo = _preencher_meses_faltantes(custos, ["A"], "2025-01-01", "2025-01-31")

    tabela = _montar_tabela_composicao_cesta([], custos, df_completo, ["A"], {"A": "UN"})

    assert tabela.empty


# ---------------------------------------------------------------------------
# Cesta Laspeyres: quantidades fixas × preço de cada mês
# ---------------------------------------------------------------------------

def test_quantidade_fixa_e_media_dos_meses_com_compra():
    """Mês sem compra não entra na média (não é quantidade zero)."""
    quantidades = [
        {"produto_nome": "A", "ano_mes": "2025-01", "quantidade_total": 2.0},
        {"produto_nome": "A", "ano_mes": "2025-03", "quantidade_total": 4.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "quantidade_total": 0.5},
        {"produto_nome": "C", "ano_mes": "2025-02", "quantidade_total": 9.0},
    ]

    assert _quantidades_fixas_cesta(quantidades, ["A", "B"]) == {"A": 3.0, "B": 0.5}


def test_cesta_pondera_preco_pela_quantidade_comprada():
    """Custo = Σ quantidade fixa × preço do mês; o item caro e pouco comprado pesa pouco.

    Regressão: a cesta era a média simples dos preços (A a R$ 10 e B a R$ 100
    pesavam igual), e a inflação de B (+10%) dominava a da cesta.
    """
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-02", "custo_unitario_medio": 10.0},
        {"produto_nome": "B", "ano_mes": "2025-01", "custo_unitario_medio": 100.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "custo_unitario_medio": 110.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-02-28")
    df_completo = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-02-28")
    df_backfilled = _aplicar_backfill(df_completo, ["A", "B"], meses)

    df_cesta = _calcular_cesta_basica_personalizada(df_backfilled, ["A", "B"], {"A": 2.0, "B": 0.5})

    assert df_cesta.sort_values("ano_mes")["custo_cesta"].tolist() == [70.0, 75.0]
    inflacao = _calcular_inflacao_acumulada(df_cesta, coluna_valor="custo_cesta")
    assert inflacao[-1] == pytest.approx(5 / 70 * 100)


def test_cesta_sem_preco_no_mes_nao_soma_parcial():
    """Sem o preço de um produto no mês, o custo fica vazio em vez de cair de degrau."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-02", "custo_unitario_medio": 10.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "custo_unitario_medio": 50.0},
    ]
    df_completo = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-02-28")

    df_cesta = _calcular_cesta_basica_personalizada(df_completo, ["A", "B"], {"A": 1.0, "B": 1.0})

    serie = df_cesta.set_index("ano_mes")["custo_cesta"]
    assert pd.isna(serie["2025-01"])
    assert serie["2025-02"] == 60.0


def test_composicao_preco_medio_so_com_meses_de_compra():
    """Meses repetidos pelo último preço (ffill) não entram no preço médio.

    Regressão: com compras em jan (R$ 10) e abr (R$ 20), fev e mar repetiam
    R$ 10 e o preço médio saía R$ 12,50 em vez de R$ 15,00.
    """
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-04", "custo_unitario_medio": 20.0},
    ]
    quantidades = [
        {"produto_nome": "A", "ano_mes": "2025-01", "quantidade_total": 1.0},
        {"produto_nome": "A", "ano_mes": "2025-04", "quantidade_total": 3.0},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-04-30")
    df_completo = _preencher_meses_faltantes(custos, ["A"], "2025-01-01", "2025-04-30")
    df_backfilled = _aplicar_backfill(df_completo, ["A"], meses)

    tabela = _montar_tabela_composicao_cesta(quantidades, custos, df_backfilled, ["A"], {"A": "KG"})

    linha = tabela.iloc[0]
    assert linha["Quantidade Mensal"] == pytest.approx(2.0)
    assert linha["Preço Médio"] == pytest.approx(15.0)
    assert linha["Preço no Último Mês"] == pytest.approx(20.0)


def test_total_da_composicao_e_o_custo_da_cesta_no_ultimo_mes():
    """O total da tabela é o mesmo custo da cesta do gráfico e do CSV no último mês."""
    custos = [
        {"produto_nome": "A", "ano_mes": "2025-01", "custo_unitario_medio": 10.0},
        {"produto_nome": "A", "ano_mes": "2025-03", "custo_unitario_medio": 12.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "custo_unitario_medio": 4.0},
    ]
    quantidades = [
        {"produto_nome": "A", "ano_mes": "2025-01", "quantidade_total": 2.0},
        {"produto_nome": "A", "ano_mes": "2025-03", "quantidade_total": 4.0},
        {"produto_nome": "B", "ano_mes": "2025-02", "quantidade_total": 0.5},
    ]
    meses = _gerar_meses_periodo("2025-01-01", "2025-03-31")
    df_completo = _preencher_meses_faltantes(custos, ["A", "B"], "2025-01-01", "2025-03-31")
    df_backfilled = _aplicar_backfill(df_completo, ["A", "B"], meses)
    qtd_fixa = _quantidades_fixas_cesta(quantidades, ["A", "B"])

    df_cesta = _calcular_cesta_basica_personalizada(df_backfilled, ["A", "B"], qtd_fixa)
    tabela = _montar_tabela_composicao_cesta(
        quantidades, custos, df_backfilled, ["A", "B"], {"A": "KG", "B": "KG"}
    )

    custo_ultimo_mes = df_cesta.set_index("ano_mes")["custo_cesta"]["2025-03"]
    assert custo_ultimo_mes == pytest.approx(3 * 12.0 + 0.5 * 4.0)
    assert tabela["Custo no Último Mês"].sum() == pytest.approx(custo_ultimo_mes)


# ---------------------------------------------------------------------------
# Período padrão dos relatórios
# ---------------------------------------------------------------------------

def test_periodo_padrao_termina_no_ultimo_mes_com_nota():
    """Os 12 meses padrão terminam no último mês com nota, não no mês atual.

    Regressão: com o último dado em nov/2025, o padrão (últimos 12 meses a
    partir de hoje) caía quase inteiro fora dos dados.
    """
    inicio, fim = _periodo_padrao(["2025-01", "2025-09", "2025-11"], datetime(2026, 10, 26).date())

    assert (inicio.isoformat(), fim.isoformat()) == ("2024-12-01", "2025-11-30")


def test_periodo_padrao_sem_notas_termina_hoje():
    inicio, fim = _periodo_padrao([], datetime(2026, 10, 26).date())

    assert (inicio.isoformat(), fim.isoformat()) == ("2025-11-01", "2026-10-26")
