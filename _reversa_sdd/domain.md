# Domain — Gerenciador de despesa

> Gerado pelo Detective em 2026-06-06

---

## Glossário

| Termo | Definição |
|-------|-----------|
| **NFC-e** | Nota Fiscal do Consumidor Eletrônica — documento fiscal digital do RS |
| **Chave de acesso** | Identificador único de 44 dígitos numéricos de uma NFC-e |
| **Item** | Linha individual de produto em uma nota fiscal (descrição, qtd, valor) |
| **Classificação híbrida** | Pipeline de 2 estágios: cache semântico (ChromaDB) → fallback LLM |
| **Cache semântico** | ChromaDB com embeddings de descrições já classificadas |
| **Produto normalizado** | Produto com nome_base + marca_base extraídos via pipeline de normalização |
| **Alias de produto** | Mapeamento texto_original da NFC-e → produto_id (aprendizado contínuo) |
| **Produto regular** | Produto comprado em ≥2 meses consecutivos (para relatórios) |
| **Cesta básica personalizada** | Conjunto de produtos regulares usado para calcular inflação personalizada |
| **Inflação acumulada composta** | `(1+inf_ant/100)*(1+var_atual/100)-1` — série temporal de preços |
| **Forward fill** | Preenchimento de meses sem compra com o último preço conhecido |
| **SEFAZ-RS** | Secretaria da Fazenda do Rio Grande do Sul — portal de NFC-e |
| **LiteLLM** | Biblioteca de abstração para chamadas a múltiplos provedores LLM |
| **Embedding** | Vetor numérico (384 dim, `all-MiniLM-L6-v2`) que representa semanticamente uma descrição |
| **Spec-Driven Development** | Metodologia SDD: especificação → implementação → teste |

---

## Regras de Domínio

### Validação e Entrada

| # | Regra | Severidade | Fonte |
|---|-------|------------|-------|
| R01 | Chave de acesso NFC-e deve ter exatamente 44 dígitos numéricos | Bloqueante | `receita_rs.py:97` |
| R02 | Uma nota fiscal é identificada unicamente pela chave de acesso | Bloqueante | Schema SQL |
| R03 | Se chave extraída do HTML divergir da chave solicitada, a importação é rejeitada com erro | Bloqueante | `receita_rs.py:251` |
| R04 | CNPJ é normalizado para 14 dígitos; se não totalizar 14, é ignorado | Informativa | `database/__init__.py:1969` |

### Classificação

| # | Regra | Severidade | Fonte |
|---|-------|------------|-------|
| R05 | Classificação é em 2 estágios: cache semântico (ChromaDB) → LLM (fallback) | Arquitetural | `classifiers/__init__.py:30` |
| R06 | Match semântico só é aceito se score ≥ 0.82 E categoria não for vazia | Paramétrica | `database/__init__.py:467` |
| R07 | Se categoria não existir no banco, é criada automaticamente no grupo "Livres" | Comportamental | `database/__init__.py:2069` |
| R08 | Fallback entre modelos LLM segue ordem de prioridade do TOML | Arquitetural | `llm_classifier.py:396` |
| R09 | Se TOML falhar, fallback hardcoded para Gemini 2.5 Flash Lite | Resiliência | `llm_classifier.py:48` |
| R10 | Toda classificação é registrada em `classificacoes_historico` (auditoria) | Obrigatória | `database/__init__.py:1389` |

### Produtos

| # | Regra | Severidade | Fonte |
|---|-------|------------|-------|
| R11 | Produto é único por par (nome_base, marca_base) | Estrutural | Schema UNIQUE |
| R12 | Produto é resolvido por: alias exato → normalização → criação | Prioridade | `database/__init__.py:1702` |
| R13 | Ao consolidar, produto destino é o com mais itens vinculados | Comportamental | `database/__init__.py:2705` |
| R14 | Se nome_final da consolidação conflitar, gera sufixo numérico | Resiliência | `database/__init__.py:2741` |
| R15 | Alias de terceiros não são migrados durante consolidação | Segurança | `database/__init__.py:2778` |
| R16 | Ao remover nota, cascata: hist_class → revisoes → itens → pagamentos → nota | Integridade | `database/__init__.py:697` |

### Relatórios

| # | Regra | Severidade | Fonte |
|---|-------|------------|-------|
| R17 | Produto regular: comprado em ≥2 meses consecutivos | Paramétrica | `relatorios.py:108` |
| R18 | Cesta básica: apenas produtos regulares, sem ponderação por quantidade | Limitação | `relatorios.py:167` |
| R19 | Inflação acumulada: composta `(1+inf_ant)*(1+var_atual)-1` | Paramétrica | `relatorios.py:96` |
| R20 | Meses sem compra: forward fill com último preço conhecido | Comportamental | `relatorios.py:69` |
| R21 | Top-N para relatórios: 10 produtos mais comprados | Paramétrica | `relatorios.py:215` |
| R22 | Período padrão de análise: últimos 12 meses | Paramétrica | `relatorios.py:191` |

### Estabelecimentos

| # | Regra | Severidade | Fonte |
|---|-------|------------|-------|
| R23 | Estabelecimento é único por CNPJ normalizado | Estrutural | Schema UNIQUE |
| R24 | Consolidação de estabelecimento é incremental (nunca sobrescreve) | Comportamental | `database/__init__.py:2028` |
| R25 | Se nota já existe, oferece 3 opções: reprocessar, cancelar, ver | UX | `importacao.py:216` |

### Embeddings

| # | Regra | Severidade | Fonte |
|---|-------|------------|-------|
| R26 | Modelo de embedding: `all-MiniLM-L6-v2` (384 dimensões) | Paramétrica | `embeddings.py:20` |
| R27 | Cache de embeddings é offline-first: carrega do cache local, fallback download | Arquitetural | `embeddings.py:95` |
| R28 | Double-checked locking para thread-safety no carregamento de embeddings | Técnica | `embeddings.py:130` |
| R29 | Toda classificação confirmada (automática ou manual) gera/atualiza embedding | Comportamental | `embeddings.py:305` |

### Marcas Conhecidas

| Marca | Variações |
|-------|-----------|
| Tio João | TIO JOAO |
| Sadia | SADIA |
| Nestlé | NESTLE |
| Ambev | AMBEV |
| Piracanjuba | PIRAC |
| Perdigão | PERDIGAO |
| Coca-Cola | COCA, COCA-COLA |
| Aurora | AURORA |
| ... total: 22 marcas mapeadas | `database/__init__.py:433` |
