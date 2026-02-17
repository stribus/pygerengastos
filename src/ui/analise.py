from __future__ import annotations

from typing import Any, List

import pandas as pd
import streamlit as st

from src.classifiers import classificar_itens_pendentes
from src.classifiers.llm_classifier import obter_modelos_com_nomes_amigaveis
from src.database import (
    ItemNotaRevisao,
    NotaParaRevisao,
    listar_itens_para_revisao,
    listar_notas_para_revisao,
    listar_revisoes_manuais,
    registrar_revisoes_manuais,
)

# Modelos de IA disponíveis (obtidos de forma centralizada)
MODELOS_IA = obter_modelos_com_nomes_amigaveis()


@st.dialog("Escolher modelo de IA")
def _dialogo_escolher_ia(chave_acesso: str, limite_classificacao: int, total_itens: int) -> None:
    """Diálogo para escolher qual modelo de IA usar para reprocessamento."""
    st.write("Selecione qual IA deseja usar para classificar os itens:")

    # NOVO: Checkbox para escolher escopo com session state
    key_checkbox = f"reprocessar_todos_{chave_acesso}"

    reprocessar_todos = st.checkbox(
        f"Reprocessar TODOS os {total_itens} itens da nota (incluindo já confirmados)",
        key=key_checkbox,
        help="Se marcado, todos os itens da nota serão reclassificados, "
             "removendo as classificações confirmadas anteriormente. "
             "Se desmarcado, apenas itens pendentes serão processados.",
    )

    if reprocessar_todos:
        st.warning(
            "⚠️ As categorias já confirmadas serão removidas e "
            "todos os itens voltarão ao estado pendente."
        )

    modelo_escolhido = st.radio(
        "Modelo de IA",
        options=list(MODELOS_IA.keys()),
        index=0,
        help="Cada modelo tem características diferentes de velocidade e precisão."
    )

    col1, col2 = st.columns(2)

    if col1.button("Cancelar", use_container_width=True):
        st.rerun()

    if col2.button("Processar", type="primary", use_container_width=True):
        modelo_selecionado = MODELOS_IA[modelo_escolhido]
        # Ler o valor do checkbox do session state
        reprocessar_todos_value = st.session_state.get(key_checkbox, False)

        # Placeholder para feedback de progresso
        progresso_placeholder = st.empty()

        def _progress_callback(mensagem: str) -> None:
            """Callback para exibir progresso em tempo real."""
            progresso_placeholder.info(f"⏳ {mensagem}")

        try:
            escopo_msg = "todos os itens" if reprocessar_todos_value else "itens pendentes"
            modo_msg = " (modo LLM-only)" if reprocessar_todos_value else ""

            with st.spinner(f"Processando {escopo_msg} com {modelo_escolhido}{modo_msg}..."):
                resultados = classificar_itens_pendentes(
                    limit=limite_classificacao,
                    confirmar=False,
                    chave_acesso=chave_acesso,
                    model=modelo_selecionado,
                    incluir_confirmados=reprocessar_todos_value,
                    limpar_confirmadas_antes=reprocessar_todos_value,
                    forcar_llm=reprocessar_todos_value,
                    progress_callback=_progress_callback,
                )

            # Limpar mensagem de progresso após conclusão
            progresso_placeholder.empty()

        except Exception as exc:
            progresso_placeholder.empty()
            st.error(f"Erro ao processar: {exc}")
            return

        # Armazenar resultado em session_state
        fila = st.session_state.setdefault("flash_analisar_msgs", [])
        if resultados:
            escopo_msg = "todos os itens" if reprocessar_todos_value else "item(ns) pendente(s)"
            modo_info = " via LLM direto" if reprocessar_todos_value else ""
            fila.append(
                {
                    "tipo": "success",
                    "texto": f"{len(resultados)} {escopo_msg} reprocessado(s) com {modelo_escolhido}{modo_info}.",
                }
            )
        else:
            fila.append(
                {
                    "tipo": "info",
                    "texto": "Nenhum item estava disponível para reprocessamento.",
                }
            )
        st.session_state["nota_em_revisao"] = chave_acesso
        st.rerun()


def _formatar_rotulo(nota: NotaParaRevisao) -> str:
    data = (nota.emissao_iso or "")[:10] or "Sem data"
    emitente = nota.emitente_nome or "Emitente desconhecido"
    valor = f"R$ {float(nota.valor_total or 0):,.2f}"
    pendentes = f"{nota.itens_pendentes} pendente(s)"
    return f"{data} · {emitente} · {valor} · {pendentes}"


def _montar_editor(itens: List[ItemNotaRevisao]) -> pd.DataFrame:
    linhas: List[dict[str, Any]] = []
    for item in itens:
        linhas.append(
            {
                "sequencia": item.sequencia,
                "descricao": item.descricao,
                "categoria": item.categoria_confirmada or item.categoria_sugerida or "",
                "produto_nome": item.produto_nome or "",
                "produto_marca": item.produto_marca or "",
                "quantidade": float(item.quantidade or 0),
                "valor_total": float(item.valor_total or 0),
            }
        )
    return pd.DataFrame(linhas)


def _converter_registros(df: pd.DataFrame, chave_acesso: str, observacoes: str | None) -> List[dict[str, Any]]:
    registros: List[dict[str, Any]] = []
    for linha in df.to_dict("records"):
        registros.append(
            {
                "chave_acesso": chave_acesso,
                "sequencia": linha["sequencia"],
                "categoria": (linha.get("categoria") or "").strip() or None,
                "produto_nome": (linha.get("produto_nome") or "").strip() or None,
                "produto_marca": (linha.get("produto_marca") or "").strip() or None,
                "observacoes": (observacoes or "").strip() or None,
            }
        )
    return registros


