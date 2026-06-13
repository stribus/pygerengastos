# Confidence Report — Gerenciador de despesa

> Gerado pelo Revisor em 2026-06-07
> doc_level: completo

## Sumário

| Métrica | Valor |
|---------|-------|
| Units revisadas | 5 (classifiers, database, scrapers, ui, config) |
| Total de arquivos revisados | 16 (5 requirements + 5 design + 5 tasks + 1 contracts) |
| Globais revisados | 2 (code-spec-matrix, spec-impact-matrix) |
| 🟢 CONFIRMADO | 114 |
| 🟡 INFERIDO | 7 |
| 🔴 LACUNA | 2 |
| **Confiança geral** | **92.7%** |

## Detalhamento por Unit

### classifiers
| Arquivo | 🟢 | 🟡 | 🔴 |
|---------|----|----|----|
| requirements.md | 10 | 0 | 0 |
| design.md | 4 | 2 | 0 |
| tasks.md | 8 | 0 | 0 |
| contracts.md | 1 | 0 | 0 |
| **Subtotal** | **23** | **2** | **0** |

### database
| Arquivo | 🟢 | 🟡 | 🔴 |
|---------|----|----|----|
| requirements.md | 13 | 0 | 0 |
| design.md | 5 | 1 | 1 |
| tasks.md | 9 | 0 | 1 |
| **Subtotal** | **27** | **1** | **2** |

### scrapers
| Arquivo | 🟢 | 🟡 | 🔴 |
|---------|----|----|----|
| requirements.md | 7 | 0 | 0 |
| design.md | 4 | 1 | 1 |
| tasks.md | 10 | 0 | 0 |
| **Subtotal** | **21** | **1** | **1** |

### ui
| Arquivo | 🟢 | 🟡 | 🔴 |
|---------|----|----|----|
| requirements.md | 23 | 0 | 0 |
| design.md | 12 | 2 | 0 |
| tasks.md | 17 | 0 | 0 |
| **Subtotal** | **52** | **2** | **0** |

### config
| Arquivo | 🟢 | 🟡 | 🔴 |
|---------|----|----|----|
| requirements.md | 7 | 0 | 0 |
| design.md | 5 | 1 | 0 |
| tasks.md | 6 | 0 | 0 |
| **Subtotal** | **18** | **1** | **0** |

## Lacunas 🔴

1. **database** — `database/__init__.py` com 2.501 LOC (violação de SRP). Reconhecida, não prioritária.
2. **scrapers** — Portal SEFAZ-RS pode mudar layout HTML. Risco operacional conhecido.
3. **database** — Sem migrations versionadas. Schema gerenciado via IF NOT EXISTS.

## Inferências 🟡

1. **classifiers** — Retry count lido de env var `LLM_NUM_RETRIES` (default 2) — sem fallback se mal formatada
2. **classifiers** — Dependência de API externa (Gemini, NVIDIA NIM, OpenAI)
3. **database** — Sem migrations versionadas
4. **scrapers** — Tratamento de timeout/reconnect do portal SEFAZ não detalhado
5. **ui** — Cesta básica não usa ponderação por quantidade (assume quantidade=1)
6. **ui** — Embeddings exigem download inicial (~80MB)
7. **config** — Timeout 30s Gemini pode ser baixo para lotes grandes

## Reclassificações

| Unit | Arquivo | Antes | Depois | Motivo |
|------|---------|-------|--------|--------|
| classifiers | contracts.md | nvidia_nim/deepseek-v4-PRO | nvidia_nim/deepseek-ai/deepseek-v4-pro | Validação do usuário |
| traceability | code-spec-matrix.md | n/a (3 entradas) | Removido | Arquivos não existem |

## Notas

- Revisão cruzada via Codex: não realizada (plugin indisponível nesta engine)
- Todas as perguntas foram respondidas pelo usuário (4/4)
- Nenhuma lacuna crítica (🔴) bloqueia reimplementação
