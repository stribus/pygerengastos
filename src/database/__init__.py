"""Camada de persistência em DuckDB.

Este módulo fornece utilitários para criar o schema padrão do sistema,
persistir notas fiscais extraídas do portal da Receita Gaúcha e recuperar
informações para etapas posteriores (classificação, dashboards, etc.).

As funções expostas aqui não têm a pretensão de serem definitivas; elas
servem como primeira iteração da camada de armazenamento, permitindo que as
demais partes do projeto evoluam em paralelo."""

from __future__ import annotations

import csv
import json
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Optional, Sequence

import duckdb

from src.scrapers.receita_rs import NotaFiscal, NotaItem, Pagamento
from src.logger import setup_logging

logger = setup_logging("database")

_BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = _BASE_DIR / "data" / "gastos.duckdb"
DEFAULT_CATEGORIAS_CSV = _BASE_DIR / "data" / "categorias.csv"

_SCHEMA_DEFINITIONS: tuple[str, ...] = (
	"""
	CREATE TABLE IF NOT EXISTS notas (
		chave_acesso VARCHAR PRIMARY KEY,
		emitente_nome TEXT,
		emitente_cnpj TEXT,
		emitente_endereco TEXT,
		numero VARCHAR,
		serie VARCHAR,
		emissao_texto TEXT,
		emissao_iso TEXT,
		total_itens INTEGER,
		valor_total DECIMAL(18, 2),
		valor_pago DECIMAL(18, 2),
		tributos DECIMAL(18, 2),
		consumidor_cpf TEXT,
		consumidor_nome TEXT,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)
	""",
	"""
	CREATE SEQUENCE IF NOT EXISTS seq_categorias START 1
	""",
	"""
	CREATE TABLE IF NOT EXISTS categorias (
		id INTEGER PRIMARY KEY DEFAULT nextval('seq_categorias'),
		grupo TEXT NOT NULL,
		nome TEXT NOT NULL,
		ativo BOOLEAN DEFAULT TRUE,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (grupo, nome)
	)
	""",
	"""
	CREATE SEQUENCE IF NOT EXISTS seq_produtos START 1
	""",
	"""
	CREATE TABLE IF NOT EXISTS produtos (
		id INTEGER PRIMARY KEY DEFAULT nextval('seq_produtos'),
		nome_base TEXT NOT NULL,
		marca_base TEXT,
		categoria_id INTEGER REFERENCES categorias(id),
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (nome_base, marca_base)
	)
	""",
	"""
	CREATE SEQUENCE IF NOT EXISTS seq_aliases_produtos START 1
	""",
	"""
	CREATE TABLE IF NOT EXISTS aliases_produtos (
		id INTEGER PRIMARY KEY DEFAULT nextval('seq_aliases_produtos'),
		produto_id INTEGER NOT NULL REFERENCES produtos(id),
		texto_original TEXT NOT NULL,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (texto_original)
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS itens (
		chave_acesso VARCHAR,
		sequencia INTEGER,
		descricao TEXT,
		codigo VARCHAR,
		quantidade DECIMAL(18, 4),
		unidade VARCHAR,
		valor_unitario DECIMAL(18, 4),
		valor_total DECIMAL(18, 4),
		produto_id INTEGER REFERENCES produtos(id),
		produto_nome TEXT,
		produto_marca TEXT,
		categoria_sugerida TEXT,
		categoria_confirmada TEXT,
		fonte_classificacao TEXT,
		confianca_classificacao DOUBLE,
		atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		PRIMARY KEY (chave_acesso, sequencia)
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS pagamentos (
		chave_acesso VARCHAR,
		forma TEXT,
		valor DECIMAL(18, 2),
		PRIMARY KEY (chave_acesso, forma)
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS classificacoes_historico (
		chave_acesso VARCHAR,
		sequencia INTEGER,
		categoria TEXT NOT NULL,
		confianca DOUBLE,
		origem TEXT,
		modelo TEXT,
		observacoes TEXT,
		resposta_json TEXT,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)
	""",
)

