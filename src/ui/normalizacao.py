"""Interface de normalização e consolidação de produtos duplicados."""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import streamlit as st

from src.database import (
	consolidar_produtos,
	listar_produtos_similares,
	normalizar_nome_produto_universal,
)
from src.logger import setup_logging

logger = setup_logging("ui.normalizacao")


@st.dialog("Confirmar consolidação", width="large")
def _dialogo_confirmar_consolidacao(dados: dict[str, Any]) -> None:
	"""Diálogo para confirmar consolidação de produtos."""
	produtos = dados["produtos"]
	nome_sugerido = dados["nome_sugerido"]

	st.markdown("### 📋 Produtos a Consolidar")

	# Mostrar lista de produtos
	for p in produtos:
		col1, col2, col3 = st.columns([2, 1, 1])
		with col1:
			st.write(f"**ID {p['id']}**: {p['nome_base']}")
			if p.get("descricoes_itens"):
				st.caption(f"📄 Descrição: {p['descricoes_itens']}")
			if p.get("nomes_itens"):
				st.caption(f"🏷️ Nome produto: {p['nomes_itens']}")
		with col2:
			st.write(f"{p['qtd_itens']} itens")
		with col3:
			st.write(f"{p['qtd_aliases']} aliases")

	st.divider()

	# Produto destino
	st.markdown("### 🎯 Produto Destino")
	produto_destino = max(produtos, key=lambda x: x["qtd_itens"])
	produto_destino_id = produto_destino["id"]
	st.info(
		f"**ID {produto_destino_id}** será o produto final "
		f"(possui mais itens vinculados: {produto_destino['qtd_itens']})"
	)

	st.divider()

	# Edição do nome final
	st.markdown("### ✏️ Ajustes")
	nome_final = st.text_input(
		"Nome final do produto",
		value=nome_sugerido,
		help="Este será o nome do produto consolidado"
	)

	observacoes = st.text_area(
		"Observações (opcional)",
		placeholder="Ex: Produtos eram variações do mesmo item",
		height=80
	)

	usuario = st.text_input(
		"Seu nome",
		value="Sistema",
		help="Nome do usuário realizando a consolidação"
	)

	st.divider()

	# Botões de ação
	col1, col2 = st.columns(2)

	with col1:
		if st.button("❌ Cancelar", width="stretch"):
			st.rerun()

	with col2:
		if st.button("✅ Consolidar", type="primary", width="stretch"):
			try:
				# Consolidar cada produto para o destino
				total_stats = {
					"itens_migrados": 0,
					"aliases_migrados": 0,
					"embeddings_atualizados": 0,
				}
				nome_usado_final = None  # Nome efetivamente usado após resolução de conflitos

				progress_bar = st.progress(0)
				status_text = st.empty()

				for idx, p in enumerate(produtos):
					if p["id"] == produto_destino_id:
						# Pular o destino na lista de origem
						continue

					status_text.text(f"Consolidando produto ID {p['id']}...")
					progress = (idx + 1) / len(produtos)
					progress_bar.progress(progress)

					stats = consolidar_produtos(
						produto_id_origem=p["id"],
						produto_id_destino=produto_destino_id,
						nome_final=nome_final if nome_final.strip() else None,
						usuario=usuario,
						observacoes=observacoes if observacoes.strip() else None,
					)

					total_stats["itens_migrados"] += stats["itens_migrados"]
					total_stats["aliases_migrados"] += stats["aliases_migrados"]
					total_stats["embeddings_atualizados"] += (
						stats["embeddings_atualizados"]
					)

					# Capturar nome final usado (da última consolidação)
					if stats.get("nome_final_usado"):
						nome_usado_final = stats["nome_final_usado"]

				# Aviso se nome foi alterado por conflito
				if nome_usado_final and nome_usado_final != nome_final.strip():
					st.warning(
						f"ℹ️ O nome foi ajustado para **'{nome_usado_final}'** "
						f"para evitar conflito com produto existente."
					)

				# Sucesso
				st.success(
					f"✅ Consolidação concluída com sucesso!\n\n"
					f"📦 {total_stats['itens_migrados']} itens migrados\n"
					f"📝 {total_stats['aliases_migrados']} aliases consolidados\n"
					f"🔍 {total_stats['embeddings_atualizados']} embeddings atualizados"
				)

				logger.info(
					"Consolidação concluída: %d produtos consolidados em ID %d por %s",
					len(produtos) - 1,
					produto_destino_id,
					usuario,
				)

				st.balloons()
				time.sleep(2)
				st.rerun()

			except Exception as exc:
				logger.exception("Erro ao consolidar produtos: %s", exc)
				st.error(f"❌ Erro ao consolidar: {exc}")


