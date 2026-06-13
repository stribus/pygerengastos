# Database

## Visão Geral

Camada de persistência SQLite3 completa com schema de 10 tabelas + 1 view, CRUD de notas fiscais, padronização de produtos, registro de classificações e 7 funções de consulta analítica para relatórios e dashboard.

## Responsabilidades

- Inicializar schema do banco (tabelas, índices, view)
- Salvar/remover notas fiscais com seus itens e pagamentos (upsert)
- Normalizar descrições de produtos (nome_base + marca_base)
- Resolver/criar produtos por alias ou normalização
- Registrar classificações (automáticas e manuais) com histórico completo
- Consolidar produtos duplicados (merge com migração de aliases e embeddings)
- Fornecer consultas analíticas para KPIs, evolução mensal, custos unitários e inflação
- Gerenciar datas_referencia (dimensão temporal para star schema)

## Regras de Negócio

- Notas usam upsert por chave de acesso (44 dígitos) 🟢
- Remoção de nota é cascata: classificacoes_historico → revisoes → itens → pagamentos → nota 🟢
- Produto é único por par (nome_base, marca_base) 🟢
- Produto é resolvido por: alias exato → normalização descrição → criação 🟢
- Marcas conhecidas hardcoded (Tio João, Sadia, Nestlé, Ambev, etc) 🟢
- Normalização: remove unidades, detecta marca, title case 🟢
- Categoria inexistente é criada automaticamente no grupo "Livres" 🟢
- Estabelecimento é único por CNPJ normalizado (14 dígitos) 🟢
- Consolidação de estabelecimento é incremental (nunca sobrescreve) 🟢
- Consolidação de produto: destino com mais itens, origem deletada 🟢
- Alias de terceiros não são migrados durante consolidação 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Inicializar banco com schema completo | Must | Tabelas, índices, triggers e view criados na primeira execução |
| RF-02 | Salvar nota fiscal com itens e pagamentos (upsert) | Must | Nota salva ou atualizada por chave_acesso; itens e pagamentos recriados |
| RF-03 | Remover nota fiscal em cascata | Must | Todos registros associados (classificações, revisões, itens, pagamentos) deletados |
| RF-04 | Normalizar descrição de produto | Must | Descrição "ARROZ TIO JOAO 5KG" → ("Arroz", "Tio João") |
| RF-05 | Resolver produto por alias, normalização ou criação | Must | Sequência: alias → normalização → produto novo |
| RF-06 | Registrar classificação de itens com histórico | Must | Classificação salva em classificacoes_historico e atualizada no item |
| RF-07 | Consolidar produtos duplicados | Should | Merge de produto origem em destino com migração de aliases e embeddings |
| RF-08 | Obter KPIs gerais (total notas, gasto, pendentes) | Must | Dashboard inicial com 3 métricas |
| RF-09 | Obter custos unitários mensais por produto | Must | Preço médio ponderado (SUM valor_total / SUM quantidade) por mês |
| RF-10 | Obter top produtos por quantidade no período | Should | Top N produtos mais comprados para relatórios |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Índices em chave_acesso, produto_nome e categoria | `database/__init__.py:240-248` | 🟢 |
| Integridade | ON CONFLIT para upsert de notas | `database/__init__.py:1592` | 🟢 |
| Integridade | Remoção em cascata manual (SQLite não suporta CASCADE nativo) | `database/__init__.py:697-735` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado uma nota fiscal NFC-e com chave de acesso
Quando salvar_nota() é chamado
Então nota, itens e pagamentos são persistidos
E se chave já existe, dados são atualizados (upsert)

Dado um item com descrição "ARROZ TIO JOAO 5KG"
Quando normalizar_produto_descricao() é chamado
Então retorna nome_base="Arroz" e marca_base="Tio João"

Dado dois produtos duplicados
Quando consolidar_produtos() é chamado com produto_id_origem e produto_id_destino
Então itens são migrados para destino
E aliases são migrados (exceto se já pertencem a outro produto)
E produto origem é deletado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Schema, CRUD de notas | Must | Base de todo o sistema |
| Classificação de itens | Must | Chamado por classifiers e ui |
| Consultas analíticas | Must | Alimenta KPIs e relatórios |
| Consolidação de produtos | Should | Importante mas produtos podem conviver duplicados |
| Normalização universal | Should | Usada em consolidação, não no fluxo principal |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/database/__init__.py:1-250` | Schema e init | 🟢 |
| `src/database/__init__.py:251-700` | CRUD notas | 🟢 |
| `src/database/__init__.py:501-680` | Normalização | 🟢 |
| `src/database/__init__.py:1380-1450` | Registro classificação | 🟢 |
| `src/database/__init__.py:1702-1767` | Resolução produto | 🟢 |
| `src/database/__init__.py:1969-2066` | Estabelecimentos | 🟢 |
| `src/database/__init__.py:2166-2430` | Queries analíticas | 🟢 |
| `src/database/__init__.py:2654-2858` | Consolidação | 🟢 |
