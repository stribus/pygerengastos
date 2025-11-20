"""Camada de persistência em DuckDB.

Este módulo fornece utilitários para criar o schema padrão do sistema,
persistir notas fiscais extraídas do portal da Receita Gaúcha e recuperar
informações para etapas posteriores (classificação, dashboards, etc.).

As funções expostas aqui não têm a pretensão de serem definitivas; elas
servem como primeira iteração da camada de armazenamento, permitindo que as
demais partes do projeto evoluam em paralelo."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterable, Iterator, Optional
import re

import duckdb

from src.scrapers.receita_rs import NotaFiscal, NotaItem, Pagamento

_BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = _BASE_DIR / "data" / "gastos.duckdb"

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
	CREATE TABLE IF NOT EXISTS itens (
		chave_acesso VARCHAR,
		sequencia INTEGER,
		descricao TEXT,
		codigo VARCHAR,
		quantidade DECIMAL(18, 4),
		unidade VARCHAR,
		valor_unitario DECIMAL(18, 4),
		valor_total DECIMAL(18, 4),
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
)


def _resolver_caminho_banco(db_path: Path | str | None = None) -> Path:
	caminho = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
	caminho.parent.mkdir(parents=True, exist_ok=True)
	return caminho


def _aplicar_schema(con: duckdb.DuckDBPyConnection) -> None:
	for ddl in _SCHEMA_DEFINITIONS:
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
				categoria_sugerida,
				categoria_confirmada,
				fonte_classificacao,
				confianca_classificacao,
				atualizado_em
			) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, CURRENT_TIMESTAMP)
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