_SCHEMA_MIGRATIONS: tuple[str, ...] = (
	"""
	ALTER TABLE itens ADD COLUMN IF NOT EXISTS produto_id INTEGER
	""",
	"""
	ALTER TABLE itens ADD COLUMN IF NOT EXISTS produto_nome TEXT
	""",
	"""
	ALTER TABLE itens ADD COLUMN IF NOT EXISTS produto_marca TEXT
	""",
)


@dataclass(slots=True)
class ItemParaClassificacao:
	chave_acesso: str
	sequencia: int
	descricao: str
	codigo: Optional[str]
	quantidade: Optional[Decimal]
	unidade: Optional[str]
	valor_unitario: Optional[Decimal]
	valor_total: Optional[Decimal]
	categoria_sugerida: Optional[str]
	categoria_confirmada: Optional[str]
	emitente_nome: Optional[str]
	emissao_iso: Optional[str]


@dataclass(slots=True)
class Categoria:
	id: Optional[int]
	grupo: str
	nome: str
	ativo: bool = True


@dataclass(slots=True)
class ProdutoPadronizado:
	id: Optional[int]
	nome_base: str
	marca_base: Optional[str]
	categoria_id: Optional[int]
	criado_em: Optional[str] = None
	atualizado_em: Optional[str] = None


@dataclass(slots=True)
class NotaParaRevisao:
	chave_acesso: str
	emitente_nome: str | None
	emissao_iso: str | None
	valor_total: Decimal | None
	total_itens: int
	itens_pendentes: int


@dataclass(slots=True)
class ItemNotaRevisao:
	chave_acesso: str
	sequencia: int
	descricao: str
	quantidade: Decimal | None
	valor_total: Decimal | None
	categoria_sugerida: str | None
	categoria_confirmada: str | None
	produto_nome: str | None
	produto_marca: str | None


_MARCAS_CONHECIDAS: dict[str, str] = {
	"TIO JOAO": "Tio João",
	"TIO JOÃO": "Tio João",
	"SADIA": "Sadia",
	"NESTLE": "Nestlé",
	"NESTLÉ": "Nestlé",
	"AMBEV": "Ambev",
	"COCA COLA": "Coca-Cola",
	"COCA-COLA": "Coca-Cola",
	"OMO": "Omo",
	"COLGATE": "Colgate",
	"DOVE": "Dove",
	"BRAHMA": "Brahma",
	"SKOL": "Skol",
	"HEINEKEN": "Heineken",
	"ITAMBE": "Itambé",
	"ITAMBÉ": "Itambé",
	"YOKI": "Yoki",
	"QUALY": "Qualy",
	"NINHO": "Ninho",
}

_STOPWORDS_DESCRICAO = {
	"DE",
	"DA",
	"DO",
	"DOS",
	"DAS",
	"COM",
	"SEM",
	"EM",
	"E",
}

_UNIDADES_REGEX = re.compile(
	r"\b\d+[.,]?\d*\s*(kg|g|mg|l|ml|un|und|cx|pct|pct\.|pack|lt|sache|sachê|cartela|garrafa|lata|pt|pacote)\b",
	re.IGNORECASE,
)

_PONTOS_REGEX = re.compile(r"[.,;:/\\-]+")


_SIMILARIDADE_MINIMA = 0.82


