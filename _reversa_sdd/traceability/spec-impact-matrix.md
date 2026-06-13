# Spec Impact Matrix — Gerenciador de despesa

> Gerado pelo Architect em 2026-06-06

## Matriz de Impacto entre Componentes

| Componente | classifiers | database | scrapers | ui | config | Externo |
|------------|-------------|----------|----------|-----|--------|---------|
| **classifiers** | — | Lê itens pendentes, registra classificação | — | Fornece classificação | Lê modelos LLM | ChromaDB, LiteLLM (Gemini/NVIDIA/OpenAI), HuggingFace |
| **database** | Registra resultados | — | Salva notas importadas | Fornece dados para KPIs/relatórios | — | SQLite3, ChromaDB (indireto) |
| **scrapers** | — | Salva notas via database | — | Chamado pela importação | — | SEFAZ-RS (HTTP) |
| **ui** | Chama classificação | Chama todas as queries | Chama importação | — | — | — |
| **config** | Consome configuração TOML | — | — | — | — | .env (variáveis de ambiente) |

## Legendas

| Símbolo | Significado |
|---------|-------------|
| **Fornece** | O componente da linha exporta funcionalidade usada pelo da coluna |
| **Consome** | O componente da linha importa/depende do da coluna |
| — | Sem dependência direta |

## Matriz de Impacto para Specs (geração do Writer)

Cada módulo virará uma pasta de specs por módulo, conforme `[specs] granularity = module`:

| Pasta de Spec | Depende de | Impacta |
|---------------|-----------|---------|
| `classifiers/` | database, config | Geração das specs de cache semântico e LLM |
| `database/` | — | Geração das specs de schema SQL, CRUD, queries |
| `scrapers/` | — | Geração das specs de scraping NFC-e |
| `ui/` | classifiers, database, scrapers | Geração das specs de 5 páginas Streamlit |
| `config/` | — | Geração das specs de modelos LLM TOML |

## Riscos de Impacto

| # | Mudança em | Impacta | Risco | Descrição |
|---|-----------|---------|-------|-----------|
| 1 | Schema do banco | database, classifiers, ui, scrapers | 🔴 Alto | Mudança em tabela afeta todos os módulos |
| 2 | Modelo de embedding | classifiers, database | 🟡 Médio | Altera pipeline de cache semântico |
| 3 | Provedor LLM | classifiers, config | 🟢 Baixo | Trocado via TOML sem mudança de código |
| 4 | Layout SEFAZ-RS | scrapers | 🟡 Médio | Pode quebrar parsing de HTML |
| 5 | API LiteLLM | classifiers | 🟢 Baixo | Abstraction layer absorve mudanças |
