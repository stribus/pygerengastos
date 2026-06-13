# ERD Completo — Gerenciador de despesa

> Gerado pelo Architect em 2026-06-06
> Banco: SQLite3 (data/gastos.db)

## Diagrama de Entidades e Relacionamentos

```mermaid
erDiagram
    notas ||--o{ itens : "1:N (chave_acesso)"
    notas ||--o{ pagamentos : "1:N (chave_acesso)"
    notas }o--|| estabelecimentos : "N:1 (estabelecimento_id)"
    itens }o--|| produtos : "N:1 (produto_id)"
    produtos }o--|| categorias : "N:1 (categoria_id)"
    produtos ||--o{ aliases_produtos : "1:N (produto_id)"
    itens }o--|| categorias : "N:1 (categoria_sugerida_id)"
    itens }o--|| categorias : "N:1 (categoria_confirmada_id)"

    notas ||--o{ classificacoes_historico : "1:N (chave_acesso)"
    notas ||--o{ revisoes_manuais : "1:N (chave_acesso)"
    notas ||--o{ consolidacoes_historico : "1:N (referencia indireta)"

    datas_referencia ||--o{ notas : "1:N (emissao_data → data_iso)"

    categorias {
        int id PK
        text grupo "UK com nome"
        text nome "UK com grupo"
        boolean ativo "default TRUE"
    }

    estabelecimentos {
        int id PK
        text nome
        text cnpj "formatado XX.XXX.XXX/XXXX-XX"
        text cnpj_normalizado UK "14 dígitos"
        text endereco
    }

    datas_referencia {
        date data_iso PK "YYYY-MM-DD"
        smallint ano
        smallint mes "1-12"
        smallint dia "1-31"
        text ano_mes "YYYY-MM"
        smallint trimestre "1-4"
        smallint semana "ISO week"
        text nome_mes "pt-br"
        text nome_dia_semana "pt-br"
    }

    notas {
        varchar chave_acesso PK "44 dígitos"
        text emitente_nome
        text emitente_cnpj
        text emitente_endereco
        varchar numero
        varchar serie
        text emissao_iso
        date emissao_data FK "→ datas_referencia"
        int estabelecimento_id FK "→ estabelecimentos"
        int total_itens
        decimal valor_total "(18,2)"
        decimal valor_pago "(18,2)"
        decimal tributos "(18,2)"
        text consumidor_cpf
        text consumidor_nome
    }

    itens {
        varchar chave_acesso PK,FK "→ notas"
        int sequencia PK
        text descricao
        varchar codigo
        decimal quantidade "(18,4)"
        varchar unidade "UN, KG, L"
        decimal valor_unitario "(18,4)"
        decimal valor_total "(18,4)"
        int produto_id FK "→ produtos"
        text produto_nome "cache desnormalizado"
        text produto_marca "cache desnormalizado"
        text categoria_sugerida
        text categoria_confirmada
        int categoria_sugerida_id FK "→ categorias"
        int categoria_confirmada_id FK "→ categorias"
        text fonte_classificacao "chroma-cache | gemini-litellm | nvidia-nim | revisao_manual"
        double confianca_classificacao "0.0 a 1.0"
    }

    produtos {
        int id PK
        text nome_base UK "com marca_base"
        text marca_base UK "com nome_base"
        int categoria_id FK "→ categorias"
    }

    aliases_produtos {
        int id PK
        int produto_id FK "→ produtos"
        text texto_original UK "descrição exata da NFC-e"
    }

    pagamentos {
        varchar chave_acesso PK,FK "→ notas"
        text forma PK
        decimal valor "(18,2)"
    }

    classificacoes_historico {
        varchar chave_acesso FK "→ notas"
        int sequencia
        text categoria
        double confianca
        text origem
        text modelo
        text observacoes
        text resposta_json "JSON completo do LLM"
    }

    revisoes_manuais {
        int id PK
        varchar chave_acesso FK "→ notas"
        int sequencia
        text categoria
        text produto_nome
        text produto_marca
        text usuario "auto-informado"
        text observacoes
        text origem "revisao_manual"
        boolean confirmado "default FALSE"
    }

    consolidacoes_historico {
        int id PK
        int produto_id_origem "produto removido"
        int produto_id_destino "produto mantido"
        text nome_origem
        text nome_destino
        text usuario
        text observacoes
        int itens_migrados
        int aliases_migrados
        int embeddings_atualizados
    }
```

## Cardinalidades

| Tabela A | Relação | Tabela B | Descrição |
|----------|---------|----------|-----------|
| notas | 1 : N | itens | Uma nota tem vários itens |
| notas | 1 : N | pagamentos | Uma nota tem várias formas de pagamento |
| notas | N : 1 | estabelecimentos | Muitas notas pertencem a um estabelecimento |
| notas | N : 1 | datas_referencia | Muitas notas referenciam uma data |
| itens | N : 1 | produtos | Muitos itens referenciam um produto padronizado |
| itens | N : 1 | categorias | Muitos itens têm uma categoria sugerida |
| itens | N : 1 | categorias | Muitos itens têm uma categoria confirmada |
| produtos | N : 1 | categorias | Muitos produtos pertencem a uma categoria |
| produtos | 1 : N | aliases_produtos | Um produto tem vários aliases (descrições originais) |
| notas | 1 : N | classificacoes_historico | Uma nota tem várias classificações registradas |
| notas | 1 : N | revisoes_manuais | Uma nota pode ter várias revisões manuais |

## View

```sql
-- vw_itens_padronizados: junta itens + notas + datas_referencia + estabelecimentos
-- Colunas: chave_acesso, sequencia, data_emissao, ano, mes, dia, ano_mes,
--          trimestre, semana, nome_mes, nome_dia_semana,
--          estabelecimento_id, estabelecimento_nome, estabelecimento_cnpj,
--          estabelecimento_endereco, categoria_final (COALESCE),
--          categoria_final_id (COALESCE), quantidade, valor_unitario,
--          valor_total, produto_id, produto_nome, produto_marca
```

## Índices

| Tabela | Índice | Tipo | Colunas |
|--------|--------|------|---------|
| itens | idx_itens_produto_nome | B-tree | produto_nome |
| itens | idx_itens_chave_acesso | B-tree | chave_acesso |
| itens | idx_itens_categoria | B-tree | categoria_sugerida, categoria_confirmada |
| aliases_produtos | idx_aliases_texto_original | B-tree | texto_original |
| classificacoes_historico | idx_class_hist_chave | B-tree | chave_acesso |
