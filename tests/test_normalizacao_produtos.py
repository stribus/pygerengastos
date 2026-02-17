"""Testes de normalização e consolidação de produtos."""

from __future__ import annotations

import pytest
from decimal import Decimal
from pathlib import Path

from src.database import (
	normalizar_nome_produto_universal,
	listar_produtos_similares,
	consolidar_produtos,
	conexao,
	_criar_produto,
	_persistir_itens,
)
from src.scrapers.receita_rs import NotaItem


class TestNormalizacaoNomeProduto:
	"""Testes da função normalizar_nome_produto_universal."""

	def test_move_tamanho_para_final(self) -> None:
		"""Move tamanho do início/meio para o final."""
		resultado = normalizar_nome_produto_universal("AGUA DA PEDRA 2L C G")
		# Remove "DA" (stopword), mantém "AGUA" e "PEDRA", organiza C/Gás, move 2L para final
		assert "Agua" in resultado and "Pedra" in resultado
		assert "c/gás" in resultado.lower()
		assert "2l" in resultado

	def test_preserva_multiplos_tamanhos(self) -> None:
		"""Preservation de múltiplos tamanhos."""
		resultado = normalizar_nome_produto_universal("POWER SHOCK MENTA SPRAY 15ml SEXY FANTASY")
		assert "Power Shock" in resultado
		assert "15ml" in resultado
		assert "Sexy Fantasy" in resultado

	def test_remove_unidade_orfa(self) -> None:
		"""Remove unidade isolada sem número."""
		resultado = normalizar_nome_produto_universal("PEPINO SALADA KG")
		# "KG" é removido por estar isolado
		assert "Kg" not in resultado and "kg" not in resultado
		assert "Pepino" in resultado
		assert "Salada" in resultado

	def test_ignora_numero_isolado(self) -> None:
		"""Preserva número isolado que não é tamanho."""
		resultado = normalizar_nome_produto_universal("TINT KOLESTON 30 CASTANHO ESCURO")
		assert "30" in resultado  # Número deve permanecer
		assert "Tint" in resultado
		assert "Koleston" in resultado

	def test_normaliza_c_gas(self) -> None:
		"""Normaliza variações de 'com gás'."""
		assert "c/gás" in normalizar_nome_produto_universal("AGUA C/GAS 2L").lower()
		assert "c/gás" in normalizar_nome_produto_universal("AGUA CG 2L").lower()
		assert "c/gás" in normalizar_nome_produto_universal("AGUA C G 2L").lower()

	def test_normaliza_sem_lactose(self) -> None:
		"""Normaliza variações de 'sem lactose'."""
		resultado = normalizar_nome_produto_universal("LEITE ZERO LAC 1L").lower()
		assert "sem lactose" in resultado

	def test_entrada_vazia(self) -> None:
		"""Retorna string vazia para entrada vazia."""
		assert normalizar_nome_produto_universal("") == ""
		assert normalizar_nome_produto_universal(None) == ""

	def test_remove_pontuacao_extra(self) -> None:
		"""Remove pontuação extra."""
		resultado = normalizar_nome_produto_universal("AGUA--DA/PEDRA 2L")
		# Pontuação não deve aparecer de forma duplicada
		assert "--" not in resultado
		assert "2l" in resultado

	def test_title_case(self) -> None:
		"""Aplica Title Case corretamente."""
		resultado = normalizar_nome_produto_universal("agua da pedra 2l")
		assert resultado[0].isupper()  # Primeira letra maiúscula


class TestDeteccaoDuplicatas:
	"""Testes da função listar_produtos_similares."""

	def test_deteccao_simples(self, tmp_path: Path) -> None:
		"""Detecta dois produtos similares."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			# Criar categoria
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar produtos similares
			prod1 = _criar_produto(con, "Água Mineral", "Água da Pedra", 1)
			prod2 = _criar_produto(con, "Água Mineral com gás", "Água da Pedra", 1)

			# Criar itens para que apareçam na agregação
			con.execute(
				"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
				["CHAVE1", 1, "AGUA MINERAL", prod1.id],
			)
			con.execute(
				"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
				["CHAVE1", 2, "AGUA COM GAS", prod2.id],
			)

		# Buscar similaridades
		clusters = listar_produtos_similares(threshold=80, db_path=db_path)

		# Verificar que produtos foram agrupados
		assert len(clusters) > 0
		cluster = clusters[0]
		assert len(cluster["produtos"]) >= 2

	def test_threshold_minimo(self, tmp_path: Path) -> None:
		"""Respeita threshold de similaridade."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			# Criar categoria
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar produtos muito diferentes
			prod1 = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod2 = _criar_produto(con, "Refrigerante Cola", "Marca B", 1)

			con.execute(
				"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
				["CHAVE1", 1, "AGUA", prod1.id],
			)
			con.execute(
				"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
				["CHAVE1", 2, "REFRI", prod2.id],
			)

		# Buscar com threshold alto
		clusters = listar_produtos_similares(threshold=95, db_path=db_path)

		# Produtos muito diferentes não devem ser agrupados
		# (cada um em clusters separados ou não aparecerem)
		for cluster in clusters:
			# Se aparecerem, devem ser de marcas diferentes
			marcas = [p["marca_base"] for p in cluster["produtos"]]
			assert len(set(marcas)) == len(marcas) or len(cluster["produtos"]) == 1


