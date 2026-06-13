# Inventário — Gerenciador de despesa

> Gerado pelo Scout em 2026-06-06

## Visão Geral

Aplicação Python + Streamlit que importa notas fiscais eletrônicas (NFC-e) do portal da Receita Gaúcha, classifica itens automaticamente via LiteLLM/Gemini e armazena tudo em SQLite3 para visualização de gastos.

## Estrutura de Diretórios

```
/
├── main.py                  # Entry point da aplicação Streamlit
├── pyproject.toml           # Configuração do projeto e dependências
├── requirements.txt         # Dependências compiladas (uv)
├── uv.lock                  # Lockfile do uv
├── build.ps1                # Script de build/Packaging
├── .env.example             # Template de variáveis de ambiente
│
├── src/
│   ├── __init__.py
│   ├── logger.py            # Configuração de logging
│   ├── classifiers/
│   │   ├── __init__.py
│   │   ├── embeddings.py    # Embeddings semânticos (ChromaDB + sentence-transformers)
│   │   └── llm_classifier.py # Classificador via LiteLLM (Gemini, NVIDIA NIM, OpenAI)
│   ├── database/
│   │   └── __init__.py      # Camada de persistência SQLite3 (schema, CRUD, consultas)
│   ├── scrapers/
│   │   ├── __init__.py
│   │   └── receita_rs.py    # Scraper NFC-e da SEFAZ-RS
│   └── ui/
│       ├── __init__.py
│       ├── home.py          # Página Home
│       ├── importacao.py    # Importação de notas fiscais
│       ├── analise.py       # Análise e classificação de itens
│       ├── normalizacao.py  # Normalização de produtos
│       └── relatorios.py    # Relatórios e dashboards
│
├── config/
│   ├── modelos_llm.toml     # Configuração de modelos LLM
│   └── README.md
│
├── tests/
│   ├── __init__.py
│   ├── test_database_utils.py
│   ├── test_database.py
│   ├── test_embeddings_cache.py
│   ├── test_embeddings_consolidacao.py
│   ├── test_embeddings_similarity.py
│   ├── test_integration_llm.py
│   ├── test_llm_classifier.py
│   ├── test_llm_config_loading.py
│   ├── test_modelos_llm_toml.py
│   ├── test_normalizacao_produtos.py
│   ├── test_produto_categoria_update.py
│   ├── test_receita_rs.py
│   ├── test_relatorios.py
│   └── test_semantic_integration.py
│
├── e2e/
│   └── example.spec.js       # Playwright E2E (stub)
│
├── data/
│   ├── categorias.csv        # Categorias de orçamento doméstico
│   ├── gastos.db             # Banco SQLite3 principal
│   ├── chroma/               # Banco vetorial ChromaDB
│   ├── raw_nfce/             # HTMLs brutos de NFC-e baixados
│   └── README.md
│
├── cache/
│   └── huggingface/          # Cache de modelos HuggingFace
│
├── logs/                     # Arquivos de log
├── docs/                     # Documentação (vazio)
├── scripts/                  # Scripts auxiliares (vazio)
└── dist/                     # Artefatos de build
```

## Entry Points

| Tipo | Caminho | Descrição |
|------|---------|-----------|
| App entry | `main.py` | Ponto de entrada do Streamlit |
| Script | `pyproject.toml → gerengastos` | `streamlit:main` |
| Build | `build.ps1` | Empacotamento para distribuição |

## Banco de Dados (SQLite3)

10 tabelas + 1 view:

| Tabela | Finalidade |
|--------|------------|
| `categorias` | Categorias de orçamento doméstico |
| `estabelecimentos` | Estabelecimentos comerciais (CNPJ) |
| `datas_referencia` | Dimensão de data para análises |
| `notas` | Notas fiscais eletrônicas |
| `produtos` | Produtos padronizados |
| `aliases_produtos` | Aliases de texto original → produto |
| `itens` | Itens de cada nota fiscal |
| `pagamentos` | Formas de pagamento por nota |
| `classificacoes_historico` | Histórico de classificações LLM |
| `revisoes_manuais` | Revisões manuais de classificação |
| `consolidacoes_historico` | Histórico de consolidação de produtos |
| `vw_itens_padronizados` | View com itens + datas + estabelecimentos |

Armazenamento vetorial: ChromaDB em `data/chroma/`

## Cobertura de Testes

- **Framework:** pytest 9.0.3 (marker: `integration`)
- **Arquivos de teste:** 14 em `tests/`
- **E2E:** Playwright (1 spec stub em `e2e/`)

## Configuração

- `.env.example` → chaves de API (Gemini, NVIDIA NIM, OpenAI)
- `config/modelos_llm.toml` → modelos LLM configurados
- Modelos: Gemini 2.5 Flash Lite, DeepSeek V4 Pro/Flash, Kimi K2.6

## CI/CD

Nenhum pipeline de CI/CD detectado.
