# Copilot Instructions - Sistema Gerenciamento de Gastos Mensais

## Arquitetura do Projeto

Este é um sistema de gerenciamento de despesas mensais em Python que implementa um pipeline completo:
1. **Web Scraping**: Extrai NFC-e do site da SEFAZ-RS via POST request com cabeçalhos específicos
2. **Classificação Híbrida**: Usa busca semântica (ChromaDB + SentenceTransformers) com fallback para LLM (Gemini via LiteLLM)
3. **Persistência**: SQLite3 com schema dimensional (datas, estabelecimentos, produtos, categorias)
4. **Interface**: Streamlit com 3 abas (Home/Importação/Análise) e navegação com redirecionamento

## Stack Tecnológico

- **Frontend**: Streamlit com `st.session_state` para navegação e cache
- **Backend**: Python 3.13.1
- **IA/ML**: 
  - Busca semântica: ChromaDB 1.3.5 + SentenceTransformers 5.1.2 (modelo `all-MiniLM-L6-v2`)
  - LLM: LiteLLM com modelos configuráveis via TOML (padrão: `gemini/gemini-2.5-flash-lite`)
  - Configuração: `config/modelos_llm.toml` com carregamento lazy + background thread
- **Banco de Dados**: SQLite3 (nativo Python) com schema normalizado e views agregadas
- **Web Scraping**: httpx + BeautifulSoup4
- **Ambiente**: `uv` como gerenciador de pacotes (use `uv pip`, `uv add`, nunca `pip install` direto)
- **Logging**: Sistema centralizado via `src/logger.py` com RotatingFileHandler em `logs/app.log`

## Fluxo de Classificação Híbrida (CRÍTICO)

O sistema usa **classificação semântica prioritária** com fallback para LLM:

1. **Busca Semântica (ChromaDB)**: Para cada item, busca produtos similares por embedding
   - Se `score >= 0.82`: reutiliza `produto_id`, `categoria`, `nome_base`, `marca_base` (origem: `chroma-cache`)
   - Embeddings gerados com `all-MiniLM-L6-v2` e armazenados em `data/chroma/`
   
2. **Fallback LLM (Gemini)**: Apenas para itens sem match semântico
   - Modelos configuráveis em `config/modelos_llm.toml` (Gemini, LLaMA, Kimi, GPT-4o)
   - Prioridade definida pela ordem no TOML ou ajustável na UI
   - Retorna: categoria + confiança + produto_nome + produto_marca + justificativa
   - Origem: `gemini-litellm` (ou outro modelo conforme configuração)

3. **Persistência Automática**: Ambos os fluxos atualizam SQLite3 e registram embeddings via `_registrar_alias_produto()`

**Exemplo de implementação**: Ver `src/classifiers/__init__.py::classificar_itens_pendentes()` e testes em `tests/test_semantic_integration.py`

## Por que SQLite3?

O projeto **migrou de DuckDB para SQLite3** (dezembro/2025) pelos seguintes motivos:

- **Melhor suporte a UPDATE com Foreign Keys**: SQLite3 permite `PRAGMA foreign_keys = OFF` temporário, resolvendo limitações do DuckDB ao atualizar colunas em tabelas com FKs apontando para elas
- **Maturidade OLTP**: Mais estável para operações frequentes de insert/update (CRUD típico)
- **Portabilidade**: Arquivo único `.db` sem dependências externas, nativo no Python (não precisa instalar pacote)
- **Performance adequada**: Volume de dados (notas fiscais pessoais) não justifica complexidade do DuckDB

## Configuração de Modelos LLM (IMPORTANTE)

### Carregamento Lazy + Background Thread

Os modelos LLM são carregados de forma **não-bloqueante** usando pattern de lazy loading com background concurrency:

```python
# main.py - Carregamento iniciado durante bootstrap do Streamlit
from src.classifiers.llm_classifier import iniciar_carregamento_background
iniciar_carregamento_background()  # Retorna Future, executa em thread

# Uso posterior - aguarda carregamento se necessário, usa cache se disponível
from src.classifiers.llm_classifier import obter_modelos_carregados
modelos = obter_modelos_carregados(aguardar=True)  # 5s timeout, fallback on failure
```

**Características:**
- **Thread-safe**: Double-checked locking para performance em sessões concorrentes
- **Cache em memória**: Uma vez carregados, reutiliza instâncias sem re-parsing
- **Fallback automático**: Se TOML malformado/ausente, usa configuração hardcoded do Gemini
- **Timeout**: 5s (constante `BACKGROUND_LOAD_TIMEOUT`) antes de fallback

### Arquivo de Configuração

`config/modelos_llm.toml` centraliza configurações de todos os modelos:

```toml
[[modelos]]
nome = "gemini/gemini-2.5-flash-lite"
nome_amigavel = "Gemini 2.5 Flash Lite (Padrão)"
api_key_env = "GEMINI_API_KEY"
max_tokens = 8000
max_itens = 50
timeout = 30.0

# Opcional: parâmetros específicos do modelo
[modelos.extra_body.chat_template_kwargs]
thinking = false
```

**Campos obrigatórios**: `nome`, `api_key_env`  
**Campos opcionais**: `max_tokens`, `max_itens`, `timeout`, `nome_amigavel`, `extra_body`

### Tratamento de Erros TOML

O sistema é **resiliente a erros de configuração**:

