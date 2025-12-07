# Copilot Instructions - Sistema Gerenciamento de Gastos Mensais

## Arquitetura do Projeto

Este é um sistema de gerenciamento de despesas mensais em Python que implementa um pipeline completo:
1. **Web Scraping**: Extrai NFC-e do site da SEFAZ-RS via POST request com cabeçalhos específicos
2. **Classificação Híbrida**: Usa busca semântica (ChromaDB + SentenceTransformers) com fallback para LLM (Gemini via LiteLLM)
3. **Persistência**: DuckDB com schema dimensional (datas, estabelecimentos, produtos, categorias)
4. **Interface**: Streamlit com 3 abas (Home/Importação/Análise) e navegação com redirecionamento

## Stack Tecnológico

- **Frontend**: Streamlit com `st.session_state` para navegação e cache
- **Backend**: Python 3.13.1
- **IA/ML**: 
  - Busca semântica: ChromaDB 1.3.5 + SentenceTransformers 5.1.2 (modelo `all-MiniLM-L6-v2`)
  - LLM: LiteLLM apontando para `gemini/gemini-2.5-flash-lite` (não `3-pro-preview`)
- **Banco de Dados**: DuckDB com schema normalizado e views agregadas
- **Web Scraping**: httpx + BeautifulSoup4
- **Ambiente**: `uv` como gerenciador de pacotes (use `uv pip`, `uv add`, nunca `pip install` direto)
- **Logging**: Sistema centralizado via `src/logger.py` com RotatingFileHandler em `logs/app.log`

## Fluxo de Classificação Híbrida (CRÍTICO)

O sistema usa **classificação semântica prioritária** com fallback para LLM:

1. **Busca Semântica (ChromaDB)**: Para cada item, busca produtos similares por embedding
   - Se `score >= 0.82`: reutiliza `produto_id`, `categoria`, `nome_base`, `marca_base` (origem: `chroma-cache`)
   - Embeddings gerados com `all-MiniLM-L6-v2` e armazenados em `data/chroma/`
   
2. **Fallback LLM (Gemini)**: Apenas para itens sem match semântico
   - Modelo: `gemini/gemini-2.5-flash-lite` via LiteLLM
   - Retorna: categoria + confiança + produto_nome + produto_marca + justificativa
   - Origem: `gemini-litellm`

3. **Persistência Automática**: Ambos os fluxos atualizam DuckDB e registram embeddings via `_registrar_alias_produto()`

**Exemplo de implementação**: Ver `src/classifiers/__init__.py::classificar_itens_pendentes()` e testes em `tests/test_semantic_integration.py`

## Convenções Específicas do Projeto

### Nomenclatura
- **Domínio**: Português BR (`salvar_nota()`, `categoria_confirmada`, `emitente_nome`)
- **Técnico**: Inglês OK para padrões Python (`logger`, `dataclass`, `db_path`)
- **Documentação**: Sempre em português

### Integração com SEFAZ-RS (src/scrapers/receita_rs.py)
```python
# POST para endpoint oficial com cabeçalhos simulando navegador
NFCE_POST_URL = "https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp"
# Payload: HML=false, chaveNFe=<44 dígitos>, Action=Avançar
# Referer: .../SAT-WEB-NFE-NFC_1.asp?chaveNFe=<chave>
# Salva HTML em: data/raw_nfce/nfce_<chave>.html
```

### Logging Padronizado
```python
from src.logger import setup_logging
logger = setup_logging(__name__)  # Usa nome do módulo
# Logs vão para logs/app.log (rotating 5MB, 3 backups) + console
```

## Ambiente de Desenvolvimento

### Setup Inicial (Windows PowerShell)
```powershell
# Ativar ambiente virtual
.\.venv\Scripts\Activate.ps1

# Instalar dependências (SEMPRE use uv)
uv sync  # Ou: uv pip install -r requirements.txt

# Rodar aplicação
streamlit run main.py

# Rodar testes
pytest  # Filtra warnings do pydantic/litellm via pyproject.toml
```

### ⚠️ CRÍTICO: Gerenciamento de Pacotes
- **NUNCA** use `pip install` diretamente
- **SEMPRE** use `uv add <pacote>` para adicionar dependências
- O `uv` atualiza automaticamente `pyproject.toml` e `uv.lock`

