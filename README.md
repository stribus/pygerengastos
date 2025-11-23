# Sistema de gerenciamento de gastos mensais

Aplicação em Python + Streamlit que importa notas fiscais eletrônicas (NFC-e) do portal da Receita Gaúcha, classifica itens automaticamente (Groq) e armazena tudo em DuckDB para visualização dos gastos.

## Status atual

- ✅ Scraper da SEFAZ-RS refeito para usar POST no endpoint oficial (`SAT-WEB-NFE-NFC_2.asp`), com cabeçalhos adequados e salvamento automático do HTML.
- ✅ Fixture pública (`.github/xmlexemplo.xml`) garante previsibilidade dos testes.
- ✅ Persistência em DuckDB com dimensões de datas/estabelecimentos e funções utilitárias para salvar/consultar.
- ✅ Tela de revisão manual em Streamlit com edição de categoria/produto, registro do revisor e histórico em DuckDB.
- 🚧 Próximos focos: normalizar consultas de resumo mensais e evoluir os dashboards Streamlit.

## interfaces

    - interface de importação de notas, oferece interface pra digitar a chave da nota fiscal pra importação
    - interface pra visualização das notas importadas junto dos items
    - interface com graficos das despesas, com graficos mensais de gastos do mes ou dos custos por itens

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

No PowerShell, use a virtualenv local e instale as dependências com o `uv pip`:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    uv pip install -r requirements.txt

Sempre que voltar ao projeto, apenas reative a venv antes de rodar a aplicação ou os testes.

## Fluxo atual de importação

O módulo `src.scrapers.receita_rs` envia um POST para `https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp`, passando `chaveNFe`, `HML=false` e `Action=Avançar`, além do *referer* esperado (`...NFC_1.asp?chaveNFe=...`). O HTML retornado é salvo automaticamente em `data/raw_nfce/nfce_<chave>.html` para depuração e, em seguida, convertido em um objeto `NotaFiscal` com metadados, itens e pagamentos.

    from src.scrapers.receita_rs import buscar_nota

    nota = buscar_nota("43251193015006003562651350005430861685582449")
    print(f"Total: {nota.valor_total}")
    print(f"Itens extraídos: {len(nota.itens)}")

Após a extração, a camada `src.database` disponibiliza `salvar_nota()` para persistir a nota no DuckDB (`data/gastos.duckdb`) e `listar_notas()`/`carregar_nota()` para alimentar o Streamlit:

    from src.database import salvar_nota, listar_notas

    salvar_nota(nota)
    print(listar_notas(limit=5))

## Schema padronizado para análises

O DuckDB agora mantém dimensões explícitas para datas e estabelecimentos, além de uma view consolidada com totais por item:

- `estabelecimentos`: guarda nome, CNPJ normalizado e endereço, evitando duplicidade entre notas.
- `datas_referencia`: armazena data ISO, ano, mês, trimestre, semana ISO e nomes amigáveis (PT-BR) para alimentar filtros temporais.
- `vw_itens_padronizados`: view que expõe cada item com data padronizada, `ano_mes`, dados do estabelecimento, categoria final (confirmada ou sugerida) e valores unitários/totais.

A função `listar_itens_padronizados()` lê diretamente essa view, o que simplifica a montagem de dashboards mensais e relatórios por categoria.

## Classificação com Groq

Configure a variável `GROQ_API_KEY` no arquivo `.env` (ou diretamente no ambiente) para habilitar a integração. O módulo `src.classifiers.groq` lê o `.env` automaticamente e expõe o helper `classificar_itens_pendentes()` que busca itens sem categoria no DuckDB, chama a Groq e grava o histórico:

## Classificação semântica (Chroma + Groq fallback)

Para acelerar a identificação de produtos, o sistema gera embeddings SentenceTransformers para cada descrição registrada e armazena-os no ChromaDB local (`data/chroma`). Quando um item novo chega, a busca semântica tenta encontrar um produto já existente com similaridade acima de 0.82. Se houver um match, reaproveitamos o `produto_id`, `nome_base` e `marca_base`. Caso contrário, a Groq continua sendo invocada para classificar o item e sugerir produto/categoria, e seus resultados enriquecem DuckDB e o índice de embeddings.

As dependências `chromadb==1.3.5` e `sentence-transformers==5.1.2` cuidam dessa camada. Garanta que o diretório `data/chroma` esteja gravável e que o modelo `all-MiniLM-L6-v2` possa ser baixado da Hugging Face.

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

## Gerando uma build distribuível (sem Docker)

Use o script `build.ps1` (PowerShell) para empacotar o projeto em `dist/pygerengastos` juntamente com um ambiente virtual pré-instalado e scripts de execução. Execute a partir da raiz do repositório:

    pwsh ./build.ps1

Por padrão, o script:

- copia `main.py`, `src/`, `data/` (sem os arquivos DuckDB pesados) e arquivos auxiliares para `dist/pygerengastos`
- remove `__pycache__`, `data/chroma` e `data/raw_nfce` (pode ser mantido usando `-IncludeRawData`)
- cria um ambiente virtual dentro do pacote e instala as dependências de `requirements.txt`
- gera `setup.ps1`, `start.ps1` e `start.bat` para configurar/rodar em outras máquinas
- produz também `dist/pygerengastos.zip`, pronto para distribuição

Parâmetros úteis:

- `-SkipVenv`: pula a criação da venv no pacote (útil para builds portáveis onde o destinatário rodará `setup.ps1`)
- `-SkipZip`: mantém apenas a pasta em `dist/` sem compactá-la
- `-IncludeRawData`: mantém `data/raw_nfce` inteiro no build

Após extrair o pacote em outro ambiente, basta executar `setup.ps1` (caso não tenha distribuído a venv) e depois `start.ps1` ou `start.bat` para abrir o Streamlit com o DuckDB local.

## Testes

Execute a suíte completa (scraper + DuckDB) para garantir que tudo esteja consistente:

    python -m pytest

## Próximos passos

- Integrar a API da Groq para classificar itens inéditos e registrar histórico/correções manuais.
- Persistir notas, itens e categorias em DuckDB para consultas analíticas.
- Construir dashboards Streamlit (lista de notas, filtros por período e gráficos mensais por categoria).

