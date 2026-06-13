# Scrapers

## Visão Geral

Módulo de web scraping do portal da SEFAZ-RS para baixar e parsear Notas Fiscais do Consumidor Eletrônica (NFC-e). Suporta dois layouts de HTML (spans modernos e tabelas legadas) com fallback de charset.

## Responsabilidades

- Validar chave de acesso NFC-e (44 dígitos numéricos)
- Baixar HTML da nota fiscal do portal SEFAZ-RS via HTTP POST
- Persistir HTML bruto em disco para depuração
- Parsear HTML em estrutura `NotaFiscal` (estabelecimento, itens, pagamentos, tributos, consumidor)
- Suportar dois layouts de HTML (moderno e legado)
- Normalizar charset ISO-8859-1 → UTF-8

## Regras de Negócio

- Chave de acesso NFC-e deve ter exatamente 44 dígitos numéricos 🟢
- HTML da SEFAZ-RS é ISO-8859-1, convertido para UTF-8 com meta charset forçado 🟢
- Dois layouts de HTML suportados: spans modernos e tabelas legadas 🟢
- HTML bruto é persistido em data/raw_nfce/ para depuração 🟢
- Chave extraída do HTML deve corresponder à chave solicitada 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Validar chave de acesso NFC-e (44 dígitos) | Must | Chave "35230312345678901234567890123456789012345678" → True; "invalida" → False |
| RF-02 | Buscar nota fiscal por chave no portal SEFAZ-RS | Must | GET/POST para SEFAZ retorna HTML válido |
| RF-03 | Baixar HTML e persistir em data/raw_nfce/ | Should | HTML salvo com nome baseado na chave para depuração |
| RF-04 | Parsear HTML em estrutura NotaFiscal | Must | Extrair estabelecimento, itens, pagamentos, totais |
| RF-05 | Suportar layout moderno (spans) e legado (tabelas) | Must | Ambos os layouts produzem NotaFiscal idêntica |
| RF-06 | Normalizar charset ISO-8859-1 → UTF-8 | Must | Caracteres acentuados preservados; arquivos corrompidos detectados por U+FFFD |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Disponibilidade | Validação de chave antes de chamada HTTP | `receita_rs.py:97-101` | 🟢 |
| Resiliência | Fallback de charset latin-1 se UTF-8 falhar | `receita_rs.py:171-223` | 🟢 |
| Resiliência | Detecção de HTML corrompido via U+FFFD | `receita_rs.py:215-220` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado uma chave de acesso válida de 44 dígitos
Quando buscar_nota(chave) é chamado
Então o HTML é baixado da SEFAZ-RS
E parseado em NotaFiscal com estabelecimento, itens e pagamentos

Dado uma chave inválida (não numérica ou != 44 dígitos)
Quando buscar_nota(chave) é chamado
Então ValueError é levantado com mensagem "Chave deve ter exatamente 44 dígitos"

Dado um HTML no layout de tabelas legadas
Quando parse_nfce_html() é chamado
Então o resultado é idêntico ao layout de spans modernos
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Validação de chave | Must | Pré-condição para qualquer chamada HTTP |
| Busca e parse de NFC-e | Must | Caminho crítico da importação |
| Suporte a dois layouts | Must | Diferentes estabelecimentos usam layouts diferentes |
| Persistência de HTML raw | Could | Útil para depuração, não crítico |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/scrapers/receita_rs.py:97-101` | `validar_chave_acesso()` | 🟢 |
| `src/scrapers/receita_rs.py:120-165` | `baixar_html()` | 🟢 |
| `src/scrapers/receita_rs.py:170-260` | `parse_nfce_html()` | 🟢 |
| `src/scrapers/receita_rs.py:300-450` | Layout spans modernos | 🟢 |
| `src/scrapers/receita_rs.py:451-500` | Layout tabelas legadas | 🟢 |
| `src/scrapers/receita_rs.py:500-530` | `buscar_nota()` | 🟢 |
