# UI, Design Técnico

## Interface

### Estrutura de Páginas

| Função | Arquivo | Retorno | Descrição |
|--------|---------|---------|-----------|
| `main()` | `main.py` | None | Entry point: init resources, sidebar nav, roteamento |
| `render_home()` | `src/ui/home.py` | None | Dashboard com KPIs, gastos mensais e por categoria |
| `render_pagina_importacao()` | `src/ui/importacao.py` | None | Formulário de importação de NFC-e |
| `render_pagina_analise()` | `src/ui/analise.py` | None | Revisão e classificação de itens |
| `render_pagina_normalizacao()` | `src/ui/normalizacao.py` | None | Agrupamento e consolidação de produtos |
| `render_pagina_relatorios()` | `src/ui/relatorios.py` | None | Relatórios de custos e inflação |

### Navegação

```
main.py
├── st.sidebar.radio → { "Home", "Importar", "Analisar", "Normalizar", "Relatórios" }
├── Home        → render_home()
├── Importar    → render_pagina_importacao()
├── Analisar    → render_pagina_analise()
├── Normalizar  → render_pagina_normalizacao()
└── Relatórios  → render_pagina_relatorios()
```

### Fluxo de Inicialização

1. `st.set_page_config()` com layout wide
2. `_inicializar_recursos_embeddings()` (cache com `@st.cache_resource`)
3. `iniciar_carregamento_background()` para LLMs (thread separada)
4. `inicializar_banco()` com seed de categorias
5. Renderizar sidebar e página selecionada

### Estado da Sessão (`st.session_state`)

| Chave | Tipo | Onde é definida | Propósito |
|-------|------|-----------------|-----------|
| `modelos_llm_carregamento_iniciado` | `bool` | `main.py` | Evita reload de LLMs |
| `embeddings_cache_inicializado` | `bool` | `main.py` | Evita reload de embeddings |
| `banco_inicializado` | `bool` | `main.py` | Evita reload do banco |
| `redirecionar_menu` | `str` | `importacao.py` | Redireciona para página específica |
| `llm_model_priority` | `list[str]` | `importacao.py` | Ordem de prioridade dos modelos LLM |
| `historico_importacoes` | `list` | `importacao.py` | Últimas 5 importações |
| `flash_analisar_msgs` | `list` | `importacao.py` | Mensagens flash para página Análise |
| `nota_em_revisao` | `str` | `importacao.py` | Chave da nota para carregar no editor |

## Fluxo Principal — Importação

1. Renderizar formulário com campo de chave, checkboxes (auto-classificar, confirmar)
2. Usuário submete → `validar_chave_acesso()` (44 dígitos)
3. Verificar duplicata via `carregar_nota()`
4. Se existir: exibir diálogo reprocessar/cancelar/visualizar
5. Se confirmado ou novo: `buscar_nota(chave)` → `salvar_nota(nota)`
6. Se auto-classificar marcado: `classificar_itens_pendentes()` com progress callback
7. `_registrar_historico()` + `_adicionar_flash_analise()` + `st.rerun()` para análise

## Fluxo Principal — Análise e Revisão

1. `listar_notas_para_revisao()` → selectbox com notas pendentes
2. Seleciona nota → `listar_itens_para_revisao()` → DataFrame editável
3. Usuário edita categoria/produto/marca no `st.data_editor`
4. Duas ações:
   - **Salvar rascunho:** `registrar_revisoes_manuais(confirmar=False)`
   - **Confirmar ajustes:** `registrar_revisoes_manuais(confirmar=True)`
5. Alternativa: "Reprocessar via IA" → diálogo modal com escolha de modelo e escopo

## Fluxo Principal — Normalização

1. `listar_produtos_similares(threshold)` → clusters com produtos similares
2. Slider 70-100% controla threshold
3. Por cluster: `st.data_editor` com checkbox para selecionar produtos
4. "Consolidar N produtos" → diálogo com:
   - Produtos selecionados
   - Destino auto-selecionado (mais itens) ou manual
   - Nome final editável
5. `consolidar_produtos()` executa merge
6. Modo manual: busca textual via `buscar_produtos()` (min 2 caracteres)

## Fluxo Principal — Relatórios

### Custos Unitários
1. Date range picker (default 12 meses)
2. `obter_top_produtos_por_quantidade(limit=10)` → top produtos
3. `obter_custos_unitarios_mensais()` → série temporal por produto
4. Checkbox por produto para toggle visibilidade
5. `st.line_chart()` com DataFrame pivotado

### Inflação Acumulada
1. Date range picker (default: último dia do mês anterior, -12 meses)
2. `obter_quantidades_mensais_produtos()` → top produtos por quantidade
3. `_preencher_meses_faltantes()` → grid completo com forward fill
4. `_identificar_produtos_regulares()` → produtos em >= 2 meses consecutivos
5. `_calcular_inflacao_acumulada()` → inflação composta por produto + média
6. `_calcular_cesta_basica_personalizada()` → custo médio mensal da cesta
7. `st.line_chart()` + tabela + download CSV

## Dependências

- `streamlit` — Framework de UI
- `src.classifiers` — Classificação de itens via IA (`classificar_itens_pendentes`)
- `src.database` — Todas as operações de banco (CRUD, consultas, relatórios)
- `src.scrapers.receita_rs` — `buscar_nota()`, `validar_chave_acesso()`
- `pandas` — Manipulação de DataFrames para exibição e exporting

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Navegação por sidebar radio | `main.py:26-32` | 🟢 |
| Inicialização lazy com flags de sessão | `main.py:68-114` | 🟢 |
| Flash messages via session_state entre páginas | `importacao.py:_adicionar_flash_analise` | 🟢 |
| Histórico de importações limitado a 5 entradas | `importacao.py:_registrar_historico` | 🟢 |
| Redirecionamento pós-importação via `st.session_state["redirecionar_menu"]` | `importacao.py:252-258` | 🟢 |
| Data editor para edição em lote de itens | `analise.py:_montar_editor` | 🟢 |
| Diálogo modal Streamlit para confirmações | `analise.py:_dialogo_escolher_ia`, `normalizacao.py:_dialogo_confirmar_consolidacao` | 🟢 |
| Forward fill para meses faltantes em séries de inflação | `relatorios.py:_preencher_meses_faltantes` | 🟢 |
| Cálculo de inflação composto (não simples) | `relatorios.py:_calcular_inflacao_acumulada` | 🟢 |
| CSV export com UTF-8 BOM e separador `;` (pt-BR Excel) | `relatorios.py:render_grafico_inflacao` | 🟢 |

## Estado Interno

Todo estado é mantido em `st.session_state` do Streamlit, que persiste durante a sessão do navegador. Não há estado de servidor além do banco SQLite.

## Observabilidade

- Logs via `src.logger` para erros em operações de banco e classificação
- `st.spinner` para operações longas (download, classificação, consolidação)
- `st.error`/`st.warning`/`st.success` para feedback ao usuário

## Riscos e Lacunas

- 🟢 Dependência de internet para download de notas (SEFAZ-RS) e classificação via LLM
- 🟢 Embeddings exigem download inicial do modelo (~80MB) — fallback com aviso na UI
- 🟡 Cesta básica não usa ponderação por quantidade — assume quantidade = 1
