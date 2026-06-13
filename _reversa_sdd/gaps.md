# Gaps — Lacunas Identificadas

> Gerado pelo Revisor em 2026-06-07
> doc_level: completo

## Lacunas Moderadas

| # | Unit | Descrição | Severidade | Status |
|---|------|-----------|------------|--------|
| 1 | database | `database/__init__.py` com 2.501 LOC — violação de SRP. Sugerido dividir em schema.py, crud.py, normalization.py, queries.py, consolidation.py | Moderado | 🙈 Reconhecida — não prioritário, boa para melhoria futura |
| 2 | database | Sem migrations versionadas — schema criado com IF NOT EXISTS, sem rastreabilidade de mudanças | Moderado | 🟡 Aberta |

## Observações

- Nenhuma lacuna crítica (🔴) permanece sem resposta.
- Todas as perguntas foram validadas com o usuário e resolvidas.
