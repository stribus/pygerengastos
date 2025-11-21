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
  - [x] Detectar itens inéditos e solicitar classificação à API da Groq com cache local (`classificar_itens_pendentes`).
  - [x] Documentar o fluxo semântico Chroma + Groq no README.md.
  - [x] Identificar produto (nome base + marca) junto com a categoria para permitir agrupamentos.
  - [ ] Expor mecanismo de revisão manual para ajustes (UI/backend ainda inexistentes — apenas flag `confirmar` via backend).
    - [ ] Construir tela Streamlit para listar itens pendentes, permitir edição de categoria/produto e confirmar ajustes.
    - [ ] Criar endpoint/função de serviço que receba a decisão manual e reutilize `registrar_classificacao_itens(confirmar=True)`.
    - [ ] Registrar histórico da revisão (usuario, timestamp) para auditoria.
- [ ] **Armazenamento e análise**
  - [x] Criar tabelas de categorias/produtos/aliases e relacionar itens a um `produto_id`.
  - [ ] Padronizar schema com datas, estabelecimentos, categorias e totais por item.
    - [ ] Normalizar consultas de resumo (views ou tabelas materializadas) para suportar dashboards mensais.
    - [ ] Adicionar constraints/defaults para garantir integridade de `emissao_iso` e `valor_total`.
  - [ ] Popular catálogo inicial de categorias a partir do CSV fornecido e permitir edição.
    - [ ] Invocar `seed_categorias_csv` no setup inicial e expor manutenção básica na UI.
- [ ] **Visualização**
  - [ ] criar interface ´home´ intuitiva e funcional
    - [ ] Definir layout responsivo com cabeçalho, KPIs resumidos e navegação entre seções.
    - [ ] Exibir total de notas importadas, gastos do mês atual e itens pendentes de revisão.
    - [ ] Adicionar cards com atalhos para importar nota e revisar itens.
  - [ ] criar tela de cadastro/importação de notas, que permitirá inserir a chave de acesso para importação e um botão de importar.
    - [x] Validar chave (44 dígitos) e apresentar mensagens de erro amigáveis.
    - [x] Exibir histórico recente de importações e status (sucesso/erro).
    - [x] Integrar ação do botão com `src.scrapers.receita_rs.buscar_nota` e `salvar_nota`, exibindo spinner de progresso.
  - [ ] criar tela para analise da nota importada, permitindo corrigir dados errados do produtos, como marca, categoria,classificação
    - [x] Listar itens da nota com categoria/produto sugeridos, destacando campos editáveis.
    - [x] Permitir ajustes manuais e enviar para `registrar_classificacao_itens(confirmar=True)`.
    - [ ] Mostrar histórico de classificações e log de revisões por usuário.
  - [ ] Construir dashboards Streamlit com listagem, filtros e status de classificação.
    - [ ] Implementar filtros por período, emitente e categoria.
    - [ ] Exibir tabela resumo com status da classificação e links para edição.
    - [ ] Adicionar exportação CSV/Excel dos resultados filtrados.
  - [ ] Adicionar gráficos mensais e comparativos por categoria.
    - [ ] Criar gráfico de barras mensais (valor pago por mês) e pizza por categoria.
    - [ ] criar grafico de Linhas mostrando a "inflação"(%) dos valores unidarios dos produtos, por produtos(selecionados), por categoria, e a media da inflação de todos os itens
    - [ ] Permitir seleção dinâmica de intervalo temporal e categorias.
    - [ ] Destacar alertas quando gastos ultrapassarem limite configurado.
- [ ] **Infra e testes**
  - [x] Estruturar pastas (`src/`, `data/`, `tests`).
  - [x] Criar fixtures e testes para o scraper.
  - [x] Adicionar testes para classificação e consultas DuckDB.
  - [x] Cobrir busca semântica de embeddings com mock do Chroma.

## Observações futuras

- Adicionar cache e paginação para listas grandes de notas.
- Permitir reclassificação manual por usuário em caso de erro da IA.
- Explorar alertas/limites mensais para manter orçamento controlado.
