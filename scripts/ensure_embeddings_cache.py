"""Script utilitário para garantir que o modelo de embeddings esteja em cache local.

Usado pelo processo de build (build.ps1) para pré-cachear o modelo antes de empacotar
a aplicação, evitando que o pacote gerado precise de conexão com a internet na primeira
execução do usuário final.

Uso:
    python scripts/ensure_embeddings_cache.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite execução a partir da raiz do projeto sem necessidade de instalar o pacote
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.classifiers.embeddings import garantir_cache_embeddings


def main() -> None:
    try:
        cache_dir = garantir_cache_embeddings()
        print(f"Cache de embeddings pronto em: {cache_dir}")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"ERRO: Falha ao garantir cache de embeddings: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
