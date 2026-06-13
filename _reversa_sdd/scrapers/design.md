# Scrapers, Design Técnico

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `validar_chave_acesso` | `(chave: str) -> bool` | `bool` | Valida 44 dígitos numéricos |
| `baixar_html` | `(chave: str, client: httpx.Client \| None, destino_html: Path \| None) -> str` | `str` | HTML bruto do portal SEFAZ-RS |
| `parse_nfce_html` | `(html: str) -> NotaFiscal` | `NotaFiscal` | Parseia spans modernos ou tabelas legadas |
| `buscar_nota` | `(chave: str, client: httpx.Client \| None) -> NotaFiscal` | `NotaFiscal` | Orquestra download + parse |

### Estruturas de Dados

**NotaFiscal**
| Campo | Tipo | Origem |
|-------|------|--------|
| `chave_acesso` | `str` | Extraído do HTML (div#chave) |
| `emitente_nome` | `Optional[str]` | div.infResumo span ou td |
| `emitente_cnpj` | `Optional[str]` | div.infResumo span ou td |
| `emitente_endereco` | `Optional[str]` | div.infResumo span ou td |
| `numero` | `Optional[str]` | Rodapé do HTML |
| `serie` | `Optional[str]` | Rodapé do HTML |
| `emissao` | `Optional[str]` | Data ISO no HTML |
| `itens` | `List[NotaItem]` | Parse de linhas de item |
| `total_itens` | `Optional[int]` | Quantidade de itens |
| `valor_total` | `Optional[Decimal]` | Soma dos itens |
| `valor_pago` | `Optional[Decimal]` | Soma dos pagamentos |
| `pagamentos` | `List[Pagamento]` | Tabela de pagamentos |
| `tributos` | `Optional[Decimal]` | Total tributos |
| `consumidor_cpf` | `Optional[str]` | CPF do consumidor |
| `consumidor_nome` | `Optional[str]` | Nome do consumidor |

**NotaItem**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `descricao` | `str` | Nome do produto |
| `codigo` | `Optional[str]` | Código interno do produto |
| `quantidade` | `Decimal` | Quantidade adquirida |
| `unidade` | `str` | UN, KG, LT, etc |
| `valor_unitario` | `Decimal` | Preço unitário |
| `valor_total` | `Decimal` | Quantidade × valor unitário |

**Pagamento**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `forma` | `str` | Dinheiro, Cartão de Crédito, Pix |
| `valor` | `Decimal` | Valor pago na forma |

## Fluxo Principal

1. **Validar chave** — `validar_chave_acesso()` verifica 44 dígitos numéricos (`receita_rs.py:97-101`)
2. **Baixar HTML** — `baixar_html()` envia POST para portal SEFAZ-RS com payload `chaveDadosConsultaNFCE` (`receita_rs.py:120-165`)
3. **Normalizar charset** — Detecta ISO-8859-1 no meta tag, converte para UTF-8, insere meta charset forçado (`receita_rs.py:171-223`)
4. **Detectar layout** — Verifica presença de spans com classe `txtTit` vs tabelas `NFCDetalhe_Item` (`receita_rs.py:374-443`)
5. **Extrair estabelecimento** — Parse de div.infResumo para nome, CNPJ, endereço
6. **Extrair itens** — Por layout: spans modernos (`span.txtTit`, `span.txtValor`) ou tabelas legadas (`td.NFCDetalhe_Item`) (`receita_rs.py:300-450`)
7. **Extrair totais e tributos** — Linha de totalização no final da tabela de itens
8. **Extrair pagamentos** — Tabela de formas de pagamento (dinheiro, crédito, débito, pix) (`receita_rs.py:460-480`)
9. **Extrair consumidor** — CPF e nome do consumidor do rodapé (`receita_rs.py:481-500`)
10. **Persistir HTML raw** — Salva em `data/raw_nfce/{chave}.html` para depuração (`receita_rs.py:163-168`)
11. **Montar e retornar** `NotaFiscal` — Objeto com todos os dados extraídos

## Fluxos Alternativos

- **Chave inválida:** `ValueError` com mensagem descritiva
- **HTML corrompido:** Detecta U+FFFD (substitution character) pós-parse, levanta `ValueError` (`receita_rs.py:215-220`)
- **Charset ISO-8859-1:** Fallback automático de UTF-8 para latin-1 se caracteres inválidos forem detectados (`receita_rs.py:200-210`)
- **Layout não identificado:** Tenta spans modernos primeiro; se falhar na extração de itens, tenta tabelas legadas

## Dependências

- `httpx` — Cliente HTTP síncrono para chamadas ao portal SEFAZ-RS
- `BeautifulSoup4` — Parser de HTML com `html.parser` nativo
- `pathlib` — Persistência de HTML raw em disco

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Cliente HTTP pode ser injetado (ou cria default interno) | `receita_rs.py:120-130` | 🟢 |
| HTML raw persistido opcionalmente via `destino_html` | `receita_rs.py:163-168` | 🟢 |
| Charset normalizado no HTML baixado (força UTF-8 no meta) | `receita_rs.py:171-223` | 🟢 |
| Parsing todo síncrono (sem async/await) | `receita_rs.py` | 🟢 |

## Estado Interno

A unit `scrapers` é stateless. Não mantém estado entre chamadas. O único efeito colateral é a persistência opcional de HTML raw em disco.

## Observabilidade

- Logs com `logging` para erros de parse e charset
- Log de início/fim de `buscar_nota()` com duração

## Riscos e Lacunas

- 🔴 Portal SEFAZ-RS pode mudar o layout HTML, quebrando o parser — não há mecanismo de auto-detecção de versão
- 🟡 Tratamento de timeout/reconnect do portal não foi observado em detalhe
- 🟢 Consumidor (CPF/nome) pode estar ausente em notas de balcão — campo opcional na estrutura
