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
	finally:
		con.close()


def inicializar_banco(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
	"""Cria (se necessário) e retorna uma conexão pronta para uso."""

	con = duckdb.connect(str(_resolver_caminho_banco(db_path)))
	_aplicar_schema(con)
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
			ORDER BY COALESCE(i.atualizado_em, CURRENT_TIMESTAMP), i.chave_acesso, i.sequencia
			LIMIT ?
			""",
			[limit],
		).fetchall()

	itens: list[ItemParaClassificacao] = []
	for row in rows:
		itens.append(
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
		)
	return itens


def listar_itens_para_revisao(
	chave_acesso: str,
	*,
	somente_pendentes: bool = False,
	db_path: Path | str | None = None,
) -> list[ItemNotaRevisao]:
	"""Retorna itens de uma nota para uso na revisão manual."""

	if not chave_acesso:
		return []

	db_file = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
	if not db_file.exists():
		return []

	where_extra = "AND categoria_confirmada IS NULL" if somente_pendentes else ""
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
		WHERE chave_acesso = ?
		{where_extra}
		ORDER BY sequencia
	"""

	with duckdb.connect(str(db_file)) as con:
		rows = con.execute(query, [chave_acesso]).fetchall()

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


def registrar_revisoes_manuais(
	itens: Sequence[Mapping[str, Any]],
	*,
	confirmar: bool,
	usuario: str | None = None,
	observacoes_padrao: str | None = None,
	db_path: Path | str | None = None,
) -> None:
	"""Consolida ajustes manuais reaproveitando registrar_classificacao_itens."""

	if not itens:
		return

	registro_timestamp = datetime.utcnow().isoformat(timespec="seconds")
	observacao_base = observacoes_padrao or f"Revisão manual em {registro_timestamp}"
	if usuario:
		observacao_base = f"{observacao_base} por {usuario}"

	payload: list[dict[str, Any]] = []
	for item in itens:
		payload.append(
			{
				"chave_acesso": item["chave_acesso"],
				"sequencia": int(item["sequencia"]),
				"categoria": (item.get("categoria") or "").strip() or None,
				"confianca": item.get("confianca"),
				"origem": "revisao-manual",
				"modelo": "streamlit-manual",
				"observacoes": item.get("observacoes") or observacao_base,
				"produto_nome": (item.get("produto_nome") or "").strip() or None,
				"produto_marca": (item.get("produto_marca") or "").strip() or None,
			}
		)

	registrar_classificacao_itens(payload, confirmar=confirmar, db_path=db_path)


def carregar_nota(chave: str, *, db_path: Path | str | None = None) -> Optional[NotaFiscal]:
	"""Reconstrói uma :class:`NotaFiscal` a partir do banco."""

	with conexao(db_path) as con:
		dados = con.execute(
			"""
			SELECT
				chave_acesso,
				emitente_nome,
				emitente_cnpj,
				emitente_endereco,
				numero,
				serie,
				emissao_texto,
				total_itens,
				valor_total,
				valor_pago,
				tributos,
				consumidor_cpf,
				consumidor_nome
			FROM notas
			WHERE chave_acesso = ?
			""",
			[chave],
		).fetchone()

		if dados is None:
			return None

		itens_rows = con.execute(
			"""SELECT sequencia, descricao, codigo, quantidade, unidade, valor_unitario, valor_total
				FROM itens WHERE chave_acesso = ? ORDER BY sequencia""",
			[chave],
		).fetchall()
		pagamentos_rows = con.execute(
			"SELECT forma, valor FROM pagamentos WHERE chave_acesso = ?",
			[chave],
		).fetchall()

	itens = [
		NotaItem(
			descricao=row[1],
			codigo=row[2],
			quantidade=_para_decimal(row[3]) or Decimal("0"),
			unidade=row[4] or "",
			valor_unitario=_para_decimal(row[5]) or Decimal("0"),
			valor_total=_para_decimal(row[6]) or Decimal("0"),
		)
		for row in itens_rows
	]

	pagamentos = [
		Pagamento(forma=row[0], valor=_para_decimal(row[1]) or Decimal("0"))
		for row in pagamentos_rows
	]

	return NotaFiscal(
		chave_acesso=dados[0],
		emitente_nome=dados[1],
		emitente_cnpj=dados[2],
		emitente_endereco=dados[3],
		numero=dados[4],
		serie=dados[5],
		emissao=dados[6],
		itens=itens,
		total_itens=dados[7],
		valor_total=_para_decimal(dados[8]),
		valor_pago=_para_decimal(dados[9]),
		tributos=_para_decimal(dados[10]),
		consumidor_cpf=dados[11],
		consumidor_nome=dados[12],
		pagamentos=pagamentos,
	)


def registrar_classificacao_itens(
	classificacoes: Iterable[object],
	*, confirmar: bool = False,
	 db_path: Path | str | None = None,
) -> int:
	"""Atualiza as categorias dos itens e registra histórico.

	`classificacoes` pode ser uma sequência de dicts ou dataclasses com os campos:
	- chave_acesso
	- sequencia
	- categoria
	- confianca (opcional)
	- origem (opcional)
	- modelo (opcional)
	- observacoes (opcional)
	- resposta_json / raw_response (opcional)
	- confirmar (opcional, sobrescreve o parâmetro da função)
	"""

	registros = [_normalizar_classificacao_input(item) for item in classificacoes]
	if not registros:
		return 0

	with conexao(db_path) as con:
		for registro in registros:
			_confirmar = bool(registro.get("confirmar", confirmar))
			params_comuns = [
				registro["categoria"],
				registro["origem"],
				registro.get("confianca"),
				registro["chave_acesso"],
				registro["sequencia"],
			]
			if _confirmar:
				con.execute(
					"""
					UPDATE itens
					SET categoria_sugerida = ?,
						categoria_confirmada = ?,
						fonte_classificacao = ?,
						confianca_classificacao = ?,
						atualizado_em = CURRENT_TIMESTAMP
					WHERE chave_acesso = ? AND sequencia = ?
					""",
					[
						registro["categoria"],
						registro["categoria"],
						registro["origem"],
						registro.get("confianca"),
						registro["chave_acesso"],
						registro["sequencia"],
					],
				)
			else:
				con.execute(
					"""
					UPDATE itens
					SET categoria_sugerida = ?,
						fonte_classificacao = ?,
						confianca_classificacao = ?,
						atualizado_em = CURRENT_TIMESTAMP
					WHERE chave_acesso = ? AND sequencia = ?
					""",
					params_comuns,
				)

			produto_nome = registro.get("produto_nome")
			produto_marca = registro.get("produto_marca")
			produto_id = None
			if produto_nome:
				produto = _buscar_ou_criar_produto_por_nome_marca(
					con, produto_nome, produto_marca
				)
				descricao_item = _obter_descricao_item(
					con, registro["chave_acesso"], registro["sequencia"]
				)
				if produto.id is not None:
					produto_id = produto.id
					if descricao_item:
						_registrar_alias_produto(con, produto_id, descricao_item)
						_registrar_embeddings_para_produto(
							produto_id,
							descricao_item,
							produto.nome_base,
							produto.marca_base,
						)
					con.execute(
						"""
						UPDATE itens
						SET produto_id = ?,
							produto_nome = ?,
							produto_marca = ?
						WHERE chave_acesso = ? AND sequencia = ?
						""",
						[
							produto_id,
							produto.nome_base,
							produto.marca_base,
							registro["chave_acesso"],
							registro["sequencia"],
						],
					)

			con.execute(
				"""
				INSERT INTO classificacoes_historico (
					chave_acesso,
					sequencia,
					categoria,
					confianca,
					origem,
					modelo,
					observacoes,
					resposta_json
				) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
				""",
				[
					registro["chave_acesso"],
					registro["sequencia"],
					registro["categoria"],
					registro.get("confianca"),
					registro["origem"],
					registro.get("modelo"),
					registro.get("observacoes"),
					registro.get("resposta_json"),
				],
			)

	return len(registros)


def _buscar_produto_por_nome_marca(
	con: duckdb.DuckDBPyConnection, nome_base: str, marca_base: Optional[str]
) -> Optional[ProdutoPadronizado]:
	row = con.execute(
		"""
		SELECT id, nome_base, marca_base, categoria_id, criado_em, atualizado_em
		FROM produtos
		WHERE lower(nome_base) = lower(?)
			AND lower(COALESCE(marca_base, '')) = lower(COALESCE(?, ''))
		""",
		[nome_base, marca_base or ""],
	).fetchone()
	if row is None:
		return None
	return ProdutoPadronizado(
		id=row[0],
		nome_base=row[1],
		marca_base=row[2],
		categoria_id=row[3],
		criado_em=row[4],
		atualizado_em=row[5],
	)


def _buscar_produto_por_id(
	con: duckdb.DuckDBPyConnection, produto_id: int
) -> Optional[ProdutoPadronizado]:
	row = con.execute(
		"""
		SELECT id, nome_base, marca_base, categoria_id, criado_em, atualizado_em
		FROM produtos
		WHERE id = ?
		""",
		[produto_id],
	).fetchone()
	if row is None:
		return None
	return ProdutoPadronizado(
		id=row[0],
		nome_base=row[1],
		marca_base=row[2],
		categoria_id=row[3],
		criado_em=row[4],
		atualizado_em=row[5],
	)


def _buscar_produto_por_descricao_similaridade(
	con: duckdb.DuckDBPyConnection, descricao: str
) -> Optional[ProdutoPadronizado]:
	from src.classifiers.embeddings import buscar_produtos_semelhantes

	resultados = buscar_produtos_semelhantes(descricao, top_k=5)
	for similar in resultados:
		score = similar.get("score") or 0.0
		if score < _SIMILARIDADE_MINIMA:
			continue
		produto_id = similar.get("produto_id")
		if not produto_id:
			continue
		produto = _buscar_produto_por_id(con, int(produto_id))
		if produto:
			return produto
	return None


def _criar_produto(
	con: duckdb.DuckDBPyConnection, nome_base: str, marca_base: Optional[str]
) -> ProdutoPadronizado:
	row = con.execute(
		"""
		INSERT INTO produtos (nome_base, marca_base)
		VALUES (?, ?)
		RETURNING id, nome_base, marca_base, categoria_id, criado_em, atualizado_em
		""",
		[nome_base, marca_base],
	).fetchone()
	if row is None:
		raise RuntimeError("Falha ao criar produto padronizado")
	return ProdutoPadronizado(
		id=row[0],
		nome_base=row[1],
		marca_base=row[2],
		categoria_id=row[3],
		criado_em=row[4],
		atualizado_em=row[5],
	)


def _buscar_ou_criar_produto_por_nome_marca(
	con: duckdb.DuckDBPyConnection, nome_base: str, marca_base: Optional[str]
) -> ProdutoPadronizado:
	produto = _buscar_produto_por_nome_marca(con, nome_base, marca_base)
	if produto is None:
		produto = _criar_produto(con, nome_base, marca_base)
	return produto


def _registrar_alias_produto(
	con: duckdb.DuckDBPyConnection, produto_id: int, descricao_original: str
) -> None:
	texto = _limpar_texto_curto(descricao_original)
	if not texto:
		return
	existe = con.execute(
		"""
		SELECT 1 FROM aliases_produtos
		WHERE produto_id = ? AND lower(texto_original) = lower(?)
		""",
		[produto_id, texto],
	).fetchone()
	if existe:
		return
	try:
		con.execute(
			"""
			INSERT INTO aliases_produtos (produto_id, texto_original)
			VALUES (?, ?)
			""",
			[produto_id, texto],
		)
	except duckdb.Error as exc:  # pragma: no cover - tratamento de alias duplicado
		mensagem = str(exc).lower()
		if "unique constraint" in mensagem or "violates unique" in mensagem:
			return
		raise


def _obter_descricao_item(
	con: duckdb.DuckDBPyConnection, chave_acesso: str, sequencia: int
) -> Optional[str]:
	row = con.execute(
		"""
		SELECT descricao FROM itens
		WHERE chave_acesso = ? AND sequencia = ?
		""",
		[chave_acesso, sequencia],
	).fetchone()
	if not row:
		return None
	descricao = row[0]
	if descricao is None:
		return None
	return str(descricao)


def _registrar_embeddings_para_produto(
	produto_id: int, descricao: str, nome_base: str, marca_base: Optional[str]
) -> None:
	from src.classifiers.embeddings import upsert_produto_embedding

	if not descricao or not nome_base:
		return
	upsert_produto_embedding(produto_id, descricao, nome_base, marca_base)


def _resolver_produto_por_descricao(
	con: duckdb.DuckDBPyConnection, descricao: str
) -> Optional[ProdutoPadronizado]:
	nome_base, marca_base = normalizar_produto_descricao(descricao)
	if not nome_base:
		return None
	produto = _buscar_produto_por_nome_marca(con, nome_base, marca_base)
	if produto is None:
		produto = _buscar_produto_por_descricao_similaridade(con, descricao)
	if produto is None:
		produto = _criar_produto(con, nome_base, marca_base)
	if produto.id is not None:
		_registrar_alias_produto(con, produto.id, descricao)
		_registrar_embeddings_para_produto(produto.id, descricao, produto.nome_base, produto.marca_base)
	return produto


def _persistir_nota(con: duckdb.DuckDBPyConnection, nota: NotaFiscal) -> None:
	con.execute("DELETE FROM pagamentos WHERE chave_acesso = ?", [nota.chave_acesso])
	con.execute("DELETE FROM itens WHERE chave_acesso = ?", [nota.chave_acesso])
	con.execute("DELETE FROM notas WHERE chave_acesso = ?", [nota.chave_acesso])

	emissao_texto, emissao_iso = _normalizar_emissao(nota.emissao)

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
			consumidor_nome,
			criado_em,
			atualizado_em
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
		""",
		[
			nota.chave_acesso,
			nota.emitente_nome,
			nota.emitente_cnpj,
			nota.emitente_endereco,
			nota.numero,
			nota.serie,
			emissao_texto,
			emissao_iso,
			nota.total_itens,
			_decimal_para_str(nota.valor_total),
			_decimal_para_str(nota.valor_pago),
			_decimal_para_str(nota.tributos),
			nota.consumidor_cpf,
			nota.consumidor_nome,
		],
	)

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
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)
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


def _persistir_pagamentos(
	con: duckdb.DuckDBPyConnection, chave: str, pagamentos: Iterable[Pagamento]
) -> None:
	for pagamento in pagamentos:
		con.execute(
			"""
			INSERT INTO pagamentos (
				chave_acesso,
				forma,
				valor
			) VALUES (?, ?, ?)
			""",
			[
				chave,
				pagamento.forma,
				_decimal_para_str(pagamento.valor),
			],
		)


_EMISSAO_PATTERNS = (
	"%d/%m/%Y %H:%M:%S",
	"%d/%m/%Y %H:%M",
	"%d/%m/%Y",
)


def _normalizar_emissao(emissao: Optional[str]) -> tuple[Optional[str], Optional[str]]:
	if not emissao:
		return None, None
	texto = re.sub(r"\s+", " ", emissao.strip())
	texto = texto.replace("às", "").replace("h", ":")
	texto = texto.replace("  ", " ").strip()
	for pattern in _EMISSAO_PATTERNS:
		try:
			dt = datetime.strptime(texto, pattern)
		except ValueError:
			continue
		return texto, dt.isoformat()
	return texto, None


def _decimal_para_str(valor: Optional[Decimal]) -> Optional[str]:
	if valor is None:
		return None
	return format(valor, "f")


def _para_decimal(valor: object | None) -> Optional[Decimal]:
	if valor is None:
		return None
	if isinstance(valor, Decimal):
		return valor
	return Decimal(str(valor))


def _limpar_texto_curto(valor: object | None) -> str:
	if valor is None:
		return ""
	texto = str(valor).strip()
	if not texto:
		return ""
	return re.sub(r"\s+", " ", texto)


def _normalizar_classificacao_input(item: object) -> dict[str, Any]:
	if isinstance(item, dict):
		dados = dict(item)
	elif is_dataclass(item) and not isinstance(item, type):
		dados = asdict(item)
	else:
		raise TypeError("Classificação deve ser um dict ou dataclass")

	for chave in ("chave_acesso", "sequencia", "categoria"):
		if chave not in dados:
			raise ValueError(f"Campo obrigatório ausente: {chave}")

	categoria = str(dados["categoria"]).strip()
	if not categoria:
		raise ValueError("Categoria não pode ser vazia")

	resposta_json = dados.get("resposta_json") or dados.get("raw_response")
	if isinstance(resposta_json, (dict, list)):
		resposta_json = json.dumps(resposta_json, ensure_ascii=False)
	elif resposta_json is not None:
		resposta_json = str(resposta_json)

	produto_info = dados.get("produto")
	if isinstance(produto_info, dict):
		produto_nome = produto_info.get("nome_base") or produto_info.get("nome")
		produto_marca = produto_info.get("marca_base") or produto_info.get("marca")
	else:
		produto_nome = dados.get("produto_nome")
		produto_marca = dados.get("produto_marca")

	def _fazer_texto(valor: object | None) -> str | None:
		if valor is None:
			return None
		texto = str(valor).strip()
		return texto or None

	retorno: dict[str, Any] = {
		"chave_acesso": str(dados["chave_acesso"]),
		"sequencia": int(dados["sequencia"]),
		"categoria": categoria,
		"confianca": _normalizar_float(dados.get("confianca")),
		"origem": str(dados.get("origem") or "groq").lower(),
		"modelo": dados.get("modelo"),
		"observacoes": dados.get("observacoes"),
		"resposta_json": resposta_json,
		"confirmar": dados.get("confirmar"),
		"produto_nome": _fazer_texto(produto_nome),
		"produto_marca": _fazer_texto(produto_marca),
	}
	return retorno


def _normalizar_float(valor: object | None) -> Optional[float]:
	if valor is None:
		return None
	if isinstance(valor, (int, float)):
		return float(valor)
	if isinstance(valor, Decimal):
		return float(valor)
	texto = str(valor).strip()
	if not texto:
		return None
	texto = texto.replace(",", ".")
	try:
		return float(texto)
	except ValueError:
		return None
