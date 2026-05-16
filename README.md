# Sistema de gerenciamento de gastos mensais

Aplicação em Python + Streamlit que importa notas fiscais eletrônicas (NFC-e) do portal da Receita Gaúcha, classifica itens automaticamente via LiteLLM/Gemini e armazena tudo em SQLite3 para visualização dos gastos.

## Status atual

- ✅ Scraper da SEFAZ-RS refeito para usar POST no endpoint oficial (`SAT-WEB-NFE-NFC_2.asp`), com cabeçalhos adequados e salvamento automático do HTML.
- ✅ Fixture pública (`.github/xmlexemplo.xml`) garante previsibilidade dos testes.
- ✅ Persistência em SQLite3 com dimensões de datas/estabelecimentos e funções utilitárias para salvar/consultar.
- ✅ Tela de revisão manual em Streamlit com edição de categoria/produto, registro do revisor e histórico em SQLite3.
- ✅ Migração de DuckDB para SQLite3 para melhor suporte a UPDATE com foreign keys.
- ✅ **Relatórios e gráficos interativos** - Acompanhe evolução de preços e inflação da sua cesta básica pessoal (veja [RELATORIOS.md](RELATORIOS.md))

## Interfaces

- **Home**: Dashboard com KPIs gerais e resumo mensal
- **Importar nota**: Interface para digitar chave da nota fiscal e importar do portal da SEFAZ-RS
- **Analisar notas**: Visualização de notas importadas com revisão manual de classificações
- **Relatórios** 📊 (NOVO):
  - Gráfico de custos unitários mensais dos 10 produtos mais comprados
  - Gráfico de inflação acumulada com identificação de produtos regulares
  - Cálculo de "Inflação Média" e "Cesta Básica Personalizada"
  - Exportação para Excel/CSV com valores e percentuais

## Estrutura do projeto

    main.py
    src/
        scrapers/
        classifiers/
        database/
        ui/
    data/
    tests/
    .github/xmlexemplo.xml

## Setup rápido

No PowerShell, use uma virtualenv local e sincronize as dependências compiladas:

```pwsh
    uv venv
    .\.venv\Scripts\Activate.ps1
    uv pip sync requirements.txt
```

Sempre que voltar ao projeto, apenas reative a venv antes de rodar a aplicação ou os testes.

## Gerenciando dependências

- `pyproject.toml` é a fonte única das dependências de produção e desenvolvimento.
- `requirements.txt` é gerado automaticamente e **não deve ser editado manualmente**.
- Para atualizar versões e regenerar o pinning reproduzível, use:

```pwsh
    uv pip compile pyproject.toml --all-extras -o requirements.txt
```

- Para instalar o conjunto compilado, prefira:

```pwsh
    uv pip sync requirements.txt
```

  Esse comando remove pacotes que não estão mais listados no arquivo compilado, ajudando a manter o ambiente limpo e reproduzível.
  Em ambientes de desenvolvimento, use-o com atenção porque pacotes instalados manualmente fora do `requirements.txt` também serão removidos.

- Se `uv` não estiver disponível, o fallback continua sendo:

```pwsh
    pip install -r requirements.txt
```

## Rodando

```pwsh

    .\.venv\script\activate.ps1
    streamlit run .\main.py
```

## Fluxo atual de importação

O módulo `src.scrapers.receita_rs` envia um POST para `https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp`, passando `chaveNFe`, `HML=false` e `Action=Avançar`, além do *referer* esperado (`...NFC_1.asp?chaveNFe=...`). O HTML retornado é salvo automaticamente em `data/raw_nfce/nfce_<chave>.html` para depuração e, em seguida, convertido em um objeto `NotaFiscal` com metadados, itens e pagamentos.

    from src.scrapers.receita_rs import buscar_nota

    nota = buscar_nota("43251193015006003562651350005430861685582449")
    print(f"Total: {nota.valor_total}")
    print(f"Itens extraídos: {len(nota.itens)}")

Após a extração, a camada `src.database` disponibiliza `salvar_nota()` para persistir a nota no SQLite3 (`data/gastos.db`) e `listar_notas()`/`carregar_nota()` para alimentar o Streamlit:

    from src.database import salvar_nota, listar_notas

    salvar_nota(nota)
    print(listar_notas(limit=5))

