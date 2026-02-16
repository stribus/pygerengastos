# Build e Distribuição - PyGerenGastos

## Gerando a Build

Este projeto usa `uv` para gerenciamento de pacotes e build. Para gerar os artefatos distribuíveis:

```powershell
# Build limpa (recomendado)
.\build_uv.ps1 -CleanFirst

# Build incremental
.\build_uv.ps1
```

Os artefatos gerados estarão em `dist/`:
- `gerenciador_de_despesa-0.1.0-py3-none-any.whl` (wheel - recomendado)
- `gerenciador_de_despesa-0.1.0.tar.gz` (source distribution)

## Instalando o Pacote

### Instalação via uv (Recomendado)

```powershell
# Instalar o wheel
uv pip install dist\gerenciador_de_despesa-0.1.0-py3-none-any.whl

# Ou instalar do source
uv pip install dist\gerenciador_de_despesa-0.1.0.tar.gz
```

### Instalação via pip

```powershell
pip install dist\gerenciador_de_despesa-0.1.0-py3-none-any.whl
```

## Executando a Aplicação Após Instalação

Após instalar o pacote, você precisa executar o Streamlit manualmente:

```powershell
# Ative seu ambiente virtual primeiro
.\.venv\Scripts\Activate.ps1

# Execute o Streamlit apontando para o main.py
streamlit run main.py
```

**Nota**: O pacote wheel/tar.gz contém apenas a biblioteca (`src/`), não o script `main.py`. Para distribuição completa com interface, use o `build.ps1` original que cria um pacote standalone.

## Opções de Distribuição

### 1. Pacote Python (uv build) - Para desenvolvedores
- Gera wheel e source distribution
- Instalável via pip/uv
- Requer configuração adicional para executar
- **Use quando**: distribuindo para outros desenvolvedores Python

### 2. Pacote Standalone (build.ps1) - Para usuários finais
- Inclui ambiente virtual completo
- Scripts de execução (.bat e .ps1)
- Pronto para uso
- **Use quando**: distribuindo para usuários não-técnicos

```powershell
# Build standalone completo
.\build.ps1 -PackageName pygerengastos

# Build standalone sem compactar (mais rápido para testes)
.\build.ps1 -SkipZip

# Build standalone incluindo dados brutos (debug)
.\build.ps1 -IncludeRawData
```

## Estrutura dos Builds

### uv build (Pacote Python)
```
dist/
├── gerenciador_de_despesa-0.1.0-py3-none-any.whl
└── gerenciador_de_despesa-0.1.0.tar.gz
```

### build.ps1 (Standalone)
```
dist/
└── pygerengastos/
    ├── .venv/              # Ambiente virtual completo
    ├── src/                # Código fonte
    ├── config/             # Configurações (modelos LLM, etc)
    ├── data/               # Dados e configurações
    ├── main.py             # Entry point
    ├── start.bat           # Executável Windows
    ├── start.ps1           # Script PowerShell
    ├── setup.ps1           # Script de configuração
    ├── .env.example        # Exemplo de configuração
    └── requirements.txt    # Dependências
```

## Configuração Pós-Instalação

Independente do método de instalação, você precisa:

1. **Configurar a API do Gemini**:
   - Obtenha sua chave em: https://aistudio.google.com/apikey
   - Crie um arquivo `.env` com: `GEMINI_API_KEY=sua_chave_aqui`

2. **Criar a estrutura de dados**:
   - A primeira execução criará automaticamente o banco DuckDB
   - As categorias serão importadas de `data/categorias.csv`

## Desenvolvimento

Para desenvolvimento ativo, use o ambiente local:

```powershell
# Sincronizar dependências
uv sync

# Ativar ambiente virtual
.\.venv\Scripts\Activate.ps1

# Executar aplicação
streamlit run main.py

# Executar testes
pytest

# Build para teste
.\build_uv.ps1
```

## Publicação no PyPI (Futuro)

Quando estiver pronto para publicar:

```powershell
# Build
uv build

# Publicar (necessita configurar credenciais)
uv publish
```
