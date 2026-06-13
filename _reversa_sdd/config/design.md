# Config, Design Técnico

## Interface

### Arquivo de Configuração

| Arquivo | Formato | Propósito |
|---------|---------|-----------|
| `config/modelos_llm.toml` | TOML | Declaração de modelos LLM com parâmetros |
| `.env.example` | Dotenv | Template de variáveis de ambiente para API keys |

### Estrutura do TOML

```toml
[[modelos]]
nome = "provedor/nome-do-modelo"      # ID LiteLLM
nome_amigavel = "Nome Exibido"        # Label na UI
api_key_env = "ENV_VAR_NAME"          # Variável de ambiente com API key
max_tokens = 8000                      # Limite de tokens de saída
max_itens = 50                         # Máximo de itens por chamada batch
timeout = 30.0                         # Timeout em segundos

[modelos.extra_body]                   # (Opcional) Configurações específicas do provedor
# Ex: chat_template_kwargs.thinking = false
```

### Parâmetros por Modelo

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `nome` | `str` | ✅ | Identificador LiteLLM (`provedor/modelo`) |
| `nome_amigavel` | `str` | ✅ | Nome exibido na interface |
| `api_key_env` | `str` | ✅ | Nome da variável de ambiente com API key |
| `max_tokens` | `int` | ✅ | Limite de tokens de saída da resposta |
| `max_itens` | `int` | ✅ | Limite de itens enviados por chamada batch |
| `timeout` | `float` | ✅ | Timeout da chamada em segundos |
| `extra_body` | `dict` | ❌ | Parâmetros extras específicos do provedor |

### Modelos Configurados (Produção)

| Modelo | Provedor | max_tokens | max_itens | timeout |
|--------|----------|------------|-----------|---------|
| `gemini/gemini-2.5-flash-lite` | Google | 8000 | 50 | 30.0 |
| `nvidia_nim/deepseek-ai/deepseek-v4-pro` | NVIDIA | 16384 | 50 | 45.0 |
| `nvidia_nim/deepseek-ai/deepseek-v4-flash` | NVIDIA | 16384 | 20 | 45.0 |
| `nvidia_nim/moonshotai/kimi-k2.6` | NVIDIA | 8192 | 25 | 45.0 |
| `nvidia_nim/stepfun-ai/step-3.7-flash` | NVIDIA | 16384 | 40 | 45.0 |
| `openai/gpt-4o` | OpenAI | 4096 | 30 | 30.0 |

### Variáveis de Ambiente

| Variável | Provedor | Exemplo |
|----------|----------|---------|
| `GEMINI_API_KEY` | Google Gemini | Chave obtida em aistudio.google.com |
| `NVIDIA_API_KEY` | NVIDIA NIM | Chave obtida em build.nvidia.com |
| `OPENAI_API_KEY` | OpenAI | Chave obtida em platform.openai.com |
| `LITELLM_LOG` | LiteLLM | `DEBUG` (opcional) |
| `LLM_NUM_RETRIES` | LiteLLM | `2` (opcional) |

## Fluxo de Carregamento

1. `carregar_modelos_do_toml()` tenta ler `config/modelos_llm.toml` (`llm_classifier.py:48-65`)
2. Para cada `[[modelos]]`, verifica se `os.environ[api_key_env]` está definida
3. Se a env var não existe → log warning, pula o modelo
4. Modelos que passam na validação são instanciados como `ModeloConfig`
5. Ordem no TOML → ordem de prioridade no array de retorno
6. **Fallback:** se o TOML não existir ou array retornado estiver vazio, usa Gemini hardcoded:
   - `gemini-2.0-flash`, 8192 tokens, 50 itens, 30s timeout, `GEMINI_API_KEY`

## Estados de Erro

| Cenário | Comportamento |
|---------|---------------|
| TOML não encontrado | Fallback para Gemini hardcoded |
| TOML com sintaxe inválida | Fallback para Gemini hardcoded |
| API key não definida | Modelo ignorado com log warning |
| Nenhum modelo disponível | `ValueError` levantado |

## Dependências

- `tomllib` (Python 3.11+) — Parser de TOML
- `os.environ` — Leitura de variáveis de ambiente
- Não depende de nenhum módulo interno do projeto

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| TOML como formato de configuração (não JSON/YAML) | `config/modelos_llm.toml` | 🟢 |
| Ordem no array define prioridade (não campo numérico) | Comentário linha 2 do TOML | 🟢 |
| API keys por env var (nunca plain text) | Campo `api_key_env` em vez de `api_key` | 🟢 |
| Fallback Gemini hardcoded para zero-config | `llm_classifier.py:48-65` | 🟢 |
| `extra_body` para parâmetros específicos do provedor | `modelos.extra_body.chat_template_kwargs` | 🟢 |

## Estado Interno

O módulo de configuração é stateless. Os dados do TOML são lidos uma vez por sessão e mantidos como lista de `ModeloConfig` pelo módulo `classifiers`.

## Observabilidade

- `logging.warning` quando TOML não é encontrado ou modelo ignorado
- `logging.info` com contagem de modelos carregados com sucesso

## Riscos e Lacunas

- 🟢 Comentários no TOML preservam contexto e instruções
- 🟢 Modelos comentados (LLaMA 3) servem como template para novos provedores
- 🟡 Timeout de 30s para Gemini pode ser baixo para lotes grandes — ajustável por usuário