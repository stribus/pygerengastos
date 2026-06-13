# Traceability, Code-Spec Matrix

| Arquivo do legado | Unit correspondente | Cobertura |
|---------|---------------------|-----------|
| `src/classifiers/llm_classifier.py` | LLM Classifier | 🟢 |
| `src/classifiers/embeddings.py` | Embeddings | 🟢 |
| `src/classifiers/__init__.py` | Classificador híbrido | 🟢 |
| `src/database/__init__.py` | Banco de dados | 🟢 |
| `src/database/__init__.py` | Persistência e queries | 🟢 |
| `src/database/__init__.py` | Normalização de produto | 🟢 |
| `src/scrapers/receita_rs.py` | Scraper | 🟢 |
| `src/ui/home.py` | Dashboard | 🟢 |
| `src/ui/importacao.py` | Importação | 🟢 |
| `src/ui/analise.py` | Revisão | 🟢 |
| `src/ui/normalizacao.py` | Normalização de produtos | 🟢 |
| `src/ui/relatorios.py` | Relatórios e dashboards | 🟢 |
| `main.py` | Entry point | 🟢 |
| `pyproject.toml` | Configuração | 🟢 |
| `uv.lock` | Dependências | 🟡 |
| `build.ps1` | Build/Package | 🟡 |
| `src/logger.py` | Logger | 🟡 |
| `src/logger.py` | Configuração de logging | 🟡 |
| `src/logger.py` | Formatação de logs | 🟡 |
| `config/modelos_llm.toml` | Configuração de LLM | 🟢 |
| `.env.example` | Template de variáveis de ambiente | 🟡 |

| `tests/` (pasta) | Test coverage mapping | n/a |
| `tests/test_receita_rs.py` | Testes de scraper | 🟡 |
| `tests/test_llm_classifier.py` | Testes de classifier | 🟡 |
| `tests/test_database.py` | Testes DB | 🟡 |
| `tests/test_embeddings_similarity.py` | Testes embeddings | 🟡 |
| `tests/test_embeddings_consolidacao.py` | Testes consolidacao | 🟡 |
| `tests/test_embeddings_cache.py` | Testes cache | 🟡 |
| `tests/test_integration_llm.py` | Testes integração LLM | 🟡 |
| `e2e/example.spec.js` | Testes E2E | 🟡 |
| `data/raw_nfce/` (pasta) | HTMLs Crusos | 🟡 |
| `data/categorias.csv` | Categorias | 🟡 |
| `data/gastos.db` | Banco principal | 🟡 |
| `data/chroma/` | Embeddings DB | 🟡 |
| `logs/` (pasta) | Logs | 🟡 |
| `script/` (pasta) | Scripts auxiliares | 🟡 |
| `dist/` (pasta) | Artefatos de build | 🟡 |