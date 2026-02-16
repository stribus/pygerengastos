# TODO — Sistema de Gerenciamento de Gastos Mensais

## Objetivo geral

- Construir o sistema completo de importação, classificação (usando LiteLLM + Gemini) e visualização das notas fiscais.
- Garantir que os dados fiquem armazenados em SQLite3 e que a interface Streamlit permita monitoramento dos gastos mensais.

## Status atual

- ✅ Scraper da SEFAZ-RS usa POST no endpoint `SAT-WEB-NFE-NFC_2.asp`, simula cabeçalhos do navegador e salva o HTML bruto para depuração.
- ✅ Testes automatizados (`tests/test_receita_rs.py`) cobrindo totais, pagamentos e itens a partir do HTML de exemplo.
- ✅ Fixture pública (`.github/xmlexemplo.xml`) garante previsibilidade dos testes.
- ✅ Persistência em SQLite3 com dimensões de datas/estabelecimentos e funções utilitárias para salvar/consultar.
- ✅ Tela de revisão manual em Streamlit com edição de categoria/produto, registro do revisor e histórico em SQLite3.
- ✅ Migração de DuckDB para SQLite3 para melhor suporte a UPDATE com foreign keys.
- ✅ Classificação semântica (Chroma) com fallback para LLM (LiteLLM/Gemini).
- ✅ Relatórios e gráficos interativos (custos unitários mensais, inflação acumulada, cesta básica personalizada).
- ✅ Configuração de modelos LLM externalizada em arquivo TOML (`config/modelos_llm.toml`) para fácil manutenção.


## Etapas prioritárias

- [x] **Importação de notas**
  - [x] Criar interface/funções para inserir a chave de acesso (44 dígitos) e validar formato.
  - [x] Reimplementar a busca usando POST no endpoint `SAT-WEB-NFE-NFC_2.asp`, simulando os cabeçalhos do navegador e salvando o HTML em `data/raw_nfce`.
  - [x] Cobrir parsing com testes automatizados e fixture pública.
- [x] **Classificação de itens**
  - [x] Detectar itens inéditos e solicitar classificação via LiteLLM/Gemini com cache local (`classificar_itens_pendentes`).
  - [x] Integrar busca semântica (Chroma) para evitar chamadas desnecessárias ao LLM.
  - [x] Documentar o fluxo semântico Chroma + LiteLLM no README.md.
  - [x] Identificar produto (nome base + marca) junto com a categoria para permitir agrupamentos.
  - [x] Expor mecanismo de revisão manual para ajustes (UI/backend ainda inexistentes — apenas flag `confirmar` via backend).
  - [x] Construir tela Streamlit para listar itens pendentes, permitir edição de categoria/produto e confirmar ajustes.
  - [x] Permitir reclassificação manual por usuário em caso de erro da IA.
  - [x] Criar endpoint/função de serviço que receba a decisão manual e reutilize `registrar_classificacao_itens(confirmar=True)`.
  - [x] Registrar histórico da revisão (usuario, timestamp) para auditoria.
  - [x] Externalizar configuração de modelos LLM em arquivo TOML para fácil manutenção.
  - [ ] Fine-tuning local com dados históricos
- [ ] **Armazenamento e análise**
  - [x] Criar tabelas de categorias/produtos/aliases e relacionar itens a um `produto_id`.
  - [x] Padronizar schema com datas, estabelecimentos, categorias e totais por item.
    - [x] Normalizar consultas de resumo (views ou tabelas materializadas) para suportar dashboards mensais.
    - [x] Listar itens da nota com categoria/produto sugeridos, destacando campos editáveis.
    - [x] Permitir ajustes manuais e enviar para `registrar_classificacao_itens(confirmar=True)`.
  - [x] Mostrar histórico de classificações e log de revisões por usuário.
  - [x] Construir dashboards Streamlit com listagem, filtros e status de classificação.
    - [x] Implementar filtros por período, emitente e categoria.
    - [x] Exibir tabela resumo com status da classificação e links para edição.
    - [x] Adicionar exportação CSV/Excel dos resultados filtrados.
  - [x] Adicionar gráficos mensais e comparativos por categoria.
    - [x] Criar gráfico de barras mensais (valor pago por mês) e tabela por categoria.
    - [x] Criar gráfico de linhas mostrando a "inflação"(%) dos valores unitários dos produtos, por produtos(selecionados), por categoria, e a média da inflação de todos os itens
    - [x] Permitir seleção dinâmica de intervalo temporal e categorias.
    - [ ] Destacar alertas quando gastos ultrapassarem limite configurado.
- [ ] **Infra e testes**
  - [x] Estruturar pastas (`src/`, `data/`, `tests`).
  - [x] Criar fixtures e testes para o scraper.
  - [x] Adicionar testes para classificação e consultas SQLite3.
  - [x] Cobrir busca semântica de embeddings com mock do Chroma.

## Observações futuras

- Adicionar alertas/limites mensais para manter orçamento controlado.
- Usar séries temporais e IA para prever gastos próximos meses.
- Fine-tuning local do modelo de classificação com dados históricos do usuário.
- Comparação com índices oficiais (IPCA, INPC) para análise de inflação pessoal vs. nacional.
- Integração com categorias personalizadas por usuário.
- Suporte a múltiplos usuários/famílias com dados segregados.
- Exportação de relatórios em PDF.
- Integração com aplicativos de banco/cartão para importação automática de transações.
