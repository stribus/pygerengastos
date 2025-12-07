import streamlit as st
import pandas as pd
from src.database import (
    obter_kpis_gerais,
    obter_resumo_mensal,
    obter_gastos_por_categoria,
)

def render_home() -> None:
    """Renderiza a página inicial com dashboards e KPIs."""
    st.title("Visão Geral")
    
    # 1. KPIs Gerais
    kpis = obter_kpis_gerais()
    col1, col2, col3 = st.columns(3)
    
    col1.metric("Total de Notas", kpis["total_notas"])
    col2.metric("Gasto Total (Histórico)", f"R$ {kpis['total_gasto']:,.2f}")
    col3.metric("Itens Pendentes", kpis["itens_pendentes"])
    
    st.markdown("---")
    
    # 2. Gráficos
    col_charts_1, col_charts_2 = st.columns(2)
    
    with col_charts_1:
        st.subheader("Evolução Mensal")
        dados_mensais = obter_resumo_mensal()
        if dados_mensais:
            df_mensal = pd.DataFrame(dados_mensais)
            df_mensal["mes"] = pd.to_datetime(df_mensal["mes"])
            df_mensal = df_mensal.sort_values("mes")
            st.bar_chart(df_mensal, x="mes", y="total")
        else:
            st.info("Sem dados suficientes para gráfico mensal.")
            
    with col_charts_2:
        st.subheader("Gastos por Categoria (Geral)")
        dados_categoria = obter_gastos_por_categoria()
        if dados_categoria:
            df_cat = pd.DataFrame(dados_categoria)
            st.dataframe(
                df_cat.style.format({"total": "R$ {:,.2f}"}),
                width="stretch",
                hide_index=True
            )
        else:
            st.info("Sem dados classificados para exibir.")
