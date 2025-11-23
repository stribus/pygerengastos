"""Camada de persistência em DuckDB.

Este módulo fornece utilitários para criar o schema padrão do sistema,
persistir notas fiscais extraídas do portal da Receita Gaúcha e recuperar
informações para etapas posteriores (classificação, dashboards, etc.).
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
	CREATE SEQUENCE IF NOT EXISTS seq_estabelecimentos START 1
	""",
	"""
	CREATE TABLE IF NOT EXISTS estabelecimentos (
		id INTEGER PRIMARY KEY DEFAULT nextval('seq_estabelecimentos'),
		nome TEXT,
		cnpj TEXT,
		cnpj_normalizado TEXT,
		endereco TEXT,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (cnpj_normalizado)
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS datas_referencia (
		data_iso DATE PRIMARY KEY,
		ano SMALLINT NOT NULL,
		mes SMALLINT NOT NULL,
		dia SMALLINT NOT NULL,
		ano_mes TEXT NOT NULL,
		trimestre SMALLINT NOT NULL,
		semana SMALLINT NOT NULL,
		nome_mes TEXT NOT NULL,
		nome_dia_semana TEXT NOT NULL,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	)
	""",
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
		emissao_data DATE,
		estabelecimento_id INTEGER REFERENCES estabelecimentos(id),
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
	CREATE SEQUENCE IF NOT EXISTS seq_revisoes_manuais START 1
	""",
	"""
	CREATE TABLE IF NOT EXISTS revisoes_manuais (
		id INTEGER PRIMARY KEY DEFAULT nextval('seq_revisoes_manuais'),
		chave_acesso VARCHAR NOT NULL,
		sequencia INTEGER NOT NULL,
		categoria TEXT,
		produto_nome TEXT,
		produto_marca TEXT,
		usuario TEXT,
		observacoes TEXT,
		origem TEXT,
		confirmado BOOLEAN DEFAULT FALSE,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
		categoria_sugerida_id INTEGER REFERENCES categorias(id),
		categoria_confirmada_id INTEGER REFERENCES categorias(id),
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
	"""
	CREATE VIEW IF NOT EXISTS vw_itens_padronizados AS
	SELECT
		i.chave_acesso,
		i.sequencia,
		n.emissao_data AS data_emissao,
		d.ano,
		d.mes,
		d.dia,
		d.ano_mes,
		d.trimestre,
		d.semana,
		d.nome_mes,
		d.nome_dia_semana,
		n.estabelecimento_id,
		e.nome AS estabelecimento_nome,
		e.cnpj AS estabelecimento_cnpj,
		e.endereco AS estabelecimento_endereco,
		COALESCE(i.categoria_confirmada, i.categoria_sugerida) AS categoria_final,
		COALESCE(i.categoria_confirmada_id, i.categoria_sugerida_id) AS categoria_final_id,
		i.quantidade,
		i.valor_unitario,
		i.valor_total,
		i.produto_id,
		i.produto_nome,
		i.produto_marca
	FROM itens i
	JOIN notas n ON n.chave_acesso = i.chave_acesso
	LEFT JOIN datas_referencia d ON d.data_iso = n.emissao_data
	LEFT JOIN estabelecimentos e ON e.id = n.estabelecimento_id
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
	"""
	ALTER TABLE notas ADD COLUMN IF NOT EXISTS emissao_data DATE
	""",
	"""
	ALTER TABLE notas ADD COLUMN IF NOT EXISTS estabelecimento_id INTEGER
	""",
	"""
	ALTER TABLE itens ADD COLUMN IF NOT EXISTS categoria_sugerida_id INTEGER
	""",
	"""
	ALTER TABLE itens ADD COLUMN IF NOT EXISTS categoria_confirmada_id INTEGER
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


@dataclass(slots=True)
class ItemPadronizado:
	chave_acesso: str
	sequencia: int
	data_emissao: str | None
	ano: int | None
	mes: int | None
	ano_mes: str | None
	estabelecimento_id: int | None
	estabelecimento_nome: str | None
	estabelecimento_cnpj: str | None
	categoria: str | None
	categoria_id: int | None
	valor_total: Decimal | None
	quantidade: Decimal | None


@dataclass(slots=True)
class RevisaoManual:
	chave_acesso: str
	sequencia: int
	categoria: str | None
	produto_nome: str | None
	produto_marca: str | None
	usuario: str | None
	observacoes: str | None
	origem: str | None
	confirmado: bool
	criado_em: str | None


def _criar_produto(
	con: duckdb.DuckDBPyConnection,
	nome_base: str,
	marca_base: str | None = None,
	categoria_id: int | None = None,
) -> ProdutoPadronizado:
	"""Cria (ou retorna) um produto padronizado para uso interno e testes."""
	nome = (nome_base or "").strip()
	marca = marca_base.strip() if marca_base else None
	if not nome:
		raise ValueError("nome_base não pode ser vazio")
	try:
		row = con.execute(
			"""
			INSERT INTO produtos (nome_base, marca_base, categoria_id)
			VALUES (?, ?, ?)
			RETURNING id, nome_base, marca_base, categoria_id, criado_em, atualizado_em
			""",
			[nome, marca, categoria_id],
		).fetchone()
	except duckdb.Error:
		row = con.execute(
			"""
			SELECT id, nome_base, marca_base, categoria_id, criado_em, atualizado_em
			FROM produtos
			WHERE lower(nome_base) = lower(?) AND COALESCE(marca_base, '') = COALESCE(?, '')
			ORDER BY id DESC
			LIMIT 1
			""",
			[nome, marca or ""],
		).fetchone()
	if not row:
		raise RuntimeError("Não foi possível criar ou recuperar o produto")
	return ProdutoPadronizado(
		id=row[0],
		nome_base=row[1],
		marca_base=row[2],
		categoria_id=row[3],
		criado_em=row[4],
		atualizado_em=row[5],
	)


def _buscar_produto_por_descricao_similaridade(
	con: duckdb.DuckDBPyConnection,
	descricao: str,
	*,
	score_minimo: float | None = None,
	top_k: int = 3,
) -> ProdutoPadronizado | None:
	"""Busca um produto por similaridade via embeddings Chroma."""
	texto = (descricao or "").strip()
	if not texto:
		return None
	try:
		from src.classifiers.embeddings import buscar_produtos_semelhantes
	except ImportError:
		return None
	limite = score_minimo if score_minimo is not None else _SIMILARIDADE_MINIMA
	matches = buscar_produtos_semelhantes(texto, top_k=top_k)
	for match in matches:
		produto_id = match.get("produto_id")
		if produto_id in (None, ""):
			continue
		try:
			produto_id_int = int(produto_id)
		except (TypeError, ValueError):
			continue
		score = match.get("score") or match.get("similaridade")
		if score is None or float(score) < limite:
			continue
		row = con.execute(
			"""
			SELECT id, nome_base, marca_base, categoria_id, criado_em, atualizado_em
			FROM produtos
			WHERE id = ?
			""",
			[produto_id_int],
		).fetchone()
		if row:
			return ProdutoPadronizado(
				id=row[0],
				nome_base=row[1],
				marca_base=row[2],
				categoria_id=row[3],
				criado_em=row[4],
				atualizado_em=row[5],
			)
	return None


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

_SIMILARIDADE_MINIMA = 0.82

_UNIDADES_REGEX = re.compile(
	r"\b\d+[.,]?\d*\s*(kg|g|mg|l|ml|un|und|cx|pct|pct\.|pack|lt|sache|sachê|cartela|garrafa|lata|pt|pacote)\b",
	re.IGNORECASE,
)

_PONTOS_REGEX = re.compile(r"[.,;:/\\-]+")

_MESES_PT = (
	"janeiro",
	"fevereiro",
	"março",
	"abril",
	"maio",
	"junho",
	"julho",
	"agosto",
	"setembro",
	"outubro",
	"novembro",
	"dezembro",
)

_DIAS_SEMANA_PT = (
	"segunda-feira",
	"terça-feira",
	"quarta-feira",
	"quinta-feira",
	"sexta-feira",
	"sábado",
	"domingo",
)


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


def carregar_nota(
	chave_acesso: str,
	*,
	db_path: Path | str | None = None,
) -> NotaFiscal | None:
	"""Reconstrói uma nota fiscal completa a partir do DuckDB."""
	with conexao(db_path) as con:
		nota_row = con.execute(
			"""
			SELECT
				emitente_nome,
				emitente_cnpj,
				emitente_endereco,
				numero,
				serie,
				emissao_texto,
				emissao_iso,
				emissao_data,
				total_itens,
				valor_total,
				valor_pago,
				tributos,
				consumidor_cpf,
				consumidor_nome
			FROM notas
			WHERE chave_acesso = ?
			""",
			[chave_acesso],
		).fetchone()
		if nota_row is None:
			return None
		itens_rows = con.execute(
			"""
			SELECT descricao, codigo, quantidade, unidade, valor_unitario, valor_total
			FROM itens
			WHERE chave_acesso = ?
			ORDER BY sequencia
			""",
			[chave_acesso],
		).fetchall()
		pagamentos_rows = con.execute(
			"""
			SELECT forma, valor
			FROM pagamentos
			WHERE chave_acesso = ?
			""",
			[chave_acesso],
		).fetchall()

	itens = [
		NotaItem(
			descricao=row[0],
			codigo=row[1],
			quantidade=_para_decimal(row[2]) or Decimal("0"),
			unidade=row[3] or "",
			valor_unitario=_para_decimal(row[4]) or Decimal("0"),
			valor_total=_para_decimal(row[5]) or Decimal("0"),
		)
		for row in itens_rows
	]
	pagamentos = [
		Pagamento(forma=row[0], valor=_para_decimal(row[1]) or Decimal("0"))
		for row in pagamentos_rows
	]

	return NotaFiscal(
		chave_acesso=chave_acesso,
		emitente_nome=nota_row[0],
		emitente_cnpj=nota_row[1],
		emitente_endereco=nota_row[2],
		numero=nota_row[3],
		serie=nota_row[4],
		emissao=nota_row[5] or nota_row[6] or nota_row[7],
		itens=itens,
		total_itens=nota_row[8],
		valor_total=_para_decimal(nota_row[9]),
		valor_pago=_para_decimal(nota_row[10]),
		tributos=_para_decimal(nota_row[11]),
		consumidor_cpf=nota_row[12],
		consumidor_nome=nota_row[13],
		pagamentos=pagamentos,
	)


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


def listar_itens_para_revisao(
	chave_acesso: str,
	*,
	somente_pendentes: bool = False,
	db_path: Path | str | None = None,
) -> list[ItemNotaRevisao]:
	"""Retorna itens de uma nota para revisão manual via UI."""

	if not chave_acesso:
		return []

	condicoes = ["chave_acesso = ?"]
	params: list[object] = [chave_acesso]
	if somente_pendentes:
		condicoes.append("categoria_confirmada IS NULL")
	query = f"""
		SELECT
			chave_acesso,
			sequencia,
			descricao,
			quantidade,
			valor_total,
			categoria_sugerida,
			categoria_confirmada,
			produto_nome,
			produto_marca
		FROM itens
		WHERE {' AND '.join(condicoes)}
		ORDER BY sequencia
	"""

	with conexao(db_path) as con:
		rows = con.execute(query, params).fetchall()

	return [
		ItemNotaRevisao(
			chave_acesso=row[0],
			sequencia=int(row[1]),
			descricao=row[2],
			quantidade=_para_decimal(row[3]),
			valor_total=_para_decimal(row[4]),
			categoria_sugerida=row[5],
			categoria_confirmada=row[6],
			produto_nome=row[7],
			produto_marca=row[8],
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


def listar_itens_padronizados(
	*,
	data_inicio: str | None = None,
	data_fim: str | None = None,
	categoria: str | None = None,
	estabelecimento_id: int | None = None,
	limit: int | None = 200,
	db_path: Path | str | None = None,
) -> list[ItemPadronizado]:
	"""Retorna itens com datas, estabelecimentos e categorias padronizados."""
	filtros: list[str] = ["1=1"]
	params: list[object] = []
	if data_inicio:
		filtros.append("data_emissao >= ?")
		params.append(data_inicio)
	if data_fim:
		filtros.append("data_emissao <= ?")
		params.append(data_fim)
	if categoria:
		filtros.append("lower(categoria_final) = lower(?)")
		params.append(categoria)
	if estabelecimento_id is not None:
		filtros.append("estabelecimento_id = ?")
		params.append(estabelecimento_id)
	where_clause = " AND ".join(filtros)
	query = f"""
		SELECT
			chave_acesso,
			sequencia,
			data_emissao,
			ano,
			mes,
			ano_mes,
			estabelecimento_id,
			estabelecimento_nome,
			estabelecimento_cnpj,
			categoria_final,
			categoria_final_id,
			quantidade,
			valor_total
		FROM vw_itens_padronizados
		WHERE {where_clause}
		ORDER BY data_emissao DESC NULLS LAST, chave_acesso, sequencia
	"""
	if limit is not None:
		query += " LIMIT ?"
		params.append(limit)
	with conexao(db_path) as con:
		rows = con.execute(query, params).fetchall()
	return [
		ItemPadronizado(
			chave_acesso=row[0],
			sequencia=int(row[1]),
			data_emissao=row[2],
			ano=row[3],
			mes=row[4],
			ano_mes=row[5],
			estabelecimento_id=row[6],
			estabelecimento_nome=row[7],
			estabelecimento_cnpj=row[8],
			categoria=row[9],
			categoria_id=row[10],
			quantidade=_para_decimal(row[11]),
			valor_total=_para_decimal(row[12]),
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
				categoria_id = _resolver_categoria_id(con, cat)
				
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
				confirmar_item = bool(item.get("confirmar")) or confirmar

				# Se tivermos info de produto, tentamos resolver/criar o produto
				produto_id = None
				if prod_nome:
					produto_obj = _resolver_produto_por_nome_marca(con, prod_nome, prod_marca, cat)
					if produto_obj:
						produto_id = produto_obj.id

				# Montar update dinâmico
				sql_update = """
					UPDATE itens
					SET
						categoria_sugerida = ?,
						fonte_classificacao = ?,
						confianca_classificacao = ?,
						atualizado_em = CURRENT_TIMESTAMP
				"""
				params = [cat, origem, conf]
				if categoria_id is not None:
					sql_update += ", categoria_sugerida_id = ?"
					params.append(categoria_id)
				else:
					sql_update += ", categoria_sugerida_id = NULL"

				if confirmar_item:
					sql_update += ", categoria_confirmada = ?"
					params.append(cat)
					if categoria_id is not None:
						sql_update += ", categoria_confirmada_id = ?"
						params.append(categoria_id)
					else:
						sql_update += ", categoria_confirmada_id = NULL"

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


def registrar_revisoes_manuais(
	registros: Sequence[Mapping[str, Any]],
	*,
	confirmar: bool = False,
	usuario: str | None = None,
	observacoes_padrao: str | None = None,
	db_path: Path | str | None = None,
) -> None:
	"""Processa ajustes vindos da UI e registra histórico de revisão."""

	if not registros:
		return

	usuario_limpo = _limpar_texto_curto(usuario)
	observacao_padrao = _limpar_texto_curto(observacoes_padrao)

	itens_para_classificar: list[dict[str, Any]] = []
	logs: list[tuple[object, ...]] = []

	for registro in registros:
		chave = registro.get("chave_acesso")
		sequencia = registro.get("sequencia")
		if not chave or sequencia is None:
			continue
		categoria = _limpar_texto_curto(registro.get("categoria"))
		if not categoria:
			if confirmar:
				raise ValueError(
					f"Categoria obrigatória para confirmar o item {sequencia} da nota {chave}."
				)
			continue
		produto_nome = _limpar_texto_curto(registro.get("produto_nome"))
		produto_marca = _limpar_texto_curto(registro.get("produto_marca"))
		observacao = _limpar_texto_curto(registro.get("observacoes")) or observacao_padrao

		payload = {
			"chave_acesso": chave,
			"sequencia": int(sequencia),
			"categoria": categoria,
			"origem": "revisao_manual",
			"modelo": "ui_streamlit",
			"observacoes": observacao,
			"confirmar": confirmar,
			"produto_nome": produto_nome,
			"produto_marca": produto_marca,
		}
		itens_para_classificar.append(payload)
		logs.append(
			(
				chave,
				int(sequencia),
				categoria,
				produto_nome,
				produto_marca,
				usuario_limpo,
				observacao,
				"revisao_manual",
				bool(confirmar),
			)
		)

	if not itens_para_classificar:
		return

	registrar_classificacao_itens(itens_para_classificar, confirmar=confirmar, db_path=db_path)

	with conexao(db_path) as con:
		for log in logs:
			con.execute(
				"""
				INSERT INTO revisoes_manuais (
					chave_acesso,
					sequencia,
					categoria,
					produto_nome,
					produto_marca,
					usuario,
					observacoes,
					origem,
					confirmado
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
				""",
				log,
			)


def listar_revisoes_manuais(
	chave_acesso: str,
	*,
	limit: int = 20,
	db_path: Path | str | None = None,
) -> list[RevisaoManual]:
	"""Retorna o histórico de revisões manuais por nota."""

	if not chave_acesso:
		return []

	with conexao(db_path) as con:
		rows = con.execute(
			"""
			SELECT
				chave_acesso,
				sequencia,
				categoria,
				produto_nome,
				produto_marca,
				usuario,
				observacoes,
				origem,
				confirmado,
				criado_em
			FROM revisoes_manuais
			WHERE chave_acesso = ?
			ORDER BY criado_em DESC, id DESC
			LIMIT ?
			""",
			[chave_acesso, limit],
		).fetchall()

	return [
		RevisaoManual(
			chave_acesso=row[0],
			sequencia=int(row[1]),
			categoria=row[2],
			produto_nome=row[3],
			produto_marca=row[4],
			usuario=row[5],
			observacoes=row[6],
			origem=row[7],
			confirmado=bool(row[8]),
			criado_em=row[9],
		)
		for row in rows
	]


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
	emissao_iso, emissao_data = _converter_data_iso_e_data(nota.emissao)
	if emissao_data:
		_garantir_dim_data(con, emissao_data)
	estabelecimento_id = _obter_ou_criar_estabelecimento(
		con,
		nota.emitente_nome,
		nota.emitente_cnpj,
		nota.emitente_endereco,
	)
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
			emissao_data,
			estabelecimento_id,
			total_itens,
			valor_total,
			valor_pago,
			tributos,
			consumidor_cpf,
			consumidor_nome
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT (chave_acesso) DO UPDATE SET
			emitente_nome = excluded.emitente_nome,
			emitente_cnpj = excluded.emitente_cnpj,
			emitente_endereco = excluded.emitente_endereco,
			numero = excluded.numero,
			serie = excluded.serie,
			emissao_texto = excluded.emissao_texto,
			emissao_iso = excluded.emissao_iso,
			emissao_data = excluded.emissao_data,
			estabelecimento_id = excluded.estabelecimento_id,
			total_itens = excluded.total_itens,
			valor_total = excluded.valor_total,
			valor_pago = excluded.valor_pago,
			tributos = excluded.tributos,
			consumidor_cpf = excluded.consumidor_cpf,
			consumidor_nome = excluded.consumidor_nome,
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
			emissao_iso,
			emissao_data,
			estabelecimento_id,
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
				categoria_sugerida_id,
				categoria_confirmada_id,
				fonte_classificacao,
				confianca_classificacao,
				atualizado_em
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, now())
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
			produto_id=produto.id,  # type: ignore
			descricao=produto.nome_base,
			nome_base=produto.nome_base,
			marca_base=produto.marca_base,
		)
	except ImportError:
		pass
	except Exception:
		# Logar erro silenciosamente ou warning
		pass


def _converter_data_iso_e_data(texto: str | None) -> tuple[str | None, str | None]:
	"""Retorna a representação ISO completa e a data (YYYY-MM-DD) extraída."""
	iso = _converter_data_iso(texto)
	if not iso:
		return None, None
	data_apenas = iso.split("T", 1)[0]
	return iso, data_apenas


def _garantir_dim_data(
	con: duckdb.DuckDBPyConnection, data_iso: str | None
) -> str | None:
	"""Garante que a data informada exista em datas_referencia."""
	if not data_iso:
		return None
	existe = con.execute(
		"""
		SELECT 1 FROM datas_referencia WHERE data_iso = ?
		""",
		[data_iso],
	).fetchone()
	if existe:
		return data_iso
	try:
		data_ref = datetime.fromisoformat(data_iso).date()
	except ValueError:
		try:
			data_ref = datetime.strptime(data_iso, "%Y-%m-%d").date()
		except ValueError:
			return None
	ano_mes = f"{data_ref.year:04d}-{data_ref.month:02d}"
	trimestre = (data_ref.month - 1) // 3 + 1
	isocal = data_ref.isocalendar()
	semana = isocal.week
	nome_mes = _MESES_PT[data_ref.month - 1]
	nome_dia = _DIAS_SEMANA_PT[data_ref.isoweekday() - 1]
	con.execute(
		"""
		INSERT INTO datas_referencia (
			data_iso,
			ano,
			mes,
			dia,
			ano_mes,
			trimestre,
			semana,
			nome_mes,
			nome_dia_semana
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
		""",
		[
			data_ref.isoformat(),
			data_ref.year,
			data_ref.month,
			data_ref.day,
			ano_mes,
			trimestre,
			semana,
			nome_mes,
			nome_dia,
		],
	)
	return data_ref.isoformat()


def _normalizar_cnpj(cnpj: str | None) -> str | None:
	if not cnpj:
		return None
	digitos = re.sub(r"\D+", "", cnpj)
	if len(digitos) != 14:
		return None
	return digitos


def _obter_ou_criar_estabelecimento(
	con: duckdb.DuckDBPyConnection,
	nome: str | None,
	cnpj: str | None,
	endereco: str | None,
) -> int | None:
	"""Resolve o identificador de estabelecimento, criando se necessário."""
	normalizado = _normalizar_cnpj(cnpj)
	row = None
	if normalizado:
		row = con.execute(
			"SELECT id FROM estabelecimentos WHERE cnpj_normalizado = ?",
			[normalizado],
		).fetchone()
	if row:
		est_id = int(row[0])
		_consolidar_estabelecimento(con, est_id, nome, cnpj, normalizado, endereco)
		return est_id
	if nome:
		row = con.execute(
			"""
			SELECT id FROM estabelecimentos
			WHERE lower(COALESCE(nome,'')) = lower(COALESCE(?, ''))
			AND lower(COALESCE(endereco,'')) = lower(COALESCE(?, ''))
			LIMIT 1
			""",
			[nome, endereco],
		).fetchone()
		if row:
			est_id = int(row[0])
			_consolidar_estabelecimento(con, est_id, nome, cnpj, normalizado, endereco)
			return est_id
	if not nome and not normalizado and not endereco:
		return None
	resultado = con.execute(
		"""
		INSERT INTO estabelecimentos (nome, cnpj, cnpj_normalizado, endereco)
		VALUES (?, ?, ?, ?)
		RETURNING id
		""",
		[nome, cnpj, normalizado, endereco],
	).fetchone()
	return int(resultado[0]) if resultado else None


def _consolidar_estabelecimento(
	con: duckdb.DuckDBPyConnection,
	est_id: int,
	nome: str | None,
	cnpj: str | None,
	cnpj_normalizado: str | None,
	endereco: str | None,
) -> None:
	con.execute(
		"""
		UPDATE estabelecimentos
		SET
			nome = COALESCE(?, nome),
			cnpj = COALESCE(?, cnpj),
			cnpj_normalizado = COALESCE(?, cnpj_normalizado),
			endereco = COALESCE(?, endereco),
			atualizado_em = CURRENT_TIMESTAMP
		WHERE id = ?
		""",
		[nome, cnpj, cnpj_normalizado, endereco, est_id],
	)


def _resolver_categoria_id(
	con: duckdb.DuckDBPyConnection, categoria_nome: str | None
) -> int | None:
	if not categoria_nome:
		return None
	nome = categoria_nome.strip()
	if not nome:
		return None
	row = con.execute(
		"""
		SELECT id FROM categorias
		WHERE lower(nome) = lower(?)
		ORDER BY ativo DESC, id ASC
		LIMIT 1
		""",
		[nome],
	).fetchone()
	if row:
		return int(row[0])
	try:
		novo = con.execute(
			"""
			INSERT INTO categorias (grupo, nome)
			VALUES (?, ?)
			RETURNING id
			""",
			["Livres", nome],
		).fetchone()
		if novo:
			return int(novo[0])
	except duckdb.Error:
		row = con.execute(
			"SELECT id FROM categorias WHERE lower(nome) = lower(?) ORDER BY id DESC LIMIT 1",
			[nome],
		).fetchone()
		if row:
			return int(row[0])
	return None


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
		total_notas_row = con.execute("SELECT COUNT(*) FROM notas").fetchone()
		
		# Total gasto (soma de valor_total das notas)
		total_gasto_row = con.execute("SELECT SUM(valor_total) FROM notas").fetchone()
		
		# Itens pendentes de classificação
		itens_pendentes_row = con.execute(
			"SELECT COUNT(*) FROM itens WHERE categoria_confirmada IS NULL"
		).fetchone()

	return {
		"total_notas": (total_notas_row[0] if total_notas_row else 0) or 0,
		"total_gasto": _para_decimal(total_gasto_row[0] if total_gasto_row else None)
		or Decimal("0.00"),
		"itens_pendentes": (itens_pendentes_row[0] if itens_pendentes_row else 0) or 0,
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
