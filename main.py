from __future__ import annotations

import streamlit as st

from src.ui import render_pagina_analise, render_pagina_importacao


def _render_home() -> None:
	"""Página inicial com indicadores básicos."""
	st.header("Visão geral")
	st.caption("Resumo rápido dos gastos e status das importações")
	col1, col2, col3 = st.columns(3)
	col1.metric("Notas importadas", "—")
	col2.metric("Gasto no mês", "R$ 0,00")
	col3.metric("Itens pendentes", "0")
	st.info(
		"Esta página exibirá KPIs e atalhos para importação e revisão assim que os dados estiverem disponíveis."
	)


def main() -> None:
	st.set_page_config(page_title="Gerenciador de Gastos", layout="wide")
	st.sidebar.title("Navegação")
	opcao = st.sidebar.radio(
		"Selecione uma área",
		(
			"Home",
			"Importar nota",
			"Analisar notas",
		),
	)

	if opcao == "Home":
		_render_home()
	elif opcao == "Importar nota":
		render_pagina_importacao()
	else:
		render_pagina_analise()


if __name__ == "__main__":
	main()