## Schema padronizado para análises

O SQLite3 agora mantém dimensões explícitas para datas e estabelecimentos, além de uma view consolidada com totais por item:

- `estabelecimentos`: guarda nome, CNPJ normalizado e endereço, evitando duplicidade entre notas.
- `datas_referencia`: armazena data ISO, ano, mês, trimestre, semana ISO e nomes amigáveis (PT-BR) para alimentar filtros temporais.
- `vw_itens_padronizados`: view que expõe cada item com data padronizada, `ano_mes`, dados do estabelecimento, categoria final (confirmada ou sugerida) e valores unitários/totais.

A função `listar_itens_padronizados()` lê diretamente essa view, o que simplifica a montagem de dashboards mensais e relatórios por categoria.

## Configuração de Modelos LLM

Os modelos de LLM disponíveis estão configurados em `config/modelos_llm.toml`. Cada modelo possui:
- Nome e ID (`gemini/gemini-2.5-flash-lite`, etc.)
- Chave de API da variável de ambiente (`GEMINI_API_KEY`, `NVIDIA_API_KEY`, etc.)
- Limites de tokens, itens por chamada e timeout
- Configurações específicas do modelo (ex: `extra_body` para o Kimi)

**Para adicionar um novo modelo**, edite `config/modelos_llm.toml` e adicione um novo bloco `[[modelos]]`. Veja [config/README.md](config/README.md) para detalhes.

## Classificação com LiteLLM (Gemini)

Configure as variáveis de API no arquivo `.env` para habilitar a integração. O módulo `src.classifiers.llm_classifier` lê as configurações de `config/modelos_llm.toml` e o `.env` automaticamente, e expõe o helper `classificar_itens_pendentes()` que busca itens sem categoria no SQLite3, chama o modelo configurado via LiteLLM e grava o histórico:

## Classificação semântica (Chroma + fallback no LLM)

Para acelerar a identificação de produtos, o sistema gera embeddings SentenceTransformers para cada descrição registrada e armazena-os no ChromaDB local (`data/chroma`). Quando um item novo chega, a busca semântica tenta encontrar um produto já existente com similaridade acima de 0.82. Se houver um match, reaproveitamos o `produto_id`, `nome_base` e `marca_base`. Caso contrário, o LLM (Gemini via LiteLLM) continua sendo invocado para classificar o item e sugerir produto/categoria, e seus resultados enriquecem SQLite3 e o índice de embeddings.

As dependências `chromadb>=1.5.1` e `sentence-transformers>=5.2.3` cuidam dessa camada. O cliente local do Chroma usa persistência em `data/chroma`, então garanta que esse diretório esteja gravável e que o modelo `all-MiniLM-L6-v2` possa ser baixado da Hugging Face.

### Cache offline de embeddings (Hugging Face)

O app agora define automaticamente cache persistente para embeddings em `cache/huggingface`, configurando:

- `HF_HOME`
- `TRANSFORMERS_CACHE`
- `SENTENCE_TRANSFORMERS_HOME`

Fluxo recomendado:

1. **Primeira execução (com internet):** o modelo `all-MiniLM-L6-v2` é baixado e salvo em `cache/huggingface`.
2. **Execuções seguintes:** o app tenta carregar o modelo **somente do cache local** e ativa modo offline (`HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`) quando o cache já existe.
3. **Se o cache não existir e não houver internet:** a UI mostra aviso claro para conectar na primeira execução.

## Regenerando o índice semântico

O índice de embeddings é atualizado automaticamente sempre que um item é persistido ou reclassificado via `salvar_nota()` e `registrar_classificacao_itens()`. Para forçar uma regeneração manual (por exemplo, após limpar `data/chroma`):

1. Reimporte as notas que deseja recalcular com `salvar_nota()`; os embeddings novos são salvos durante `_registrar_alias_produto`.
2. Caso precise reclassificar tudo, execute `from src.classifiers import classificar_itens_pendentes; classificar_itens_pendentes(confirmar=True)` para regravar categoria/produto e disparar a atualização de embeddings.
3. Limpe o diretório `data/chroma` com o banco fechado antes de rodar novamente para reiniciar o índice completo.

