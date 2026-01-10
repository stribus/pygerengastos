# Relatórios e Gráficos - Documentação

## Visão Geral

A funcionalidade de relatórios permite acompanhar a evolução dos preços dos produtos ao longo do tempo e calcular a inflação da sua cesta de compras pessoal.

## Funcionalidades Implementadas

### 1. Gráfico de Custos Unitários Mensais

**Localização:** Aba "Relatórios" > "Custos Unitários Mensais"

**O que faz:**
- Mostra a evolução do preço unitário médio dos 10 produtos mais comprados
- Permite selecionar período customizado (data início e data fim)
- Cada produto pode ser mostrado/oculto individualmente via checkboxes
- Exibe gráfico de linhas interativo

**Como usar:**
1. Navegue até "Relatórios" no menu lateral
2. Na aba "Custos Unitários Mensais":
   - Ajuste as datas de início e fim do período desejado
   - Marque/desmarque os produtos que deseja visualizar
   - O gráfico atualiza automaticamente
3. Expanda "Ver dados em tabela" para ver os valores numéricos

**Exemplo de uso:**
- Compare o preço do arroz em janeiro vs. dezembro
- Identifique produtos com maior variação de preço
- Planeje compras baseado em tendências históricas

### 2. Gráfico de Inflação Acumulada

**Localização:** Aba "Relatórios" > "Inflação Acumulada"

**O que faz:**
- Calcula a variação percentual acumulada dos preços ao longo do tempo
- Mostra top 10 produtos mais comprados
- Preenche meses sem compra com o último preço conhecido
- Identifica produtos regulares (⭐) - comprados em meses consecutivos
- Calcula "Inflação Média" dos produtos regulares
- Calcula "Cesta Básica Personalizada" - média ponderada dos produtos que você compra regularmente
- Permite exportar dados para Excel/CSV

**Como usar:**
1. Navegue até "Relatórios" > "Inflação Acumulada"
2. Ajuste o período desejado
3. Selecione os produtos que deseja acompanhar
4. Marque as opções:
   - "Inflação Média" - mostra inflação média dos produtos regulares
   - "Cesta Básica Personalizada" - mostra inflação da sua cesta pessoal
5. Clique em "Baixar Excel (CSV)" para exportar os dados

**Conceitos importantes:**

- **Produto Regular (⭐)**: Produtos comprados em pelo menos 2 meses consecutivos. Apenas estes entram no cálculo da inflação média, pois produtos esporádicos distorcem a análise.

- **Inflação Média**: Média da inflação acumulada apenas dos produtos regulares. Ignora produtos comprados esporadicamente.

- **Cesta Básica Personalizada**: Calcula o custo médio mensal dos produtos que você compra regularmente. Útil para entender quanto sua cesta de compras típica está variando.

- **Preenchimento de Meses**: Se você não comprou um produto em um mês específico, o sistema usa o preço da última compra para manter a continuidade da análise.

**Exemplo de uso:**
- Veja quanto sua cesta básica inflacionou no último ano
- Compare a inflação real dos seus produtos vs. inflação oficial
- Identifique produtos com inflação acima da média
- Exporte dados para análise em Excel

### 3. Exportação de Dados

O botão "Baixar Excel (CSV)" na aba de Inflação gera um arquivo com:

**Colunas incluídas:**
- Mês
- Para cada produto:
  - `[Produto] - Preço (UN/KG)`: Preço unitário médio do mês
  - `[Produto] - Inflação (%)`: Inflação acumulada até aquele mês
- `Inflação Média (%)`: Média dos produtos regulares
- `Cesta Básica - Custo (R$)`: Custo médio mensal da cesta
- `Cesta Básica - Inflação (%)`: Inflação acumulada da cesta

**Formato:** CSV com:
- Separador: ponto-e-vírgula (;)
- Decimal: vírgula (,)
- Encoding: UTF-8 com BOM
- Compatível com Microsoft Excel

## Requisitos Técnicos

### Dados Necessários

Para usar os relatórios, você precisa ter:
1. ✅ Notas fiscais importadas
2. ✅ Itens classificados (categoria confirmada)
3. ✅ Produtos padronizados (nome e marca)
4. ✅ Pelo menos 2-3 meses de histórico

