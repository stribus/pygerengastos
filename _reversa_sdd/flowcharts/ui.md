# Fluxograma — ui

> Gerado pelo Archaeologist

## Fluxo de Importação

```mermaid
flowchart TD
    A[render_pagina_importacao] --> B[Formulário: chave + opções]
    B --> C{Nota já existe?}
    C -->|Sim| D[Confirmar reprocessamento?]
    D -->|Sim| E[Remover nota antiga]
    D -->|Não| F[Cancelar]
    E --> G[Buscar nota na SEFAZ-RS]
    C -->|Não| G
    G --> H[Salvar no banco]
    H --> I[Classificar automaticamente?]
    I -->|Sim| J[Executar classificação]
    I -->|Não| K[Redirecionar para análise]
    J --> K
```

## Fluxo de Análise e Revisão

```mermaid
flowchart TD
    A[render_pagina_analise] --> B[Listar notas para revisão]
    B --> C[Selecionar nota]
    C --> D[Exibir itens em data_editor]
    D --> E{Ação do usuário}
    E -->|Reprocessar via IA| F[Diálogo escolher modelo]
    F --> G[classificar_itens_pendentes]
    E -->|Salvar rascunho| H[registrar_revisoes_manuais(confirmar=False)]
    E -->|Confirmar ajustes| I[registrar_revisoes_manuais(confirmar=True)]
    H --> J[Atualizar UI]
    I --> J
```

## Fluxo de Relatórios — Inflação Acumulada

```mermaid
flowchart TD
    A[render_grafico_inflacao] --> B[Filtros de período]
    B --> C[Top 10 produtos]
    C --> D[Custos unitários mensais]
    D --> E[Preencher meses faltantes]
    E --> F[Identificar produtos regulares]
    F --> G[Calcular inflação por produto]
    F --> H[Calcular inflação média]
    F --> I[Calcular cesta básica]
    G --> J[Plotar gráfico]
    H --> J
    I --> J
```
