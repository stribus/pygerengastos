# ADR-007: Streamlit como Plataforma de Interface

**Data:** 2024
**Status:** Aceito
**Confiança:** 🟡 INFERIDO

## Contexto

O sistema precisava de uma interface gráfica para importar notas, classificar itens, normalizar produtos e visualizar relatórios. Sendo uma ferramenta pessoal de uso local, uma aplicação web full-stack seria excessiva.

## Decisão

Usar Streamlit como framework de UI. Com Python puro, permite criar dashboards interativos com gráficos nativos, tabelas e formulários sem html/css/js.

## Consequências

- Desenvolvimento rápido (5 páginas em ~1.594 LOC)
- Gráficos nativos (`st.line_chart`, `st.bar_chart`) sem bibliotecas JS
- Single-user (servido via `streamlit run`)
- Execução local, sem deploy
- Limitações de personalização visual comparado a frameworks web
- Estado de UI via `st.session_state`