### Performance

As queries foram otimizadas para:
- Agregação no banco de dados (SQLite3)
- Uso de índices nas datas de emissão
- Limitação de resultados (top 10 produtos)
- Cache de dados quando apropriado

**Tempo esperado:**
- 12 meses de dados, 10 produtos: < 1 segundo
- 24 meses de dados, 20 produtos: < 2 segundos

## Limitações Conhecidas

1. **Produtos sem histórico contínuo**: Se um produto foi comprado apenas uma vez, não aparecerá nos gráficos de inflação (requer pelo menos 2 compras)

2. **Mudança de marca**: Se você trocar a marca de um produto, ele pode aparecer como produto diferente. Solução: use a funcionalidade de revisão manual para padronizar o nome.

3. **Produtos fracionados**: Produtos vendidos por peso (kg, g) podem ter variação de quantidade que afeta o preço médio. O sistema já calcula preço unitário (R$/kg) automaticamente.

## Fórmulas de Cálculo

### Inflação Acumulada

```
Para cada mês i (começando do mês 1):

Inflação[0] = 0%  (mês base)

Para i > 0:
  variação_i = (Preço[i] - Preço[i-1]) / Preço[i-1] * 100
  
  Inflação[i] = ((1 + Inflação[i-1]/100) * (1 + variação_i/100) - 1) * 100
```

Esta fórmula usa capitalização composta, que é o método correto para calcular inflação acumulada.

### Inflação Média

```
Inflação_Média[mês] = Soma(Inflação_Produto_Regular[mês]) / Quantidade_Produtos_Regulares
```

Considera apenas produtos regulares para evitar distorções.

### Cesta Básica Personalizada

```
Custo_Cesta[mês] = Média(Preço_Unitário[produto, mês]) para todos produtos regulares
```

Simplificação: assume quantidade média igual para todos produtos. Em versões futuras, pode ser ponderado pela quantidade média mensal de cada produto.

## Solução de Problemas

**Problema:** "Nenhum produto encontrado no período"

**Solução:** 
- Verifique se há notas importadas no período
- Confirme que os itens estão classificados
- Ajuste o período selecionado

---

**Problema:** Produtos aparecem com nomes duplicados

**Solução:**
- Use a aba "Analisar notas" para padronizar nomes de produtos
- Certifique-se de preencher "nome base" e "marca" corretamente

---

**Problema:** Gráfico de inflação mostra valores muito altos

**Possíveis causas:**
- Produto teve mudança de embalagem (ex: 1kg → 500g)
- Preço registrado incorretamente na nota fiscal
- Promoção excepcional em um mês distorcendo a média

**Solução:** Revise os dados originais na aba "Analisar notas"

## Exemplos Práticos

### Exemplo 1: Descobrir qual produto mais inflacionou

1. Vá em "Relatórios" > "Inflação Acumulada"
2. Selecione período de 12 meses
3. Marque todos os produtos
4. Observe as linhas no gráfico - a mais alta é o produto com maior inflação
5. Exporte para Excel para ver valores exatos

### Exemplo 2: Comparar sua inflação vs. oficial

1. Gere o gráfico de inflação da sua cesta básica
2. Anote o valor final (ex: 15% em 12 meses)
3. Compare com IPCA/INPC do período
4. Use isso para negociar reajuste salarial! 📊

### Exemplo 3: Identificar melhores momentos para comprar

1. Vá em "Custos Unitários Mensais"
2. Selecione produto específico (ex: Arroz)
3. Observe padrão sazonal
4. Planeje compras em meses com preços mais baixos

## Roadmap de Melhorias Futuras

- [ ] Adicionar gráficos de pizza para composição de gastos
- [ ] Comparar com índices oficiais (IPCA, IGP-M)
- [ ] Previsão de preços usando ML
- [ ] Alertas de produtos com inflação anormal
- [ ] Comparação entre estabelecimentos
- [ ] Gráfico de sazonalidade
- [ ] Dashboard executivo com KPIs principais
- [ ] Exportação para PDF com relatório formatado

## Suporte

Para reportar bugs ou sugerir melhorias, abra uma issue no GitHub:
https://github.com/stribus/pygerengastos/issues
