# C4 Containers — Gerenciador de despesa

> Nível 2: Diagrama de Containers

```mermaid
C4Container
  title Diagrama de Containers — Gerenciador de despesa

  Person(usuario, "Usuário", "Operador do sistema")

  System_Boundary(sistema, "Gerenciador de Despesa") {

    Container(streamlit, "Streamlit App", "Python + Streamlit 1.54.0", "Interface desktop local com 5 páginas")
    Container(sqlite, "SQLite3 Database", "SQLite3", "Dados estruturados: notas, itens, produtos, categorias")
    Container(chroma, "ChromaDB", "ChromaDB 1.5.7", "Cache vetorial de embeddings de produtos classificados")
    Container(embedding, "SentenceTransformer", "all-MiniLM-L6-v2", "Modelo de embeddings (384 dim)")
    Container(litellm, "LiteLLM Client", "LiteLLM 1.86.2", "Gateway unificado para múltiplos provedores LLM")

    Container_Boundary(modules, "Módulos da Aplicação") {
      Container(ui, "UI Module", "src/ui/", "5 páginas: home, importacao, analise, normalizacao, relatorios")
      Container(classifiers, "Classifiers Module", "src/classifiers/", "Pipeline híbrido: cache semântico + LLM")
      Container(database, "Database Module", "src/database/", "CRUD, normalização, queries analíticas")
      Container(scrapers, "Scrapers Module", "src/scrapers/", "Scraping de NFC-e da SEFAZ-RS")
    }
  }

  System_Ext(sefaz, "SEFAZ-RS", "Portal NFC-e")
  System_Ext(llm_providers, "LLM Providers", "Gemini / NVIDIA NIM / OpenAI")

  Rel(usuario, streamlit, "Usa", "CLI: streamlit run main.py")
  Rel(streamlit, ui, "Renderiza páginas")
  Rel(ui, classifiers, "Chama classificação")
  Rel(ui, database, "Chama queries")
  Rel(ui, scrapers, "Chama importação")
  Rel(classifiers, database, "Lê itens pendentes, registra classificação")
  Rel(classifiers, chroma, "Busca/armazena embeddings")
  Rel(classifiers, embedding, "Gera embeddings")
  Rel(classifiers, litellm, "Chama LLM para classificação")
  Rel(database, sqlite, "Persiste dados")
  Rel(scrapers, sefaz, "Baixa HTML NFC-e", "HTTPS POST")
  Rel(litellm, llm_providers, "Classificação via LLM", "HTTPS")
  Rel(chroma, sqlite, "Persistência ChromaDB usa SQLite internamente")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="2")
```

## Containers

| Container | Tecnologia | Função | Estado |
|-----------|-----------|--------|--------|
| **Streamlit App** | Python + Streamlit 1.54.0 | Interface do usuário — 5 páginas | 🟢 Ativo |
| **SQLite3 Database** | SQLite3 (stdlib) | Dados estruturados (gastos.db) | 🟢 Ativo |
| **ChromaDB** | ChromaDB 1.5.7 | Cache vetorial (data/chroma/) | 🟢 Ativo |
| **SentenceTransformer** | all-MiniLM-L6-v2 | Modelo de embeddings (384 dim) | 🟢 Ativo |
| **LiteLLM Client** | LiteLLM 1.86.2 | Gateway para LLMs | 🟢 Ativo |
