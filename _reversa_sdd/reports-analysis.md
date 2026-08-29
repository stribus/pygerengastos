# Análise de Relatórios e Analytics

> Complemento ao Archaeologist focado no core business do sistema.

---

## Objetivo Principal do Sistema

**Monitorar a evolução de preços de produtos de supermercado ao longo do tempo, calcular inflação personalizada e permitir validação de preços entre compras.**

O fluxo de classificação e scraping existe para sustentar este objetivo — não é um fim em si mesmo.

---

## Pipeline Analítico

```
Importação NFC-e → Classificação → Padronização → Analytics (preços/inflação/cestas)
                                                      ↓
                                              Home KPIs + Relatórios
```

---

## Dashboard Inicial (`home.py`)

| Componente | Função | Tipo |
|------------|--------|------|
| Total de Notas | `obter_kpis_gerais` | Métrica (card) |
| Gasto Total Histórico | `obter_kpis_gerais` | Métrica (card) |
| Itens Pendentes | `obter_kpis_gerais` | Métrica (card) |
| Evolução Mensal | `obter_resumo_mensal` | Gráfico de barras (últimos 12 meses) |
| Gastos por Categoria | `obter_gastos_por_categoria` | Tabela de gastos |

---

## Relatórios de Preço (`relatorios.py`)

### Tab 1: Custos Unitários Mensais

- **Objetivo:** Visualizar evolução de preços unitários dos produtos mais comprados
- **Query:** `obter_custos_unitarios_mensais()` — preço médio ponderado = `SUM(valor_total) / SUM(quantidade)` por produto/mês
- **Top N:** top 10 produtos por quantidade no período (via `obter_top_produtos_por_quantidade`)
- **Filtro:** data início/fim (padrão: últimos 12 meses)
- **Visualização:** `st.line_chart` (linhas, uma por produto)
- **Unidades:** detectadas via `obter_unidades_produtos()` (unidade mais frequente)
- **Seleção:** checkboxes para mostrar/ocultar produtos
- **Tabela:** expander com dados pivotados

### Tab 2: Inflação Acumulada

- **Objetivo:** Acompanhar variação percentual acumulada de preços
- **Métrica principal:** inflação composta: `(1 + inf_ant/100) * (1 + var_atual/100) - 1`

#### Etapas do Cálculo

1. **Preenchimento de meses faltantes** (`_preencher_meses_faltantes`): forward fill — último preço conhecido mantido para meses sem compra; meses anteriores à 1ª compra ficam NaN
2. **Identificação de produtos regulares** (`_identificar_produtos_regulares`): avaliada sobre dados brutos de quantidade mensal (não sobre a série preenchida) — nos últimos 6 **meses ativos** do período (ou todos, se menos), nunca 2 meses seguidos sem compra (bordas incluídas); unitários exigem qtd ≥1 no mês; fracionáveis (KG/G/L/ML/MG) exigem média mensal >0,1 na janela. Meses sem nota importada (`obter_meses_com_notas`) são removidos da janela: sem esse filtro, uma lacuna de coleta de 2 meses zera a lista de regulares e achata a inflação média em 0%
3. **Inflação por produto**: `_calcular_inflacao_acumulada()` para cada produto individual — base 0% no 1º mês com preço; NaN antes (linha começa na 1ª compra real)
4. **Backfill para agregados** (`_aplicar_backfill`): para produtos regulares, meses anteriores à 1ª compra recebem o primeiro preço conhecido — usado apenas por inflação média e cesta
5. **Inflação média** (`_calcular_inflacao_media`): média das inflações dos produtos regulares (séries com backfill — produto contribui 0% nos meses retro-preenchidos). Sem nenhum regular, a base vira todos os produtos do top com preço e a tela exibe aviso; mês sem dado é NaN, nunca 0%
6. **Cesta básica personalizada** (`_calcular_cesta_basica_personalizada`): média simples dos custos unitários dos produtos regulares sobre as séries com backfill (composição constante; sem ponderação por quantidade atualmente)
7. **Inflação da cesta**: inflação acumulada sobre o custo da cesta

#### Saídas

- Gráfico de linhas (produtos selecionáveis + inflação média + cesta básica)
- Exportação CSV (separador `;`, decimal `,`, encoding UTF-8-SIG)
- Tabela completa (preços + inflação intercalados)
- Composição da cesta: tabela com produto, unidade, qtd média, preço médio, custo mensal

---

## Consultas Analíticas (`database/__init__.py`)

| Função | SQL | Finalidade |
|--------|-----|------------|
| `obter_kpis_gerais` | COUNT notas, SUM valor_total, COUNT pendentes | Cards do dashboard |
| `obter_resumo_mensal` | SUM valor_total GROUP BY mês, LIMIT 12 | Evolução mensal (barras) |
| `obter_gastos_por_categoria` | SUM valor_total JOIN notas, GROUP BY categoria | Gastos por categoria |
| `obter_top_produtos_por_quantidade` | SUM quantidade GROUP BY produto, ORDER BY DESC, LIMIT n | Top produtos para relatório |
| `obter_custos_unitarios_mensais` | SUM(valor_total)/SUM(quantidade) GROUP BY produto, mês | Preço médio ponderado |
| `obter_unidades_produtos` | unidade mais frequente por produto | Legenda dos gráficos |
| `obter_quantidades_mensais_produtos` | SUM quantidade GROUP BY produto, mês | Cesta básica |

### View Consolidada

`vw_itens_padronizados` — view que junta itens + notas + datas_referencia + estabelecimentos, usada como base para consultas analíticas futuras.

---

## Métricas de Negócio

| Métrica | Fórmula | Onde |
|---------|---------|------|
| Preço médio ponderado | Σ(valor_total) / Σ(quantidade) por produto/mês | `obter_custos_unitarios_mensais` |
| Inflação acumulada | `(1+inf_ant)(1+var_atual)-1`, base 0% no 1º mês com preço | `_calcular_inflacao_acumulada` |
| Produto regular | Últimos 6 meses ativos: nunca 2 meses seguidos sem compra; unitários qtd ≥1/mês; fracionáveis média mensal >0,1 | `_identificar_produtos_regulares` |
| Mês ativo | Mês com ao menos uma nota importada | `obter_meses_com_notas` |
| Cesta básica | Média simples dos custos unitários regulares (séries com backfill) | `_calcular_cesta_basica_personalizada` |
| Forward fill | Último preço conhecido mantido | `_preencher_meses_faltantes` |
| Backfill (cesta/média) | 1º preço conhecido vale para meses anteriores à 1ª compra | `_aplicar_backfill` |
