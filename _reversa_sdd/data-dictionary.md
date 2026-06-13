# Dicionário de Dados — Gerenciador de despesa

> Gerado pelo Archaeologist em 2026-06-06

## Banco de Dados: SQLite3 (`data/gastos.db`)

---

### 1. `categorias`

Categorias de orçamento doméstico para classificação de itens.

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| id | INTEGER | Sim | AUTOINCREMENT | Chave primária |
| grupo | TEXT | Sim | — | Grupo da categoria (ex: Alimentação, Limpeza) |
| nome | TEXT | Sim | — | Nome da categoria (ex: Laticínios e Frios) |
| ativo | BOOLEAN | Não | TRUE | Se a categoria está ativa |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data de criação |
| atualizado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da última atualização |

**Constraints:** UNIQUE(grupo, nome)

---

### 2. `estabelecimentos`

Estabelecimentos comerciais extraídos das notas fiscais.

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| id | INTEGER | Sim | AUTOINCREMENT | Chave primária |
| nome | TEXT | Não | — | Nome comercial |
| cnpj | TEXT | Não | — | CNPJ formatado (XX.XXX.XXX/XXXX-XX) |
| cnpj_normalizado | TEXT | Não | — | CNPJ apenas dígitos (14 caracteres) |
| endereco | TEXT | Não | — | Endereço completo |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data de criação |
| atualizado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da última atualização |

**Constraints:** UNIQUE(cnpj_normalizado)

---

### 3. `datas_referencia`

Dimensão de data para análises temporais (star schema).

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| data_iso | DATE | Sim | — | Chave primária (YYYY-MM-DD) |
| ano | SMALLINT | Sim | — | Ano (ex: 2024) |
| mes | SMALLINT | Sim | — | Mês (1-12) |
| dia | SMALLINT | Sim | — | Dia (1-31) |
| ano_mes | TEXT | Sim | — | Ano-mês (YYYY-MM) |
| trimestre | SMALLINT | Sim | — | Trimestre (1-4) |
| semana | SMALLINT | Sim | — | Semana do ano (ISO) |
| nome_mes | TEXT | Sim | — | Nome do mês em português |
| nome_dia_semana | TEXT | Sim | — | Nome do dia da semana em português |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data de criação |

---

### 4. `notas`

Notas fiscais eletrônicas (NFC-e) importadas.

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| chave_acesso | VARCHAR | Sim | — | Chave de acesso de 44 dígitos (PK) |
| emitente_nome | TEXT | Não | — | Nome do emitente/estabelecimento |
| emitente_cnpj | TEXT | Não | — | CNPJ do emitente |
| emitente_endereco | TEXT | Não | — | Endereço do emitente |
| numero | VARCHAR | Não | — | Número da nota fiscal |
| serie | VARCHAR | Não | — | Série da nota |
| emissao_texto | TEXT | Não | — | Data de emissão em texto original |
| emissao_iso | TEXT | Não | — | Data de emissão em ISO 8601 |
| emissao_data | DATE | Não | — | Data de emissão (YYYY-MM-DD) |
| estabelecimento_id | INTEGER | Não | — | FK → estabelecimentos.id |
| total_itens | INTEGER | Não | — | Quantidade total de itens |
| valor_total | DECIMAL(18,2) | Não | — | Valor total da nota |
| valor_pago | DECIMAL(18,2) | Não | — | Valor efetivamente pago |
| tributos | DECIMAL(18,2) | Não | — | Valor estimado de tributos |
| consumidor_cpf | TEXT | Não | — | CPF do consumidor |
| consumidor_nome | TEXT | Não | — | Nome do consumidor |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data de criação |
| atualizado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da última atualização |

---

### 5. `produtos`

Produtos padronizados (nome_base + marca_base únicos).

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| id | INTEGER | Sim | AUTOINCREMENT | Chave primária |
| nome_base | TEXT | Sim | — | Nome base padronizado (ex: "Arroz Tipo 1") |
| marca_base | TEXT | Não | — | Marca padronizada (ex: "Tio João") |
| categoria_id | INTEGER | Não | — | FK → categorias.id |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data de criação |
| atualizado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da última atualização |

**Constraints:** UNIQUE(nome_base, marca_base)

---

### 6. `aliases_produtos`

