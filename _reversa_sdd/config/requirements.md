# Config

## Visão Geral

Módulo de configuração do sistema que define modelos LLM disponíveis para classificação de itens de notas fiscais. Utiliza formato TOML para declarar provedores (Google Gemini, etc.) com suas respectivas chaves de API e limites de uso.

## Responsabilidades

- Declarar modelos LLM com parâmetros de uso (max_tokens, max_itens, timeout)
- Definir ordem de prioridade de modelos (primeiro no TOML = primeira tentativa)
- Referenciar chaves de API via variáveis de ambiente (nunca em plain text)
- Fornecer fallback hardcoded para Gemini caso o TOML não possa ser lido

## Regras de Negócio

- Ordem no TOML define prioridade de fallback entre modelos LLM 🟢
- API keys são lidas de variáveis de ambiente definidas no `.env` 🟢
- Fallback hardcoded para Gemini se TOML não puder ser lido (resiliência) 🟢
- Cada modelo define `max_itens` (limite de itens por chamada batch) 🟢

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-01 | Definir modelos LLM em `config/modelos_llm.toml` | Must | Arquivo TOML válido com tabela `[[modelos]]` |
| RF-02 | Ler API keys de variáveis de ambiente | Must | Não é possível usar o modelo sem a env var definida |
| RF-03 | Fornecer fallback para Gemini se TOML ausente | Should | Sistema funciona com modelo padrão `gemini-2.0-flash` |
| RF-04 | Definir parâmetros por modelo (max_tokens, max_itens, timeout) | Must | Cada entrada `[[modelos]]` tem todos os campos obrigatórios |

## Requisitos Não Funcionais

| Tipo | Requisito inferido | Evidência no código | Confiança |
|------|--------------------|---------------------|-----------|
| Segurança | API keys nunca em plain text, sempre via `api_key_env` | `config/modelos_llm.toml` e `.env.example` | 🟢 |
| Resiliência | Fallback hardcoded se `modelos_llm.toml` não existir | `src/classifiers/llm_classifier.py:48-65` | 🟢 |
| Configurabilidade | Usuário pode adicionar/remover modelos editando TOML | Layout declarativo do arquivo | 🟢 |

## Critérios de Aceitação

```gherkin
Dado que o arquivo `config/modelos_llm.toml` existe e é válido
Quando o sistema carrega os modelos
Então todos os modelos listados são carregados com suas configurações

Dado que o arquivo `config/modelos_llm.toml` não existe ou é inválido
Quando o sistema tenta carregar modelos
Então um fallback para Gemini (`gemini-2.0-flash`) com `GEMINI_API_KEY` é utilizado

Dado que uma variável de ambiente referenciada em `api_key_env` não está definida
Quando o sistema tenta carregar aquele modelo
Então o modelo é ignorado (log warning) e o próximo na prioridade é tentado
```

## Prioridade (MoSCoW)

| Requisito | MoSCoW | Justificativa |
|-----------|--------|---------------|
| Declaração de modelos (RF-01, RF-04) | Must | Sem modelos, sem classificação |
| API keys via env (RF-02) | Must | Requisito de segurança |
| Fallback Gemini (RF-03) | Should | Resiliência operacional |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `config/modelos_llm.toml` | Tabela `[[modelos]]` | 🟢 |
| `.env.example` | Variáveis de ambiente | 🟢 |
| `src/classifiers/llm_classifier.py:48-65` | `carregar_modelos_do_toml()` | 🟢 |
| `src/classifiers/llm_classifier.py:396-462` | `classificar_itens()` com fallback | 🟢 |