Use o script `debug_product_update.py` (na raiz do projeto) para experimentar reclassificações, inspecionar produtos e ver como o `produto_id` aparece no banco.

    from src.classifiers import classificar_itens_pendentes

    resultados = classificar_itens_pendentes(limit=5, confirmar=False)
    for resultado in resultados:
        print(resultado.sequencia, resultado.categoria, resultado.confianca)

Toda classificação fica salva nas colunas `categoria_sugerida`, `fonte_classificacao`, `confianca_classificacao` da tabela `itens` e o histórico completo (com modelo, origem e resposta) vai para `classificacoes_historico`.

## Revisão manual e auditoria

A aba **Análise** do Streamlit (`src/ui/analise.py`) lista as notas com itens pendentes, permite filtrar apenas os que faltam confirmar e abre um editor tabular para ajustar `categoria`, `produto (nome base)` e `marca`. O revisor pode informar seu nome e observações; ao salvar rascunho, os dados alimentam `registrar_revisoes_manuais(confirmar=False)` (atualizando apenas sugestões). Ao confirmar, o mesmo fluxo grava `categoria_confirmada`, associa/gera `produto_id` e adiciona entradas tanto em `classificacoes_historico` quanto na nova tabela `revisoes_manuais` (que mantém `usuario`, `observacoes`, flag de confirmação e timestamp).

O histórico mais recente aparece na própria tela, facilitando auditorias rápidas. Para consultas posteriores, use `listar_revisoes_manuais(chave_acesso)` que retorna os registros com usuário, data e comentários.

## Por que SQLite3?

O projeto migrou de DuckDB para SQLite3 pelos seguintes motivos:

- **Melhor suporte a UPDATE com Foreign Keys**: SQLite3 permite desabilitar temporariamente validação de FKs via `PRAGMA foreign_keys = OFF`, resolvendo limitações do DuckDB ao atualizar tabelas referenciadas.
- **Maturidade OLTP**: Mais estável para operações de insert/update frequentes típicas de CRUD.
- **Portabilidade**: Arquivo único `.db` sem dependências externas, nativo no Python.
- **Performance suficiente**: Para o volume de dados do projeto (notas fiscais pessoais), SQLite3 oferece desempenho adequado mesmo para queries analíticas.

## Gerando uma build distribuível (sem Docker)

Use o script `build.ps1` (PowerShell) para empacotar o projeto em `dist/pygerengastos` juntamente com um ambiente virtual pré-instalado e scripts de execução. Execute a partir da raiz do repositório:

    pwsh ./build.ps1

Por padrão, o script:

- copia `main.py`, `src/`, `data/` (sem os arquivos SQLite3 pesados) e arquivos auxiliares para `dist/pygerengastos`
- remove `__pycache__`, `data/chroma` e `data/raw_nfce` (pode ser mantido usando `-IncludeRawData`)
- cria um ambiente virtual dentro do pacote e instala as dependências de `requirements.txt`
- gera `setup.ps1`, `start.ps1` e `start.bat` para configurar/rodar em outras máquinas
- produz também `dist/pygerengastos.zip`, pronto para distribuição

Parâmetros úteis:

- `-SkipVenv`: pula a criação da venv no pacote (útil para builds portáveis onde o destinatário rodará `setup.ps1`)
- `-SkipZip`: mantém apenas a pasta em `dist/` sem compactá-la
- `-IncludeRawData`: mantém `data/raw_nfce` inteiro no build

Após extrair o pacote em outro ambiente, basta executar `setup.ps1` (caso não tenha distribuído a venv) e depois `start.ps1` ou `start.bat` para abrir o Streamlit com o SQLite3 local.

## Testes

Execute a suíte completa (scraper + SQLite3) para garantir que tudo esteja consistente:

    python -m pytest

## Próximos passos

- Evoluir a integração do LiteLLM/Gemini (monitor de custo, retries e estratégias de fallback adicionais) e registrar histórico/correções manuais.
- Persistir notas, itens e categorias em SQLite3 para consultas analíticas.
- Construir dashboards Streamlit (lista de notas, filtros por período e gráficos mensais por categoria).
