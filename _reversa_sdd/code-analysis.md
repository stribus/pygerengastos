# Análise de Código — Gerenciador de despesa

> Gerado pelo Archaeologist em 2026-06-06
> Nível: Completo

---

## Módulo: classifiers `src/classifiers/`

🟢 **CONFIRMADO** — 3 arquivos, ~1.271 LOC

### Propósito
Pipeline de classificação automática de itens de notas fiscais. Opera em dois estágios: (1) cache semântico via ChromaDB/sentence-transformers, (2) fallback para LLM via LiteLLM.

### Fluxo de Controle

1. **`classificar_itens_pendentes()`** (`__init__.py:30-226`)
   - Limpeza opcional de classificações anteriores
   - Estágio 1: busca semântica no ChromaDB (score mínimo 0.82)
   - Estágio 2: LLM para itens não resolvidos pelo cache
   - Fallback automático entre modelos em ordem de prioridade

2. **`LLMClassifier.classificar_itens()`** (`llm_classifier.py:382-463`)
   - Itera sobre modelos configurados em ordem de prioridade
   - Para cada modelo: divide itens em lotes (max_itens configurável)
   - Monta prompt com contexto (estabelecimento, data, categorias)
   - Interpreta resposta JSON do LLM (categoria, confiança, produto)

3. **`inicializar_modelo_embeddings()`** (`embeddings.py:95-185`)
   - Offline-first: tenta carregar do cache local
   - Fallback: download automático do HuggingFace
   - Double-checked locking para thread-safety

### Algoritmos

| Algoritmo | Localização |
|-----------|-------------|
| Classificação híbrida (cache + LLM) | `__init__.py:150-218` |
| Fallback entre modelos LLM com retry | `llm_classifier.py:396-462` |
| Busca por similaridade vetorial (ChromaDB) | `embeddings.py:305-355` |
| Cache com double-checked locking | `embeddings.py:95-185` |

### Constantes Relevantes

| Nome | Valor | Local |
|------|-------|-------|
| `_EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | `embeddings.py:20` |
| `_CHROMA_COLLECTION_NAME` | `produtos` | `embeddings.py:21` |
| `_SIMILARIDADE_MINIMA` | `0.82` | `database/__init__.py:467` |
| `DEFAULT_MODEL` | `gemini/gemini-2.5-flash-lite` | `llm_classifier.py:24` |

### Entidades

- `ModeloConfig` — configuração de modelo LLM (nome, api_key_env, max_tokens, timeout)
- `ClassificacaoResultado` — resultado da classificação (categoria, confianca, origem, produto)
- `_RespostaLLM` — resposta parseada do LLM (uso interno)

---

## Módulo: database `src/database/`

🟢 **CONFIRMADO** — 1 arquivo, ~2.501 LOC

### Propósito
Camada de persistência SQLite3 completa: schema com 10 tabelas + 1 view, CRUD de notas, classificação, padronização de produtos e consultas analíticas.

### Schema do Banco

```sql
-- 10 tabelas + 1 view (detalhado no data-dictionary.md)
categorias, estabelecimentos, datas_referencia, notas,
produtos, aliases_produtos, itens, pagamentos,
classificacoes_historico, revisoes_manuais, consolidacoes_historico
vw_itens_padronizados -- view consolidada
```

### Fluxo de Controle

1. **Importação de nota**: `salvar_nota()` → `_persistir_nota()` → `_persistir_itens()` + `_persistir_pagamentos()`
   - Upsert da nota (ON CONFLICT por chave_acesso)
   - Resolução/criação de produto via descrição
   - Registro de alias para aprendizado futuro
   - Geração de embeddings para novos produtos

2. **Classificação**: `registrar_classificacao_itens()` → histórico + update do item
   - Sempre registra em `classificacoes_historico`
   - Atualiza `categoria_sugerida` ou `categoria_confirmada`
   - Resolve/cria produto padronizado

3. **Normalização**: `normalizar_produto_descricao()` → extrai nome_base + marca_base
   - Remove quantidades/unidades
   - Detecta marcas conhecidas (dicionário hardcoded)
   - Remove stopwords

### Algoritmos de Normalização

- **`normalizar_nome_produto_universal()`** (`__init__.py:542-622`): extrai tamanhos (2L, 500ml), move para final, normaliza variações (C/G → c/gás, ZERO LAC → sem lactose)
- **`normalizar_produto_descricao()`** (`__init__.py:502-539`): remove unidades, detecta marca conhecida, title case
- **Resolução de produto** (`__init__.py:1702-1767`): alias exato → normalização → criação
- **Busca semântica** (`__init__.py:385-430`): consulta ChromaDB via `buscar_produtos_semelhantes()`

---

## Módulo: scrapers `src/scrapers/`

🟢 **CONFIRMADO** — 2 arquivos, ~593 LOC

### Propósito
Web scraping do portal da SEFAZ-RS para baixar e parsear NFC-e (Nota Fiscal do Consumidor Eletrônica).

### Fluxo de Controle

1. `buscar_nota(chave)` → `baixar_html()` → `parse_nfce_html()`
2. POST para `https://www.sefaz.rs.gov.br/ASP/AAE_ROOT/NFE/SAT-WEB-NFE-NFC_2.asp`
3. Normalização de charset: ISO-8859-1 → UTF-8
4. Parsing com BeautifulSoup: dois layouts suportados (spans modernos e tabelas legadas)
5. Extração: chave (44 dígitos), estabelecimento, itens, totais, tributos, pagamentos, consumidor

