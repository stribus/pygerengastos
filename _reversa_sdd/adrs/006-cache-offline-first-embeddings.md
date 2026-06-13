# ADR-006: Cache Offline-First para Modelo de Embeddings

**Data:** 2025-2026
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

O modelo de embeddings `all-MiniLM-L6-v2` (~80MB) precisa ser baixado do HuggingFace Hub. Em ambientes sem internet ou com conexão instável, a inicialização do sistema falhava.

## Decisão

Implementar cache offline-first:
1. Tentar carregar modelo do cache local (`~/.cache/huggingface/`)
2. Se não encontrado, baixar do HuggingFace Hub
3. Double-checked locking para thread-safety
4. Script de build (`build.ps1`) com `garantir_cache_embeddings()` para pré-carregar offline

## Alternativas consideradas

- **Download sempre online**: falha sem internet
- **Modelo incluído no repositório**: muito grande para versionar

## Consequências

- Inicialização offline possível (após primeiro download)
- Resiliência em ambientes sem internet
- Thread-safe para cenários concorrentes
- Script de build que garante cache antes da execução