| Erro | Comportamento |
|------|---------------|
| Sintaxe TOML inválida | Loga erro + usa fallback Gemini |
| Campo obrigatório ausente | Pula modelo inválido + carrega válidos |
| Nenhum modelo válido | Usa fallback Gemini hardcoded |
| Arquivo não encontrado | Loga erro + usa fallback Gemini |

**Fallback Gemini** (`_obter_modelos_fallback()`):
```python
ModeloConfig(
    nome="gemini/gemini-2.5-flash-lite",
    api_key_env="GEMINI_API_KEY",
    max_tokens=8000,
    max_itens=50,
    timeout=30.0,
    nome_amigavel="Gemini 2.5 Flash Lite (Fallback)"
)
```

### Hot-Reload (Sem Reiniciar App)

Recarregar configurações após editar TOML:

**Via UI**: "Importar nota" → "⚙️ Configurações de LLM" → "🔄 Recarregar modelos"

**Via código**:
```python
from src.classifiers.llm_classifier import recarregar_modelos
modelos = recarregar_modelos()  # Invalida cache + recarrega TOML
```

### Helpers para Acessar Modelos

**SEMPRE use funções helpers** (nunca acesse `DEFAULT_MODELOS` diretamente):

```python
from src.classifiers.llm_classifier import (
    obter_modelos_disponiveis,      # Lista de IDs: ["gemini/...", "nvidia_nim/..."]
    obter_modelos_com_nomes_amigaveis,  # Dict {nome_amigavel: model_id}
    obter_modelos_carregados        # Lista de ModeloConfig (com cache)
)

# UI de seleção
modelos_dict = obter_modelos_com_nomes_amigaveis()
modelo_selecionado = st.selectbox("Modelo", options=list(modelos_dict.keys()))
model_id = modelos_dict[modelo_selecionado]
```

### Testes de Configuração

Testes abrangentes em `tests/test_llm_config_loading.py` (17 testes):
- TOML malformado → fallback
- Campos obrigatórios ausentes → pula modelo
- Carregamento concorrente (10 threads) → thread-safe
- Timeout em background loading → fallback
- Cache e invalidação → reuso correto
- Hot-reload → atualização sem restart

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
├── config/
│   ├── modelos_llm.toml         # Configuração de modelos LLM (Gemini, LLaMA, Kimi, GPT-4o)
│   └── README.md                # Documentação de configuração e hot-reload
├── src/
│   ├── logger.py                # Logging centralizado (RotatingFileHandler)
│   ├── scrapers/
│   │   └── receita_rs.py        # Scraper SEFAZ-RS + dataclasses (NotaFiscal, NotaItem)
│   ├── classifiers/
│   │   ├── __init__.py          # classificar_itens_pendentes() - orquestra semântica + LLM
│   │   ├── embeddings.py        # ChromaDB: upsert_produto_embedding(), buscar_produtos_semelhantes()
│   │   └── llm_classifier.py    # LLMClassifier + lazy loading + background thread + cache
│   ├── database/
│   │   └── __init__.py          # SQLite3: salvar_nota(), registrar_classificacao_itens(), views
│   └── ui/
│       ├── home.py              # Dashboard com KPIs e gráficos mensais
│       ├── importacao.py        # Input chave NFC-e + classificação automática + reload LLM
│       └── analise.py           # Edição de categoria/produto + histórico de revisões
├── data/
│   ├── gastos.db                # Banco principal (SQLite3)
│   ├── categorias.csv           # Seed de categorias (carregado via seed_categorias_csv())
│   ├── chroma/                  # Índice de embeddings
│   └── raw_nfce/                # HTMLs brutos das notas (debug)
├── tests/                       # Testes com pytest + fixtures públicas
│   ├── test_llm_config_loading.py  # 17 testes de lazy loading + concurrency + fallback
│   └── test_modelos_llm_toml.py    # Testes de sintaxe TOML (sub-tabela vs inline)
├── build.ps1                    # Script de build para distribuição
└── pyproject.toml               # Config uv + pytest (filtra warnings)
```

## Schema SQLite3 (Dimensional)

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

### Transações SQLite3
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
- **SQLite3**: Queries rápidas via views materializadas (`vw_itens_padronizados`)
- **LLM**: 
  - Apenas chamado para itens sem match semântico (economia de tokens/custo)
  - Modelos carregados em background thread (não bloqueia UI)
  - Cache em memória thread-safe (evita re-parsing TOML)
  - Fallback automático para Gemini em caso de erro (resiliente)
- **HTML Cache**: `data/raw_nfce/` facilita re-parsing sem re-scraping

## Debugging/Troubleshooting

- **Logs**: Sempre consulte `logs/app.log` primeiro
- **Embeddings**: Se busca semântica falha, delete `data/chroma/` e reimporte notas
- **LLM**: 
  - Verifique `GEMINI_API_KEY` (ou outra chave) no `.env` (carregado via `python-dotenv`)
  - Erros de configuração: veja `logs/app.log` para detalhes de parsing TOML
  - Recarregue modelos via UI se editou `config/modelos_llm.toml`
  - Se TOML malformado, sistema usa fallback Gemini automaticamente
- **Testes**: Fixture pública em `.github/xmlexemplo.xml` garante testes determinísticos
- **Debug de produtos**: Use `debug_product_update.py` para inspecionar `produto_id` e aliases
- **Configuração LLM**:
  - Teste sintaxe TOML: `python -m tomllib config/modelos_llm.toml`
  - Veja modelos carregados: `tests/test_llm_config_loading.py::test_arquivo_modelos_llm_atual`
  - Hot-reload: use botão UI ou `recarregar_modelos()` em código