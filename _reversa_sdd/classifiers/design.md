# Classifiers, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `classificar_itens_pendentes` | `(limit: int, confirmar: bool, db_path, classifier, model, temperature, chave_acesso, model_priority, progress_callback, incluir_confirmados, limpar_confirmadas_antes, forcar_llm)` | `list[ClassificacaoResultado]` | Pipeline principal, 12 parâmetros |
| `LLMClassifier.classificar_itens` | `(itens: Sequence[ItemParaClassificacao], model_priority, progress_callback)` | `list[ClassificacaoResultado]` | Fallback LLM |
| `inicializar_modelo_embeddings` | `()` | `SentenceTransformer` | Singleton, offline-first |
| `buscar_produtos_semelhantes` | `(descricao: str, top_k: int)` | `List[Dict]` | ChromaDB query |
| `upsert_descricao_embedding` | `(descricao_original, nome_base, marca_base, categoria, produto_id)` | `None` | Cria/atualiza embedding |
| `recarregar_modelos` | `()` | `None` | Hot-reload TOML |

### ClassificacaoResultado

| Campo | Tipo | Descrição |
|-------|------|-----------|
| chave_acesso | str | FK da nota |
| sequencia | int | Sequência do item |
| categoria | str | Categoria atribuída |
| confianca | float \| None | Score de confiança |
| origem | str | chroma-cache, gemini-litellm, nvidia-nim, etc. |
| modelo | str \| None | Modelo usado |
| observacoes | str \| None | Justificativa |
| resposta_json | str \| None | JSON completo da resposta LLM |
| produto_nome | str \| None | Nome base sugerido |
| produto_marca | str \| None | Marca sugerida |

## Fluxo Principal

1. `classificar_itens_pendentes()` lê itens do banco via `obter_itens_para_classificar()` (`__init__.py:30-80`)
2. Se `limpar_confirmadas_antes=True`, reseta `categoria_confirmada` dos itens (`__init__.py:90-126`)
3. Para cada item, tenta `buscar_produtos_semelhantes()` no ChromaDB (`__init__.py:150-180`)
4. Se score >= 0.82 e categoria não-vazia: classificação via cache (`__init__.py:168`)
5. Itens não resolvidos pelo cache vão para `LLMClassifier.classificar_itens()` (`__init__.py:190-218`)
6. LLM itera modelos em ordem de prioridade, divide em lotes (max_itens), monta prompt com contexto (`llm_classifier.py:382-463`)
7. Resposta LLM é parseada como JSON (categoria, confianca, justificativa, produto_nome, produto_marca) (`llm_classifier.py:500-560`)
8. Resultados são persistidos via `registrar_classificacao_itens()` (`__init__.py:220-226`)
9. Para cada classificação confirmada, `upsert_descricao_embedding()` atualiza ChromaDB (`embeddings.py:305-355`)

## Fluxos Alternativos

- **Score abaixo de 0.82:** item vai para LLM (não usa resultado do cache)
- **LLM retorna JSON inválido:** `RespostaLLMInvalidaError` é levantada e loggada
- **Modelo primário falha:** fallback para próximo modelo na prioridade (retry incluso)
- **Todos modelos falham:** `FalhaModeloError` com detalhes de cada falha
- **ChromaDB vazio:** todos itens vão direto para LLM (primeira execução)

## Dependências

- **database**: lê itens pendentes, registra classificações (`__init__.py:220`)
- **config**: lê configuração de modelos LLM do TOML (`llm_classifier.py:48-65`)
- **ChromaDB**: cache vetorial (`embeddings.py:21`)
- **sentence-transformers**: modelo de embeddings (`embeddings.py:20`)
- **LiteLLM**: gateway para provedores LLM (`llm_classifier.py:4`)

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Cache semântico antes do LLM (híbrido) | `__init__.py:153-189` | 🟢 |
| Double-checked locking para thread-safety em embeddings | `embeddings.py:130` | 🟢 |
| Background loading de modelos LLM com timeout 5s | `llm_classifier.py:27,129-213` | 🟢 |
| Lazy loading de configuração TOML | `llm_classifier.py:48-65` | 🟢 |

## Estado Interno

- `_modelo_embeddings` (module-level): instância singleton do SentenceTransformer
- `_chroma_collection` (module-level): coleção ChromaDB "produtos"
- `_modelos_cache` (LLMClassifier): lista de ModeloConfig carregada do TOML
- `_carregamento_em_andamento` (LLMClassifier): Future do background loading

## Observabilidade

- Logging via módulo `logger` com nome `__name__` em cada arquivo
- Erros de embedding tratados com classes específicas: `ErroInicializacaoEmbeddings`, `ErroCacheEmbeddings`, `ErroDownloadEmbeddings`
- Falhas de LLM loggadas com modelo, status code e mensagem de erro

## Riscos e Lacunas

- 🔴 Modelo sentence-transformers all-MiniLM-L6-v2 (~80MB) precisa ser baixado na primeira execução se não houver cache
- 🟡 Dependência de API externa (Gemini, NVIDIA NIM, OpenAI) para classificação residual
- 🟡 Retry count lido de env var `LLM_NUM_RETRIES` (default 2) — sem fallback se env var mal formatada
