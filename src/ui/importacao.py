from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

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
				}
				for idx, item in enumerate(nota.itens)
			],
			height=300,
		)


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

	if executar_classificacao:
		st.info(
			"Classificação automática ainda não foi integrada à UI, mas os itens já estão disponíveis para o serviço Groq."
		)

	st.caption("Dica: utilize a aba de análise para revisar categorias antes de confirmar.")
	_renderizar_historico()