Mapeamento de texto original da nota → produto padronizado (aprendizado contínuo).

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| id | INTEGER | Sim | AUTOINCREMENT | Chave primária |
| produto_id | INTEGER | Sim | — | FK → produtos.id |
| texto_original | TEXT | Sim | — | Descrição original da nota (ex: "CR LEITE PIRAC ZERO LAC 200G") |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data de criação |

**Constraints:** UNIQUE(texto_original)

---

### 7. `itens`

Itens individuais de cada nota fiscal.

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| chave_acesso | VARCHAR | Sim | — | FK → notas.chave_acesso (PK composta) |
| sequencia | INTEGER | Sim | — | Número de sequência do item (PK composta) |
| descricao | TEXT | Não | — | Descrição original do produto |
| codigo | VARCHAR | Não | — | Código do produto (fornecido pelo estabelecimento) |
| quantidade | DECIMAL(18,4) | Não | — | Quantidade comprada |
| unidade | VARCHAR | Não | — | Unidade de medida (UN, KG, L, etc.) |
| valor_unitario | DECIMAL(18,4) | Não | — | Valor unitário |
| valor_total | DECIMAL(18,4) | Não | — | Valor total do item |
| produto_id | INTEGER | Não | — | FK → produtos.id |
| produto_nome | TEXT | Não | — | Nome base do produto (cache desnormalizado) |
| produto_marca | TEXT | Não | — | Marca do produto (cache desnormalizado) |
| categoria_sugerida | TEXT | Não | — | Categoria sugerida pela IA |
| categoria_confirmada | TEXT | Não | — | Categoria confirmada pelo usuário |
| categoria_sugerida_id | INTEGER | Não | — | FK → categorias.id (sugerida) |
| categoria_confirmada_id | INTEGER | Não | — | FK → categorias.id (confirmada) |
| fonte_classificacao | TEXT | Não | — | Fonte: chroma-cache, gemini-litellm, nvidia-nim, revisao_manual |
| confianca_classificacao | DOUBLE | Não | — | Score de confiança (0.0 a 1.0) |
| atualizado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da última atualização |

**Constraints:** PRIMARY KEY(chave_acesso, sequencia)

---

### 8. `pagamentos`

Formas de pagamento de cada nota.

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| chave_acesso | VARCHAR | Sim | — | FK → notas.chave_acesso (PK composta) |
| forma | TEXT | Sim | — | Forma de pagamento (PK composta) |
| valor | DECIMAL(18,2) | Não | — | Valor pago nesta forma |

**Constraints:** PRIMARY KEY(chave_acesso, forma)

---

### 9. `classificacoes_historico`

Histórico completo de todas as classificações realizadas (LLM ou cache).

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| chave_acesso | VARCHAR | Sim | — | FK → notas.chave_acesso |
| sequencia | INTEGER | Sim | — | Sequência do item |
| categoria | TEXT | Sim | — | Categoria atribuída |
| confianca | DOUBLE | Não | — | Score de confiança |
| origem | TEXT | Não | — | Fonte (gemini-litellm, chroma-cache, revisao_manual, etc.) |
| modelo | TEXT | Não | — | Modelo usado (gemini/gemini-2.5-flash-lite, etc.) |
| observacoes | TEXT | Não | — | Justificativa ou observação |
| resposta_json | TEXT | Não | — | JSON completo da resposta do LLM |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da classificação |

---

### 10. `revisoes_manuais`

Registro de revisões manuais feitas pelo usuário na interface.

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| id | INTEGER | Sim | AUTOINCREMENT | Chave primária |
| chave_acesso | VARCHAR | Sim | — | FK → notas.chave_acesso |
| sequencia | INTEGER | Sim | — | Sequência do item revisado |
| categoria | TEXT | Não | — | Categoria ajustada |
| produto_nome | TEXT | Não | — | Nome do produto ajustado |
| produto_marca | TEXT | Não | — | Marca ajustada |
| usuario | TEXT | Não | — | Nome do revisor |
| observacoes | TEXT | Não | — | Observações da revisão |
| origem | TEXT | Não | — | Origem (revisao_manual) |
| confirmado | BOOLEAN | Não | FALSE | Se a revisão foi confirmada |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da revisão |

---

### 11. `consolidacoes_historico`

Histórico de operações de consolidação de produtos (merge).

