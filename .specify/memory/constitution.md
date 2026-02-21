# Gerenciador de Despesas (pygerengastos) Constitution

<!-- Sync Impact Report
Version change: None → 1.0.0
List of modified principles:
- I. Automação de Ponta a Ponta (Added)
- II. Privacidade e Soberania de Dados (Added)
- III. Auditabilidade e Revisão Humana (Added)
- IV. Consistência Semântica (Added)
- V. Interoperabilidade e Extensibilidade (Added)
Added sections:
- Core Principles
- Restrições Técnicas e Stack
- Fluxo de Desenvolvimento e Qualidade
Removed sections: None
Templates requiring updates:
- ✅ .specify/templates/plan-template.md (In sync)
- ✅ .specify/templates/spec-template.md (In sync)
- ✅ .specify/templates/tasks-template.md (In sync)
Follow-up TODOs: None
-->

## Core Principles

### I. Automação de Ponta a Ponta (End-to-End Automation)
O sistema DEVE automatizar a captura (scraping) e a classificação (IA) de despesas para minimizar a entrada manual de dados. A intervenção humana deve focar na validação e não na entrada primária.

### II. Privacidade e Soberania de Dados (Privacy-First & Local Storage)
Todos os dados financeiros e sensíveis DEVEM ser armazenados localmente (SQLite3/ChromaDB). O uso de serviços de nuvem deve se limitar estritamente ao processamento de IA (via LiteLLM) sem persistência externa de dados brutos da nota fiscal.

### III. Auditabilidade e Revisão Humana (Human-in-the-Loop)
Toda classificação automatizada é tratada como uma sugestão (sugerida). O sistema DEVE permitir revisão manual, manter histórico de alterações e identificar claramente a origem da classificação (IA vs. Humano) através de colunas de metadados.

### IV. Consistência Semântica (Semantic Consistency)
O sistema DEVE utilizar embeddings (ChromaDB) para garantir que o mesmo produto físico seja identificado consistentemente em diferentes estabelecimentos, independentemente de pequenas variações na descrição textual da nota fiscal.

### V. Interoperabilidade e Extensibilidade
O sistema DEVE suportar múltiplos modelos de IA (via LiteLLM) e permitir a exportação de dados em formatos abertos (Excel/CSV) para garantir que o usuário não fique preso à aplicação.

## Restrições Técnicas e Stack

- **Linguagem**: Python 3.13+.
- **Interface**: Streamlit para dashboard e interação visual.
- **Persistência Relacional**: SQLite3 para transações e dados estruturados.
- **Persistência Vetorial**: ChromaDB para busca semântica e similaridade de produtos.
- **Classificação**: LiteLLM como camada de abstração para LLMs.

## Fluxo de Desenvolvimento e Qualidade

- **Testes**: Uso obrigatório de `pytest` para lógica de scraping, processamento de dados e integração com banco de dados.
- **Build**: Uso do script `build.ps1` para garantir que o ambiente de execução seja reproduzível em diferentes máquinas Windows.
- **Normalização**: CNPJ e descrições devem passar por processos de limpeza e normalização antes da persistência.

## Governance

A Constituição do Projeto prevalece sobre qualquer outra prática de desenvolvimento. Alterações nesta constituição requerem a atualização da versão seguindo SemVer e a geração de um novo Relatório de Impacto de Sincronização. Todas as revisões de código devem verificar conformidade com os princípios acima. Complexidade adicional no schema do banco deve ser justificada pela necessidade de análise ou integridade.

**Version**: 1.0.0 | **Ratified**: 2026-02-21 | **Last Amended**: 2026-02-21
