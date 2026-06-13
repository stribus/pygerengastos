# Classifiers

## Visão Geral

Pipeline de classificação automática de itens de notas fiscais em categorias de orçamento doméstico. Opera em dois estágios: (1) cache semântico via ChromaDB/sentence-transformers, (2) fallback para LLM via LiteLLM com múltiplos provedores.

## Responsabilidades

- Classificar itens pendentes de notas fiscais usando cache semântico (ChromaDB)
- Fallback para LLM (LiteLLM) quando cache não encontra match com score suficiente
- Gerenciar embeddings de descrições de produtos no ChromaDB
- Registrar classificações no banco de dados (histórico + atualização do item)
- Manter cache offline-first do modelo de embeddings

## Regras de Negócio

- Classificação híbrida: primeiro tenta cache semântico (ChromaDB), fallback para LLM 🟢
- Match semântico só é aceito se score >= 0.82 E categoria não for vazia 🟢
- Fallback automático entre modelos LLM segue ordem de prioridade do TOML 🟢
- Se TOML falhar, fallback hardcoded para Gemini 2.5 Flash Lite 🟢
- Modelo de embeddings: all-MiniLM-L6-v2 com cache local offline-first 🟢
- Toda classificação confirmada gera/atualiza embedding no ChromaDB 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Classificar itens pendentes usando pipeline híbrido (cache → LLM) | Must | Itens sem classificação recebem categoria, confiança, origem e modelo |
| RF-02 | Buscar produtos semelhantes no ChromaDB por descrição | Must | Descrições similares retornam com score >= 0.82 |
| RF-03 | Fallback automático entre modelos LLM em ordem de prioridade | Must | Se modelo primário falha, tenta próximo da lista |
| RF-04 | Carregar modelo de embeddings offline-first | Must | Sistema não falha sem internet se cache local existir |
| RF-05 | Configurar modelos LLM via TOML (prioridade, timeout, max_itens) | Should | Alterar TOML reflete na ordem de fallback sem modificar código |
| RF-06 | Recarregar configuração de modelos em runtime | Should | recarregar_modelos() invalida cache e recarrega |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Performance | Timeout de 30s em chamadas LLM (padrão) | `llm_classifier.py:24-27` | 🟢 |
| Performance | Lotes de até 50 itens por chamada LLM | `llm_classifier.py:26` | 🟢 |
| Disponibilidade | Retry automático em falha de LLM (2 retries, padrão) | `llm_classifier.py:30-31` | 🟢 |
| Resiliência | Cache offline-first com double-checked locking | `embeddings.py:95-185` | 🟢 |
| Performance | Busca semântica como cache antes do LLM | `classifiers/__init__.py:153-189` | 🟢 |

## Critérios de Aceitação

```gherkin
Dado uma nota com itens pendentes de classificação
Quando classificar_itens_pendentes() é chamado
Então itens com match semântico >= 0.82 recebem categoria do cache
E itens sem match recebem categoria do LLM
E todos os itens têm categoria, confianca, origem e modelo preenchidos

Dado um item com descrição nova (sem match no cache)
Quando o LLM é chamado
Então a categoria retornada pelo LLM é registrada com origem "gemini-litellm" ou "nvidia-nim"

Dado que o modelo de embeddings não está em cache local
Quando inicializar_modelo_embeddings() é chamado
Então o modelo é baixado do HuggingFace Hub automaticamente

Dado que todos os modelos LLM configurados falham
Quando classificar_itens_pendentes() é chamado
Então exceção FalhaModeloError é levantada com detalhes de cada falha
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Classificação híbrida (cache → LLM) | Must | Caminho crítico, chamado em toda importação |
| Fallback entre modelos LLM | Must | Resiliência sem custo de downtime |
| Cache offline-first de embeddings | Must | Necessário para funcionamento sem internet |
| Configuração de modelos via TOML | Should | Importante mas fallback hardcoded existe |
| Recarregar modelos em runtime | Could | Raramente necessário, restart resolve |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `src/classifiers/__init__.py` | `classificar_itens_pendentes()` | 🟢 |
| `src/classifiers/llm_classifier.py` | `LLMClassifier.classificar_itens()` | 🟢 |
| `src/classifiers/embeddings.py` | `inicializar_modelo_embeddings()` | 🟢 |
| `src/classifiers/embeddings.py` | `buscar_produtos_semelhantes()` | 🟢 |
| `src/classifiers/embeddings.py` | `upsert_descricao_embedding()` | 🟢 |
| `config/modelos_llm.toml` | Configuração de modelos | 🟢 |
