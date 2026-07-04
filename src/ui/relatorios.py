"""Módulo de relatórios com gráficos interativos para análise de preços."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import streamlit as st

from src.database import (
    obter_custos_unitarios_mensais,
    obter_quantidades_mensais_produtos,
    obter_top_produtos_por_quantidade,
    obter_unidades_produtos,
)


def _calcular_variacao_percentual(valor_anterior: float, valor_atual: float) -> float:
    """Calcula variação percentual entre dois valores."""
    if valor_anterior == 0 or valor_anterior is None:
        return 0.0
    return ((valor_atual - valor_anterior) / valor_anterior) * 100


def _preencher_meses_faltantes(
    dados: list[dict[str, Any]],
    produtos: list[str],
    data_inicio_str: str,
    data_fim_str: str,
) -> pd.DataFrame:
    """Preenche meses faltantes com o último preço conhecido para cada produto.

    Retorna DataFrame com colunas: ano_mes, produto_nome, custo_unitario_medio
    Garante que todos os produtos apareçam em todos os meses do período.
    """
    # Converter dados para DataFrame
    df = pd.DataFrame(dados)

    if df.empty:
        # Retorna DataFrame vazio com estrutura esperada
        return pd.DataFrame(columns=["ano_mes", "produto_nome", "custo_unitario_medio"])

    # Gerar lista completa de meses no período usando pd.period_range
    data_inicio = datetime.strptime(data_inicio_str, "%Y-%m-%d")
    data_fim = datetime.strptime(data_fim_str, "%Y-%m-%d")

    # Inclui o mês que contém data_fim no range de meses
    meses = pd.period_range(
        start=data_inicio,
        end=data_fim,
        freq="M",
    ).strftime("%Y-%m").tolist()

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

    Retorna lista de valores de inflação acumulada em percentual.
    Valores None são preservados para meses sem dados.
    """
    if df.empty:
        return []

    valores = df[coluna_valor].tolist()
    inflacao_acumulada = [None] * len(valores)

    # Encontrar o primeiro valor não-None
    idx_inicio = None
    for i, val in enumerate(valores):
        if val is not None:
            idx_inicio = i
            break

    if idx_inicio is None:
        return inflacao_acumulada

    # Começar inflação a partir do primeiro valor não-None
    inflacao_acumulada[idx_inicio] = 0.0

    for i in range(idx_inicio + 1, len(valores)):
        if valores[i] is not None and valores[i-1] is not None:
            var_percentual = _calcular_variacao_percentual(valores[i-1], valores[i])
            # Acumular: (1 + inflacao_anterior/100) * (1 + var_atual/100) - 1
            inflacao_anterior = inflacao_acumulada[i-1]
            if inflacao_anterior is not None:
                inflacao_nova = ((1 + inflacao_anterior/100) * (1 + var_percentual/100) - 1) * 100
                inflacao_acumulada[i] = inflacao_nova

    return inflacao_acumulada


def _identificar_produtos_regulares(
    df: pd.DataFrame,
    meses_consecutivos_min: int = 2,
) -> list[str]:
    """Identifica produtos comprados regularmente (pelo menos N meses consecutivos).

    Retorna lista de nomes de produtos regulares.
    """
    produtos_regulares = []

    for produto in df["produto_nome"].unique():
        df_produto = df[df["produto_nome"] == produto].sort_values("ano_mes")
        meses = df_produto["ano_mes"].tolist()

        if len(meses) < meses_consecutivos_min:
            continue

        # Verificar se há pelo menos N meses consecutivos
        consecutivos_max = 1
        consecutivos_atual = 1

        for i in range(1, len(meses)):
            mes_anterior = datetime.strptime(meses[i-1], "%Y-%m")
            mes_atual = datetime.strptime(meses[i], "%Y-%m")

            # Verificar se é mês seguinte
            if mes_anterior.month == 12:
                mes_esperado = mes_anterior.replace(year=mes_anterior.year + 1, month=1)
            else:
                mes_esperado = mes_anterior.replace(month=mes_anterior.month + 1)

            if mes_atual == mes_esperado:
                consecutivos_atual += 1
                consecutivos_max = max(consecutivos_max, consecutivos_atual)
            else:
                consecutivos_atual = 1

        if consecutivos_max >= meses_consecutivos_min:
            produtos_regulares.append(produto)

    return produtos_regulares


