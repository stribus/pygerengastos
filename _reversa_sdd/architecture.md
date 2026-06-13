# Architecture — Gerenciador de despesa

> Gerado pelo Architect em 2026-06-06

## Visão Geral

Aplicação desktop local em Python + Streamlit para importação de NFC-e (Nota Fiscal do Consumidor Eletrônica) do Rio Grande do Sul, classificação automática de itens via IA híbrida (cache semântico + LLM), e geração de relatórios de evolução de preços e inflação personalizada.

## Stack Tecnológica

| Camada | Tecnologia | Versão | Propósito |
|--------|-----------|--------|-----------|
| Linguagem | Python | ≥3.13 | Base da aplicação |
| UI | Streamlit | 1.54.0 | Interface gráfica desktop |
| ORM/Persistência | SQLite3 (stdlib) | — | Banco relacional (data/gastos.db) |
| Vetorial | ChromaDB | 1.5.7 | Cache semântico de classificações |
| Embeddings | sentence-transformers | 5.4.0 | Modelo all-MiniLM-L6-v2 (384d) |
| LLM Gateway | LiteLLM | 1.86.2 | Abstração multi-provedor |
| Scraping | BeautifulSoup4 + httpx | — | Parsing de HTML da SEFAZ-RS |
| Análise | pandas | 2.3.3 | Agregações e relatórios |
| Fuzzy Matching | rapidfuzz | 3.14.3 | Busca de produtos similares |
| Gerenciador | uv | — | Dependências e build |

## Arquitetura em Camadas

```
┌─────────────────────────────────────────────────────────────┐
│                      Streamlit UI                           │
│  Home  │  Importar  │  Analisar  │  Normalizar  │ Relatórios │
│  (KPIs) │  (NFC-e)   │ (Revisão)   │ (Consolidação) │ (Preços)   │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    src/classifiers/                          │
│  Cache Semântico (ChromaDB) → Fallback LLM (LiteLLM)       │
│  embeddings.py │ __init__.py │ llm_classifier.py             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│                    src/database/                             │
│  SQLite3 CRUD │ Normalização │ Consultas Analíticas         │
│  __init__.py (2.501 LOC)                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    src/scrapers/                             │
│  SEFAZ-RS NFC-e (BeautifulSoup)                             │
│  receita_rs.py (593 LOC)                                     │
└──────────────────────────────────────────────────────────────┘
```

## Integrações Externas

| Sistema | Tipo | Protocolo | Provedor |
|---------|------|-----------|----------|
| SEFAZ-RS NFC-e | Scraping web | HTTPS POST/GET | Governo RS |
| Gemini API | LLM | HTTPS (LiteLLM) | Google |
| NVIDIA NIM | LLM | HTTPS (LiteLLM) | NVIDIA |
| OpenAI API | LLM | HTTPS (LiteLLM) | OpenAI |
| HuggingFace Hub | Model hosting | HTTPS | HuggingFace |

## Dívidas Técnicas

| # | Descrição | Severidade | Local |
|---|-----------|------------|-------|
| DT01 | `database/__init__.py` com 2.501 LOC — viola SRP severamente | Alta | `src/database/__init__.py` |
| DT02 | Cesta básica usa média simples sem ponderação por quantidade | Média | `relatorios.py:167` |
| DT03 | Marcas conhecidas hardcoded (22 marcas) em vez de tabela no banco | Média | `database/__init__.py:433` |
| DT04 | Sem testes E2E (Playwright é stub) | Média | `tests/` |
| DT05 | `normalizar_produto_descricao` duplica lógica de normalização textual que existe em outras funções | Baixa | `database/__init__.py:502` |
| DT06 | Sem tratamento de throttling/rate-limit para scraping SEFAZ-RS | Baixa | `scrapers/receita_rs.py` |
| DT07 | ImportError fallback para `LocalEntryNotFoundError` — compatibilidade frágil entre transformers 4.x e 5.x | Baixa | `embeddings.py:9` |

## Decision Records

Ver ADRs em `_reversa_sdd/adrs/`:

1. Migração DuckDB → SQLite3
2. LiteLLM sobre Groq direto
3. ChromaDB como cache semântico
4. Configuração de modelos LLM em TOML
5. Classificação híbrida em 2 estágios
6. Cache offline-first para embeddings
7. Streamlit como plataforma de UI
8. Adoção de Spec-Driven Development
