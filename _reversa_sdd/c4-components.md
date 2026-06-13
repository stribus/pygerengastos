# C4 Components — Gerenciador de despesa

> Nível 3: Componentes internos dos containers mais relevantes

## Streamlit App — Componentes

```mermaid
C4Component
  title Componentes — Streamlit App

  System_Boundary(sistema, "Gerenciador de Despesa") {
    Component(home, "Página Home", "home.py", "KPIs, evolução mensal, gastos por categoria")
    Component(importacao, "Página Importar", "importacao.py", "Busca NFC-e por chave, importa, classifica")
    Component(analise, "Página Analisar", "analise.py", "Revisão manual de classificação de itens")
    Component(normalizacao, "Página Normalizar", "normalizacao.py", "Consolidação de produtos duplicados")
    Component(relatorios, "Página Relatórios", "relatorios.py", "Custos unitários, inflação acumulada, cesta básica")

    Component(classifier, "Cache Semântico", "classifiers/embeddings.py", "Busca no ChromaDB por similaridade vetorial")
    Component(llm, "Classificador LLM", "classifiers/llm_classifier.py", "Fallback para LiteLLM com múltiplos modelos")
    Component(orchestrator, "Orquestrador", "classifiers/__init__.py", "Pipeline híbrido: cache → LLM")

    Component(crud, "CRUD Database", "database/__init__.py", "SQLite3: schema, upsert, consultas analíticas")
    Component(scraper, "Scraper SEFAZ-RS", "scrapers/receita_rs.py", "Baixa e parseia NFC-e")
  }

  Rel(home, crud, "obter_kpis_gerais, obter_resumo_mensal")
  Rel(importacao, scraper, "buscar_nota()")
  Rel(importacao, crud, "salvar_nota()")
  Rel(importacao, orchestrator, "classificar_itens_pendentes()")
  Rel(analise, crud, "registrar_revisoes_manuais()")
  Rel(normalizacao, crud, "consolidar_produtos()")
  Rel(relatorios, crud, "obter_custos_unitarios_mensais() e outras queries")
  Rel(orchestrator, classifier, "Busca semântica (ChromaDB)")
  Rel(orchestrator, llm, "Classificação via LiteLLM")
  Rel(classifier, crud, "Registra classificações do cache")
```

## Database Module — Componentes

```mermaid
C4Component
  title Componentes — Database Module

  Component(schema, "Schema & Init", "database/__init__.py:1-250", "Criação de tabelas, índices, triggers, view")
  Component(crud_notas, "CRUD Notas", "database/__init__.py:251-700", "salvar_nota, remover_nota, upsert itens/pagamentos")
  Component(normalizacao_func, "Normalização", "database/__init__.py:501-680", "normalizar_produto_descricao, normalizar_nome_produto_universal")
  Component(class_registry, "Registro Classificação", "database/__init__.py:1380-1450", "registrar_classificacao_itens, registrar_revisoes_manuais")
  Component(queries, "Queries Analíticas", "database/__init__.py:2166-2430", "7 funções de consulta para relatórios e dashboard")
  Component(consolidacao, "Consolidação", "database/__init__.py:2654-2858", "consolidar_produtos com merge de aliases e embeddings")
  Component(estabelecimentos, "Estabelecimentos", "database/__init__.py:1969-2066", "Resolução/deduplicação de estabelecimentos por CNPJ")

  Rel(schema, crud_notas, "usa")
  Rel(schema, normalizacao_func, "usa")
  Rel(crud_notas, normalizacao_func, "chama para padronizar descrições")
  Rel(crud_notas, class_registry, "chama para registrar classificações")
  Rel(queries, schema, "consulta via vw_itens_padronizados")
  Rel(consolidacao, normalizacao_func, "usa para resolução de conflitos")
```

## Classifiers Module — Componentes

```mermaid
C4Component
  title Componentes — Classifiers Module

  Component(orchestrator, "Orquestrador", "__init__.py", "classificar_itens_pendentes(): cache → LLM")
  Component(llm_classifier, "LLM Classifier", "llm_classifier.py", "classificar_itens(): LiteLLM + fallback")
  Component(embeddings, "Embeddings Manager", "embeddings.py", "Criação/busca de embeddings no ChromaDB")

  Rel(orchestrator, embeddings, "buscar_produtos_semelhantes()")
  Rel(orchestrator, llm_classifier, "classificar_itens() para fallback")
  Rel(llm_classifier, embeddings, "upsert_descricao_embedding() pós-classificação")
```

## Scrapers Module — Fluxo

```mermaid
flowchart LR
  A["buscar_nota(chave)"] --> B["validar_chave_acesso()"]
  B -->|Inválida| C["ValueError"]
  B -->|Válida| D["baixar_html()"]
  D --> E["parse_nfce_html()"]
  E --> F["Layout spans modernos?"]
  F -->|Sim| G["Extrair spans com classes"]
  F -->|Não| H["Layout tabela legada"]
  H --> G
  G --> I["NotaFiscal"]
  I --> J["Persistir HTML raw em data/raw_nfce/"]
```

## UI Module — Navegação

```mermaid
flowchart TD
  A["main.py"] --> B["Dicionário PAGINAS"]
  B --> C["home.py: render_home()"]
  B --> D["importacao.py: render_pagina_importacao()"]
  B --> E["analise.py: render_pagina_analise()"]
  B --> F["normalizacao.py: render_pagina_normalizacao()"]
  B --> G["relatorios.py: render_pagina_relatorios()"]

  C --> H["KPIs + Gráficos mensais + Gastos por categoria"]
  D --> I["Formulário chave NFC-e → Scraper → Salvar → Classificar"]
  E --> J["Tabela itens → Revisão manual → salvar revisão"]
  F --> K["Busca produtos → Selecionar merge → Consolidar"]
  G --> L["Tab Custos Unitários | Tab Inflação Acumulada"]
```