def render_pagina_normalizacao() -> None:
	"""Renderiza página de normalização e consolidação de produtos."""
	st.title("🔧 Normalizar Produtos")
	st.write(
		"Identifique e consolide produtos com nomes variantes "
		"(ex: 'Água da Pedra 2L C G' vs 'Água Mineral com Gás')."
	)

	st.divider()

	# Filtros
	col1, col2, col3 = st.columns(3)

	with col1:
		threshold = st.slider(
			"Similaridade mínima (%)",
			min_value=70,
			max_value=100,
			value=85,
			help="Produtos com similaridade acima deste valor serão agrupados",
		)

	with col2:
		mostrar_apenas_clusters = st.checkbox(
			"Apenas com duplicatas",
			value=True,
			help="Mostrar apenas produtos que têm variantes similares",
		)

	with col3:
		if st.button("🔄 Atualizar análise", width="stretch"):
			st.rerun()

	st.divider()

	# Buscar clusters
	with st.spinner("Analisando produtos similares..."):
		clusters = listar_produtos_similares(threshold=threshold)

	if mostrar_apenas_clusters:
		clusters = [c for c in clusters if len(c["produtos"]) > 1]

	if not clusters:
		st.info(
			f"✅ Nenhum produto duplicado detectado "
			f"(threshold: {threshold}%)."
		)
		return

	st.success(
		f"🔹 {len(clusters)} cluster(s) de produtos similares encontrado(s)."
	)

	st.divider()

	# Exibir clusters em expanders
	for cluster in clusters:
		num_produtos = len(cluster["produtos"])
		nome_cluster = cluster["nome_sugerido"]
		similares_text = f"{num_produtos} variante{'s' if num_produtos > 1 else ''}"

		with st.expander(f"📦 {nome_cluster} ({similares_text})"):
			# Preparar DataFrame
			df = pd.DataFrame(cluster["produtos"])
			df["selecionar"] = False
			# Mover coluna de seleção para o início
			df = df[["selecionar"] + [c for c in df.columns if c != "selecionar"]]

			# Tabela editável
			df_editado = st.data_editor(
				df,
				hide_index=True,
				width="stretch",
				column_config={
					"selecionar": st.column_config.CheckboxColumn(
						"✓ Consolidar",
						help="Marque os produtos para consolidar"
					),
					"id": st.column_config.NumberColumn(
						"ID",
						disabled=True,
						width="small",
					),
					"nome_base": st.column_config.TextColumn(
						"Nome Atual",
						disabled=True,
						width="medium",
					),
					"marca_base": st.column_config.TextColumn(
						"Marca",
						disabled=True,
						width="small",
					),
					"categoria_nome": st.column_config.TextColumn(
						"Categoria",
						disabled=True,
						width="small",
					),
					"qtd_aliases": st.column_config.NumberColumn(
						"Aliases",
						disabled=True,
						width="small",
					),
					"qtd_itens": st.column_config.NumberColumn(
						"Itens",
						disabled=True,
						width="small",
					),
					"score": st.column_config.NumberColumn(
						"Similaridade",
						disabled=True,
						format="%.0f%%",
						width="small",
					),
				},
				key=f"cluster_{cluster['cluster_id']}",
			)

			# Processar seleção
			selecionados = df_editado[df_editado["selecionar"]]

			if len(selecionados) >= 2:
				st.warning(
					f"⚠️ {len(selecionados)} produtos serão consolidados "
					f"no produto com mais itens vinculados."
				)

				if st.button(
					f"🔗 Consolidar {len(selecionados)} produtos",
					key=f"btn_consolidar_{cluster['cluster_id']}",
					type="primary",
					width="stretch",
				):
					_dialogo_confirmar_consolidacao(
						{
							"produtos": selecionados.to_dict("records"),
							"nome_sugerido": cluster["nome_sugerido"],
						}
					)
			elif len(selecionados) == 1:
				st.info("Selecione pelo menos 2 produtos para consolidar.")
			else:
				st.text("Selecione produtos acima para consolidar.")

	st.divider()

	# Seção de informações
	with st.expander("ℹ️ Como usar"):
		st.markdown(
			"""
			### Passo a Passo

			1. **Revisar clusters**: Cada seção agrupa produtos similares encontrados
			2. **Selecionar**: Marque os checkboxes dos produtos a consolidar
			3. **Confirmar**: Clique no botão "Consolidar N produtos"
			4. **Revisar preview**: O diálogo mostra o que será feito
			5. **Editar nome**: Opcionalmente ajuste o nome final do produto
			6. **Confirmar final**: Clique em "✅ Consolidar" para completar

			### O que acontece na consolidação

			- ✅ Todos os itens são transferidos para o produto destino
			- ✅ Alias (descrições alternativas) são consolidados
			- ✅ Embeddings (cache semântico) são atualizados
			- ✅ Histórico completo é mantido em `consolidacoes_historico`
			- ❌ Produto original é deletado permanentemente

			### Dicas

			- Threshold mais baixo (ex: 70%) encontra mais variações
			- Produto com mais itens é automaticamente o destino
			- Observações são registradas para auditoria
			"""
		)
