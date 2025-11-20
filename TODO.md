# TODO — Sistema de Gerenciamento de Gastos Mensais

## Objetivo geral

- Construir o sistema completo de importação, classificação (usando Groq) e visualização das notas fiscais.
- Garantir que os dados fiquem armazenados em DuckDB e que a interface Streamlit permita monitoramento dos gastos mensais.

## Status atual

- ✅ Scraper da SEFAZ-RS usa POST no endpoint `SAT-WEB-NFE-NFC_2.asp`, simula cabeçalhos do navegador e salva o HTML bruto para depuração.
- ✅ Testes automatizados (`tests/test_receita_rs.py`) cobrindo totais, pagamentos e itens a partir do HTML de exemplo.
- 🚧 Próximo foco imediato: classificação inteligente de itens e persistência em DuckDB.

## Etapas prioritárias

- [x] **Importação de notas**
   - [x] Criar interface/funções para inserir a chave de acesso (44 dígitos) e validar formato.
   - [x] Reimplementar a busca usando POST no endpoint `SAT-WEB-NFE-NFC_2.asp`, simulando os cabeçalhos do navegador e salvando o HTML em `data/raw_nfce`.
   - [x] Cobrir parsing com testes automatizados e fixture pública.
- [ ] **Classificação de itens**
   - [ ] Detectar itens inéditos e solicitar classificação à API da Groq com cache local.
   - [ ] Expor mecanismo de revisão manual para ajustes.
- [ ] **Armazenamento e análise**
   - [ ] Persistir notas, itens e classificações no DuckDB.
   - [ ] Padronizar schema com datas, estabelecimentos, categorias e totais por item.
- [ ] **Visualização**
   - [ ] Construir dashboards Streamlit com listagem, filtros e status de classificação.
   - [ ] Adicionar gráficos mensais e comparativos por categoria.
- [ ] **Infra e testes**
   - [x] Estruturar pastas (`src/`, `data/`, `tests/`).
   - [x] Criar fixtures e testes para o scraper.
   - [ ] Adicionar testes para classificação e consultas DuckDB.

## Observações futuras

- Adicionar cache e paginação para listas grandes de notas.
- Permitir reclassificação manual por usuário em caso de erro da IA.
- Explorar alertas/limites mensais para manter orçamento controlado.
