from __future__ import annotations

from typing import Any, Dict, List, Tuple

import streamlit as st

from src.classifiers import classificar_itens_pendentes
from src.classifiers.llm_classifier import obter_modelos_disponiveis
from src.database import salvar_nota, carregar_nota, remover_nota
from src.scrapers import receita_rs
from src.logger import setup_logging


logger = setup_logging("ui.importacao")

# Lista de modelos disponíveis (obtida de forma centralizada)
MODELOS_LLM_DISPONIVEIS = obter_modelos_disponiveis()


def _registrar_historico(resultado: Dict[str, Any]) -> None:
	"""Guarda um histórico mínimo de importações na sessão atual."""
	historico: List[Dict[str, Any]] = st.session_state.setdefault("historico_importacoes", [])
	historico.insert(0, resultado)
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
	fila: List[Dict[str, str]] = st.session_state.setdefault("flash_analisar_msgs", [])
	fila.append({"tipo": tipo, "texto": texto})


def _redirecionar_para_editor(chave_acesso: str) -> None:
	"""Configura sinalização para abrir automaticamente a aba de análise."""
	logger.info("Redirecionando para aba de análise da nota %s", chave_acesso)
	st.session_state["nota_em_revisao"] = chave_acesso
	st.session_state["redirecionar_menu"] = "Analisar notas"
	st.rerun()


