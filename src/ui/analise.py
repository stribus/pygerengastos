from __future__ import annotations

from typing import Any, List

import pandas as pd
import streamlit as st

from src.database import (
    ItemNotaRevisao,
    NotaParaRevisao,
    listar_itens_para_revisao,
    listar_notas_para_revisao,
    listar_revisoes_manuais,
    registrar_revisoes_manuais,
)


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

    filtro_notas = st.checkbox("Mostrar somente notas com itens pendentes", value=True)
    notas = listar_notas_para_revisao(limit=100, somente_pendentes=filtro_notas)
    if not notas:
        st.info("Nenhuma nota disponível para revisão.")
        return

    indice = st.selectbox(
        "Escolha a nota",
        options=list(range(len(notas))),
        format_func=lambda idx: _formatar_rotulo(notas[idx]),
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
        observacoes = st.text_area(
            "Observações adicionais",
            placeholder="Ex.: Ajuste confirmado com base em embalagem física.",
        )

        col_a, col_b = st.columns(2)
        salvar = col_a.form_submit_button("Salvar rascunho", type="secondary")
        confirmar = col_b.form_submit_button("Confirmar ajustes", type="primary")

    if usuario:
        st.session_state["usuario_revisao"] = usuario

    if salvar or confirmar:
        registros = _converter_registros(df_editado, nota.chave_acesso, observacoes)
        try:
            registrar_revisoes_manuais(
                registros,
                confirmar=confirmar,
                usuario=usuario.strip() or None,
                observacoes_padrao=observacoes.strip() or None,
            )
        except Exception as exc:  # pragma: no cover - interação manual
            st.error(f"Não foi possível registrar a revisão: {exc}")
            return

        if confirmar:
            st.success("Ajustes confirmados e persistidos no DuckDB.")
        else:
            st.info("Rascunho salvo. Confirme quando finalizar a revisão.")

        # atualizar dados em memória
        st.experimental_rerun()

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
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