def normalizar_produto_descricao(descricao: str | None) -> tuple[str, Optional[str]]:
	"""Remove quantidades/unidades e detecta marcas conhecidas.

	Retorna uma tupla (nome_base, marca_base). Caso não seja possível normalizar,
	`nome_base` será string vazia e `marca_base` None.
	"""

	if not descricao:
		return "", None

	texto = _limpar_texto_curto(descricao)
	if not texto:
		return "", None

	texto_sem_pontos = _PONTOS_REGEX.sub(" ", texto)
	texto_sem_unidades = _UNIDADES_REGEX.sub(" ", texto_sem_pontos)
	texto_sem_unidades = re.sub(r"\s+", " ", texto_sem_unidades).strip()

	marca = None
	texto_para_procura = texto_sem_unidades.upper()
	for marcador, marca_normalizada in _MARCAS_CONHECIDAS.items():
		if marcador in texto_para_procura:
			marca = marca_normalizada
			texto_sem_unidades = re.sub(marcador, " ", texto_sem_unidades, flags=re.IGNORECASE)
			texto_para_procura = texto_sem_unidades.upper()
			break

	tokens = [
		token
		for token in texto_sem_unidades.split()
		if token.upper() not in _STOPWORDS_DESCRICAO and not token.isdigit()
	]

	nome_base = " ".join(tokens).strip()
	if not nome_base:
		nome_base = texto_sem_unidades.strip()

	return nome_base.title(), marca


def _resolver_caminho_banco(db_path: Path | str | None = None) -> Path:
	caminho = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
	caminho.parent.mkdir(parents=True, exist_ok=True)
	return caminho


def _aplicar_schema(con: duckdb.DuckDBPyConnection) -> None:
	for ddl in _SCHEMA_DEFINITIONS:
		con.execute(ddl)
	for ddl in _SCHEMA_MIGRATIONS:
		con.execute(ddl)


@contextmanager
def conexao(db_path: Path | str | None = None) -> Iterator[duckdb.DuckDBPyConnection]:
	"""Abre uma conexão com o DuckDB garantindo que o schema exista."""

	con = duckdb.connect(str(_resolver_caminho_banco(db_path)))
	try:
		_aplicar_schema(con)
		yield con
	except duckdb.Error as e:
		logger.error(f"Erro no banco de dados: {e}")
		raise
	finally:
		con.close()


