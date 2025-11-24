from __future__ import annotations

import streamlit as st

from src.database import inicializar_banco, seed_categorias_csv
from src.ui import render_pagina_analise, render_pagina_importacao
from src.ui.home import render_home
from src.logger import setup_logging

logger = setup_logging("main")

def main() -> None:
	logger.info("Iniciando aplicação Gerenciador de Gastos")
	st.set_page_config(page_title="Gerenciador de Gastos", layout="wide")
	
	# Inicialização do banco e categorias
	if "banco_inicializado" not in st.session_state:
		try:
			inicializar_banco()
			seed_categorias_csv()
			st.session_state["banco_inicializado"] = True
			logger.info("Banco de dados inicializado com sucesso")
		except Exception as e:
			logger.error(f"Erro na inicialização do banco: {e}")
			st.error("Erro crítico ao iniciar banco de dados.")

	st.sidebar.title("Navegação")
	paginas = ("Home", "Importar nota", "Analisar notas")
	if "menu_navegacao" not in st.session_state:
		st.session_state["menu_navegacao"] = paginas[0]
	proximo_menu = st.session_state.pop("redirecionar_menu", None)
	if proximo_menu in paginas:
		logger.info("Redirecionamento pendente detectado: %s", proximo_menu)
		st.session_state["menu_navegacao"] = proximo_menu
	opcao = st.sidebar.radio(
		"Selecione uma área",
		paginas,
		key="menu_navegacao",
	)

	if opcao == "Home":
		render_home()
	elif opcao == "Importar nota":
		render_pagina_importacao()
	else:
		render_pagina_analise()


if __name__ == "__main__":
	main()