### Estrutura Real do Projeto
```
├── main.py                      # Entry point Streamlit com navegação via session_state
├── src/
│   ├── logger.py                # Logging centralizado (RotatingFileHandler)
│   ├── scrapers/
│   │   └── receita_rs.py        # Scraper SEFAZ-RS + dataclasses (NotaFiscal, NotaItem)
│   ├── classifiers/
│   │   ├── __init__.py          # classificar_itens_pendentes() - orquestra semântica + LLM
│   │   ├── embeddings.py        # ChromaDB: upsert_produto_embedding(), buscar_produtos_semelhantes()
│   │   └── llm_classifier.py    # LLMClassifier - wrapper LiteLLM/Gemini
│   ├── database/
│   │   └── __init__.py          # DuckDB: salvar_nota(), registrar_classificacao_itens(), views
│   └── ui/
│       ├── home.py              # Dashboard com KPIs e gráficos mensais
│       ├── importacao.py        # Input chave NFC-e + classificação automática
│       └── analise.py           # Edição de categoria/produto + histórico de revisões
├── data/
│   ├── gastos.duckdb            # Banco principal
│   ├── categorias.csv           # Seed de categorias (carregado via seed_categorias_csv())
│   ├── chroma/                  # Índice de embeddings
│   └── raw_nfce/                # HTMLs brutos das notas (debug)
├── tests/                       # Testes com pytest + fixtures públicas
├── build.ps1                    # Script de build para distribuição
└── pyproject.toml               # Config uv + pytest (filtra warnings)
```

## Schema DuckDB (Dimensional)

### Tabelas Principais
- `notas`: Cabeçalho da NFC-e (chave_acesso PK, estabelecimento_id FK, emissao_data)
- `itens`: Produtos da nota (chave_acesso + sequencia PK, produto_id FK, categoria_sugerida, categoria_confirmada)
- `produtos`: Entidade canônica (id PK, nome_base, marca_base, categoria_id FK)
- `aliases_produtos`: Mapeia descrições originais → produto_id (texto_original UNIQUE)
- `categorias`: Lista de categorias (id PK, grupo, nome)
- `estabelecimentos`: Emitentes normalizados (cnpj_normalizado UNIQUE)
- `datas_referencia`: Dimensão temporal (data_iso PK, ano_mes, nome_mes PT-BR)

### Tabelas de Auditoria
- `classificacoes_historico`: Log de todas as classificações (chroma-cache, gemini-litellm, revisao-manual)
- `revisoes_manuais`: Ajustes feitos por usuários (usuario, observacoes, confirmado)

### Views
- `vw_itens_padronizados`: Join completo com datas + estabelecimentos + categorias (usada pelos dashboards)

## Padrões de Implementação

### Transações DuckDB
```python
from src.database import conexao, salvar_nota

# SEMPRE use context manager
with conexao() as con:
    con.execute("BEGIN TRANSACTION")
    try:
        # operações...
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
```

### Navegação Streamlit
```python
# Redirecionar entre abas
st.session_state["redirecionar_menu"] = "Analisar notas"
st.rerun()

# Passar dados entre telas
st.session_state["nota_em_revisao"] = chave_acesso
```

### Classificação Manual vs Automática
```python
# Sugestão (categoria_sugerida):
classificar_itens_pendentes(confirmar=False)

# Confirmação (categoria_confirmada + produto_id):
registrar_revisoes_manuais([...], confirmar=True, usuario="João")
```

## Comandos de Build/Distribuição

```powershell
# Build completo com venv empacotada
.\build.ps1 -PackageName pygerengastos

# Build sem compactar
.\build.ps1 -SkipZip

# Build com dados brutos (para debug)
.\build.ps1 -IncludeRawData
```

## Considerações de Performance

- **ChromaDB**: Índice regenerado automaticamente em `upsert_produto_embedding()` após cada classificação
- **DuckDB**: Queries rápidas via views materializadas (`vw_itens_padronizados`)
- **LLM**: Apenas chamado para itens sem match semântico (economia de tokens/custo)
- **HTML Cache**: `data/raw_nfce/` facilita re-parsing sem re-scraping

## Debugging/Troubleshooting

- **Logs**: Sempre consulte `logs/app.log` primeiro
- **Embeddings**: Se busca semântica falha, delete `data/chroma/` e reimporte notas
- **LLM**: Verifique `GEMINI_API_KEY` no `.env` (carregado via `python-dotenv`)
- **Testes**: Fixture pública em `.github/xmlexemplo.xml` garante testes determinísticos
- **Debug de produtos**: Use `debug_product_update.py` para inspecionar `produto_id` e aliases