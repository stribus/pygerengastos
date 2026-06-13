# C4 Context — Gerenciador de despesa

> Nível 1: Diagrama de Contexto

```mermaid
C4Context
  title Diagrama de Contexto — Gerenciador de despesa

  Person(usuario, "Usuário", "Operador do sistema que importa notas e analisa gastos")

  System_Boundary(sistema, "Gerenciador de Despesa") {
    System(gerengastos, "Gerenciador de Despesa", "Importa NFC-e, classifica itens, gera relatórios de preços e inflação")
  }

  System_Ext(sefaz, "SEFAZ-RS", "Portal da Receita Gaúcha\nFornece HTML de NFC-e")
  System_Ext(gemini, "Google Gemini API", "LLM para classificação de itens")
  System_Ext(nvidia, "NVIDIA NIM", "LLMs DeepSeek e Kimi (fallback)")
  System_Ext(openai, "OpenAI API", "LLM GPT-4o (fallback)")
  System_Ext(huggingface, "HuggingFace Hub", "Download do modelo de embeddings all-MiniLM-L6-v2")

  Rel(usuario, gerengastos, "Importa notas, revisa classificação,\nvisualiza relatórios", "CLI (streamlit run)")
  Rel(gerengastos, sefaz, "Busca NFC-e por chave de acesso", "HTTPS POST")
  Rel(gerengastos, gemini, "Classifica itens via LiteLLM", "HTTPS")
  Rel(gerengastos, nvidia, "Classifica itens via LiteLLM (fallback)", "HTTPS")
  Rel(gerengastos, openai, "Classifica itens via LiteLLM (fallback)", "HTTPS")
  Rel(gerengastos, huggingface, "Download do modelo de embeddings", "HTTPS")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## Relacionamentos

| De | Para | O quê | Protocolo | Frequência |
|----|------|-------|-----------|------------|
| Usuário | Sistema | Importar nota, revisar classificação, ver relatórios | CLI local | Sob demanda |
| Sistema | SEFAZ-RS | Baixar HTML da NFC-e | HTTPS POST | Por importação |
| Sistema | Gemini API | Classificar itens não encontrados no cache | HTTPS (LiteLLM) | Por lote de itens |
| Sistema | NVIDIA NIM | Classificar (fallback se Gemini falhar) | HTTPS (LiteLLM) | Sob falha |
| Sistema | OpenAI API | Classificar (fallback final) | HTTPS (LiteLLM) | Sob falha |
| Sistema | HuggingFace | Baixar modelo all-MiniLM-L6-v2 | HTTPS | 1x (offline-first após cache) |
