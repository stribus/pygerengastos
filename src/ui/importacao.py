from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from src.classifiers import classificar_itens_pendentes
from src.database import salvar_nota
from src.scrapers import receita_rs


def _registrar_historico(resultado: Dict[str, Any]) -> None:
	"""Guarda um histórico mínimo de importações na sessão atual."""
	historico: List[Dict[str, Any]] = st.session_state.setdefault("historico_importacoes", [])
	historico.insert(0, resultado)
	# manter somente os cinco mais recentes
	if len(historico) > 5:
		del historico[5:]


def _renderizar_historico() -> None:
	"""Exibe o histórico recente de importações realizadas nesta sessão."""
	historico: List[Dict[str, Any]] = st.session_state.get("historico_importacoes", [])
	if not historico:
		st.info("Nenhuma nota importada nesta sessão ainda.")
		return
	st.subheader("Histórico recente")
	st.table(historico)


def _exibir_resumo_nota(nota: receita_rs.NotaFiscal) -> None:
	"""Mostra um pequeno resumo da nota importada."""
	col1, col2 = st.columns(2)
	col1.metric("Emitente", nota.emitente_nome or "—")
	col1.metric("Valor total", f"R$ {nota.valor_total or 0:.2f}")
	col2.metric("Itens", nota.total_itens or len(nota.itens))
	col2.metric("Pagamentos", len(nota.pagamentos))
	with st.expander("Detalhes dos itens", expanded=False):
		st.dataframe(
			[
				{
					"Sequência": idx + 1,
					"Descrição": item.descricao,
					"Qtd": float(item.quantidade),
					"Valor total": float(item.valor_total),
		def _mostrar_itens_classificados(chave_acesso: str) -> bool:
			"""Exibe uma tabela com categorias sugeridas e status após classificação."""
			itens = listar_itens_para_revisao(chave_acesso, somente_pendentes=False)
			if not itens:
				st.info("Ainda não há itens registrados para esta nota no banco de dados.")
				return False

			st.subheader("Categorias sugeridas pelos serviços de IA")
			linhas: List[Dict[str, Any]] = []
			for item in itens:
				status = "Confirmada" if item.categoria_confirmada else ("Sugerida" if item.categoria_sugerida else "Pendente")
				linhas.append(
					{
						"Seq.": item.sequencia,
						"Descrição": item.descricao,
						"Categoria sugerida": item.categoria_sugerida or "—",
						"Categoria confirmada": item.categoria_confirmada or "—",
						"Produto": item.produto_nome or "—",
						"Marca": item.produto_marca or "—",
						"Valor total": float(item.valor_total or 0),
						"Status": status,
					}
				)

			st.dataframe(linhas, hide_index=True, use_container_width=True)
			return True


		def _exibir_cta_analisar(nota: receita_rs.NotaFiscal) -> None:
			"""Mostra call-to-action para abrir a aba de análise já destacando a nota atual."""
			st.info(
				"Finalize a classificação confirmando os itens na aba ‘Analisar notas’."
			)
			if st.button(
				"Abrir aba ‘Analisar notas’",
				key=f"cta_analise_{nota.chave_acesso}",
				type="primary",
				use_container_width=True,
			):
				st.session_state["menu_navegacao"] = "Analisar notas"
				st.session_state["nota_em_revisao"] = nota.chave_acesso
				st.rerun()


		def _executar_classificacao_para_nota(nota: receita_rs.NotaFiscal) -> None:
			"""Dispara a classificação automática e exibe os resultados ao usuário."""
			from __future__ import annotations

			from typing import Any, Dict, List

			import streamlit as st

			from src.classifiers import classificar_itens_pendentes
			from src.database import listar_itens_para_revisao, salvar_nota
			from src.scrapers import receita_rs


			def _registrar_historico(resultado: Dict[str, Any]) -> None:
				"""Guarda um histórico mínimo de importações na sessão atual."""
				historico: List[Dict[str, Any]] = st.session_state.setdefault("historico_importacoes", [])
				historico.insert(0, resultado)
				# manter somente os cinco mais recentes
				if len(historico) > 5:
					del historico[5:]


			def _renderizar_historico() -> None:
				"""Exibe o histórico recente de importações realizadas nesta sessão."""
				historico: List[Dict[str, Any]] = st.session_state.get("historico_importacoes", [])
				if not historico:
					st.info("Nenhuma nota importada nesta sessão ainda.")
					return
				st.subheader("Histórico recente")
				st.table(historico)


			def _exibir_resumo_nota(nota: receita_rs.NotaFiscal) -> None:
				"""Mostra um pequeno resumo da nota importada."""
				col1, col2 = st.columns(2)
				col1.metric("Emitente", nota.emitente_nome or "—")
				col1.metric("Valor total", f"R$ {nota.valor_total or 0:.2f}")
				col2.metric("Itens", nota.total_itens or len(nota.itens))
				col2.metric("Pagamentos", len(nota.pagamentos))
				with st.expander("Detalhes dos itens", expanded=False):
					st.dataframe(
						[
							{
								"Sequência": idx + 1,
								"Descrição": item.descricao,
								"Qtd": float(item.quantidade),
								"Valor total": float(item.valor_total),
							}
							for idx, item in enumerate(nota.itens)
						],
						height=300,
					)



			def _adicionar_flash_analise(texto: str, tipo: str = "info") -> None:
				"""Empilha mensagens para serem exibidas na página de análise."""
				fila: list[dict[str, str]] = st.session_state.setdefault("flash_analisar_msgs", [])
				fila.append({"tipo": tipo, "texto": texto})


			def _redirecionar_para_editor(chave_acesso: str) -> None:
				"""Ajusta o menu e abre automaticamente a aba de análise."""
				st.session_state["nota_em_revisao"] = chave_acesso
				st.session_state["menu_navegacao"] = "Analisar notas"
				st.rerun()


			def _executar_classificacao_para_nota(
				nota: receita_rs.NotaFiscal,
			) -> tuple[bool, list[tuple[str, str]]]:
				"""Dispara a classificação automática e retorna mensagens para a aba de análise."""
				quantidade_itens = nota.total_itens or len(nota.itens)
				limite = max(int(quantidade_itens or 0), 1)
				mensagens: list[tuple[str, str]] = []
				try:
					with st.spinner("Classificando itens automaticamente..."):
						resultados = classificar_itens_pendentes(
							limit=limite,
							confirmar=False,
							chave_acesso=nota.chave_acesso,
						)
				except Exception as exc:  # pragma: no cover - interação manual
					st.error(f"Não foi possível classificar os itens automaticamente: {exc}")
					return False, mensagens

				if not resultados:
					mensagens.append(
						(
							"warning",
							"Nenhum item pendente foi localizado para classificação automática nesta nota. Revise manualmente na aba de análise.",
						)
					)
					return True, mensagens

				mensagens.append(("success", f"Classificação concluída para {len(resultados)} item(ns)."))
				return True, mensagens


			def render_pagina_importacao() -> None:
				"""Renderiza a página de cadastro/importação de notas."""
				st.header("Importar Nota Fiscal")
				st.write(
					"Informe a chave de acesso (44 dígitos) para buscar a nota diretamente no portal da Receita Gaúcha."
				)

				with st.form("form_importacao"):
					chave_input = st.text_input("Chave de acesso", max_chars=54, help="Cole ou digite os 44 dígitos")
					col_a, col_b = st.columns([1, 1])
					with col_a:
						salvar_html = st.checkbox(
							"Salvar HTML para depuração",
							value=True,
							help="Mantém uma cópia do HTML em data/raw_nfce",
						)
					with col_b:
						executar_classificacao = st.checkbox(
							"Classificar itens automaticamente",
							value=False,
							help="Enfileira itens recém-importados para a Groq",
						)
					submetido = st.form_submit_button("Importar nota")

				if not submetido:
					_renderizar_historico()
					return

				chave_normalizada = chave_input.strip()
				if not chave_normalizada:
					st.error("A chave de acesso é obrigatória.")
					_renderizar_historico()
					return

				if not receita_rs.validar_chave_acesso(chave_normalizada):
					st.error("A chave precisa ter exatamente 44 dígitos numéricos.")
					_renderizar_historico()
					return

				try:
					with st.spinner("Consultando portal da Receita Gaúcha..."):
						nota = receita_rs.buscar_nota(chave_normalizada)
						salvar_nota(nota)
				except Exception as exc:  # pragma: no cover - interface streamlit
					st.error(f"Falha ao importar nota: {exc}")
					_renderizar_historico()
					return

				st.success("Nota importada com sucesso!")
				_exibir_resumo_nota(nota)

				resultado = {
					"chave": nota.chave_acesso,
					"emitente": nota.emitente_nome or "(desconhecido)",
					"valor_total": float(nota.valor_total or 0),
					"itens": nota.total_itens or len(nota.itens),
				}
				_registrar_historico(resultado)

				mensagens_para_flash: list[tuple[str, str]] = []
				if executar_classificacao:
					sucesso_classificacao, mensagens_classificacao = _executar_classificacao_para_nota(nota)
					mensagens_para_flash.extend(mensagens_classificacao)
					if not sucesso_classificacao:
						# Mantém usuário na tela de importação para corrigir o problema
						st.caption("Dica: utilize a aba de análise para revisar categorias antes de confirmar.")
						_renderizar_historico()
						return

				mensagens_para_flash.insert(
					0,
					(
						"success",
						f"Nota {nota.chave_acesso} importada com sucesso. Emitente: {nota.emitente_nome or '—'}.",
					),
				)
				for tipo, texto in mensagens_para_flash:
					_adicionar_flash_analise(texto, tipo)

				_redirecionar_para_editor(nota.chave_acesso)