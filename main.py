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

# Dicionário de páginas: mapeia nome da opção -> função de renderização
# Esta estrutura elimina erros de digitação e centraliza a definição das páginas.
# Para adicionar uma nova página:
#   1. Adicione uma entrada neste dicionário
#   2. Importe a função de renderização no topo do arquivo
# O código de navegação (linhas 49-68) usa automaticamente as chaves deste dicionário.
PAGINAS = {
	"Home": render_home,
	"Importar nota": render_pagina_importacao,
	"Analisar notas": render_pagina_analise,
	"Normalizar produtos": render_pagina_normalizacao,
	"Relatórios": render_pagina_relatorios,
}

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
		# Usar as chaves do dicionário como opções do menu
		opcoes_menu = tuple(PAGINAS.keys())
		if "menu_navegacao" not in st.session_state:
			st.session_state["menu_navegacao"] = opcoes_menu[0]
		proximo_menu = st.session_state.pop("redirecionar_menu", None)
		if proximo_menu in opcoes_menu:
			logger.info("Redirecionamento pendente detectado: %s", proximo_menu)
			st.session_state["menu_navegacao"] = proximo_menu
		opcao = st.sidebar.radio(
			"Selecione uma área",
			opcoes_menu,
			key="menu_navegacao",
		)

		# Renderizar a página selecionada usando o dicionário
		render_func = PAGINAS.get(opcao)
		if render_func:
			render_func()
		else:
			logger.error(f"Opção de menu desconhecida: {opcao}")
			st.error(f"Página '{opcao}' não encontrada.")
	except Exception as e:
		logger.exception(f"Erro não tratado na aplicação: {e}")
		st.error(f"Ocorreu um erro inesperado: {e}")
	finally:
		logger.info("Aplicação encerrada")

if __name__ == "__main__":
	main()
