# Database, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `inicializar_banco` | `(db_path)` | `sqlite3.Connection` | Singleton, cria schema se não existir |
| `salvar_nota` | `(nota: NotaFiscal, db_path)` | `None` | Upsert por chave_acesso |
| `remover_nota` | `(chave_acesso: str, db_path)` | `None` | Cascata manual |
| `normalizar_produto_descricao` | `(descricao: str)` | `tuple[str, Optional[str]]` | (nome_base, marca_base) |
| `normalizar_nome_produto_universal` | `(nome: str)` | `str` | Normalização avançada |
| `registrar_classificacao_itens` | `(dados, confirmar, db_path)` | `None` | Histórico + update item |
| `consolidar_produtos` | `(produto_id_origem, produto_id_destino, nome_final, db_path)` | `None` | Merge completo |
| `obter_kpis_gerais` | `(db_path)` | `dict` | 3 métricas do dashboard |
| `obter_custos_unitarios_mensais` | `(produtos, data_inicio, data_fim, db_path)` | `list[dict]` | Preço médio ponderado |
| `obter_top_produtos_por_quantidade` | `(data_inicio, data_fim, top_n, db_path)` | `list[dict]` | Top N produtos |

## Fluxo Principal — Salvar Nota

1. `salvar_nota()` recebe `NotaFiscal` do scraper (`database/__init__.py:1580-1610`)
2. Chama `_persistir_nota()`: upsert da nota (ON CONFLICT por chave_acesso) (`__init__.py:1592`)
3. Remove itens e pagamentos antigos se existirem (reprocessamento) (`__init__.py:1595-1600`)
4. Para cada item: chama `_resolver_produto_por_descricao()` (`__init__.py:1702-1767`)
5. Resolução: alias exato → normalização descrição → criação de produto (`__init__.py:1720-1750`)
6. Registra alias para aprendizado futuro (`__init__.py:1760`)
7. Gera embedding no ChromaDB via `upsert_descricao_embedding()` (`__init__.py:1765`)
8. Persiste itens e pagamentos (`__init__.py:1610-1630`)

## Fluxo Principal — Registrar Classificação

1. `registrar_classificacao_itens()` recebe lista de resultados (`__init__.py:1380-1420`)
2. Para cada resultado: insere em `classificacoes_historico` (`__init__.py:1390`)
3. Atualiza item: `categoria_sugerida`, `confianca`, `fonte`, `modelo` (`__init__.py:1400`)
4. Se `confirmar=True`: preenche `categoria_confirmada` = `categoria_sugerida` (`__init__.py:1410`)
5. Se classificador sugeriu produto: resolve ou cria via `_resolver_produto_por_nome_marca()` (`__init__.py:1415`)

## Fluxo Principal — Consolidar Produtos

1. `consolidar_produtos(origem, destino, nome_final)` (`__init__.py:2654`)
2. Migra itens da origem para o destino (UPDATE produto_id) (`__init__.py:2700-2720`)
3. Migra aliases da origem para o destino (protegendo aliases de terceiros) (`__init__.py:2730-2750`)
4. Se nome_final conflitar com produto existente, gera sufixo numérico (`__init__.py:2741`)
5. Registra em `consolidacoes_historico` (`__init__.py:2790`)
6. Deleta produto origem (`__init__.py:2800`)
7. Atualiza embeddings no ChromaDB (fora da transação) (`__init__.py:2810-2858`)

## Fluxo Principal — Queries Analíticas

1. `obter_custos_unitarios_mensais()`: `SELECT produto_nome, strftime('%Y-%m', emissao_data), SUM(valor_total)/SUM(quantidade)` (`__init__.py:2285-2339`)
2. `obter_kpis_gerais()`: `COUNT(*) notas, SUM(valor_total), COUNT(*) pendentes` (`__init__.py:2166-2185`)
3. `obter_gastos_por_categoria()`: `SELECT categoria_confirmada, SUM(valor_total)` com JOIN notas (`__init__.py:2208-2233`)

## Dependências

- **classifiers.embeddings**: chama `upsert_descricao_embedding()` ao salvar nota (`__init__.py:1765`)
- **scrapers**: recebe `NotaFiscal` como entrada (`__init__.py:1580`)
- **SQLite3**: persistência (`data/gastos.db`)

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Conexões SQLite3 gerenciadas via context manager `conexao()` | `__init__.py:225-238` | 🟢 |
| Upsert manual com ON CONFLICT para notas | `__init__.py:1592` | 🟢 |
| Remoção em cascata manual (SQLite não tem CASCADE nativo para DELETE) | `__init__.py:697-735` | 🟢 |
| Dimensão temporal datas_referencia populada programaticamente | `__init__.py:2110-2160` | 🟢 |
| Fuzzy matching com rapidfuzz para produtos similares | `__init__.py:2430-2540` | 🟢 |

## Estado Interno

- `_conexoes` (module-level): cache de conexões por db_path (não usado atualmente)
- Schema gerenciado via `inicializar_banco()` que cria tabelas com IF NOT EXISTS

## Observabilidade

- Logging via módulo `logger` configurado em `src/logger.py`
- Operações de consolidação registradas em `consolidacoes_historico` (auditoria)
- Conexões de banco gerenciadas por context manager com commit/rollback automático

## Riscos e Lacunas

- 🔴 `database/__init__.py` com 2.501 LOC — severa violação de SRP, difícil manutenção
- 🔴 Marcas conhecidas hardcoded em dicionário — qualquer marca nova exige modificação de código
- 🟡 Sem migrations versionadas — schema é criado com IF NOT EXISTS, sem rastreabilidade de mudanças