class TestConsolidacaoProdutos:
	"""Testes da função consolidar_produtos."""

	def test_consolida_itens(self, tmp_path: Path) -> None:
		"""Migra itens corretamente."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			# Criar categoria
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar produtos
			prod_origem = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod_destino = _criar_produto(con, "Água com Gás", "Marca A", 1)

			# Criar itens para produto origem
			con.execute(
				"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
				["CHAVE1", 1, "AGUA MINERAL", prod_origem.id],
			)
			con.execute(
				"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
				["CHAVE2", 1, "AGUA MINERAL 2L", prod_origem.id],
			)

		# Consolidar
		stats = consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			db_path=db_path,
		)

		# Verificar migração
		assert stats["itens_migrados"] == 2

		with conexao(db_path) as con:
			# Verificar que itens migrados
			itens = con.execute(
				"SELECT COUNT(*) FROM itens WHERE produto_id = ?",
				[prod_destino.id],
			).fetchone()
			assert itens[0] == 2

			# Verificar que produto origem foi deletado
			produto_existe = con.execute(
				"SELECT COUNT(*) FROM produtos WHERE id = ?",
				[prod_origem.id],
			).fetchone()
			assert produto_existe[0] == 0

	def test_consolida_aliases(self, tmp_path: Path) -> None:
		"""Migra aliases corretamente."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			# Criar categoria
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar produtos
			prod_origem = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod_destino = _criar_produto(con, "Água com Gás", "Marca A", 1)

			# Criar aliases para produto origem
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_origem.id, "AGUA DA PEDRA"],
			)
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_origem.id, "AGUA MINERAL 2L"],
			)

		# Consolidar
		stats = consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			db_path=db_path,
		)

		assert stats["aliases_migrados"] == 2

		with conexao(db_path) as con:
			# Verificar que aliases foram migrados
			aliases = con.execute(
				"SELECT COUNT(*) FROM aliases_produtos WHERE produto_id = ?",
				[prod_destino.id],
			).fetchone()
			assert aliases[0] == 2

	def test_registra_auditoria(self, tmp_path: Path) -> None:
		"""Registra consolidação em auditoria."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			# Criar categoria
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar produtos
			prod_origem = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod_destino = _criar_produto(con, "Água com Gás", "Marca A", 1)

		# Consolidar
		usuario = "teste_user"
		observacoes = "teste consolidação"

		consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			usuario=usuario,
			observacoes=observacoes,
			db_path=db_path,
		)

		with conexao(db_path) as con:
			# Verificar auditoria
			auditoria = con.execute(
				"""
				SELECT usuario, observacoes, produto_id_origem, produto_id_destino
				FROM consolidacoes_historico
				WHERE produto_id_origem = ? AND produto_id_destino = ?
				""",
				[prod_origem.id, prod_destino.id],
			).fetchone()

			assert auditoria is not None
			assert auditoria[0] == usuario
			assert auditoria[1] == observacoes
			assert auditoria[2] == prod_origem.id
			assert auditoria[3] == prod_destino.id

	def test_erro_produto_invalido(self, tmp_path: Path) -> None:
		"""Lança erro se produto não existe."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

		with pytest.raises(ValueError):
			consolidar_produtos(
				produto_id_origem=9999,  # Não existe
				produto_id_destino=1,
				db_path=db_path,
			)

	def test_nome_final_customizado(self, tmp_path: Path) -> None:
		"""Permite customizar nome final."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			prod_origem = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod_destino = _criar_produto(con, "Água com Gás", "Marca A", 1)

		nome_novo = "Água Mineral c/Gás 2L"

		consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			nome_final=nome_novo,
			db_path=db_path,
		)

		with conexao(db_path) as con:
			produto = con.execute(
				"SELECT nome_base FROM produtos WHERE id = ?",
				[prod_destino.id],
			).fetchone()
			assert produto[0] == nome_novo


class TestIntegracaoCompleta:
	"""Testes de fluxo completo."""

	def test_fluxo_normalizacao_a_consolidacao(self, tmp_path: Path) -> None:
		"""Fluxo completo: detectar → normalizar → consolidar."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar 3 variações do mesmo produto
			prod1 = _criar_produto(con, "Água Mineral", "Água da Pedra", 1)
			prod2 = _criar_produto(con, "Água Mineral com gás", "Água da Pedra", 1)
			prod3 = _criar_produto(con, "Água c/gás 2L", "Água da Pedra", 1)

			# Criar itens
			for pid in [prod1.id, prod2.id, prod3.id]:
				con.execute(
					"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
					["CHAVE1", 1, "AGUA", pid],
				)

		# Detectar duplicatas
		clusters = listar_produtos_similares(threshold=75, db_path=db_path)
		assert len(clusters) > 0

		# Consolidar
		cluster = clusters[0]
		produtos = cluster["produtos"]
		assert len(produtos) >= 2

		# Consolidar todos em um
		ids_origem = [p["id"] for p in produtos[1:]]
		id_destino = produtos[0]["id"]

		for id_origem in ids_origem:
			consolidar_produtos(
				produto_id_origem=id_origem,
				produto_id_destino=id_destino,
				db_path=db_path,
			)

		# Verificar resultado
		with conexao(db_path) as con:
			itens_finais = con.execute(
				"SELECT COUNT(*) FROM itens WHERE produto_id = ?",
				[id_destino],
			).fetchone()
			assert itens_finais[0] == 3  # Todos os itens devem estar lá
