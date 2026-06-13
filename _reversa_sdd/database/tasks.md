# Database, Tarefas de Implementação

## Pré-requisitos

- [ ] SQLite3 disponível (stdlib Python)
- [ ] ChromaDB configurado para embeddings (se aplicável)

## Tarefas

- [ ] T-01, Implementar schema do banco (10 tabelas + 1 view + índices)
  - Origem no legado: `src/database/__init__.py:1-250`
  - Critério de pronto: `inicializar_banco()` cria todas as tabelas com IF NOT EXISTS; view vw_itens_padronizados criada; índices criados
  - Confiança: 🟢

- [ ] T-02, Implementar CRUD de notas fiscais com upsert (salvar/remover)
  - Origem no legado: `src/database/__init__.py:1580-1630`
  - Critério de pronto: `salvar_nota()` persiste nota+itens+pagamentos; upsert por chave_acesso; `remover_nota()` deleta em cascata
  - Confiança: 🟢

- [ ] T-03, Implementar normalização de descrições de produtos
  - Origem no legado: `src/database/__init__.py:501-680`
  - Critério de pronto: `normalizar_produto_descricao()` retorna (nome_base, marca_base); marcas conhecidas detectadas; unidades removidas; `normalizar_nome_produto_universal()` extrai tamanhos
  - Confiança: 🟢

- [ ] T-04, Implementar resolução de produto (alias → normalização → criação)
  - Origem no legado: `src/database/__init__.py:1702-1767`
  - Critério de pronto: alias exato vincula produto; fallback para normalização; criação se não existir; alias registrado
  - Confiança: 🟢

- [ ] T-05, Implementar registro de classificação com histórico
  - Origem no legado: `src/database/__init__.py:1380-1450`
  - Critério de pronto: `registrar_classificacao_itens()` insere em classificacoes_historico, atualiza item com categoria, confianca, fonte
  - Confiança: 🟢

- [ ] T-06, Implementar consolidação de produtos (merge)
  - Origem no legado: `src/database/__init__.py:2654-2858`
  - Critério de pronto: itens migrados, aliases migrados (exceto de terceiros), origem deletada, consolidacoes_historico registrado, embeddings atualizados
  - Confiança: 🟢

- [ ] T-07, Implementar 7 queries analíticas
  - Origem no legado: `src/database/__init__.py:2166-2430`
  - Critério de pronto: KPIs, resumo mensal, gastos por categoria, top produtos, custos unitários, unidades, quantidades mensais — todas implementadas e testadas
  - Confiança: 🟢

- [ ] T-08, Implementar gerenciamento de estabelecimentos (resolução/deduplicação)
  - Origem no legado: `src/database/__init__.py:1969-2066`
  - Critério de pronto: estabelecimento único por CNPJ normalizado; consolidação incremental não sobrescreve dados existentes
  - Confiança: 🟢

- [ ] T-09, Implementar datas_referencia (dimensão temporal)
  - Origem no legado: `src/database/__init__.py:2110-2160`
  - Critério de pronto: datas_referencia populada com ano, mês, dia, ano_mes, trimestre, semana ISO, nome_mes, nome_dia_semana
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Teste happy path: salvar nota e verificar itens/pagamentos persistidos
- [ ] TT-02, Teste upsert: salvar mesma nota duas vezes não duplica dados
- [ ] TT-03, Teste remoção cascata: remover nota deleta todos registros associados
- [ ] TT-04, Teste normalização: "ARROZ TIO JOAO 5KG" → ("Arroz", "Tio João")
- [ ] TT-05, Teste consolidação: merge de produtos migra itens e aliases corretamente
- [ ] TT-06, Teste queries analíticas: KPIs, custos unitários, top produtos retornam dados consistentes

## Ordem Sugerida

1. T-01 (schema) — base para tudo
2. T-02 (CRUD) + T-03 (normalização) + T-04 (resolução) — fluxo de importação
3. T-05 (classificação) — registro de classificação
4. T-07 (queries) + T-08 (estabelecimentos) + T-09 (datas) — analytics
5. T-06 (consolidação) — merge de produtos

## Lacunas Pendentes (🔴)

- 🔴 database/__init__.py tem 2.501 LOC — considerar dividir em módulos menores (schema.py, crud.py, normalization.py, queries.py, consolidation.py)
