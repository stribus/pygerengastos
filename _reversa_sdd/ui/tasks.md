# UI, Tarefas de Implementação

## Pré-requisitos
- [ ] Streamlit instalado (>= 1.54.0)
- [ ] Módulos `database`, `scrapers`, `classifiers` implementados e testados
- [ ] Pasta `data/` criada com permissão de escrita
- [ ] `.env` configurado com `SEFAZRS_URL` (portal da receita)

## Tarefas

- [ ] T-01, Implementar entry point com inicialização de recursos e sidebar navigation
  - Origem no legado: `main.py:68-114`
  - Critério de pronto: App inicia, banco, embeddings e LLMs inicializados uma vez, sidebar renderizada com 5 opções
  - Confiança: 🟢

- [ ] T-02, Implementar página Home com KPIs e gráficos
  - Origem no legado: `src/ui/home.py`
  - Critério de pronto: Métricas de total de notas, gasto total e pendentes exibidas; bar chart mensal e table de gastos por categoria renderizados
  - Confiança: 🟢

- [ ] T-03, Implementar formulário de importação com validação de chave
  - Origem no legado: `src/ui/importacao.py:80-120`
  - Critério de pronto: Campo de chave com validação de 44 dígitos; submit chama `buscar_nota()` e `salvar_nota()`
  - Confiança: 🟢

- [ ] T-04, Implementar detecção e reprocessamento de notas duplicadas
  - Origem no legado: `src/ui/importacao.py:216-288`
  - Critério de pronto: Se nota já existe, exibir diálogo com opções Reprocessar / Cancelar / Visualizar
  - Confiança: 🟢

- [ ] T-05, Implementar classificação automática pós-importação
  - Origem no legado: `src/ui/importacao.py:295-340`
  - Critério de pronto: Checkbox "Classificar itens automaticamente" dispara `classificar_itens_pendentes()` com progress callback
  - Confiança: 🟢

- [ ] T-06, Implementar editor de prioridade de modelos LLM
  - Origem no legado: `src/ui/importacao.py:65-75`
  - Critério de pronto: Data editor com colunas de ordem e nome do modelo; botão "Recarregar modelos" funcional
  - Confiança: 🟢

- [ ] T-07, Implementar histórico de importações na sessão
  - Origem no legado: `src/ui/importacao.py:_registrar_historico`, `_renderizar_historico`
  - Critério de pronto: Últimas 5 importações exibidas em tabela; redirecionamento para análise após importação
  - Confiança: 🟢

- [ ] T-08, Implementar página de Análise com seletor de notas e data editor
  - Origem no legado: `src/ui/analise.py:60-180`
  - Critério de pronto: Selectbox de notas pendentes, data editor com colunas editáveis (categoria, produto, marca) e protegidas (seq, descrição, qtd, valor)
  - Confiança: 🟢

- [ ] T-09, Implementar ações de salvar rascunho e confirmar ajustes
  - Origem no legado: `src/ui/analise.py:190-230`
  - Critério de pronto: "Salvar rascunho" chama `registrar_revisoes_manuais(confirmar=False)`; "Confirmar ajustes" chama `registrar_revisoes_manuais(confirmar=True)`
  - Confiança: 🟢

- [ ] T-10, Implementar diálogo de reprocessamento via IA
  - Origem no legado: `src/ui/analise.py:_dialogo_escolher_ia`
  - Critério de pronto: Modal com seleção de modelo LLM e escopo (pendentes/todos); executa `classificar_itens_pendentes()`
  - Confiança: 🟢

- [ ] T-11, Implementar filtros e exibição de revisões manuais
  - Origem no legado: `src/ui/analise.py:260-290`
  - Critério de pronto: Checkbox "Somente com pendentes" e "Apenas itens pendentes" funcionais; tabela de histórico de revisões exibida
  - Confiança: 🟢

- [ ] T-12, Implementar página de Normalização com clusterização por similaridade
  - Origem no legado: `src/ui/normalizacao.py:50-150`
  - Critério de pronto: Slider 70-100% recalcula clusters via `listar_produtos_similares()`; expanders com lista de produtos similares
  - Confiança: 🟢

- [ ] T-13, Implementar consolidação de produtos (automática)
  - Origem no legado: `src/ui/normalizacao.py:_dialogo_confirmar_consolidacao`
  - Critério de pronto: Selecionar 2+ produtos → diálogo com destino auto-selecionado (mais itens) + nome final editável → `consolidar_produtos()`
  - Confiança: 🟢

- [ ] T-14, Implementar busca manual de produtos para agrupamento
  - Origem no legado: `src/ui/normalizacao.py:_render_consolidacao_manual`
  - Critério de pronto: Formulário com busca textual (min 2 caracteres), tabela de resultados adicionáveis, consolidação via mesmo diálogo
  - Confiança: 🟢

- [ ] T-15, Implementar tab de Custos Unitários Mensais
  - Origem no legado: `src/ui/relatorios.py:render_grafico_custos_unitarios`
  - Critério de pronto: Date range picker, top 10 produtos, gráfico de linhas com toggle por produto, tabela expandable
  - Confiança: 🟢

- [ ] T-16, Implementar tab de Inflação Acumulada
  - Origem no legado: `src/ui/relatorios.py:render_grafico_inflacao`
  - Critério de pronto: Date range, forward fill de meses faltantes, inflação composta por produto, inflação média, cesta básica, download CSV
  - Confiança: 🟢

- [ ] T-17, Implementar exportação CSV de relatório de inflação
  - Origem no legado: `src/ui/relatorios.py` (download button)
  - Critério de pronto: CSV com encoding UTF-8 BOM, separador `;`, decimal `,`; compatível com Excel pt-BR
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Teste de navegação: todas as 5 páginas renderizam sem erro
- [ ] TT-02, Teste de importação com chave válida mockada (HTML fixture)
- [ ] TT-03, Teste de importação com chave inválida → erro exibido
- [ ] TT-04, Teste de reprocessamento de nota duplicada → diálogo exibido
- [ ] TT-05, Teste de editor de revisão: salvar rascunho e confirmar
- [ ] TT-06, Teste de normalização: threshold 95% agrupa corretamente
- [ ] TT-07, Teste de consolidação: 2 produtos mergeados sem perda de dados
- [ ] TT-08, Teste de relatório de inflação: forward fill preenche meses faltantes

## Ordem Sugerida

1. T-01 (entry point) — tudo depende da inicialização
2. T-03 a T-07 (importação) — primeiro fluxo do usuário
3. T-02 (Home) — precisa de dados para exibir KPIs
4. T-08 a T-11 (análise) — depois que notas existem
5. T-12 a T-14 (normalização) — depois que produtos existem
6. T-15 a T-17 (relatórios) — por último, consome todos os dados

## Lacunas Pendentes (🔴)

- Nenhuma lacuna identificada — todos os comportamentos são confirmados no código legado