### Tratamento de Erros

- Validação de chave: exatamente 44 dígitos
- Charset fallback: latin-1 se UTF-8 falhar
- Arquivos corrompidos detectados por U+FFFD (caractere de substituição)

---

## Módulo: ui `src/ui/`

🟢 **CONFIRMADO** — 5 arquivos, ~1.594 LOC

### Propósito
Interface Streamlit com 5 páginas orquestradas por `main.py`.

### Páginas

| Página | Arquivo | Função | Finalidade |
|--------|---------|--------|------------|
| Home | `home.py` | `render_home()` | KPIs, evolução mensal, gastos por categoria |
| Importar nota | `importacao.py` | `render_pagina_importacao()` | Busca NFC-e por chave, importa, classifica |
| Analisar notas | `analise.py` | `render_pagina_analise()` | Revisão manual de classificação |
| Normalizar produtos | `normalizacao.py` | `render_pagina_normalizacao()` | Consolidação de produtos duplicados |
| Relatórios | `relatorios.py` | `render_pagina_relatorios()` | Custos unitários, inflação acumulada |

### Algoritmos de Relatórios

- **Inflação acumulada composta** (`relatorios.py:81-103`): `(1 + inf_ant/100) * (1 + var_atual/100) - 1`
- **Produtos regulares** (`relatorios.py:106-146`): identifica itens comprados em N+ meses consecutivos
- **Cesta básica personalizada** (`relatorios.py:149-176`): média simples dos custos unitários
- **Preenchimento de meses faltantes** (`relatorios.py:26-78`): forward fill com último preço conhecido

---

## Módulo: config `config/`

🟢 **CONFIRMADO** — 2 arquivos

### Propósito
Configuração centralizada de modelos LLM.

### Modelos Configurados

| Modelo | Provedor | Prioridade |
|--------|----------|------------|
| Gemini 2.5 Flash Lite | Google Gemini | 1ª |
| DeepSeek V4 Pro | NVIDIA NIM | 2ª |
| DeepSeek V4 Flash | NVIDIA NIM | 3ª |
| Kimi K2.6 | NVIDIA NIM | 4ª |

Fallback hardcoded para Gemini se TOML falhar (`llm_classifier.py:48-65`).

---

## Dicionário de Dados (Resumido)

### Tabelas SQLite3

Todas as tabelas, colunas, tipos e constraints estão detalhados em `data-dictionary.md`.

### Entidades Python (Dataclasses)

| Classe | Módulo | Uso |
|--------|--------|-----|
| `NotaFiscal` | scrapers | Dados completos da NFC-e |
| `NotaItem` | scrapers | Item individual da nota |
| `Pagamento` | scrapers | Forma de pagamento |
| `ItemParaClassificacao` | database | Item pendente de classificação |
| `Categoria` | database | Categoria de orçamento |
| `ProdutoPadronizado` | database | Produto normalizado |
| `ItemPadronizado` | database | Item com dados consolidados (view) |
| `ClassificacaoResultado` | classifiers | Resultado da classificação |
| `ModeloConfig` | classifiers | Config de modelo LLM |

---

## Escala de Confiança

🟢 **CONFIRMADO** — Todos os dados foram extraídos diretamente do código-fonte.
