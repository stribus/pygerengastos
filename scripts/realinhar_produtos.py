"""Realinha produtos, itens e cache semântico às regras de identidade do produto.

Regras (ver src/database): o produto é identificado pelo nome, sem diferenciar
maiúsculas, acentos de caixa ou espaços sobrando; a marca de cada compra fica
no item; o cache semântico guarda o produto_id e o nome canônico do produto.

Os dados gravados antes dessas regras ficaram inconsistentes. Este script:

1. funde produtos com o mesmo nome no que tem mais itens (via
   consolidar_produtos, que registra a auditoria e migra aliases e embeddings);
2. alinha itens.produto_nome ao nome do produto (a marca do item é mantida);
3. religa itens órfãos (produto_id de produto inexistente) pelo alias da
   descrição ou pelo nome; sem nenhum dos dois, o produto fica vazio;
4. limpa o cache semântico (data/chroma): remove entradas com categoria cuja
   descrição não existe em nenhum item, ou que apontam para produto
   inexistente, e reindexa os itens classificados com o produto canônico.

Por padrão apenas simula e mostra o que mudaria; use --aplicar para gravar.
Faça backup de data/gastos.db e de data/chroma antes de aplicar.

As etapas não formam uma transação única (cada fusão confirma a sua, e o
Chroma não é transacional). Se a execução for interrompida, rode o script de
novo: ele recalcula o que falta e é idempotente.

Uso:
    python scripts/realinhar_produtos.py [--aplicar] [--db CAMINHO] [--chroma PASTA]
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

# Permite execução a partir da raiz do projeto sem necessidade de instalar o pacote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import (
    DEFAULT_DB_PATH,
    _resolver_produto_por_nome_marca,
    conexao,
    consolidar_produtos,
)


def _chave_nome(nome: str | None) -> str:
    """Chave de identidade do produto: sem caixa e sem espaços sobrando."""
    return " ".join(unicodedata.normalize("NFKC", nome or "").casefold().split())


def _planejar_fusoes(con) -> list[tuple[int, list[int], str]]:
    """Grupos de produtos com o mesmo nome: (destino, origens, nome do destino).

    O destino é o produto com mais itens (empate: menor id).
    """
    grupos: dict[str, list[tuple[int, str, int]]] = defaultdict(list)
    for produto_id, nome, qtd_itens in con.execute(
        "SELECT p.id, p.nome_base, (SELECT COUNT(*) FROM itens i WHERE i.produto_id = p.id) FROM produtos p"
    ):
        grupos[_chave_nome(nome)].append((produto_id, nome, qtd_itens))

    fusoes = []
    for produtos in grupos.values():
        if len(produtos) < 2:
            continue
        produtos.sort(key=lambda p: (-p[2], p[0]))
        destino_id, destino_nome, _ = produtos[0]
        fusoes.append((destino_id, sorted(p[0] for p in produtos[1:]), destino_nome))
    return sorted(fusoes)


def _contar_nomes_desalinhados(con) -> int:
    return con.execute(
        """
        SELECT COUNT(*) FROM itens i JOIN produtos p ON p.id = i.produto_id
        WHERE i.produto_nome IS NOT p.nome_base
        """
    ).fetchone()[0]


def _itens_orfaos(con) -> list[tuple[str, int, str, str | None, str | None]]:
    return con.execute(
        """
        SELECT i.chave_acesso, i.sequencia, i.descricao, i.produto_nome, i.produto_marca
        FROM itens i LEFT JOIN produtos p ON p.id = i.produto_id
        WHERE i.produto_id IS NOT NULL AND p.id IS NULL
        """
    ).fetchall()


def _religar_orfao(con, chave: str, seq: int, descricao: str, nome: str | None, marca: str | None) -> None:
    row = con.execute(
        """
        SELECT p.id, p.nome_base FROM aliases_produtos a JOIN produtos p ON p.id = a.produto_id
        WHERE lower(a.texto_original) = lower(?)
        """,
        [(descricao or "").strip()],
    ).fetchone()
    if row is None and nome:
        produto = _resolver_produto_por_nome_marca(con, nome, marca, None)
        row = (produto.id, produto.nome_base) if produto else None
    if row:
        con.execute(
            "UPDATE itens SET produto_id = ?, produto_nome = ? WHERE chave_acesso = ? AND sequencia = ?",
            [row[0], row[1], chave, seq],
        )
    else:
        con.execute(
            "UPDATE itens SET produto_id = NULL WHERE chave_acesso = ? AND sequencia = ?",
            [chave, seq],
        )


def _planejar_cache(con) -> tuple[list[str], list[tuple[Any, ...]]]:
    """(ids do Chroma a remover, itens classificados a reindexar)."""
    from src.classifiers.embeddings import _get_collection

    itens = con.execute(
        """
        SELECT i.descricao, i.produto_id, p.nome_base, i.produto_marca,
               COALESCE(i.categoria_confirmada, i.categoria_sugerida)
        FROM itens i JOIN produtos p ON p.id = i.produto_id
        WHERE COALESCE(i.categoria_confirmada, i.categoria_sugerida) IS NOT NULL
          AND TRIM(COALESCE(i.descricao, '')) <> ''
        """
    ).fetchall()
    descricoes_reais = {
        (d or "").strip().upper() for (d,) in con.execute("SELECT descricao FROM itens")
    }
    produtos_existentes = {str(pid) for (pid,) in con.execute("SELECT id FROM produtos")}

    dados = _get_collection().get(include=["metadatas", "documents"])
    remover = []
    for doc_id, documento, metadado in zip(dados["ids"], dados["documents"], dados["metadatas"]):
        metadado = metadado or {}
        produto_id = (metadado.get("produto_id") or "").strip()
        com_categoria = bool((metadado.get("categoria") or "").strip())
        descricao_real = (documento or "").strip().upper() in descricoes_reais
        if (com_categoria and not descricao_real) or (produto_id and produto_id not in produtos_existentes):
            remover.append(doc_id)
    return remover, itens


def realinhar(db_path: Path, *, aplicar: bool) -> dict[str, Any]:
    """Executa (ou só planeja, se aplicar=False) o realinhamento. Retorna um relatório."""
    with conexao(db_path) as con:
        fusoes = _planejar_fusoes(con)

    if aplicar:
        for destino, origens, nome in fusoes:
            nome_final = nome.strip() if nome != nome.strip() else None
            for origem in origens:
                consolidar_produtos(
                    origem, destino, nome_final=nome_final, usuario="realinhar_produtos",
                    observacoes="Fusão automática: mesmo nome de produto", db_path=db_path,
                )
                nome_final = None  # o destino já foi renomeado na primeira fusão

    with conexao(db_path) as con:
        nomes_desalinhados = _contar_nomes_desalinhados(con)
        orfaos = _itens_orfaos(con)
        if aplicar:
            con.execute(
                """
                UPDATE itens SET produto_nome = (SELECT p.nome_base FROM produtos p WHERE p.id = itens.produto_id)
                WHERE produto_id IN (SELECT id FROM produtos)
                  AND produto_nome IS NOT (SELECT p.nome_base FROM produtos p WHERE p.id = itens.produto_id)
                """
            )
            for orfao in orfaos:
                _religar_orfao(con, *orfao)
        remover, itens_cache = _planejar_cache(con)

    reindexados = 0
    if aplicar:
        from src.classifiers.embeddings import _get_collection, upsert_descricao_embedding

        if remover:
            _get_collection().delete(ids=remover)
        for descricao, produto_id, nome, marca, categoria in itens_cache:
            upsert_descricao_embedding(descricao, nome, marca, categoria, produto_id=produto_id)
            reindexados += 1

    return {
        "fusoes": fusoes,
        "nomes_desalinhados": nomes_desalinhados,
        "orfaos": len(orfaos),
        "embeddings_a_remover": len(remover),
        "embeddings_removidos": len(remover) if aplicar else 0,
        "itens_a_reindexar": len(itens_cache),
        "embeddings_reindexados": reindexados,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aplicar", action="store_true", help="grava as alterações (padrão: só simula)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="banco SQLite")
    parser.add_argument("--chroma", type=Path, default=None, help="pasta do cache semântico (padrão: data/chroma)")
    args = parser.parse_args()

    if args.chroma is not None:
        from src.classifiers import embeddings

        embeddings._CHROMA_PERSIST_DIR = args.chroma

    if not args.db.exists():
        print(f"ERRO: banco não encontrado: {args.db}", file=sys.stderr)
        sys.exit(1)

    relatorio = realinhar(args.db, aplicar=args.aplicar)
    fusoes = relatorio["fusoes"]
    print(f"Produtos de mesmo nome a fundir: {sum(len(o) for _, o, _ in fusoes)} em {len(fusoes)} grupo(s)")
    for destino, origens, nome in fusoes:
        print(f"  {nome!r} (id {destino}) <- {origens}")
    print(f"Itens com nome diferente do produto: {relatorio['nomes_desalinhados']}")
    print(f"Itens órfãos (produto inexistente): {relatorio['orfaos']}")
    print(f"Entradas do cache semântico a remover: {relatorio['embeddings_a_remover']}")
    print(f"Itens classificados a reindexar no cache: {relatorio['itens_a_reindexar']}")
    if args.aplicar:
        print(f"\nAplicado. Embeddings removidos: {relatorio['embeddings_removidos']}; "
              f"reindexados: {relatorio['embeddings_reindexados']}.")
    else:
        print("\nSimulação: nada foi gravado. Use --aplicar para gravar (faça backup antes).")


if __name__ == "__main__":
    main()
