# Sistema de gerenciamento de gastos mensais

Aplicação em Python + Streamlit que importa notas fiscais eletrônicas (NFC-e) do portal da Receita Gaúcha, classifica itens automaticamente (Groq) e armazena tudo em DuckDB para visualização dos gastos.

## Status atual

- ✅ Scraper da SEFAZ-RS refeito para usar POST no endpoint oficial (`SAT-WEB-NFE-NFC_2.asp`), com cabeçalhos adequados e salvamento automático do HTML.
- ✅ Fixture pública (`.github/xmlexemplo.xml`) garante previsibilidade dos testes.
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

## Testes

Execute os testes que validam o parser com o HTML de exemplo (lembrando de estar com a venv ativa):

    python -m pytest tests/test_receita_rs.py

## Próximos passos

- Integrar a API da Groq para classificar itens inéditos e registrar histórico/correções manuais.
- Persistir notas, itens e categorias em DuckDB para consultas analíticas.
- Construir dashboards Streamlit (lista de notas, filtros por período e gráficos mensais por categoria).

