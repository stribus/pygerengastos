# UI — Interface Streamlit

## Visão Geral

Interface web construída com Streamlit para gerenciamento de notas fiscais eletrônicas (NFC-e). Oferece 5 páginas: Home (visão geral), Importação, Análise, Normalização de Produtos e Relatórios de inflação.

## Responsabilidades

- Exibir dashboard com KPIs gerais (total de notas, gasto acumulado, itens pendentes)
- Importar NFC-e via chave de acesso (44 dígitos) do portal SEFAZ-RS
- Revisar e classificar itens de notas (categoria, produto, marca) manualmente ou via IA
- Normalizar produtos duplicados via agrupamento por similaridade
- Calcular e exibir relatórios de custos unitários e inflação acumulada

## Regras de Negócio

- Navegação centralizada via `st.sidebar.radio` com dispatch para função por página 🟢
- Inicialização de recursos (DB, embeddings, LLMs) ocorre uma vez na inicialização via `st.session_state` 🟢
- Importação rejeita chaves não numéricas ou com != 44 dígitos 🟢
- Notas já importadas exigem confirmação de reprocessamento antes de reimportar 🟢
- Classificação automática pós-importação é opcional (checkbox) 🟢
- Revisão de itens suporta salvar rascunho (`confirmar=False`) ou confirmar (`confirmar=True`) 🟢
- Similaridade mínima para agrupamento: 70%, máxima: 100% 🟢
- Consolidação de produtos requer no mínimo 2 selecionados; destino é o produto com mais itens 🟢
- Produtos regulares para inflação: comprados em pelo menos 2 meses consecutivos 🟢
- Meses faltantes em série temporal são preenchidos com último preço conhecido (forward fill) 🟢
- Período padrão de relatórios: últimos 12 meses 🟢
- Cada produto listado tem checkbox marcado por padrão; se nenhum produto for selecionado, exibe aviso e não renderiza o gráfico 🟢
- Inflação Média e Cesta Básica são séries opcionais controladas por checkboxes independentes 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Exibir dashboard com KPIs (total notas, gasto total, itens pendentes) | Must | KPIs calculados e exibidos na Home |
| RF-02 | Exibir gráfico de evolução mensal de gastos | Must | Bar chart com gastos por mês na Home |
| RF-03 | Exibir gastos por categoria em tabela formatada | Must | DataFrame com valores em moeda na Home |
| RF-04 | Importar NFC-e por chave de acesso de 44 dígitos | Must | Formulário → download SEFAZ → parse → salvar no DB |
| RF-05 | Confirmar reprocessamento se nota já existe no DB | Should | Diálogo com Reprocessar/Cancelar/Visualizar |
| RF-06 | Classificar itens automaticamente via IA pós-importação | Should | Opcional por checkbox; executa classificar_itens_pendentes |
| RF-07 | Permitir reordenar prioridade de modelos LLM | Could | Data editor na página de importação |
| RF-08 | Exibir itens de nota para revisão em data editor | Must | Grid editável com categoria, produto, marca |
| RF-09 | Salvar rascunho de revisão sem confirmar | Should | `registrar_revisoes_manuais(confirmar=False)` |
| RF-10 | Confirmar revisão de itens | Must | `registrar_revisoes_manuais(confirmar=True)` |
| RF-11 | Reprocessar itens via IA com escolha de modelo | Should | Diálogo modal com seleção de modelo e escopo |
| RF-12 | Exibir histórico de revisões manuais | Should | Tabela de revisões anteriores por nota |
| RF-13 | Agrupar produtos similares por threshold de similaridade | Must | Slider 70-100% com clusterização |
| RF-14 | Consolidar produtos duplicados em um só | Must | Diálogo de confirmação com escolha de destino |
| RF-15 | Busca manual de produtos para agrupamento | Should | Formulário com mínimo 2 caracteres |
| RF-16 | Exibir custos unitários mensais em gráfico de linhas | Must | Tab de Custos Unitários com filtro de período |
| RF-17 | Exibir inflação acumulada por produto e média | Must | Tab de Inflação Acumulada com gráfico de linhas |
| RF-18 | Calcular cesta básica personalizada | Should | Custo mensal da cesta com produtos regulares |
| RF-19 | Exportar relatório de inflação para CSV | Could | Download button com encoding UTF-8 BOM |
| RF-20 | Ocultar/exibir produtos individualmente no gráfico | Should | Checkbox por produto (default marcado); só os visíveis entram no gráfico de custos e de inflação |
| RF-21 | Alternar exibição de séries agregadas (Inflação Média e Cesta Básica) | Could | Checkboxes `mostrar_media` e `mostrar_cesta` no gráfico de inflação |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Inicialização única de recursos pesados (embeddings, banco) | `main.py` com `@st.cache_resource` e flags `st.session_state` | 🟢 |
| Usabilidade | Flash messages entre páginas via session_state | `importacao.py:_adicionar_flash_analise` | 🟢 |
| Usabilidade | Histórico de importações na sessão (últimas 5) | `importacao.py:_registrar_historico` | 🟢 |
| Resiliência | Fallback gracioso se embeddings não puderem ser baixados | `main.py:st.warning` sobre internet | 🟢 |

