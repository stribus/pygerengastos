from __future__ import annotations

import streamlit as st
import traceback

from src.database import inicializar_banco, seed_categorias_csv
from src.ui import render_pagina_analise, render_pagina_importacao, render_pagina_relatorios
from src.ui.home import render_home
from src.ui.normalizacao import render_pagina_normalizacao
from src.logger import setup_logging
from src.classifiers.llm_classifier import iniciar_carregamento_background

logger = setup_logging("main")

def main() -> None:
	try:
		logger.info("Iniciando aplicação Gerenciador de Gastos")
		st.set_page_config(page_title="Gerenciador de Gastos", layout="wide")

		# Iniciar carregamento de modelos LLM em background (não bloqueia UI)
		if "modelos_llm_carregamento_iniciado" not in st.session_state:
			logger.info("Iniciando carregamento de modelos LLM em background")
			iniciar_carregamento_background()
			st.session_state["modelos_llm_carregamento_iniciado"] = True

		# Inicialização do banco e categorias
		if "banco_inicializado" not in st.session_state:
			try:
				inicializar_banco()
				seed_categorias_csv()
				st.session_state["banco_inicializado"] = True
				logger.info("Banco de dados inicializado com sucesso")
			except Exception as e:
				logger.exception(f"Erro na inicialização do banco: {e}")
				st.error("Erro crítico ao iniciar banco de dados.")
				return

		st.sidebar.title("Navegação")
		paginas = ("Home", "Importar nota", "Analisar notas", "Normalizar produtos", "Relatórios")
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
		elif opcao == "Analisar notas":
			render_pagina_analise()
		elif opcao == "Normalizar Produtos":
			render_pagina_normalizacao()
		elif opcao == "Relatórios":
			render_pagina_relatorios()

if __name__ == "__main__":
	main()
