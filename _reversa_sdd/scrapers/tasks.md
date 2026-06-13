# Scrapers, Tarefas de Implementação

## Pré-requisitos
- [ ] `httpx` e `beautifulsoup4` disponíveis no ambiente
- [ ] Pasta `data/raw_nfce/` criada (para persistência HTML)
- [ ] Acesso ao portal SEFAZ-RS disponível (sem bloqueio de rede)

## Tarefas

- [ ] T-01, Implementar validação de chave de acesso NFC-e (44 dígitos numéricos)
  - Origem no legado: `src/scrapers/receita_rs.py:97-101`
  - Critério de pronto: `validar_chave_acesso("35230312345678901234567890123456789012345678")` → True; `validar_chave_acesso("invalida")` → False
  - Confiança: 🟢

- [ ] T-02, Implementar download de HTML do portal SEFAZ-RS via POST
  - Origem no legado: `src/scrapers/receita_rs.py:120-165`
  - Critério de pronto: Enviar POST para URL da SEFAZ-RS com payload `chaveDadosConsultaNFCE` e receber HTML 200
  - Confiança: 🟢

- [ ] T-03, Implementar normalização de charset ISO-8859-1 → UTF-8
  - Origem no legado: `src/scrapers/receita_rs.py:171-223`
  - Critério de pronto: HTML com acentos latinos convertido corretamente para UTF-8; caracteres U+FFFD detectados como erro
  - Confiança: 🟢

- [ ] T-04, Implementar parser de layout moderno (spans)
  - Origem no legado: `src/scrapers/receita_rs.py:300-450`
  - Critério de pronto: Extrair descricao, codigo, quantidade, unidade, valor_unitario, valor_total de `span.txtTit` e `span.txtValor`
  - Confiança: 🟢

- [ ] T-05, Implementar parser de layout legado (tabelas)
  - Origem no legado: `src/scrapers/receita_rs.py:451-500`
  - Critério de pronto: Extrair mesmos campos de `td.NFCDetalhe_Item`; resultado idêntico ao layout moderno para mesma nota
  - Confiança: 🟢

- [ ] T-06, Implementar extração de estabelecimento (nome, CNPJ, endereço)
  - Origem no legado: `src/scrapers/receita_rs.py:330-370`
  - Critério de pronto: Dados do emitente extraídos de `div.infResumo`
  - Confiança: 🟢

- [ ] T-07, Implementar extração de totais, tributos e pagamentos
  - Origem no legado: `src/scrapers/receita_rs.py:460-480`
  - Critério de pronto: Valor total, tributos e lista de `Pagamento` (forma + valor) extraídos corretamente
  - Confiança: 🟢

- [ ] T-08, Implementar extração de consumidor (CPF, nome)
  - Origem no legado: `src/scrapers/receita_rs.py:481-500`
  - Critério de pronto: CPF e nome do consumidor extraídos do rodapé da nota; aceitar ausência (notas de balcão)
  - Confiança: 🟢

- [ ] T-09, Implementar função orquestradora `buscar_nota()`
  - Origem no legado: `src/scrapers/receita_rs.py:500-530`
  - Critério de pronto: Dada chave válida, baixar HTML, parsear e retornar `NotaFiscal` completa
  - Confiança: 🟢

- [ ] T-10, Implementar persistência opcional de HTML raw em disco
  - Origem no legado: `src/scrapers/receita_rs.py:163-168`
  - Critério de pronto: Arquivo salvo em `data/raw_nfce/{chave}.html` quando `destino_html` é fornecido
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Teste do happy path: chave válida → download → parse → NotaFiscal com itens, pagamentos
- [ ] TT-02, Teste de chave inválida: `ValueError` esperado
- [ ] TT-03, Teste de HTML corrompido: `ValueError` por U+FFFD detectado
- [ ] TT-04, Teste de ambos os layouts (spans modernos e tabelas legadas) com fixtures HTML
- [ ] TT-05, Teste de charset ISO-8859-1 com caracteres acentuados

## Ordem Sugerida

1. T-01 (validação) primeiro, pois é pré-condição de tudo
2. T-02 (download) e T-03 (charset) em sequência
3. T-04 a T-08 (extrações) podem ser paralelas após parser HTML funcional
4. T-09 (orquestradora) depois que parsers individuais estão prontos
5. T-10 (persistência) por último
6. Testes após toda a unit implementada

## Lacunas Pendentes (🔴)

- Nenhuma lacuna identificada — todos os comportamentos são confirmados no código legado