def _calcular_cesta_basica_personalizada(
    df_completo: pd.DataFrame,
    produtos_regulares: list[str],
) -> pd.DataFrame:
    """Calcula custo médio mensal da cesta a partir da média simples dos custos unitários.

    Atualmente não há ponderação por quantidade: assume-se quantidade = 1 para todos
    os produtos regulares em cada mês. Retorna DataFrame com: ano_mes, custo_cesta
    (valor médio simples dos custos unitários).
    """
    # Filtrar apenas produtos regulares
    df_regulares = df_completo[df_completo["produto_nome"].isin(produtos_regulares)]

    if df_regulares.empty:
        return pd.DataFrame(columns=["ano_mes", "custo_cesta"])

    # Para cada produto, calcular quantidade média mensal
    # (simplificação: assumir quantidade = 1 para todos, pois não temos no df)
    # Em implementação real, deveria buscar quantidade média do banco

    # Calcular custo médio mensal da cesta
    resultado = df_regulares.groupby("ano_mes").agg({
        "custo_unitario_medio": "mean"
    }).reset_index()

    resultado.columns = ["ano_mes", "custo_cesta"]

    return resultado


def render_grafico_custos_unitarios() -> None:
    """Renderiza gráfico de custos unitários mensais dos produtos."""
    st.subheader("📊 Custos Unitários Mensais - Top 10 Produtos")
    st.write(
        "Visualize a evolução dos preços unitários dos produtos mais comprados "
        "ao longo do tempo."
    )

    # Filtros de período
    col1, col2 = st.columns(2)

    # Período padrão: últimos 12 meses
    data_fim_padrao = datetime.now().date()
    data_inicio_padrao = data_fim_padrao - timedelta(days=365)

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
    with st.spinner("Carregando produtos mais comprados..."):
        top_produtos = obter_top_produtos_por_quantidade(
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

    # Buscar unidades dos produtos
    unidades = obter_unidades_produtos(produtos_nomes)

    # Adicionar seletor de produtos visíveis
    st.write("**Produtos disponíveis** (marque para exibir no gráfico):")

    produtos_visiveis = []
    cols = st.columns(2)
    for idx, produto in enumerate(produtos_nomes):
        unidade = unidades.get(produto, "UN")
        rotulo = f"{produto} ({unidade})"

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
    df_pivot.columns = [f"{col} ({unidades.get(col, 'UN')})" for col in df_pivot.columns]

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

    # Período padrão: últimos 12 meses completos (até final do mês anterior)
    hoje = datetime.now().date()
    # Último dia do mês anterior
    data_fim_padrao = hoje.replace(day=1) - timedelta(days=1)
    # 12 meses antes, início do mês
    data_inicio_padrao = (data_fim_padrao.replace(day=1) - timedelta(days=365)).replace(day=1)

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
    with st.spinner("Carregando produtos mais comprados..."):
        top_produtos = obter_top_produtos_por_quantidade(
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

    # Identificar produtos regulares (comprados pelo menos 2 meses consecutivos)
    produtos_regulares = _identificar_produtos_regulares(df_completo)

    # Calcular inflação acumulada para cada produto
    inflacao_por_produto = {}
    meses_ordenados = sorted(df_completo["ano_mes"].unique())

    # Criar mapa de índices para alinhamento correto
    mapa_mes_idx = {mes: idx for idx, mes in enumerate(meses_ordenados)}

    for produto in produtos_nomes:
        df_produto = df_completo[df_completo["produto_nome"] == produto].sort_values("ano_mes")
        if not df_produto.empty:
            inflacao_calculada = _calcular_inflacao_acumulada(df_produto)
            meses_produto = df_produto["ano_mes"].tolist()

            # Criar lista alinhada com meses_ordenados
            inflacao_alinhada = [float('nan')] * len(meses_ordenados)

            # Mapear cada valor de inflação para seu mês correto
            for idx, mes in enumerate(meses_produto):
                if mes in mapa_mes_idx and inflacao_calculada[idx] is not None:
                    inflacao_alinhada[mapa_mes_idx[mes]] = inflacao_calculada[idx]

            inflacao_por_produto[produto] = inflacao_alinhada

    # Calcular inflação média (apenas produtos regulares)
    if produtos_regulares:
        inflacao_media = []
        for i in range(len(meses_ordenados)):
            valores_mes = [
                inflacao_por_produto[p][i]
                for p in produtos_regulares
                if p in inflacao_por_produto and not pd.isna(inflacao_por_produto[p][i])
            ]
            if valores_mes:
                inflacao_media.append(sum(valores_mes) / len(valores_mes))
            else:
                inflacao_media.append(0.0)
    else:
        inflacao_media = [0.0] * len(meses_ordenados)

    # Calcular cesta básica personalizada
    df_cesta = _calcular_cesta_basica_personalizada(df_completo, produtos_regulares)
    if not df_cesta.empty:
        inflacao_cesta_lista = _calcular_inflacao_acumulada(df_cesta, coluna_valor="custo_cesta")
        # Alinhar com meses_ordenados usando mapeamento correto
        inflacao_cesta = [float('nan')] * len(meses_ordenados)
        meses_cesta = df_cesta["ano_mes"].tolist()
        for idx, mes in enumerate(meses_cesta):
            if mes in mapa_mes_idx and inflacao_cesta_lista[idx] is not None:
                inflacao_cesta[mapa_mes_idx[mes]] = inflacao_cesta_lista[idx]
    else:
        inflacao_cesta = [float('nan')] * len(meses_ordenados)

    # Buscar unidades dos produtos
    unidades = obter_unidades_produtos(produtos_nomes)

    # Seletor de produtos visíveis
    st.write("**Produtos disponíveis** (marque para exibir no gráfico):")

    produtos_visiveis = []
    cols = st.columns(2)
    for idx, produto in enumerate(produtos_nomes):
        unidade = unidades.get(produto, "UN")
        rotulo = f"{produto} ({unidade})"
        eh_regular = " ⭐" if produto in produtos_regulares else ""

        col_idx = idx % 2
        with cols[col_idx]:
            if st.checkbox(
                rotulo + eh_regular,
                value=True,
                key=f"inflacao_check_{produto}",
                help="⭐ = produto regular (comprado em meses consecutivos)"
            ):
                produtos_visiveis.append(produto)

    # Sempre mostrar inflação média e cesta básica
    mostrar_media = st.checkbox(
        "📊 Inflação Média (produtos regulares)",
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
            unidade = unidades.get(produto, "UN")
            df_inflacao[f"{produto} ({unidade})"] = inflacao_por_produto[produto]

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
        f"{col} - Preço ({unidades.get(col, 'UN')})"
        for col in df_precos.columns
    ]

    # 2. Criar DataFrame de inflação por produto
    # inflacao_por_produto já está alinhado com meses_ordenados (linha 394-395)
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
        unidade = unidades.get(produto, "UN")
        col_preco = f"{produto} - Preço ({unidade})"
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
            df_export.style.format({
                col: "{:.2f}" for col in df_export.columns if col != "Mês"
            }),
            width='stretch',
        )

    # Mostrar composição da Cesta Básica Personalizada
    if mostrar_cesta and produtos_regulares:
        st.write("---")
        st.subheader("🛒 Composição da Cesta Básica Personalizada")
        st.write(
            "Esta tabela mostra os produtos que compõem sua cesta básica personalizada "
            "(produtos regulares comprados em meses consecutivos) e as quantidades médias mensais."
        )

        # Buscar quantidades mensais dos produtos regulares
        quantidades = obter_quantidades_mensais_produtos(
            produtos_regulares,
            data_inicio=data_inicio.isoformat(),
            data_fim=data_fim.isoformat(),
        )

        if quantidades:
            # Calcular média mensal por produto
            df_qtd = pd.DataFrame(quantidades)
            media_mensal = df_qtd.groupby("produto_nome").agg({
                "quantidade_total": "mean"
            }).reset_index()
            media_mensal.columns = ["Produto", "Quantidade Média Mensal"]

            # Adicionar unidades
            media_mensal["Unidade"] = media_mensal["Produto"].map(unidades)

            # Adicionar preço médio no período
            df_precos = df_completo[df_completo["produto_nome"].isin(produtos_regulares)]
            preco_medio = df_precos.groupby("produto_nome").agg({
                "custo_unitario_medio": "mean"
            }).reset_index()
            preco_medio.columns = ["Produto", "Preço Médio"]

            # Juntar informações
            tabela_cesta = media_mensal.merge(preco_medio, on="Produto")

            # Calcular custo médio mensal
            tabela_cesta["Custo Mensal Médio"] = (
                tabela_cesta["Quantidade Média Mensal"] * tabela_cesta["Preço Médio"]
            )

            # Reordenar colunas
            tabela_cesta = tabela_cesta[[
                "Produto",
                "Unidade",
                "Quantidade Média Mensal",
                "Preço Médio",
                "Custo Mensal Médio"
            ]]

            # Adicionar linha de total
            total_custo = tabela_cesta["Custo Mensal Médio"].sum()

            # Exibir tabela
            st.dataframe(
                tabela_cesta.style.format({
                    "Quantidade Média Mensal": "{:.2f}",
                    "Preço Médio": "R$ {:.2f}",
                    "Custo Mensal Médio": "R$ {:.2f}",
                }),
                width='stretch',
                hide_index=True,
            )

            st.metric(
                "💰 Custo Total Médio Mensal da Cesta",
                f"R$ {total_custo:.2f}",
                help="Soma dos custos mensais médios de todos os produtos da cesta"
            )

            # Explicação adicional
            with st.expander("ℹ️ Como é calculada a cesta básica?"):
                st.markdown("""
                **Produtos incluídos:** Apenas produtos regulares (⭐), ou seja, aqueles
                comprados em pelo menos 2 meses consecutivos no período selecionado.

                **Quantidade Média Mensal:** Média de quantidade comprada por mês para cada produto.

                **Preço Médio:** Preço unitário médio do produto no período.

                **Custo Mensal Médio:** Quantidade média × Preço médio.

                **Inflação da Cesta:** Calculada sobre a média dos custos unitários de todos
                os produtos regulares mês a mês, mostrando como o custo total da sua cesta
                evolui ao longo do tempo.
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
