---
trigger: always_on
---

# Instructions - Sistema Gerenciamento de Gastos Mensais

## Arquitetura do Projeto

Este é um sistema de gerenciamento de despesas mensais em Python que:
1. Extrai dados de notas fiscais do site da Receita Gaúcha (`https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx`)
2. Classifica automaticamente os itens usando IA via LiteLLM (modelos Gemini)
3. Armazena dados no DuckDB para análise
4. Apresenta interface web com Streamlit

## Stack Tecnológico

- **Frontend**: Streamlit (interface web)
- **Backend**: Python 3.13.1
- **IA/ML**: LiteLLM com modelos Gemini (`gemini/gemini-2.5-pro`) para classificação de itens
- **Banco de Dados**: DuckDB
- **Web Scraping**: Para extração de dados da Receita Gaúcha
- **Ambiente**: Virtual environment com `uv` (Python package manager)(`uv pip`, `uv venv`,`uv run`,`uv add`, etc.)
- **ambeiente virtual**: `.venv`, verifique sempre estar com o ambiente ativo, use `.\.venv\Scripts\Activate.ps1` no powershell

## Estrutura de Interfaces Planejadas

### 1. Interface de Importação
- Input para chave de acesso da nota fiscal
- Validação e busca automática no site da Receita Gaúcha
- Processamento e armazenamento dos dados

### 2. Interface de Visualização
- Lista de notas fiscais importadas
- Detalhamento dos itens por nota
- Status de classificação dos produtos

### 3. Interface de Relatórios
- Gráficos mensais de gastos
- Análise de custos por categoria de itens
- Dashboards interativos com Streamlit

## Convenções Específicas do Projeto

### Nomenclatura
- Use português brasileiro para nomes de variáveis e funções relacionadas ao domínio
- Mantenha comentários e documentação em português
- Exemplos: `classificar_item()`, `nota_fiscal`, `categoria_produto`

### Integração com Receita Gaúcha
- A consulta deve enviar um POST para `https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp` com `HML=false`, `chaveNFe=<44 dígitos>` e `Action=Avançar`, usando como *referer* `.../SAT-WEB-NFE-NFC_1.asp?chaveNFe=<44 dígitos>`.
- Simule os cabeçalhos de um navegador moderno (User-Agent, Accept, Accept-Language, Origin, Cache-Control, etc.) para evitar bloqueios.
- Salve o HTML retornado em `data/raw_nfce/nfce_<chave>.html` para facilitar depuração.
- Implemente tratamento robusto de erros para web scraping e considere rate limiting para evitar bloqueios.

### Classificação com IA
- Use LiteLLM apontando para `gemini/gemini-2.5-pro` para classificar itens nunca processados
- Configure `GEMINI_API_KEY` no `.env`
- Armazene classificações para evitar reprocessamento
- Implemente fallback para classificação manual

## Ambiente de Desenvolvimento

### Setup Inicial
```bash
# Ativar ambiente virtual
.\.venv\Scripts\Activate.ps1

# Instalar dependências
uv pip install -r requirements.txt

# OU instalar pacotes individuais
uv pip install streamlit duckdb httpx beautifulsoup4 pytest python-dotenv
```

### ⚠️ IMPORTANTE: Gerenciamento de Pacotes
- **SEMPRE use `uv pip install`** ao invés de `pip install`
- **SEMPRE use `uv pip`** para todas as operações de pacotes
- O projeto usa `uv` como gerenciador de pacotes Python
- Comando para rodar testes: `.\.venv\Scripts\Activate.ps1; pytest`

### Estrutura de Arquivos Sugerida
```
├── main.py                 # Ponto de entrada Streamlit
├── src/
│   ├── scrapers/           # Módulos para extração de dados
│   ├── classifiers/        # Integração com LiteLLM + Gemini
│   ├── database/           # Operações DuckDB
│   └── ui/                 # Componentes Streamlit
├── data/                   # Banco DuckDB e arquivos temporários
└── tests/                  # Testes unitários
```

### Comandos Essenciais
```bash
# Rodar testes
.\.venv\Scripts\Activate.ps1; pytest

# Executar aplicação Streamlit
.\.venv\Scripts\Activate.ps1; streamlit run main.py

# Desenvolvimento com auto-reload
.\.venv\Scripts\Activate.ps1; streamlit run main.py --server.runOnSave true

# Instalar nova dependência
.\.venv\Scripts\Activate.ps1; uv pip install <pacote>
```

## Padrões de Dados

### Nota Fiscal
- Chave de acesso: 44 dígitos numéricos
- Dados essenciais: data, estabelecimento, valor total, itens
- Armazenar dados brutos e normalizados separadamente

### Classificação de Itens
- Categorias sugeridas: alimentação, limpeza, higiene, etc.
- Manter histórico de classificações para aprendizado
- Implementar validação manual para correções

## Considerações de Performance

- Use DuckDB para consultas analíticas rápidas
- Cache classificações de IA para evitar custos desnecessários  
- Implemente paginação para listas de notas fiscais
- Otimize queries com índices apropriados no DuckDB