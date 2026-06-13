# ADR-005: Classificação Híbrida em Dois Estágios

**Data:** 2024-2025
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

O sistema precisava classificar itens de notas fiscais em categorias de orçamento doméstico. Uma abordagem puramente baseada em LLM seria cara e lenta; puramente baseada em regras seria frágil.

## Decisão

Implementar pipeline de classificação em 2 estágios:
1. **Cache semântico** (ChromaDB + sentence-transformers): busca por similaridade vetorial em descrições já classificadas
2. **LLM** (LiteLLM): fallback para itens sem match no cache

O LLM recebe contexto (estabelecimento, data, categorias disponíveis) para melhor precisão.

## Consequências

- Itens recorrentes classificados instantaneamente (sem LLM)
- LLM residual para itens novos ou descrições muito diferentes
- Pipeline extensível: novos estágios podem ser adicionados
- Complexidade de orquestração entre estágios
- Necessidade de gerenciar score de similaridade (threshold 0.82)
