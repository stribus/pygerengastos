"""Testes para validar atualização de categoria em produtos."""

import tempfile
from pathlib import Path

import pytest

from src.database import (
	conexao,
	inicializar_banco,
	seed_categorias_csv,
	registrar_classificacao_itens,
)
from src.logger import setup_logging

logger = setup_logging("test_produto_categoria_update")


@pytest.fixture
def db_teste():
	"""Cria um banco temporário para testes."""
	with tempfile.TemporaryDirectory() as temp_dir:
		db_path = Path(temp_dir) / "test.db"
		con = inicializar_banco(db_path)
		con.close()  # Fecha a conexão retornada por inicializar_banco
		seed_categorias_csv(db_path=db_path)
		yield db_path


def test_produto_sem_categoria_recebe_categoria(db_teste):
	"""Testa que um produto sem categoria recebe categoria na primeira classificação."""
	
	# 1. Criar produto sem categoria
	with conexao(db_teste) as con:
		con.execute(
			"INSERT INTO produtos (nome_base, marca_base, categoria_id) VALUES (?, ?, ?)",
			["Arroz", "Tio João", None]
		)
		produto_row = con.execute(
			"SELECT id, categoria_id FROM produtos WHERE nome_base = ? AND marca_base = ?",
			["Arroz", "Tio João"]
		).fetchone()
		assert produto_row is not None
		produto_id, categoria_inicial = produto_row[0], produto_row[1]
		assert categoria_inicial is None, "Produto deve iniciar sem categoria"
		
		# 2. Criar nota e item para classificar
		con.execute(
			"""
			INSERT INTO notas (chave_acesso, emitente_nome, emissao_iso, valor_total)
			VALUES (?, ?, ?, ?)
			""",
			["43250100000000000000000000000000000000000001", "Mercado Teste", "2025-12-07", "10.00"]
		)
		con.execute(
			"""
			INSERT INTO itens (chave_acesso, sequencia, descricao, quantidade, valor_total)
			VALUES (?, ?, ?, ?, ?)
			""",
			["43250100000000000000000000000000000000000001", 1, "Arroz Tio João 1kg", 1, 10.00]
		)
	
	# 3. Classificar item com categoria
	dados = [{
		"chave_acesso": "43250100000000000000000000000000000000000001",
		"sequencia": 1,
		"categoria": "Arroz",
		"confianca": 0.95,
		"origem": "teste",
		"modelo": "manual",
		"produto_nome": "Arroz",
		"produto_marca": "Tio João",
	}]
	
	registrar_classificacao_itens(dados, confirmar=True, db_path=db_teste)
	
	# 4. Verificar que o produto agora tem categoria
	with conexao(db_teste) as con:
		produto_atualizado = con.execute(
			"SELECT categoria_id FROM produtos WHERE id = ?",
			[produto_id]
		).fetchone()
		assert produto_atualizado is not None
		assert produto_atualizado[0] is not None, "Produto deve ter recebido categoria"
		
		# Verifica que a categoria é "Arroz"
		categoria_nome = con.execute(
			"SELECT nome FROM categorias WHERE id = ?",
			[produto_atualizado[0]]
		).fetchone()
		assert categoria_nome[0] == "Arroz"


