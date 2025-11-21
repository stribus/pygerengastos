# Sistema de gerenciamento de gastos mensais

Aplicação em Python + Streamlit que importa notas fiscais eletrônicas (NFC-e) do portal da Receita Gaúcha, classifica itens automaticamente (Groq) e armazena tudo em DuckDB para visualização dos gastos.

## Status atual

- ✅ Scraper da SEFAZ-RS refeito para usar POST no endpoint oficial (`SAT-WEB-NFE-NFC_2.asp`), com cabeçalhos adequados e salvamento automático do HTML.
- ✅ Fixture pública (`.github/xmlexemplo.xml`) garante previsibilidade dos testes.
- ✅ Persistência inicial em DuckDB com tabelas para notas, itens e pagamentos, além de utilitários para salvar e consultar.
- 🚧 Próximos focos: classificação via Groq, persistência em DuckDB e dashboards Streamlit.

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

## Testes

Execute a suíte completa (scraper + DuckDB) para garantir que tudo esteja consistente:

    python -m pytest

## Próximos passos

- Integrar a API da Groq para classificar itens inéditos e registrar histórico/correções manuais.
- Persistir notas, itens e categorias em DuckDB para consultas analíticas.
- Construir dashboards Streamlit (lista de notas, filtros por período e gráficos mensais por categoria).

