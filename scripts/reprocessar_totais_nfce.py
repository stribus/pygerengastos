"""Recalcula totais, descontos e pagamentos das notas já gravadas a partir do HTML salvo.

Notas importadas antes da leitura do bloco de totais do layout tabular ficaram
com o valor bruto (sem desconto) e sem formas de pagamento. Este script relê os
arquivos de data/raw_nfce e atualiza apenas valor_total, desconto, valor_pago e
pagamentos — itens, produtos e classificações não são tocados. Notas sem HTML
salvo ficam como estão.

Por padrão apenas simula e mostra o que mudaria; use --aplicar para gravar.
Faça backup de data/gastos.db antes de aplicar.

Uso:
    python scripts/reprocessar_totais_nfce.py [--aplicar] [--db CAMINHO] [--html PASTA]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite execução a partir da raiz do projeto sem necessidade de instalar o pacote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database import DEFAULT_DB_PATH, atualizar_totais_nota, carregar_nota
from src.scrapers.receita_rs import RAW_HTML_DIR, carregar_nfce_de_arquivo


def _pagamentos(nota) -> list[tuple[str, object]]:
    """Formas de pagamento comparáveis independentemente da ordem."""
    return sorted((pagamento.forma, pagamento.valor) for pagamento in nota.pagamentos)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--aplicar", action="store_true", help="grava as alterações (padrão: só simula)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="banco SQLite")
    parser.add_argument("--html", type=Path, default=RAW_HTML_DIR, help="pasta com nfce_<chave>.html")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"ERRO: banco não encontrado: {args.db}", file=sys.stderr)
        sys.exit(1)

    arquivos = sorted(args.html.glob("nfce_*.html"))
    alteradas = 0
    for arquivo in arquivos:
        nota = carregar_nfce_de_arquivo(arquivo)
        atual = carregar_nota(nota.chave_acesso, db_path=args.db)
        if atual is None:
            print(f"{nota.chave_acesso}: não está no banco, ignorada")
            continue

        mudou = (
            atual.valor_total != nota.valor_total
            or atual.desconto != nota.desconto
            or atual.valor_pago != nota.valor_pago
            or _pagamentos(atual) != _pagamentos(nota)
        )
        if not mudou:
            print(f"{nota.chave_acesso}: já correta")
            continue

        alteradas += 1
        print(
            f"{nota.chave_acesso}: valor_total {atual.valor_total} -> {nota.valor_total}, "
            f"desconto {atual.desconto} -> {nota.desconto}, "
            f"valor_pago {atual.valor_pago} -> {nota.valor_pago}, "
            f"pagamentos {len(atual.pagamentos)} -> {len(nota.pagamentos)}"
        )
        if args.aplicar:
            atualizar_totais_nota(nota, db_path=args.db)

    modo = "atualizada(s)" if args.aplicar else "a atualizar (simulação; use --aplicar para gravar)"
    print(f"\n{len(arquivos)} HTML(s) lido(s); {alteradas} nota(s) {modo}.")


if __name__ == "__main__":
    main()