def test_produto_com_categoria_nao_sobrescreve(db_teste):
	"""Testa que um produto com categoria não é sobrescrito por categoria nula."""
	
	# 1. Criar produto COM categoria
	with conexao(db_teste) as con:
		# Obter ID da categoria Arroz
		cat_row = con.execute(
			"SELECT id FROM categorias WHERE nome = ?",
			["Arroz"]
		).fetchone()
		categoria_arroz_id = cat_row[0]
		
		con.execute(
			"INSERT INTO produtos (nome_base, marca_base, categoria_id) VALUES (?, ?, ?)",
			["Feijão", "Camil", categoria_arroz_id]
		)
		produto_row = con.execute(
			"SELECT id, categoria_id FROM produtos WHERE nome_base = ? AND marca_base = ?",
			["Feijão", "Camil"]
		).fetchone()
		produto_id, categoria_inicial = produto_row[0], produto_row[1]
		assert categoria_inicial == categoria_arroz_id, "Produto deve ter categoria Arroz"
		
		# 2. Criar nota e item
		con.execute(
			"""
			INSERT INTO notas (chave_acesso, emitente_nome, emissao_iso, valor_total)
			VALUES (?, ?, ?, ?)
			""",
			["43250100000000000000000000000000000000000002", "Mercado Teste", "2025-12-07", "8.00"]
		)
		con.execute(
			"""
			INSERT INTO itens (chave_acesso, sequencia, descricao, quantidade, valor_total)
			VALUES (?, ?, ?, ?, ?)
			""",
			["43250100000000000000000000000000000000000002", 1, "Feijão Camil 1kg", 1, 8.00]
		)
	
	# 3. Tentar classificar com categoria None (ou sem produto_nome)
	dados = [{
		"chave_acesso": "43250100000000000000000000000000000000000002",
		"sequencia": 1,
		"categoria": "Arroz",  # Categoria válida, mas não vamos passar produto info
		"confianca": 0.90,
		"origem": "teste",
		"modelo": "manual",
		# Sem produto_nome, não deve afetar o produto existente
	}]
	
	registrar_classificacao_itens(dados, confirmar=True, db_path=db_teste)
	
	# 4. Verificar que o produto mantém a categoria original
	with conexao(db_teste) as con:
		produto_final = con.execute(
			"SELECT categoria_id FROM produtos WHERE id = ?",
			[produto_id]
		).fetchone()
		assert produto_final[0] == categoria_arroz_id, "Categoria não deve ter mudado"


def test_produto_atualiza_categoria_se_receber_nova_valida(db_teste):
	"""Testa que produto sem categoria recebe categoria quando classificado."""
	
	# 1. Criar produto sem categoria
	with conexao(db_teste) as con:
		con.execute(
			"INSERT INTO produtos (nome_base, marca_base, categoria_id) VALUES (?, ?, ?)",
			["Macarrão", "Barilla", None]
		)
		produto_row = con.execute(
			"SELECT id FROM produtos WHERE nome_base = ? AND marca_base = ?",
			["Macarrão", "Barilla"]
		).fetchone()
		produto_id = produto_row[0]
		
		# 2. Criar nota e item
		con.execute(
			"""
			INSERT INTO notas (chave_acesso, emitente_nome, emissao_iso, valor_total)
			VALUES (?, ?, ?, ?)
			""",
			["43250100000000000000000000000000000000000003", "Mercado Teste", "2025-12-07", "12.00"]
		)
		con.execute(
			"""
			INSERT INTO itens (chave_acesso, sequencia, descricao, quantidade, valor_total)
			VALUES (?, ?, ?, ?, ?)
			""",
			["43250100000000000000000000000000000000000003", 1, "Macarrão Barilla 500g", 1, 12.00]
		)
	
	# 3. Classificar com categoria válida E produto_nome
	dados = [{
		"chave_acesso": "43250100000000000000000000000000000000000003",
		"sequencia": 1,
		"categoria": "Macarrão e Massas",
		"confianca": 0.92,
		"origem": "teste",
		"modelo": "manual",
		"produto_nome": "Macarrão",
		"produto_marca": "Barilla",
	}]
	
	registrar_classificacao_itens(dados, confirmar=True, db_path=db_teste)
	
	# 4. Verificar que produto recebeu categoria
	with conexao(db_teste) as con:
		produto_final = con.execute(
			"SELECT c.nome FROM produtos p JOIN categorias c ON c.id = p.categoria_id WHERE p.id = ?",
			[produto_id]
		).fetchone()
		assert produto_final is not None
		assert produto_final[0] == "Macarrão e Massas", "Produto deve ter categoria Macarrão e Massas"
