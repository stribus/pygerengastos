"""Módulo de relatórios com gráficos interativos para análise de preços."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st

from src.database import (
    obter_compras_fora_da_unidade,
    obter_custos_unitarios_mensais,
    obter_meses_com_notas,
    obter_quantidades_mensais_produtos,
    obter_top_produtos_por_gasto,
    obter_unidades_produtos,
)
from src.medidas import normalizar_unidade

JANELA_REGULARIDADE_MESES = 6
QTD_MINIMA_MES_UNITARIO = 1.0
MEDIA_MINIMA_MENSAL_FRACIONAVEL = 0.1


def _eh_unidade_fracionavel(unidade: str | None) -> bool:
    """Indica se a unidade representa produto vendido fracionado (peso/volume)."""
    return normalizar_unidade(unidade) in ("KG", "L")


def _rotulo_produto(produto: str, unidade: str | None) -> str:
    """Nome do produto com a medida do preço: "Coxa Frango (R$/kg)"."""
    return f"{produto} (R$/{(unidade or 'UN').lower()})"


def _avisar_compras_fora_da_unidade(descartadas: dict[str, int]) -> None:
    """Informa as compras que ficaram fora do gráfico por estarem em outra medida."""
    total = sum(descartadas.values())
    if total:
        detalhe = ", ".join(f"{produto}: {qtd}" for produto, qtd in descartadas.items())
        st.caption(
            f"ℹ️ {total} compra(s) ficaram fora do gráfico por estarem numa medida "
            f"diferente da principal do produto (ex.: descrição sem o tamanho da "
            f"embalagem): {detalhe}."
        )


def _calcular_variacao_percentual(valor_anterior: float, valor_atual: float) -> float:
    """Calcula variação percentual entre dois valores."""
    if valor_anterior is None or pd.isna(valor_anterior) or valor_anterior == 0:
        return 0.0
    return ((valor_atual - valor_anterior) / valor_anterior) * 100


def _gerar_meses_periodo(data_inicio_str: str, data_fim_str: str) -> list[str]:
    """Gera a lista ordenada de meses "YYYY-MM" do período (inclui o mês de data_fim)."""
    data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d")
    data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d")

    return pd.period_range(
        start=data_inicio,
        end=data_fim,
        freq="M",
    ).strftime("%Y-%m").tolist()


def _periodo_padrao(meses_com_notas: list[str], hoje: date) -> tuple[date, date]:
    """Período padrão dos relatórios: os 12 meses até o último mês com nota.

    Terminar no mês atual deixaria o período vazio quando as notas pararem de
    ser importadas; sem nenhuma nota, os 12 meses terminam hoje.
    """
    if meses_com_notas:
        ultimo_mes = pd.Period(meses_com_notas[-1], freq="M")
        data_fim = ultimo_mes.end_time.date()
    else:
        ultimo_mes = pd.Period(hoje, freq="M")
        data_fim = hoje

    return (ultimo_mes - 11).start_time.date(), data_fim


def _preencher_meses_faltantes(
    dados: list[dict[str, Any]],
    produtos: list[str],
    data_inicio_str: str,
    data_fim_str: str,
) -> pd.DataFrame:
    """Preenche meses faltantes com o último preço conhecido para cada produto.

    Retorna DataFrame com colunas: ano_mes, produto_nome, custo_unitario_medio.
    Garante que todos os produtos apareçam em todos os meses do período; meses
    anteriores à primeira compra ficam sem preço (NaN após a conversão do pandas).
    """
    # Converter dados para DataFrame
    df = pd.DataFrame(dados)

    if df.empty:
        # Retorna DataFrame vazio com estrutura esperada
        return pd.DataFrame(columns=["ano_mes", "produto_nome", "custo_unitario_medio"])

    meses = _gerar_meses_periodo(data_inicio_str, data_fim_str)

    # Criar DataFrame completo com todos produtos x meses
    linhas_completas = []
    for produto in produtos:
        ultimo_preco = None
        for mes in meses:
            # Buscar preço do mês atual
            preco_mes = df[
                (df["produto_nome"] == produto) & (df["ano_mes"] == mes)
            ]

            if not preco_mes.empty:
                preco = float(preco_mes.iloc[0]["custo_unitario_medio"])
                ultimo_preco = preco
            else:
                # Usa último preço conhecido ou None
                preco = ultimo_preco

            # Sempre adicionar a linha para garantir alinhamento correto de meses
            linhas_completas.append({
                "ano_mes": mes,
                "produto_nome": produto,
                "custo_unitario_medio": preco
            })

    return pd.DataFrame(linhas_completas)


def _calcular_inflacao_acumulada(
    df: pd.DataFrame,
    coluna_mes: str = "ano_mes",
    coluna_valor: str = "custo_unitario_medio",
) -> list[float | None]:
    """Calcula inflação acumulada para série temporal de preços.

    Retorna lista de valores de inflação acumulada em percentual, alinhada com
    as linhas do DataFrame. Meses sem dado (None/NaN) permanecem como None; a
    acumulação começa em 0% no primeiro mês com preço e, havendo lacunas
    interiores, compõe sobre o último preço válido.
    """
    if df.empty:
        return []

    valores = df[coluna_valor].tolist()
    inflacao_acumulada: list[float | None] = [None] * len(valores)

    ultimo_valor: float | None = None
    inflacao_atual = 0.0

    for i, val in enumerate(valores):
        if val is None or pd.isna(val):
            continue

        val_f = float(val)
        if ultimo_valor is None:
            # Primeiro mês com dado é a base (0%)
            inflacao_atual = 0.0
        else:
            var_percentual = _calcular_variacao_percentual(ultimo_valor, val_f)
            # Acumular: (1 + inflacao_anterior/100) * (1 + var_atual/100) - 1
            inflacao_atual = ((1 + inflacao_atual / 100) * (1 + var_percentual / 100) - 1) * 100

        inflacao_acumulada[i] = inflacao_atual
        ultimo_valor = val_f

    return inflacao_acumulada


def _identificar_produtos_regulares(
    quantidades: list[dict[str, Any]],
    produtos: list[str],
    unidades: dict[str, str],
    meses_periodo: list[str],
    janela_meses: int = JANELA_REGULARIDADE_MESES,
    meses_com_notas: Iterable[str] | None = None,
) -> list[str]:
    """Identifica produtos comprados com regularidade na janela recente do período.

    Um produto é regular quando, nos últimos ``janela_meses`` meses ativos do
    período selecionado (ou em todos eles, se forem menos), nunca fica 2 meses
    seguidos sem compra — incluindo as bordas da janela. A avaliação usa os
    meses de compra real (``quantidades``, saída de
    obter_quantidades_mensais_produtos):

    - Produto unitário (UN, PC...): o mês conta se quantidade >= 1.
    - Produto fracionável (KG, G, L...): o mês conta se quantidade > 0, e a
      média mensal de quantidade na janela deve superar
      ``MEDIA_MINIMA_MENSAL_FRACIONAVEL``.

    ``meses_com_notas`` (saída de obter_meses_com_notas) lista os meses em que
    houve alguma nota importada. Meses fora dessa lista são descartados da
    janela: sem nenhuma nota, o mês reflete lacuna de coleta, não ausência de
    compra, e penalizaria todos os produtos de uma vez. A adjacência da regra
    passa então a valer entre meses ativos consecutivos, não no calendário.
    Quando omitido, todos os meses do período são considerados ativos.

    Retorna lista de nomes de produtos regulares, preservando a ordem de
    ``produtos``.
    """
    if not meses_periodo:
        return []

    if meses_com_notas is not None:
        ativos = set(meses_com_notas)
        meses_periodo = [mes for mes in meses_periodo if mes in ativos]
        if not meses_periodo:
            return []

    meses_janela = meses_periodo[-janela_meses:]
    n_janela = len(meses_janela)

    qtd_por_produto_mes: dict[tuple[str, str], float] = {}
    for registro in quantidades:
        chave = (registro["produto_nome"], registro["ano_mes"])
        qtd_por_produto_mes[chave] = (
            qtd_por_produto_mes.get(chave, 0.0) + float(registro["quantidade_total"])
        )

    produtos_regulares = []
    for produto in produtos:
        fracionavel = _eh_unidade_fracionavel(unidades.get(produto))
        qtds = [qtd_por_produto_mes.get((produto, mes), 0.0) for mes in meses_janela]

        if fracionavel:
            comprou = [q > 0 for q in qtds]
        else:
            comprou = [q >= QTD_MINIMA_MES_UNITARIO for q in qtds]

        # Produto sem nenhuma compra na janela nunca é regular
        if not any(comprou):
            continue

        # Nunca 2 meses seguidos sem compra dentro da janela (bordas incluídas)
        if any(not comprou[i] and not comprou[i + 1] for i in range(len(comprou) - 1)):
            continue

        # Fracionáveis exigem volume mínimo médio na janela
        if fracionavel and (sum(qtds) / n_janela) <= MEDIA_MINIMA_MENSAL_FRACIONAVEL:
            continue

        produtos_regulares.append(produto)

    return produtos_regulares


def _aplicar_backfill(
    df_completo: pd.DataFrame,
    produtos: list[str],
    meses_ordenados: list[str],
) -> pd.DataFrame:
    """Aplica backfill: o primeiro preço conhecido vale para os meses anteriores.

    Recebe o DataFrame já preenchido com forward fill e restringe a ``produtos``;
    meses anteriores à primeira compra recebem o primeiro preço conhecido, como
    se esse fosse o preço original. Usado apenas para cesta básica e inflação
    média, mantendo a composição constante em todo o período.

    Retorna DataFrame com colunas: ano_mes, produto_nome, custo_unitario_medio.
    """
    colunas = ["ano_mes", "produto_nome", "custo_unitario_medio"]

    if df_completo.empty or not produtos:
        return pd.DataFrame(columns=colunas)

    df_sel = df_completo[df_completo["produto_nome"].isin(produtos)]
    if df_sel.empty:
        return pd.DataFrame(columns=colunas)

    # pivot_table com aggfunc="mean" protege contra eventuais duplicatas
    pivot = df_sel.pivot_table(
        index="ano_mes",
        columns="produto_nome",
        values="custo_unitario_medio",
        aggfunc="mean",
    )
    pivot = pivot.reindex(meses_ordenados).sort_index().bfill()
    pivot.index.name = "ano_mes"

    return pivot.reset_index().melt(
        id_vars="ano_mes",
        var_name="produto_nome",
        value_name="custo_unitario_medio",
    )


def _quantidades_fixas_cesta(
    quantidades: list[dict[str, Any]],
    produtos: list[str],
) -> dict[str, float]:
    """Quantidade mensal de cada produto na cesta, na medida base (kg, l, un).

    É a média das quantidades compradas nos meses com compra no período (mês sem
    compra não conta como zero). ``quantidades`` é a saída de
    obter_quantidades_mensais_produtos.
    """
    df = pd.DataFrame(quantidades)
    if df.empty:
        return {}

    df = df[df["produto_nome"].isin(produtos)]
    por_mes = df.groupby(["produto_nome", "ano_mes"])["quantidade_total"].sum()
    return por_mes.groupby("produto_nome").mean().to_dict()


def _calcular_cesta_basica_personalizada(
    df_completo: pd.DataFrame,
    produtos: list[str],
    quantidades_fixas: dict[str, float],
) -> pd.DataFrame:
    """Custo mensal da cesta (Laspeyres): Σ quantidade fixa × preço do mês.

    As quantidades (_quantidades_fixas_cesta) ficam fixas em todo o período, de
    modo que a variação do custo vem só dos preços, ponderada pelo quanto se
    compra de cada produto. Espera as séries com backfill (_aplicar_backfill),
    que dão preço a todos os produtos em todos os meses; mês em que falta o
    preço de algum produto fica sem custo, em vez de somar a cesta incompleta.
    Retorna DataFrame com: ano_mes, custo_cesta.
    """
    produtos = [p for p in produtos if p in quantidades_fixas]
    df = df_completo[df_completo["produto_nome"].isin(produtos)]

    if df.empty:
        return pd.DataFrame(columns=["ano_mes", "custo_cesta"])

    precos = df.pivot_table(
        index="ano_mes",
        columns="produto_nome",
        values="custo_unitario_medio",
        aggfunc="mean",
    )
    quantidades = pd.Series(quantidades_fixas)[precos.columns]
    custo = (precos * quantidades).sum(axis=1, skipna=False)

    return custo.rename("custo_cesta").rename_axis("ano_mes").reset_index()


def _montar_series_inflacao(
    df_completo: pd.DataFrame,
    produtos: list[str],
    meses_ordenados: list[str],
) -> dict[str, list[float]]:
    """Calcula a inflação acumulada de cada produto alinhada a ``meses_ordenados``.

    Meses sem dado (antes da primeira compra) ficam como NaN, para que o gráfico
    inicie a linha do produto no primeiro mês com compra real (em 0%).
    """
    mapa_mes_idx = {mes: idx for idx, mes in enumerate(meses_ordenados)}
    series: dict[str, list[float]] = {}

    for produto in produtos:
        df_produto = df_completo[df_completo["produto_nome"] == produto].sort_values("ano_mes")
        if df_produto.empty:
            continue

        inflacao_calculada = _calcular_inflacao_acumulada(df_produto)
        meses_produto = df_produto["ano_mes"].tolist()

        inflacao_alinhada = [float('nan')] * len(meses_ordenados)
        for idx, mes in enumerate(meses_produto):
            if mes in mapa_mes_idx and inflacao_calculada[idx] is not None:
                inflacao_alinhada[mapa_mes_idx[mes]] = inflacao_calculada[idx]

        series[produto] = inflacao_alinhada

    return series


def _calcular_inflacao_media(
    series: dict[str, list[float]],
    produtos: list[str],
    n_meses: int,
) -> list[float]:
    """Média mês a mês da inflação acumulada dos ``produtos`` informados.

    Mês em que nenhum produto tem dado vira NaN — e não 0.0 —, para que ausência
    de dado não seja desenhada no gráfico como "inflação zero".
    """
    media: list[float] = []
    for i in range(n_meses):
        valores_mes = [
            series[p][i]
            for p in produtos
            if p in series and not pd.isna(series[p][i])
        ]
        media.append(sum(valores_mes) / len(valores_mes) if valores_mes else float('nan'))

    return media


def _montar_tabela_composicao_cesta(
    quantidades: list[dict[str, Any]],
    custos: list[dict[str, Any]],
    df_precos_cesta: pd.DataFrame,
    produtos_cesta: list[str],
    unidades: dict[str, str],
) -> pd.DataFrame:
    """Monta a tabela "Composição da Cesta Básica" para os ``produtos_cesta``.

    ``produtos_cesta`` deve ser a mesma base usada no gráfico (regulares ou, no
    fallback, todos os produtos com preço). O preço médio usa só os meses com
    compra (``custos``, saída de obter_custos_unitarios_mensais); o custo usa o
    preço do último mês das séries da cesta (``df_precos_cesta``), de modo que
    o total da tabela é o custo da cesta nesse mês, igual ao do gráfico e do
    CSV. Retorna DataFrame vazio se não houver quantidades.
    """
    colunas = [
        "Produto",
        "Unidade",
        "Quantidade Mensal",
        "Preço Médio",
        "Preço no Último Mês",
        "Custo no Último Mês",
    ]

    quantidades_fixas = _quantidades_fixas_cesta(quantidades, produtos_cesta)
    if not quantidades_fixas:
        return pd.DataFrame(columns=colunas)

    df_custos = pd.DataFrame(custos)
    preco_medio = df_custos.groupby("produto_nome")["custo_unitario_medio"].mean()

    ultimo_mes = df_precos_cesta["ano_mes"].max()
    preco_ultimo_mes = df_precos_cesta[df_precos_cesta["ano_mes"] == ultimo_mes].set_index(
        "produto_nome"
    )["custo_unitario_medio"]

    tabela_cesta = pd.DataFrame({"Produto": list(quantidades_fixas)})
    tabela_cesta["Unidade"] = tabela_cesta["Produto"].map(unidades)
    tabela_cesta["Quantidade Mensal"] = tabela_cesta["Produto"].map(quantidades_fixas)
    tabela_cesta["Preço Médio"] = tabela_cesta["Produto"].map(preco_medio)
    tabela_cesta["Preço no Último Mês"] = tabela_cesta["Produto"].map(preco_ultimo_mes)
    tabela_cesta["Custo no Último Mês"] = (
        tabela_cesta["Quantidade Mensal"] * tabela_cesta["Preço no Último Mês"]
    )

    return tabela_cesta[colunas]


def render_grafico_custos_unitarios() -> None:
    """Renderiza gráfico de custos unitários mensais dos produtos."""
    st.subheader("📊 Custos Unitários Mensais - Top 10 Produtos")
    st.write(
        "Visualize a evolução dos preços dos 10 produtos com maior gasto ao longo do "
        "tempo, por quilo, litro ou unidade."
    )

    # Filtros de período
    col1, col2 = st.columns(2)

    # Período padrão: 12 meses até o último mês com nota
    data_inicio_padrao, data_fim_padrao = _periodo_padrao(
        obter_meses_com_notas(), datetime.now().date()
    )

    with col1:
        data_inicio = st.date_input(
            "Data início",
            value=data_inicio_padrao,
            key="custo_data_inicio",
        )

    with col2:
        data_fim = st.date_input(
            "Data fim",
            value=data_fim_padrao,
            key="custo_data_fim",
        )

    if data_inicio > data_fim:
        st.error("Data de início deve ser anterior à data de fim.")
        return

    # Buscar top 10 produtos
    with st.spinner("Carregando produtos com maior gasto..."):
        top_produtos = obter_top_produtos_por_gasto(
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
            top_n=10,
        )

    if not top_produtos:
        st.info("Nenhum produto encontrado no período selecionado.")
        return

    produtos_nomes = [p["produto_nome"] for p in top_produtos]

    # Buscar custos unitários mensais
    with st.spinner("Carregando custos unitários..."):
        custos = obter_custos_unitarios_mensais(
            produtos_nomes,
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
        )

    if not custos:
        st.info("Nenhum dado de custo encontrado para os produtos selecionados.")
        return

    # Converter para DataFrame
    df = pd.DataFrame(custos)

    # Medida base de cada produto (KG, L, UN...) e compras que ficaram de fora
    unidades = obter_unidades_produtos(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )
    _avisar_compras_fora_da_unidade(obter_compras_fora_da_unidade(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    ))

    # Adicionar seletor de produtos visíveis
    st.write("**Produtos disponíveis** (marque para exibir no gráfico):")

    produtos_visiveis = []
    cols = st.columns(2)
    for idx, produto in enumerate(produtos_nomes):
        rotulo = _rotulo_produto(produto, unidades.get(produto))

        col_idx = idx % 2
        with cols[col_idx]:
            if st.checkbox(rotulo, value=True, key=f"custo_check_{produto}"):
                produtos_visiveis.append(produto)

    if not produtos_visiveis:
        st.warning("Selecione pelo menos um produto para visualizar.")
        return

    # Filtrar apenas produtos visíveis
    df_filtrado = df[df["produto_nome"].isin(produtos_visiveis)]

    # Criar gráfico de linhas usando chart nativo do Streamlit
    # Transformar dados para formato wide (cada produto = coluna)
    df_pivot = df_filtrado.pivot(
        index="ano_mes",
        columns="produto_nome",
        values="custo_unitario_medio"
    )

    # Renomear colunas com unidades
    df_pivot.columns = [_rotulo_produto(col, unidades.get(col)) for col in df_pivot.columns]

    st.line_chart(df_pivot)

    # Mostrar tabela de dados
    with st.expander("📋 Ver dados em tabela"):
        df_exibicao = df_filtrado.pivot(
            index="ano_mes",
            columns="produto_nome",
            values="custo_unitario_medio"
        )
        st.dataframe(
            df_exibicao.style.format("{:.2f}"),
            width='stretch',
        )


def render_grafico_inflacao() -> None:
    """Renderiza gráfico de inflação acumulada dos produtos."""
    st.subheader("📈 Inflação Acumulada - Variação de Preços")
    st.write(
        "Acompanhe a variação percentual acumulada dos preços unitários ao longo do tempo. "
        "Inclui cálculo de inflação média e cesta básica personalizada."
    )

    # Filtros de período
    col1, col2 = st.columns(2)

    # Período padrão: 12 meses até o último mês com nota
    data_inicio_padrao, data_fim_padrao = _periodo_padrao(
        obter_meses_com_notas(), datetime.now().date()
    )

    with col1:
        data_inicio = st.date_input(
            "Data início",
            value=data_inicio_padrao,
            key="inflacao_data_inicio",
        )

    with col2:
        data_fim = st.date_input(
            "Data fim",
            value=data_fim_padrao,
            key="inflacao_data_fim",
        )

    if data_inicio > data_fim:
        st.error("Data de início deve ser anterior à data de fim.")
        return

    # Buscar top 10 produtos
    with st.spinner("Carregando produtos com maior gasto..."):
        top_produtos = obter_top_produtos_por_gasto(
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
            top_n=10,
        )

    if not top_produtos:
        st.info("Nenhum produto encontrado no período selecionado.")
        return

    produtos_nomes = [p["produto_nome"] for p in top_produtos]

    # Buscar custos unitários mensais
    with st.spinner("Carregando custos unitários..."):
        custos = obter_custos_unitarios_mensais(
            produtos_nomes,
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
        )

    if not custos:
        st.info("Nenhum dado de custo encontrado para os produtos selecionados.")
        return

    # Quantidades mensais: usadas na regra de regularidade e na composição da cesta
    quantidades = obter_quantidades_mensais_produtos(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )

    # Medida base de cada produto (regra de regularidade e rótulos do gráfico)
    unidades = obter_unidades_produtos(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )
    _avisar_compras_fora_da_unidade(obter_compras_fora_da_unidade(
        produtos_nomes,
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    ))

    # Meses com nota importada: mês sem nenhuma nota é lacuna de coleta, não de
    # compra, e por isso não conta contra a regularidade dos produtos
    meses_com_notas = obter_meses_com_notas(
        data_inicio=data_inicio.isoformat(),
        data_fim=data_fim.isoformat(),
    )

    # Preencher meses faltantes com último preço conhecido
    df_completo = _preencher_meses_faltantes(
        custos,
        produtos_nomes,
        data_inicio.isoformat(),
        data_fim.isoformat(),
    )

    if df_completo.empty:
        st.info("Não há dados suficientes para calcular inflação.")
        return

    meses_ordenados = _gerar_meses_periodo(data_inicio.isoformat(), data_fim.isoformat())

    # Identificar produtos regulares (compras reais na janela de meses ativos)
    produtos_regulares = _identificar_produtos_regulares(
        quantidades,
        produtos_nomes,
        unidades,
        meses_ordenados,
        meses_com_notas=meses_com_notas,
    )

    # Cesta e média exigem preço conhecido em pelo menos um mês do período
    produtos_com_preco = set(
        df_completo.loc[df_completo["custo_unitario_medio"].notna(), "produto_nome"]
    )
    produtos_regulares = [p for p in produtos_regulares if p in produtos_com_preco]

    # Base dos agregados: os regulares ou, na falta deles, todos os produtos com
    # preço — assim média e cesta nunca viram uma linha reta em 0% sem explicação
    usando_fallback = not produtos_regulares
    if usando_fallback:
        produtos_para_agregados = [p for p in produtos_nomes if p in produtos_com_preco]
        if produtos_para_agregados:
            st.warning(
                "Nenhum produto atingiu o critério de regularidade neste período "
                "(nunca ficar 2 meses seguidos sem compra, considerando apenas os "
                "meses com notas importadas). A Inflação Média e a Cesta Básica "
                "abaixo estão usando **todos os produtos** do top, e não apenas os "
                "regulares — interprete com cautela."
            )
    else:
        produtos_para_agregados = produtos_regulares

    # Inflação acumulada por produto (sem backfill: linha começa na 1ª compra real)
    inflacao_por_produto = _montar_series_inflacao(df_completo, produtos_nomes, meses_ordenados)

    # Séries com backfill: o primeiro preço conhecido vale para os meses anteriores,
    # mantendo a composição da cesta e da média constante em todo o período
    df_backfilled = _aplicar_backfill(df_completo, produtos_para_agregados, meses_ordenados)

    # Calcular inflação média (séries com backfill dos produtos agregados)
    if produtos_para_agregados and not df_backfilled.empty:
        series_agregados = _montar_series_inflacao(
            df_backfilled, produtos_para_agregados, meses_ordenados
        )
        inflacao_media = _calcular_inflacao_media(
            series_agregados, produtos_para_agregados, len(meses_ordenados)
        )
    else:
        inflacao_media = [float('nan')] * len(meses_ordenados)

    # Calcular cesta básica personalizada (séries com backfill, quantidades fixas)
    quantidades_cesta = _quantidades_fixas_cesta(quantidades, produtos_para_agregados)
    df_cesta = _calcular_cesta_basica_personalizada(
        df_backfilled, produtos_para_agregados, quantidades_cesta
    )
    if not df_cesta.empty:
        inflacao_cesta_lista = _calcular_inflacao_acumulada(df_cesta, coluna_valor="custo_cesta")
        # Alinhar com meses_ordenados usando mapeamento correto
        mapa_mes_idx = {mes: idx for idx, mes in enumerate(meses_ordenados)}
        inflacao_cesta = [float('nan')] * len(meses_ordenados)
        meses_cesta = df_cesta["ano_mes"].tolist()
        for idx, mes in enumerate(meses_cesta):
            if mes in mapa_mes_idx and inflacao_cesta_lista[idx] is not None:
                inflacao_cesta[mapa_mes_idx[mes]] = inflacao_cesta_lista[idx]
    else:
        inflacao_cesta = [float('nan')] * len(meses_ordenados)

    # Seletor de produtos visíveis
    st.write("**Produtos disponíveis** (marque para exibir no gráfico):")

    produtos_visiveis = []
    cols = st.columns(2)
    for idx, produto in enumerate(produtos_nomes):
        rotulo = _rotulo_produto(produto, unidades.get(produto))
        eh_regular = " ⭐" if produto in produtos_regulares else ""

        col_idx = idx % 2
        with cols[col_idx]:
            if st.checkbox(
                rotulo + eh_regular,
                value=True,
                key=f"inflacao_check_{produto}",
                help=(
                    "⭐ = produto regular (comprado com frequência nos últimos 6 meses "
                    "com notas importadas)"
                )
            ):
                produtos_visiveis.append(produto)

    # Rótulo da média acompanha a base realmente usada no cálculo
    rotulo_media = (
        "📊 Inflação Média (todos os produtos)"
        if usando_fallback
        else "📊 Inflação Média (produtos regulares)"
    )

    # Sempre mostrar inflação média e cesta básica
    mostrar_media = st.checkbox(
        rotulo_media,
        value=True,
        key="inflacao_check_media",
    )

    mostrar_cesta = st.checkbox(
        "🛒 Cesta Básica Personalizada",
        value=True,
        key="inflacao_check_cesta",
    )

    # Criar DataFrame para gráfico
    df_inflacao = pd.DataFrame({"ano_mes": meses_ordenados})

    # Adicionar produtos selecionados
    for produto in produtos_visiveis:
        if produto in inflacao_por_produto:
            df_inflacao[_rotulo_produto(produto, unidades.get(produto))] = inflacao_por_produto[produto]

    # Adicionar inflação média
    if mostrar_media:
        df_inflacao["📊 Inflação Média"] = inflacao_media

    # Adicionar cesta básica
    if mostrar_cesta and not df_cesta.empty:
        df_inflacao["🛒 Cesta Básica"] = inflacao_cesta

    # Definir ano_mes como índice
    df_inflacao = df_inflacao.set_index("ano_mes")

    if df_inflacao.empty or len(df_inflacao.columns) == 0:
        st.warning("Selecione pelo menos um item para visualizar.")
        return

    # Plotar gráfico
    st.line_chart(df_inflacao)

    # Botão de exportação para Excel
    st.write("---")
    st.write("**Exportar dados**")

    # Preparar DataFrame para exportação com valores unitários E percentuais
    # Abordagem declarativa usando pivot e merge do pandas

    # 1. Pivotar os preços: transformar produtos em colunas
    # Usa pivot_table para lidar com possíveis duplicatas (média automática)
    df_precos = df_completo.pivot_table(
        index="ano_mes",
        columns="produto_nome",
        values="custo_unitario_medio",
        aggfunc="mean"
    ).reindex(meses_ordenados)

    # Renomear colunas para incluir unidade e tipo de dado
    df_precos.columns = [
        f"{col} - Preço (R$/{unidades.get(col, 'UN').lower()})"
        for col in df_precos.columns
    ]

    # 2. Criar DataFrame de inflação por produto
    # inflacao_por_produto já está alinhado com meses_ordenados (_montar_series_inflacao)
    # mas usamos reindex para garantir robustez contra mudanças futuras
    df_inflacao_produtos = pd.DataFrame(
        inflacao_por_produto,
        index=meses_ordenados
    ).reindex(meses_ordenados)

    # Renomear colunas para incluir tipo de dado
    df_inflacao_produtos.columns = [
        f"{col} - Inflação (%)"
        for col in df_inflacao_produtos.columns
    ]

    # 3. Criar DataFrame com inflação média e dados da cesta
    df_extras = pd.DataFrame(index=meses_ordenados)
    df_extras["Inflação Média (%)"] = inflacao_media

    if not df_cesta.empty:
        # Custo da cesta alinhado com meses_ordenados
        df_extras["Cesta Básica - Custo (R$)"] = (
            df_cesta.set_index("ano_mes")["custo_cesta"]
            .reindex(meses_ordenados)
        )

        # Inflação da cesta já está alinhada com meses_ordenados
        df_extras["Cesta Básica - Inflação (%)"] = inflacao_cesta

    # 4. Intercalar colunas de preço e inflação para cada produto
    colunas_ordenadas = ["Mês"]
    for produto in produtos_nomes:
        col_preco = f"{produto} - Preço (R$/{unidades.get(produto, 'UN').lower()})"
        col_inflacao = f"{produto} - Inflação (%)"
        if col_preco in df_precos.columns:
            colunas_ordenadas.append(col_preco)
        if col_inflacao in df_inflacao_produtos.columns:
            colunas_ordenadas.append(col_inflacao)

    # Adicionar colunas extras
    colunas_ordenadas.extend(df_extras.columns.tolist())

    # 5. Juntar todos os DataFrames
    df_export = pd.concat(
        [df_precos, df_inflacao_produtos, df_extras],
        axis=1
    )

    # Garantir que o índice tem um nome conhecido antes de resetar
    df_export.index.name = "ano_mes"

    # Resetar índice para transformar ano_mes em coluna "Mês"
    df_export = df_export.reset_index().rename(columns={"ano_mes": "Mês"})

    # Reordenar colunas para intercalar preço e inflação
    # A filtragem garante que apenas colunas existentes sejam incluídas
    # (proteção contra casos onde produtos não têm dados completos)
    df_export = df_export[
        [col for col in colunas_ordenadas if col in df_export.columns]
    ]

    # Converter para CSV para download
    csv = df_export.to_csv(index=False, encoding="utf-8-sig", sep=";", decimal=",")

    st.download_button(
        label="📥 Baixar Excel (CSV)",
        data=csv,
        file_name=f"inflacao_produtos_{data_inicio}_{data_fim}.csv",
        mime="text/csv",
        help="Arquivo CSV compatível com Excel (separador: ponto-e-vírgula, decimal: vírgula)",
    )

    # Mostrar tabela de dados
    with st.expander("📋 Ver dados completos em tabela"):
        st.dataframe(
            df_export.style.format(
                {col: "{:.2f}" for col in df_export.columns if col != "Mês"},
                na_rep="",
            ),
            width='stretch',
        )

    # Mostrar composição da Cesta Básica Personalizada
    if mostrar_cesta and produtos_para_agregados:
        st.write("---")
        st.subheader("🛒 Composição da Cesta Básica Personalizada")
        st.write(
            "Esta tabela mostra os produtos que compõem sua cesta básica personalizada "
            + (
                "(todos os produtos do top, pois nenhum atingiu o critério de regularidade) "
                if usando_fallback
                else "(produtos comprados com frequência nos últimos 6 meses com notas) "
            )
            + "e a quantidade mensal de cada um."
        )

        tabela_cesta = _montar_tabela_composicao_cesta(
            quantidades, custos, df_backfilled, produtos_para_agregados, unidades
        )

        if not tabela_cesta.empty:
            # Total = custo da cesta no último mês (o mesmo do gráfico e do CSV)
            total_custo = tabela_cesta["Custo no Último Mês"].sum()
            inflacao_periodo = inflacao_cesta[-1]

            # Exibir tabela
            st.dataframe(
                tabela_cesta.style.format({
                    "Quantidade Mensal": "{:.2f}",
                    "Preço Médio": "R$ {:.2f}",
                    "Preço no Último Mês": "R$ {:.2f}",
                    "Custo no Último Mês": "R$ {:.2f}",
                }),
                width='stretch',
                hide_index=True,
            )

            st.metric(
                f"💰 Custo da Cesta em {meses_ordenados[-1]}",
                f"R$ {total_custo:.2f}",
                delta=(
                    None
                    if pd.isna(inflacao_periodo)
                    else f"{inflacao_periodo:+.1f}% desde {meses_ordenados[0]}"
                ),
                delta_color="inverse",
                help=(
                    "Soma de quantidade mensal × preço no último mês de todos os "
                    "produtos da cesta"
                ),
            )

            # Explicação adicional
            with st.expander("ℹ️ Como é calculada a cesta básica?"):
                st.markdown("""
                **Produtos incluídos:** Apenas produtos regulares (⭐): nos últimos 6 meses
                **com notas importadas** dentro do período (ou em todos eles, se forem
                menos), o produto nunca fica 2 meses seguidos sem compra. Meses sem
                nenhuma nota importada são ignorados na janela — eles indicam lacuna de
                coleta, não ausência de compra. Produtos vendidos por unidade contam o mês
                quando há pelo menos 1 unidade comprada; produtos fracionados (kg, l etc.)
                contam qualquer quantidade, mas exigem média mensal acima de 0,1 na janela.

                Se nenhum produto atingir o critério no período, a cesta e a inflação média
                passam a usar **todos os produtos** do top, com um aviso acima do gráfico.

                **Quantidade Mensal:** Média da quantidade comprada por mês, considerando
                só os meses com compra no período selecionado (não confundir com a média da
                janela de 6 meses, usada apenas no critério de regularidade). Ela fica fixa
                em todos os meses da cesta.

                **Preço Médio:** Média dos preços do produto nos meses em que houve compra,
                por quilo, litro ou unidade. Produtos vendidos por unidade com o tamanho na
                descrição ("ARROZ 5KG", "CERVEJA 473ML") entram pelo peso ou volume; compras
                em outra medida (ex.: descrição sem o tamanho) ficam de fora.

                **Preço no Último Mês:** Preço usado na cesta no último mês do período; sem
                compra nesse mês, vale o último preço pago.

                **Custo no Último Mês:** Quantidade mensal × Preço no último mês. A soma é o
                custo da cesta nesse mês, o mesmo do gráfico e do CSV.

                **Custo e Inflação da Cesta:** Em cada mês, o custo da cesta é a soma de
                quantidade mensal × preço do mês de todos os produtos. Como as quantidades
                ficam fixas, o custo só muda com os preços, e cada produto pesa pelo quanto
                você gasta com ele: um item caro e comprado raramente pesa pouco. Em mês
                sem compra, vale o último preço pago; para meses anteriores à primeira
                compra de um produto, o primeiro preço conhecido é usado como preço
                original (contribuindo 0% de inflação).

                **Inflação Média:** Média simples da inflação de cada produto, sem
                ponderação por quantidade.
                """)
        else:
            st.info("Não há dados de quantidade disponíveis para os produtos da cesta.")


def render_pagina_relatorios() -> None:
    """Renderiza página principal de relatórios."""
    st.title("📊 Relatórios e Análises")
    st.write(
        "Visualize a evolução dos preços dos produtos ao longo do tempo e "
        "acompanhe a inflação da sua cesta de compras."
    )

    # Abas para diferentes gráficos
    tab1, tab2 = st.tabs([
        "📊 Custos Unitários Mensais",
        "📈 Inflação Acumulada",
    ])

    with tab1:
        render_grafico_custos_unitarios()

    with tab2:
        render_grafico_inflacao()
