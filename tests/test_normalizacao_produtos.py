"""Testes de normalização e consolidação de produtos."""

from __future__ import annotations

import pytest
import sqlite3
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from src.database import (
	normalizar_nome_produto_universal,
	listar_produtos_similares,
	buscar_produtos,
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
		"""Preservação de múltiplos tamanhos."""
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

		stats = consolidar_produtos(
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
			assert stats["nome_final_usado"] == nome_novo

	def test_nome_final_conflito_unique_constraint(self, tmp_path: Path) -> None:
		"""Gera nome alternativo quando há conflito de UNIQUE (nome_base, marca_base)."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar 3 produtos com mesma marca
			prod_origem = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod_destino = _criar_produto(con, "Água com Gás", "Marca A", 1)
			prod_conflito = _criar_produto(con, "Água Normalizada", "Marca A", 1)  # Conflita com nome_final

		nome_novo = "Água Normalizada"  # Já existe em prod_conflito

		stats = consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			nome_final=nome_novo,
			db_path=db_path,
		)

		# Deve ter gerado nome alternativo
		assert stats["nome_final_usado"] != nome_novo
		assert stats["nome_final_usado"].startswith(nome_novo)
		assert "(" in stats["nome_final_usado"]  # Contém sufixo numérico

		with conexao(db_path) as con:
			# Verificar que produto destino foi renomeado com sufixo
			produto = con.execute(
				"SELECT nome_base FROM produtos WHERE id = ?",
				[prod_destino.id],
			).fetchone()
			assert produto[0] == stats["nome_final_usado"]
			assert produto[0] != nome_novo

			# Produto conflito ainda existe com nome original
			produto_conflito_atual = con.execute(
				"SELECT nome_base FROM produtos WHERE id = ?",
				[prod_conflito.id],
			).fetchone()
			assert produto_conflito_atual[0] == "Água Normalizada"


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

		# Criar itens (cada um com sequencia diferente para evitar constraint UNIQUE)
		with conexao(db_path) as con:
			for idx, pid in enumerate([prod1.id, prod2.id, prod3.id], start=1):
				con.execute(
					"INSERT INTO itens (chave_acesso, sequencia, descricao, produto_id) VALUES (?, ?, ?, ?)",
					["CHAVE1", idx, "AGUA", pid],
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

	def test_alias_ja_existe_para_destino_nao_conta_como_migrado(self, tmp_path: Path) -> None:
		"""Quando alias já existe para destino, não deve contar como migrado nem causar erro."""
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

			# Criar dois aliases para produto origem
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_origem.id, "AGUA DA PEDRA"],
			)
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_origem.id, "AGUA MINERAL"],
			)
			
			# Manualmente migrar um dos aliases para o destino (simula consolidação parcial anterior)
			con.execute(
				"UPDATE aliases_produtos SET produto_id = ? WHERE texto_original = ?",
				[prod_destino.id, "AGUA DA PEDRA"],
			)

		# Agora origem tem apenas "AGUA MINERAL" e destino tem "AGUA DA PEDRA"
		# Ao consolidar, apenas "AGUA MINERAL" deve ser migrado
		stats = consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			db_path=db_path,
		)

		# Apenas 1 alias deve ser contado como migrado (AGUA MINERAL)
		# AGUA DA PEDRA já pertencia ao destino
		assert stats["aliases_migrados"] == 1

		with conexao(db_path) as con:
			# Verificar que ambos os aliases agora pertencem ao destino
			aliases = con.execute(
				"SELECT texto_original FROM aliases_produtos WHERE produto_id = ? ORDER BY texto_original",
				[prod_destino.id],
			).fetchall()
			alias_texts = [row[0] for row in aliases]
			assert "AGUA DA PEDRA" in alias_texts
			assert "AGUA MINERAL" in alias_texts
			assert len(alias_texts) == 2

	def test_aliases_de_terceiros_nao_sao_afetados(self, tmp_path: Path) -> None:
		"""Verifica que aliases de terceiros produtos permanecem intactos durante consolidação."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			# Criar categoria
			con.execute(
				"INSERT INTO categorias (grupo, nome) VALUES (?, ?)",
				["Bebidas", "Água"],
			)

			# Criar três produtos
			prod_origem = _criar_produto(con, "Água Mineral", "Marca A", 1)
			prod_destino = _criar_produto(con, "Água com Gás", "Marca A", 1)
			prod_terceiro = _criar_produto(con, "Água Natural", "Marca B", 1)

			# Criar alias para produto origem
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_origem.id, "AGUA DA PEDRA"],
			)
			
			# Criar alias para terceiro produto (não relacionado à consolidação)
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_terceiro.id, "AGUA MINERAL 2L"],
			)

		# Consolidar origem->destino
		stats = consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			db_path=db_path,
		)

		# Apenas 1 alias migrado (AGUA DA PEDRA)
		assert stats["aliases_migrados"] == 1

		with conexao(db_path) as con:
			# Verificar que alias do terceiro produto permanece intacto
			alias_terceiro = con.execute(
				"SELECT COUNT(*) FROM aliases_produtos WHERE produto_id = ? AND texto_original = ?",
				[prod_terceiro.id, "AGUA MINERAL 2L"],
			).fetchone()
			assert alias_terceiro[0] == 1
			
			# Verificar que destino recebeu apenas o alias da origem
			aliases_destino = con.execute(
				"SELECT texto_original FROM aliases_produtos WHERE produto_id = ?",
				[prod_destino.id],
			).fetchall()
			assert len(aliases_destino) == 1
			assert aliases_destino[0][0] == "AGUA DA PEDRA"

	def test_migra_alias_sem_conflito(self, tmp_path: Path) -> None:
		"""Migra alias normalmente quando não há conflito."""
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

			# Criar alias único para produto origem
			con.execute(
				"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
				[prod_origem.id, "AGUA DA PEDRA"],
			)

		# Consolidar
		stats = consolidar_produtos(
			produto_id_origem=prod_origem.id,
			produto_id_destino=prod_destino.id,
			db_path=db_path,
		)

		# O alias deve ser migrado com sucesso
		assert stats["aliases_migrados"] == 1

		with conexao(db_path) as con:
			# Verificar que o alias foi migrado para o destino
			aliases_destino = con.execute(
				"SELECT COUNT(*) FROM aliases_produtos WHERE produto_id = ? AND texto_original = ?",
				[prod_destino.id, "AGUA DA PEDRA"],
			).fetchone()
			assert aliases_destino[0] == 1