| Coluna | Tipo | Obrigatório | Padrão | Descrição |
|--------|------|-------------|--------|-----------|
| id | INTEGER | Sim | AUTOINCREMENT | Chave primária |
| produto_id_origem | INTEGER | Sim | — | ID do produto removido |
| produto_id_destino | INTEGER | Sim | — | ID do produto mantido |
| nome_origem | TEXT | Não | — | Nome do produto removido |
| nome_destino | TEXT | Não | — | Nome do produto mantido |
| usuario | TEXT | Não | — | Usuário que consolidou |
| observacoes | TEXT | Não | — | Observações |
| itens_migrados | INTEGER | Não | 0 | Quantos itens foram migrados |
| aliases_migrados | INTEGER | Não | 0 | Quantos aliases foram migrados |
| embeddings_atualizados | INTEGER | Não | 0 | Quantos embeddings foram atualizados |
| criado_em | TIMESTAMP | Não | CURRENT_TIMESTAMP | Data da consolidação |

---

### 12. View: `vw_itens_padronizados`

View consolidada que junta itens + notas + datas_referencia + estabelecimentos.

| Coluna | Origem | Descrição |
|--------|--------|-----------|
| chave_acesso | itens | Chave da nota |
| sequencia | itens | Sequência do item |
| data_emissao | notas.emissao_data | Data de emissão |
| ano | datas_referencia | Ano |
| mes | datas_referencia | Mês |
| dia | datas_referencia | Dia |
| ano_mes | datas_referencia | Ano-mês |
| trimestre | datas_referencia | Trimestre |
| semana | datas_referencia | Semana ISO |
| nome_mes | datas_referencia | Nome do mês |
| nome_dia_semana | datas_referencia | Nome do dia |
| estabelecimento_id | notas | ID do estabelecimento |
| estabelecimento_nome | estabelecimentos | Nome |
| estabelecimento_cnpj | estabelecimentos | CNPJ |
| estabelecimento_endereco | estabelecimentos | Endereço |
| categoria_final | COALESCE | Confirmada ou sugerida |
| categoria_final_id | COALESCE | ID da categoria final |
| quantidade | itens | Quantidade |
| valor_unitario | itens | Valor unitário |
| valor_total | itens | Valor total |
| produto_id | itens | ID do produto |
| produto_nome | itens | Nome do produto |
| produto_marca | itens | Marca do produto |

---

## Armazenamento Vetorial: ChromaDB (`data/chroma/`)

**Collection:** `produtos`
**Modelo:** `all-MiniLM-L6-v2` (384 dimensões)
**Função:** Cache semântico para busca por similaridade de descrições de produtos

### Metadados por embedding

| Campo | Tipo | Descrição |
|-------|------|-----------|
| descricao_original | str | Texto original da nota fiscal |
| nome_base | str | Nome padronizado do produto |
| marca_base | str | Marca padronizada |
| categoria | str | Categoria validada |
| produto_id | str | ID do produto (string para compatibilidade ChromaDB) |

**ID do documento:** MD5 hash da descrição normalizada (upper case).

---

## Dataclasses Python

| Classe | Módulo | Campos | Uso |
|--------|--------|--------|-----|
| NotaFiscal | scrapers | 15 campos | Dados completos da NFC-e |
| NotaItem | scrapers | 6 campos | Item individual |
| Pagamento | scrapers | 2 campos | Forma de pagamento |
| ItemParaClassificacao | database | 12 campos | Item para classificação |
| Categoria | database | 4 campos | Categoria de gasto |
| ProdutoPadronizado | database | 5 campos | Produto normalizado |
| NotaParaRevisao | database | 6 campos | Nota para revisão UI |
| ItemNotaRevisao | database | 10 campos | Item na interface de revisão |
| ItemPadronizado | database | 13 campos | Item via view consolidada |
| RevisaoManual | database | 10 campos | Histórico de revisão |
| ClassificacaoResultado | classifiers | 10 campos | Resultado de classificação |
| ModeloConfig | classifiers | 7 campos | Configuração de modelo LLM |
| FalhaModelo | classifiers | 2 campos | Registro de falha de modelo |
| _RespostaLLM | classifiers | 4 campos | Resposta parseada do LLM |
| ErroInicializacaoEmbeddings | classifiers | — | Erro base de embeddings |
| ErroCacheEmbeddings | classifiers | — | Erro de cache |
| ErroDownloadEmbeddings | classifiers | — | Erro de download |
| RespostaLLMInvalidaError | classifiers | — | Erro de JSON inválido |
| FalhaModeloError | classifiers | — | Erro de falha de modelo |
