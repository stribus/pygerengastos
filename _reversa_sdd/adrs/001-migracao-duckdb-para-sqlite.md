# ADR-001: Migração de DuckDB para SQLite3

**Data:** 2024 (inferido do histórico Git)
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

O sistema originalmente usava DuckDB como banco de dados relacional. Durante o desenvolvimento, a integração com ChromaDB (que usa SQLite internamente) criou complexidade adicional por gerenciar dois motores de banco distintos.

## Decisão

Migrar todo o armazenamento relacional de DuckDB para SQLite3, mantendo um único motor de banco SQLite para dados estruturados e ChromaDB para dados vetoriais.

## Consequências

- Eliminação de dependência de DuckDB
- Banco de dados único em `data/gastos.db`
- Portabilidade: SQLite3 é zero-config e não requer servidor
- Perda de funcionalidades analíticas nativas do DuckDB (compensado por pandas)
- Testes refatorados para usar SQLite em vez de DuckDB
