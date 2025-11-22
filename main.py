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
	try:
		inicializar_banco()
		seed_categorias_csv()
		logger.info("Banco de dados inicializado com sucesso")
	except Exception as e:
		logger.error(f"Erro na inicialização do banco: {e}")
		st.error("Erro crítico ao iniciar banco de dados.")

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
		render_home()
	elif opcao == "Importar nota":
		render_pagina_importacao()
	else:
		render_pagina_analise()


if __name__ == "__main__":
	main()
