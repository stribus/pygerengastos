# Classifiers, Tarefas de Implementação

## Pré-requisitos

- [ ] Dependências da unit listadas em `design.md` estão disponíveis (ChromaDB, sentence-transformers, LiteLLM)
- [ ] Schema/migrations do banco compatíveis (tabelas itens, classificacoes_historico)
- [ ] Variáveis de ambiente / configs necessárias documentadas (GEMINI_API_KEY, NVIDIA_API_KEY, OPENAI_API_KEY)

## Tarefas

- [ ] T-01, Implementar `inicializar_modelo_embeddings()` com cache offline-first
  - Origem no legado: `src/classifiers/embeddings.py:95-185`
  - Critério de pronto: singleton retorna SentenceTransformer; se cache local existe, não faz download
  - Confiança: 🟢

- [ ] T-02, Implementar `buscar_produtos_semelhantes()` para query no ChromaDB
  - Origem no legado: `src/classifiers/embeddings.py:305-355`
  - Critério de pronto: busca por descrição retorna documentos com score de similaridade
  - Confiança: 🟢

- [ ] T-03, Implementar `upsert_descricao_embedding()` para criar/atualizar embeddings
  - Origem no legado: `src/classifiers/embeddings.py:240-300`
  - Critério de pronto: embedding upsertado no ChromaDB com metadados (descricao, nome_base, marca_base, categoria)
  - Confiança: 🟢

- [ ] T-04, Implementar carregamento de modelos LLM do TOML com lazy loading
  - Origem no legado: `src/classifiers/llm_classifier.py:48-120`
  - Critério de pronto: `recarregar_modelos()` retorna lista de ModeloConfig do TOML; fallback hardcoded para Gemini se TOML falhar
  - Confiança: 🟢

- [ ] T-05, Implementar `LLMClassifier.classificar_itens()` com iteração por prioridade
  - Origem no legado: `src/classifiers/llm_classifier.py:382-463`
  - Critério de pronto: itera modelos, divide itens em lotes (max_itens), monta prompt com contexto, parseia resposta JSON
  - Confiança: 🟢

- [ ] T-06, Implementar `classificar_itens_pendentes()` com pipeline híbrido
  - Origem no legado: `src/classifiers/__init__.py:30-226`
  - Critério de pronto: itens com match semântico >= 0.82 usam cache; demais vão para LLM; resultados registrados no banco
  - Confiança: 🟢

- [ ] T-07, Implementar fallback entre modelos LLM com retry
  - Origem no legado: `src/classifiers/llm_classifier.py:396-462`
  - Critério de pronto: se modelo atual falha com exceção, tenta próximo da lista até N retries
  - Confiança: 🟢

- [ ] T-08, Implementar tratamento de erros específicos de embedding
  - Origem no legado: `src/classifiers/embeddings.py:200-235`
  - Critério de pronto: ErroInicializacaoEmbeddings, ErroCacheEmbeddings, ErroDownloadEmbeddings com mensagens descritivas
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Teste do happy path: item com match semântico usa cache
- [ ] TT-02, Teste de fallback: quando cache não encontra match, LLM é chamado
- [ ] TT-03, Teste de retry: quando LLM falha, tenta próximo modelo
- [ ] TT-04, Teste de erro: quando todos modelos falham, levanta FalhaModeloError
- [ ] TT-05, Teste de offline: modelo de embeddings carrega do cache local sem internet

## Ordem Sugerida

1. T-01 (embeddings init) → T-02 (busca) → T-03 (upsert) — base do cache semântico
2. T-04 (config loading) → T-05 (LLM classifier) — base LLM
3. T-06 (pipeline híbrido) → T-07 (fallback) → T-08 (erros) — orquestração

## Lacunas Pendentes (🔴)

- Nenhuma lacuna identificada — todos os comportamentos estão explicitamente no código legado