class TestBuscarProdutos:
	"""Testes da função buscar_produtos."""

	def test_busca_por_nome(self, tmp_path: Path) -> None:
		"""Encontra produtos pelo nome."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute("INSERT INTO categorias (grupo, nome) VALUES (?, ?)", ["Bebidas", "Água"])
			_criar_produto(con, "Água Mineral", "Marca A", 1)
			_criar_produto(con, "Suco de Laranja", "Marca B", 1)

		resultados = buscar_produtos("Água", db_path=db_path)

		assert len(resultados) == 1
		assert resultados[0]["nome_base"] == "Água Mineral"

	def test_busca_por_marca(self, tmp_path: Path) -> None:
		"""Encontra produtos pela marca."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute("INSERT INTO categorias (grupo, nome) VALUES (?, ?)", ["Bebidas", "Água"])
			_criar_produto(con, "Água Mineral", "Pedra Azul", 1)
			_criar_produto(con, "Suco de Laranja", "Outra Marca", 1)

		resultados = buscar_produtos("Pedra", db_path=db_path)

		assert len(resultados) == 1
		assert resultados[0]["marca_base"] == "Pedra Azul"

	def test_busca_case_insensitive(self, tmp_path: Path) -> None:
		"""Busca ignora maiúsculas/minúsculas para caracteres ASCII."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute("INSERT INTO categorias (grupo, nome) VALUES (?, ?)", ["Bebidas", "Suco"])
			_criar_produto(con, "Suco de Laranja", "Marca A", 1)

		assert len(buscar_produtos("suco", db_path=db_path)) == 1
		assert len(buscar_produtos("SUCO", db_path=db_path)) == 1
		assert len(buscar_produtos("Suco de Laranja", db_path=db_path)) == 1
		assert len(buscar_produtos("sUcO dE lArAnJa", db_path=db_path)) == 1

	def test_busca_sem_resultados(self, tmp_path: Path) -> None:
		"""Retorna lista vazia quando não há resultados."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute("INSERT INTO categorias (grupo, nome) VALUES (?, ?)", ["Bebidas", "Água"])
			_criar_produto(con, "Água Mineral", "Marca A", 1)

		resultados = buscar_produtos("Inexistente", db_path=db_path)
		assert resultados == []

	def test_retorna_campos_corretos(self, tmp_path: Path) -> None:
		"""Verifica que os campos esperados estão presentes."""
		db_path = tmp_path / "test.db"

		with conexao(db_path) as con:
			con.execute("INSERT INTO categorias (grupo, nome) VALUES (?, ?)", ["Bebidas", "Água"])
			_criar_produto(con, "Água Mineral", "Marca A", 1)

		resultados = buscar_produtos("Água", db_path=db_path)

		assert len(resultados) == 1
		campos = resultados[0].keys()
		for campo in ("id", "nome_base", "marca_base", "categoria_nome", "qtd_aliases", "qtd_itens"):
			assert campo in campos