def inicializar_banco(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
	"""Cria (se necessário) e retorna uma conexão pronta para uso."""

	con = duckdb.connect(str(_resolver_caminho_banco(db_path)))
	_aplicar_schema(con)
	logger.info("Schema do banco de dados inicializado com sucesso.")
	return con


def salvar_nota(nota: NotaFiscal, *, db_path: Path | str | None = None) -> None:
	"""Persiste a nota fiscal (e relações) em uma transação única."""

	with conexao(db_path) as con:
		con.execute("BEGIN TRANSACTION")
		try:
			_persistir_nota(con, nota)
			con.execute("COMMIT")
		except Exception:
			con.execute("ROLLBACK")
			raise


def listar_notas(
	*, limit: int = 50, offset: int = 0, db_path: Path | str | None = None
) -> list[dict[str, object]]:
	"""Retorna um resumo das notas persistidas para dashboards iniciais."""

	with conexao(db_path) as con:
		resultado = con.execute(
			"""
			SELECT
				chave_acesso,
				emitente_nome,
				emissao_iso,
				emissao_texto,
				valor_total,
				valor_pago,
				total_itens
			FROM notas
			ORDER BY emissao_iso DESC NULLS LAST, atualizado_em DESC
			LIMIT ? OFFSET ?
			""",
			[limit, offset],
		).fetchall()

	notas: list[dict[str, object]] = []
	for row in resultado:
		emissao_iso = row[2]
		emissao_texto = row[3]
		notas.append(
			{
				"chave_acesso": row[0],
				"emitente_nome": row[1],
				"emissao_iso": emissao_iso,
				"emissao_display": emissao_iso or emissao_texto,
				"valor_total": _para_decimal(row[4]),
				"valor_pago": _para_decimal(row[5]),
				"total_itens": row[6],
			}
		)
	return notas


def listar_notas_para_revisao(
	limit: int = 50,
	*,
	somente_pendentes: bool = False,
	db_path: Path | str | None = None,
) -> list[NotaParaRevisao]:
	"""Retorna notas com agregados para uso da interface de revisão manual."""

	db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
	if not db_file.exists():
		return []

	where_clause = "WHERE COALESCE(a.pendentes, 0) > 0" if somente_pendentes else ""
	query = f"""
		WITH itens_agg AS (
			SELECT
				chave_acesso,
				COUNT(*) AS total_itens,
				SUM(CASE WHEN categoria_confirmada IS NULL THEN 1 ELSE 0 END) AS pendentes
			FROM itens
			GROUP BY chave_acesso
		)
		SELECT
			n.chave_acesso,
			n.emitente_nome,
			n.emissao_iso,
			n.valor_total,
			COALESCE(a.total_itens, 0) AS total_itens,
			COALESCE(a.pendentes, 0) AS pendentes
		FROM notas n
		LEFT JOIN itens_agg a ON a.chave_acesso = n.chave_acesso
		{where_clause}
		ORDER BY n.emissao_iso DESC NULLS LAST, n.chave_acesso DESC
		LIMIT ?
	"""

	with duckdb.connect(str(db_file)) as con:
		rows = con.execute(query, [limit]).fetchall()

	return [
		NotaParaRevisao(
			chave_acesso=row[0],
			emitente_nome=row[1],
			emissao_iso=row[2],
			valor_total=_para_decimal(row[3]),
			total_itens=int(row[4] or 0),
			itens_pendentes=int(row[5] or 0),
		)
		for row in rows
	]


def listar_categorias(
	*, apenas_ativos: bool = True, db_path: Path | str | None = None
) -> list[Categoria]:
	"""Retorna as categorias disponíveis (opcionalmente apenas as ativas)."""

	query = "SELECT id, grupo, nome, COALESCE(ativo, TRUE) FROM categorias"
	if apenas_ativos:
		query += " WHERE COALESCE(ativo, TRUE)"
	query += " ORDER BY grupo, nome"

	with conexao(db_path) as con:
		rows = con.execute(query).fetchall()

	return [Categoria(id=row[0], grupo=row[1], nome=row[2], ativo=bool(row[3])) for row in rows]


def seed_categorias_csv(
	csv_path: Path | str | None = None,
	*, db_path: Path | str | None = None,
) -> int:
	"""Importa categorias a partir de um CSV (Grupo,Categoria).

	Linhas repetidas ou inválidas são ignoradas. Retorna o total de novas categorias inseridas.
	"""

	caminho = Path(csv_path) if csv_path is not None else DEFAULT_CATEGORIAS_CSV
	if not caminho.exists():
		raise FileNotFoundError(f"Arquivo de categorias não encontrado: {caminho}")

	with caminho.open(encoding="utf-8") as arquivo:
		reader = csv.DictReader(arquivo)
		registros: list[tuple[str, str]] = []
		for linha in reader:
			grupo = _limpar_texto_curto(linha.get("Grupo"))
			nome = _limpar_texto_curto(linha.get("Categoria"))
			if not grupo or not nome:
				continue
			registros.append((grupo, nome))

	if not registros:
		return 0

	inseridos = 0
	with conexao(db_path) as con:
		for grupo, nome in registros:
			existe = con.execute(
				"""
				SELECT 1 FROM categorias
				WHERE lower(grupo) = lower(?) AND lower(nome) = lower(?)
				""",
				[grupo, nome],
			).fetchone()
			if existe:
				continue
			con.execute(
				"""
				INSERT INTO categorias (grupo, nome)
				VALUES (?, ?)
				""",
				[grupo, nome],
			)
			inseridos += 1
	return inseridos


def listar_itens_para_classificacao(
	*, limit: int = 25, apenas_sem_categoria: bool = True, db_path: Path | str | None = None
) -> list[ItemParaClassificacao]:
	"""Retorna itens ainda não classificados para uso pela IA."""

	where_clauses = ["i.categoria_confirmada IS NULL"]
	if apenas_sem_categoria:
		where_clauses.append("i.categoria_sugerida IS NULL")
	where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

	with conexao(db_path) as con:
		rows = con.execute(
			f"""
			SELECT
				i.chave_acesso,
				i.sequencia,
				i.descricao,
				i.codigo,
				i.quantidade,
				i.unidade,
				i.valor_unitario,
				i.valor_total,
				i.categoria_sugerida,
				i.categoria_confirmada,
				n.emitente_nome,
				n.emissao_iso
			FROM itens i
			JOIN notas n ON n.chave_acesso = i.chave_acesso
			WHERE {where_sql}
			ORDER BY n.emissao_iso DESC, i.chave_acesso, i.sequencia
			LIMIT ?
			""",
			[limit],
		).fetchall()

	return [
		ItemParaClassificacao(
			chave_acesso=row[0],
			sequencia=row[1],
			descricao=row[2],
			codigo=row[3],
			quantidade=_para_decimal(row[4]),
			unidade=row[5],
			valor_unitario=_para_decimal(row[6]),
			valor_total=_para_decimal(row[7]),
			categoria_sugerida=row[8],
			categoria_confirmada=row[9],
			emitente_nome=row[10],
			emissao_iso=row[11],
		)
		for row in rows
	]


def registrar_classificacao_itens(
	dados: Sequence[Mapping[str, Any]],
	*,
	confirmar: bool = False,
	db_path: Path | str | None = None,
) -> None:
	"""Salva o histórico de classificação e atualiza a tabela de itens."""

	if not dados:
		return

	with conexao(db_path) as con:
		con.execute("BEGIN TRANSACTION")
		try:
			for item in dados:
				chave = item["chave_acesso"]
				seq = item["sequencia"]
				cat = item["categoria"]
				conf = item.get("confianca")
				origem = item.get("origem")
				modelo = item.get("modelo")
				obs = item.get("observacoes")
				resp_json = json.dumps(item.get("resposta_json"), ensure_ascii=False) if item.get("resposta_json") else None
				
				# Campos de produto padronizado
				prod_nome = item.get("produto_nome")
				prod_marca = item.get("produto_marca")

				# 1. Registrar histórico
				con.execute(
					"""
					INSERT INTO classificacoes_historico (
						chave_acesso, sequencia, categoria, confianca,
						origem, modelo, observacoes, resposta_json
					) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
					""",
					[chave, seq, cat, conf, origem, modelo, obs, resp_json],
				)

				# 2. Atualizar item
				# Se confirmar=True, gravamos em categoria_confirmada
				# Caso contrário, apenas em categoria_sugerida
				coluna_cat = "categoria_confirmada" if confirmar else "categoria_sugerida"
				
				# Se tivermos info de produto, tentamos resolver/criar o produto
				produto_id = None
				if prod_nome:
					produto_obj = _resolver_produto_por_nome_marca(con, prod_nome, prod_marca, cat)
					if produto_obj:
						produto_id = produto_obj.id

				# Montar update dinâmico
				sql_update = f"""
					UPDATE itens
					SET
						{coluna_cat} = ?,
						fonte_classificacao = ?,
						confianca_classificacao = ?,
						atualizado_em = CURRENT_TIMESTAMP
				"""
				params = [cat, origem, conf]

				if produto_id:
					sql_update += ", produto_id = ?, produto_nome = ?, produto_marca = ?"
					params.extend([produto_id, prod_nome, prod_marca])

				sql_update += " WHERE chave_acesso = ? AND sequencia = ?"
				params.extend([chave, seq])

				con.execute(sql_update, params)

			con.execute("COMMIT")
		except Exception:
			con.execute("ROLLBACK")
			raise


def _resolver_produto_por_nome_marca(
	con: duckdb.DuckDBPyConnection,
	nome: str,
	marca: str | None,
	categoria_nome: str | None
) -> ProdutoPadronizado | None:
	"""Busca ou cria um produto com base no nome e marca normalizados."""
	
	nome = nome.strip()
	if not nome:
		return None
		
	marca = marca.strip() if marca else None
	
	# Tenta achar exato
	query_busca = "SELECT id, nome_base, marca_base, categoria_id FROM produtos WHERE lower(nome_base) = lower(?)"
	params_busca = [nome]
	
	if marca:
		query_busca += " AND lower(marca_base) = lower(?)"
		params_busca.append(marca)
	else:
		query_busca += " AND marca_base IS NULL"
		
	row = con.execute(query_busca, params_busca).fetchone()
	if row:
		return ProdutoPadronizado(id=row[0], nome_base=row[1], marca_base=row[2], categoria_id=row[3])
		
	# Se não achou, cria
	categoria_id = None
	if categoria_nome:
		cat_row = con.execute("SELECT id FROM categorias WHERE lower(nome) = lower(?)", [categoria_nome]).fetchone()
		if cat_row:
			categoria_id = cat_row[0]
			
	try:
		con.execute(
			"""
			INSERT INTO produtos (nome_base, marca_base, categoria_id)
			VALUES (?, ?, ?)
			""",
			[nome, marca, categoria_id]
		)
		# Recupera ID gerado
		# DuckDB suporta RETURNING id, mas para compatibilidade garantida fazemos select
		# Na verdade, com RETURNING é melhor:
		# row_id = con.execute("INSERT ... RETURNING id").fetchone()
		# Mas vamos manter o padrão de busca pós-insert se o driver antigo não suportar
		
		# Vamos tentar buscar de novo
		row = con.execute(query_busca, params_busca).fetchone()
		if row:
			return ProdutoPadronizado(id=row[0], nome_base=row[1], marca_base=row[2], categoria_id=row[3])
			
	except Exception:
		# Pode ter havido concorrência
		pass
		
	return None


def _persistir_nota(con: duckdb.DuckDBPyConnection, nota: NotaFiscal) -> None:
	con.execute(
		"""
		INSERT INTO notas (
			chave_acesso,
			emitente_nome,
			emitente_cnpj,
			emitente_endereco,
			numero,
			serie,
			emissao_texto,
			emissao_iso,
			total_itens,
			valor_total,
			valor_pago,
			tributos,
			consumidor_cpf,
			consumidor_nome
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT (chave_acesso) DO UPDATE SET
			atualizado_em = now()
		""",
		[
			nota.chave_acesso,
			nota.emitente_nome,
			nota.emitente_cnpj,
			nota.emitente_endereco,
			nota.numero,
			nota.serie,
			nota.emissao,
			_converter_data_iso(nota.emissao),
			nota.total_itens,
			_decimal_para_str(nota.valor_total),
			_decimal_para_str(nota.valor_pago),
			_decimal_para_str(nota.tributos),
			nota.consumidor_cpf,
			nota.consumidor_nome,
		],
	)

	# Remove itens e pagamentos antigos para substituir (estratégia simples de replace)
	con.execute("DELETE FROM itens WHERE chave_acesso = ?", [nota.chave_acesso])
	con.execute("DELETE FROM pagamentos WHERE chave_acesso = ?", [nota.chave_acesso])

	_persistir_itens(con, nota.chave_acesso, nota.itens)
	_persistir_pagamentos(con, nota.chave_acesso, nota.pagamentos)


def _persistir_itens(
	con: duckdb.DuckDBPyConnection, chave: str, itens: Iterable[NotaItem]
) -> None:
	for sequencia, item in enumerate(itens, start=1):
		produto = _resolver_produto_por_descricao(con, item.descricao)
		produto_id = produto.id if produto else None
		produto_nome = produto.nome_base if produto else None
		produto_marca = produto.marca_base if produto else None
		con.execute(
			"""
			INSERT INTO itens (
				chave_acesso,
				sequencia,
				descricao,
				codigo,
				quantidade,
				unidade,
				valor_unitario,
				valor_total,
				produto_id,
				produto_nome,
				produto_marca,
				categoria_sugerida,
				categoria_confirmada,
				fonte_classificacao,
				confianca_classificacao,
				atualizado_em
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, now())
			""",
			[
				chave,
				sequencia,
				item.descricao,
				item.codigo,
				_decimal_para_str(item.quantidade),
				item.unidade,
				_decimal_para_str(item.valor_unitario),
				_decimal_para_str(item.valor_total),
				produto_id,
				produto_nome,
				produto_marca,
			],
		)

		# Se resolveu produto, registra embedding se necessário (futuro)
		if produto:
			_registrar_embeddings_para_produto(produto)


def _persistir_pagamentos(
	con: duckdb.DuckDBPyConnection, chave: str, pagamentos: Iterable[Pagamento]
) -> None:
	for pgto in pagamentos:
		con.execute(
			"""
			INSERT INTO pagamentos (chave_acesso, forma, valor)
			VALUES (?, ?, ?)
			""",
			[chave, pgto.forma, _decimal_para_str(pgto.valor)],
		)


def _resolver_produto_por_descricao(
	con: duckdb.DuckDBPyConnection, descricao: str
) -> ProdutoPadronizado | None:
	"""Tenta encontrar um produto existente via alias ou cria um novo baseado na descrição."""
	
	# 1. Busca exata na tabela de aliases
	row = con.execute(
		"""
		SELECT p.id, p.nome_base, p.marca_base, p.categoria_id
		FROM aliases_produtos a
		JOIN produtos p ON p.id = a.produto_id
		WHERE lower(a.texto_original) = lower(?)
		""",
		[descricao.strip()]
	).fetchone()
	
	if row:
		return ProdutoPadronizado(id=row[0], nome_base=row[1], marca_base=row[2], categoria_id=row[3])

	# 2. Normaliza descrição
	nome_base, marca_base = normalizar_produto_descricao(descricao)
	if not nome_base:
		return None

	# 3. Busca na tabela de produtos
	query = "SELECT id, nome_base, marca_base, categoria_id FROM produtos WHERE lower(nome_base) = lower(?)"
	params = [nome_base]
	if marca_base:
		query += " AND lower(marca_base) = lower(?)"
		params.append(marca_base)
	else:
		query += " AND marca_base IS NULL"
		
	row = con.execute(query, params).fetchone()
	
	produto_id = None
	if row:
		produto = ProdutoPadronizado(id=row[0], nome_base=row[1], marca_base=row[2], categoria_id=row[3])
		produto_id = row[0]
	else:
		# 4. Cria novo produto (sem categoria por enquanto)
		try:
			con.execute(
				"INSERT INTO produtos (nome_base, marca_base) VALUES (?, ?)",
				[nome_base, marca_base]
			)
			# Recupara ID (assumindo sequencial e sem concorrência alta no desktop app)
			row_id = con.execute("SELECT id FROM produtos WHERE nome_base = ? AND (marca_base = ? OR (marca_base IS NULL AND ? IS NULL))", [nome_base, marca_base, marca_base]).fetchone()
			if row_id:
				produto_id = row_id[0]
				produto = ProdutoPadronizado(id=produto_id, nome_base=nome_base, marca_base=marca_base, categoria_id=None)
			else:
				return None
		except Exception:
			return None

	# 5. Cria alias para aprendizado futuro
	try:
		con.execute(
			"INSERT INTO aliases_produtos (produto_id, texto_original) VALUES (?, ?)",
			[produto_id, descricao.strip()]
		)
	except Exception:
		pass # Alias já existe ou erro de constraint
		
	return produto


def _registrar_embeddings_para_produto(produto: ProdutoPadronizado) -> None:
	"""Gera e salva embeddings para o produto no ChromaDB (se configurado)."""
	# Importação local para evitar ciclo ou erro se dependências de ML não estiverem prontas
	try:
		from src.classifiers.embeddings import upsert_produto_embedding
		upsert_produto_embedding(
			produto_id=produto.id, # type: ignore
			nome=produto.nome_base,
			marca=produto.marca_base
		)
	except ImportError:
		pass
	except Exception:
		# Logar erro silenciosamente ou warning
		pass


def _converter_data_iso(texto: str | None) -> str | None:
	if not texto:
		return None
	# Tenta formatos comuns: DD/MM/YYYY HH:MM:SS
	# Exemplo: 26/12/2023 15:34:12
	try:
		dt = datetime.strptime(texto.strip(), "%d/%m/%Y %H:%M:%S")
		return dt.isoformat()
	except ValueError:
		pass
	
	try:
		dt = datetime.strptime(texto.strip(), "%d/%m/%Y")
		return dt.date().isoformat()
	except ValueError:
		return None


def _decimal_para_str(valor: Decimal | None) -> str | None:
	if valor is None:
		return None
	return str(valor)


def _para_decimal(valor: Any) -> Decimal | None:
	if valor is None:
		return None
	if isinstance(valor, Decimal):
		return valor
	if isinstance(valor, (int, float)):
		return Decimal(str(valor))
	try:
		return Decimal(str(valor))
	except:
		return None


def _limpar_texto_curto(texto: Any) -> str | None:
	if not texto:
		return None
	s = str(texto).strip()
	return s if s else None


def obter_categoria_de_produto(produto_id: int, *, db_path: Path | str | None = None) -> str | None:
	"""Retorna o nome da categoria associada a um produto."""
	with conexao(db_path) as con:
		row = con.execute(
			"""
			SELECT c.nome
			FROM produtos p
			JOIN categorias c ON c.id = p.categoria_id
			WHERE p.id = ?
			""",
			[produto_id],
		).fetchone()
		return row[0] if row else None


def obter_kpis_gerais(*, db_path: Path | str | None = None) -> dict[str, Any]:
	"""Retorna KPIs gerais para o dashboard."""
	with conexao(db_path) as con:
		# Total de notas
		total_notas = con.execute("SELECT COUNT(*) FROM notas").fetchone()[0]
		
		# Total gasto (soma de valor_total das notas)
		total_gasto = con.execute("SELECT SUM(valor_total) FROM notas").fetchone()[0]
		
		# Itens pendentes de classificação
		itens_pendentes = con.execute(
			"SELECT COUNT(*) FROM itens WHERE categoria_confirmada IS NULL"
		).fetchone()[0]

	return {
		"total_notas": total_notas or 0,
		"total_gasto": _para_decimal(total_gasto) or Decimal("0.00"),
		"itens_pendentes": itens_pendentes or 0,
	}


def obter_resumo_mensal(*, db_path: Path | str | None = None) -> list[dict[str, Any]]:
	"""Retorna gastos agrupados por mês (YYYY-MM)."""
	with conexao(db_path) as con:
		rows = con.execute(
			"""
			SELECT strftime(CAST(emissao_iso AS DATE), '%Y-%m') as mes, SUM(valor_total)
			FROM notas
			WHERE emissao_iso IS NOT NULL
			GROUP BY 1
			ORDER BY 1 DESC
			LIMIT 12
			"""
		).fetchall()
	
	return [
		{"mes": row[0], "total": _para_decimal(row[1]) or Decimal("0.00")}
		for row in rows
	]


def obter_gastos_por_categoria(*, mes_iso: str | None = None, db_path: Path | str | None = None) -> list[dict[str, Any]]:
	"""Retorna gastos agrupados por categoria. Opcionalmente filtra por mês."""
	
	where_clause = "WHERE i.categoria_confirmada IS NOT NULL"
	params = []
	
	if mes_iso:
		where_clause += " AND strftime(CAST(n.emissao_iso AS DATE), '%Y-%m') = ?"
		params.append(mes_iso)
		
	query = f"""
		SELECT i.categoria_confirmada, SUM(i.valor_total)
		FROM itens i
		JOIN notas n ON n.chave_acesso = i.chave_acesso
		{where_clause}
		GROUP BY 1
		ORDER BY 2 DESC
	"""
	
	with conexao(db_path) as con:
		rows = con.execute(query, params).fetchall()
		
	return [
		{"categoria": row[0], "total": _para_decimal(row[1]) or Decimal("0.00")}
		for row in rows
	]