## Critérios de Aceitação

```gherkin
Dado que o usuário acessa a Home
Quando a página carrega
Então os KPIs de total de notas, gasto total e itens pendentes são exibidos

Dado que o usuário está na página de Importação
Quando insere uma chave de 44 dígitos e clica em Importar
Então a nota é baixada da SEFAZ-RS, salva no banco e exibida

Dado que o usuário está na página de Importação
Quando insere uma chave inválida
Então uma mensagem de erro é exibida

Dado que uma nota já existe no banco
Quando o usuário tenta importá-la novamente
Então um diálogo de confirmação de reprocessamento é exibido

Dado que o usuário está na página de Análise
Quando seleciona uma nota e edita os itens no data editor
Então as alterações são salvas como rascunho ou confirmadas

Dado que o usuário está na página de Normalização
Quando ajusta o threshold de similaridade
Então os clusters de produtos similares são recalculados

Dado que o usuário está na página de Relatórios
Quando seleciona um período
Então os gráficos de custos unitários e inflação são exibidos

Dado que o usuário está na página de Relatórios com produtos listados
Quando desmarca o checkbox de um produto
Então esse produto deixa de aparecer no gráfico

Dado que o usuário desmarca todos os produtos
Quando o gráfico tentaria renderizar
Então um aviso é exibido e nenhum gráfico é renderizado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Importação de NFC-e (RF-04) | Must | Caminho crítico, sem isso nada funciona |
| Revisão de itens (RF-08, RF-10) | Must | Necessário para classificação |
| Dashboard Home (RF-01, RF-02, RF-03) | Must | Valor central do app |
| Normalização de produtos (RF-13, RF-14) | Must | Essencial para qualidade dos dados |
| Relatórios de inflação (RF-16, RF-17) | Must | Funcionalidade principal de análise |
| Classificação automática (RF-06) | Should | Importante mas pode ser feito manualmente |
| Consolidação manual (RF-15) | Could | Alternativa à clusterização automática |
| Exportação CSV (RF-19) | Could | Valor adicional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `main.py` | `main()` | 🟢 |
| `src/ui/home.py` | `render_home()` | 🟢 |
| `src/ui/importacao.py` | `render_pagina_importacao()` | 🟢 |
| `src/ui/analise.py` | `render_pagina_analise()` | 🟢 |
| `src/ui/normalizacao.py` | `render_pagina_normalizacao()` | 🟢 |
| `src/ui/relatorios.py` | `render_pagina_relatorios()` | 🟢 |
| `src/ui/relatorios.py` | `render_grafico_inflacao()` | 🟢 |
| `src/ui/relatorios.py:255` | Checkbox por produto (custos) | 🟢 |
| `src/ui/relatorios.py:423-438` | Checkboxes de itens, média e cesta (inflação) | 🟢 |