def _executar_classificacao_para_nota(
	nota: receita_rs.NotaFiscal,
) -> Tuple[bool, List[Tuple[str, str]]]:
	"""Dispara a classificação automática e retorna mensagens para a aba de análise."""
	quantidade_itens = nota.total_itens or len(nota.itens)
	limite = max(int(quantidade_itens or 0), 1)
	mensagens: List[Tuple[str, str]] = []
	progresso_placeholder = st.empty()
	model_priority = st.session_state.get("llm_model_priority")

	def _progress_callback(mensagem: str) -> None:
		progresso_placeholder.info(mensagem)
	try:
		with st.spinner("Classificando itens automaticamente..."):
			resultados = classificar_itens_pendentes(
				limit=limite,
				confirmar=False,
				chave_acesso=nota.chave_acesso,
				model_priority=model_priority,
				progress_callback=_progress_callback,
			)
	except Exception as exc:  # pragma: no cover - interação manual
		logger.exception("Falha ao classificar itens da nota %s", nota.chave_acesso)
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

	with st.expander("⚙️ Configurações de LLM", expanded=False):
		st.caption("Defina a prioridade dos modelos para tentativas em caso de falha.")
		ordem_atual = st.session_state.get("llm_model_priority")
		if not ordem_atual:
			ordem_atual = MODELOS_LLM_DISPONIVEIS.copy()
			st.session_state["llm_model_priority"] = ordem_atual

		linhas = [
			{"prioridade": idx + 1, "modelo": modelo} for idx, modelo in enumerate(ordem_atual)
		]
		editado = st.data_editor(
			linhas,
			hide_index=True,
			num_rows="fixed",
			column_config={
				"prioridade": st.column_config.NumberColumn(
					"Ordem",
					min_value=1,
					step=1,
					width="small",
				),
				"modelo": st.column_config.TextColumn("Modelo", disabled=True),
			},
		)

		def _ordenar_modelos(linhas_editadas, referencia):
			def _prioridade_valor(linha, padrao):
				try:
					return int(linha.get("prioridade", padrao))
				except (TypeError, ValueError):
					return padrao

			ordenadas = sorted(
				linhas_editadas,
				key=lambda item: (_prioridade_valor(item, 9999), referencia.index(item["modelo"])),
			)
			return [item["modelo"] for item in ordenadas]

		nova_ordem = _ordenar_modelos(editado, ordem_atual)
		st.session_state["llm_model_priority"] = nova_ordem

	with st.form("form_importacao"):
		chave_input = st.text_input("Chave de acesso", max_chars=54, help="Cole ou digite os 44 dígitos")
		col_a, col_b = st.columns([1, 1])
		with col_a:
			st.checkbox(
				"Salvar HTML para depuração",
				value=True,
				help="Mantém uma cópia do HTML em data/raw_nfce",
			)
		with col_b:
			executar_classificacao = st.checkbox(
				"Classificar itens automaticamente",
				value=True,
				help="Enfileira itens recém-importados para classificação via LLM",
			)
		submetido = st.form_submit_button("Importar nota")

	chave_reprocessamento = st.session_state.get("confirmar_reprocessamento")

	if not submetido and not chave_reprocessamento:
		_renderizar_historico()
		return

	if chave_reprocessamento:
		chave_normalizada = chave_reprocessamento
		if "reprocessamento_classificar" in st.session_state:
			executar_classificacao = st.session_state.pop("reprocessamento_classificar")
	else:
		chave_normalizada = chave_input.strip()
	if not chave_normalizada:
		st.error("A chave de acesso é obrigatória.")
		_renderizar_historico()
		return

	if not receita_rs.validar_chave_acesso(chave_normalizada):
		st.error("A chave precisa ter exatamente 44 dígitos numéricos.")
		_renderizar_historico()
		return

	# Verifica se a nota já foi importada anteriormente
	nota_existente = carregar_nota(chave_normalizada)
	if nota_existente:
		# Se estamos num fluxo de reprocessamento confirmado para esta nota, pulamos a exibição do aviso
		# e seguimos direto para a remoção/reimportação.
		if st.session_state.get("confirmar_reprocessamento") != chave_normalizada:
			st.warning(
				f"⚠️ Esta nota já foi importada anteriormente.\n\n"
				f"**Emitente:** {nota_existente.emitente_nome or '—'}\n\n"
				f"**Data:** {nota_existente.emissao or '—'}\n\n"
				f"**Valor:** R$ {float(nota_existente.valor_total or 0):.2f}\n\n"
				f"**Itens:** {nota_existente.total_itens or len(nota_existente.itens)}\n\n"
			)

			logger.info(f"Nota {nota_existente.chave_acesso} já existe no sistema.")

			# Callbacks para os botões
			def _cb_reprocessar():
				st.session_state["confirmar_reprocessamento"] = chave_normalizada
				st.session_state["reprocessamento_classificar"] = executar_classificacao
				logger.info(f"Usuário solicitou reprocessamento da nota {chave_normalizada}")

			def _cb_cancelar():
				st.session_state.pop("confirmar_reprocessamento", None)
				logger.info("Usuário cancelou importação.")

			def _cb_ver():
				logger.info(f"Usuário pediu para ver nota existente {chave_normalizada}")
				_redirecionar_para_editor(chave_normalizada)

			col1, col2, col3 = st.columns(3)
			with col1:
				st.button(
					"🔄 Sim, reprocessar",
					key=f"reprocessar_{chave_normalizada}",
					type="primary",
					width="stretch",
					on_click=_cb_reprocessar
				)
			with col2:
				st.button(
					"❌ Não, cancelar",
					key=f"cancelar_{chave_normalizada}",
					width="stretch",
					on_click=_cb_cancelar
				)
			with col3:
				st.button(
					"👁️ Ver nota existente",
					key=f"ver_{chave_normalizada}",
					width="stretch",
				on_click=_cb_ver
			)

			# Interrompe o fluxo para aguardar ação do usuário
			_renderizar_historico()
			return

		# Se chegou aqui, é porque confirmar_reprocessamento == chave_normalizada
		# Proceder com a remoção da nota antiga
		try:
			with st.spinner("Removendo nota anterior do banco de dados..."):
				remover_nota(chave_normalizada)
			st.success("✅ Nota anterior removida. Prosseguindo com a importação...")
			logger.info("Nota %s removida para reprocessamento.", chave_normalizada)
		except Exception as exc:
			logger.exception("Erro ao remover nota %s para reprocessamento: %s", chave_normalizada, exc)
			st.error(f"Erro ao remover a nota anterior: {exc}")
			_renderizar_historico()
			return
		finally:
			# Limpa o estado para evitar loops futuros ou estados inconsistentes
			st.session_state.pop("confirmar_reprocessamento", None)

	try:
		with st.spinner("Consultando portal da Receita Gaúcha..."):
			nota = receita_rs.buscar_nota(chave_normalizada)
			salvar_nota(nota)
	except Exception as exc:  # pragma: no cover - interface streamlit
		logger.exception(
			"Falha ao importar a nota %s a partir da Receita Gaúcha por causa de: %s",
			chave_normalizada,
			exc,
		)
		st.error(f"Falha ao importar nota: {exc}")
		_renderizar_historico()
		return

	st.success("Nota importada com sucesso!")
	logger.info(
		"Nota %s importada com sucesso. Emitente=%s Valor_total=%s",
		nota.chave_acesso,
		nota.emitente_nome,
		nota.valor_total,
	)
	_exibir_resumo_nota(nota)

	resultado = {
		"chave": nota.chave_acesso,
		"emitente": nota.emitente_nome or "(desconhecido)",
		"valor_total": float(nota.valor_total or 0),
		"itens": nota.total_itens or len(nota.itens),
	}
	_registrar_historico(resultado)

	mensagens_para_flash: List[Tuple[str, str]] = []
	if executar_classificacao:
		sucesso_classificacao, mensagens_classificacao = _executar_classificacao_para_nota(nota)
		mensagens_para_flash.extend(mensagens_classificacao)
		if not sucesso_classificacao:
			st.caption("Dica: utilize a aba de análise para revisar categorias antes de confirmar.")
			_renderizar_historico()
			return

	mensagens_para_flash.insert(
		0,
		(
			"success",
			f"Nota {nota.chave_acesso} importada com sucesso. Emitente: {nota.emitente_nome or '—' }.",
		),
	)
	for tipo, texto in mensagens_para_flash:
		_adicionar_flash_analise(texto, tipo)

	_redirecionar_para_editor(nota.chave_acesso)