def render_pagina_analise() -> None:
    st.header("Análise e revisão de notas")
    st.write("Selecione uma nota para revisar categorias, nomes base e marcas antes de confirmar.")

    flash_msgs = st.session_state.pop("flash_analisar_msgs", [])
    for alerta in flash_msgs:
        tipo = (alerta or {}).get("tipo", "info")
        texto = (alerta or {}).get("texto")
        if not texto:
            continue
        if tipo == "success":
            st.success(texto)
        elif tipo == "warning":
            st.warning(texto)
        elif tipo == "error":
            st.error(texto)
        else:
            st.info(texto)

    filtro_notas = st.checkbox("Mostrar somente notas com itens pendentes", value=True)
    notas = listar_notas_para_revisao(limit=100, somente_pendentes=filtro_notas)
    if not notas:
        st.info("Nenhuma nota disponível para revisão.")
        return

    nota_destaque = st.session_state.pop("nota_em_revisao", None)
    indice_padrao = 0
    if nota_destaque:
        for idx, item in enumerate(notas):
            if item.chave_acesso == nota_destaque:
                indice_padrao = idx
                break

    indice = st.selectbox(
        "Escolha a nota",
        options=list(range(len(notas))),
        format_func=lambda idx: _formatar_rotulo(notas[idx]),
        index=indice_padrao,
    )
    nota = notas[indice]

    col1, col2, col3 = st.columns(3)
    col1.metric("Emitente", nota.emitente_nome or "—")
    col2.metric("Valor total", f"R$ {float(nota.valor_total or 0):,.2f}")
    col3.metric("Itens pendentes", nota.itens_pendentes)

    filtro_itens = st.checkbox("Exibir apenas itens pendentes desta nota", value=True)
    itens = listar_itens_para_revisao(nota.chave_acesso, somente_pendentes=filtro_itens)
    if not itens:
        st.success("Sem itens pendentes para esta nota.")
        return

    df_base = _montar_editor(itens)

    itens_pendentes_total = int(nota.itens_pendentes or 0)
    total_itens_nota = int(nota.total_itens or 0)

    # Botão habilitado se houver itens (pendentes ou não)
    botao_reprocessar = st.button(
        "Reprocessar itens via IA",
        type="secondary",
        disabled=total_itens_nota == 0,
        help="Classifica ou reclassifica os itens da nota usando IA. "
             "Você pode escolher processar apenas pendentes ou todos os itens.",
    )

    if botao_reprocessar:
        limite_classificacao = max(total_itens_nota, len(itens), 1)
        # Abrir diálogo para escolher a IA
        _dialogo_escolher_ia(nota.chave_acesso, limite_classificacao, total_itens_nota)

    with st.form(f"form_revisao_{nota.chave_acesso}"):
        st.write("Ajuste os campos necessários e escolha salvar rascunho ou confirmar.")
        df_editado = st.data_editor(
            df_base,
            hide_index=True,
            num_rows="fixed",
            key=f"editor_{nota.chave_acesso}",
            column_config={
                "sequencia": st.column_config.NumberColumn("Seq.", disabled=True),
                "descricao": st.column_config.TextColumn("Descrição", disabled=True, width="large"),
                "quantidade": st.column_config.NumberColumn("Qtd.", disabled=True, format="%.3f"),
                "valor_total": st.column_config.NumberColumn("Valor total", disabled=True, format="R$ %.2f"),
                "categoria": st.column_config.TextColumn("Categoria"),
                "produto_nome": st.column_config.TextColumn("Produto (nome base)"),
                "produto_marca": st.column_config.TextColumn("Marca"),
            },
        )

        usuario = st.text_input(
            "Revisor responsável (opcional)",
            value=st.session_state.get("usuario_revisao", ""),
        )
        usuario_limpo = (usuario or "").strip()
        observacoes = st.text_area(
            "Observações adicionais",
            placeholder="Ex.: Ajuste confirmado com base em embalagem física.",
        )

        col_a, col_b = st.columns(2)
        salvar = col_a.form_submit_button("Salvar rascunho", type="secondary")
        confirmar = col_b.form_submit_button("Confirmar ajustes", type="primary")

    if usuario_limpo:
        st.session_state["usuario_revisao"] = usuario_limpo

    if salvar or confirmar:
        registros = _converter_registros(df_editado, nota.chave_acesso, observacoes)
        try:
            registrar_revisoes_manuais(
                registros,
                confirmar=confirmar,
                usuario=usuario_limpo or None,
                observacoes_padrao=(observacoes or "").strip() or None,
            )
        except Exception as exc:  # pragma: no cover - interação manual
            st.error(f"Não foi possível registrar a revisão: {exc}")
            return

        if confirmar:
            st.success("Ajustes confirmados e persistidos no SQLite3.")
        else:
            st.info("Rascunho salvo. Confirme quando finalizar a revisão.")

        # atualizar dados em memória
        st.rerun()

    historico = listar_revisoes_manuais(nota.chave_acesso, limit=15)
    if historico:
        st.subheader("Histórico recente de revisões")
        df_hist = pd.DataFrame(
            [
                {
                    "Data": rev.criado_em,
                    "Seq.": rev.sequencia,
                    "Categoria": rev.categoria or "—",
                    "Produto": rev.produto_nome or "—",
                    "Marca": rev.produto_marca or "—",
                    "Usuário": rev.usuario or "—",
                    "Confirmado": "Sim" if rev.confirmado else "Não",
                    "Observações": rev.observacoes or "—",
                }
                for rev in historico
            ]
        )
        st.dataframe(df_hist, width="stretch", hide_index=True)
