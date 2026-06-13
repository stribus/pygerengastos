# Config, Tarefas de Implementação

## Pré-requisitos
- [ ] Python 3.11+ (usa `tomllib` nativo)
- [ ] Arquivo `config/modelos_llm.toml` criado com pelo menos um modelo
- [ ] Variáveis de ambiente configuradas no `.env`

## Tarefas

- [ ] T-01, Criar esquema TOML para declaração de modelos LLM
  - Origem no legado: `config/modelos_llm.toml`
  - Critério de pronto: Arquivo TOML válido com tabela `[[modelos]]` contendo `nome`, `nome_amigavel`, `api_key_env`, `max_tokens`, `max_itens`, `timeout`
  - Confiança: 🟢

- [ ] T-02, Implementar carregamento de modelos do TOML com validação de env vars
  - Origem no legado: `src/classifiers/llm_classifier.py:48-65`
  - Critério de pronto: Função lê TOML, para cada modelo verifica `os.environ[api_key_env]`, retorna lista de `ModeloConfig` na ordem do TOML
  - Confiança: 🟢

- [ ] T-03, Implementar fallback para Gemini se TOML ausente ou inválido
  - Origem no legado: `src/classifiers/llm_classifier.py:48-65`
  - Critério de pronto: Se TOML não existir ou nenhum modelo carregado, retorna configuração hardcoded do Gemini
  - Confiança: 🟢

- [ ] T-04, Criar template `.env.example` com chaves de API
  - Origem no legado: `.env.example`
  - Critério de pronto: Arquivo contém `GEMINI_API_KEY=sua_chave_gemini_aqui`, `NVIDIA_API_KEY=sua_chave_nvidia_aqui`, `OPENAI_API_KEY=sua_chave_openai_aqui` com comentários
  - Confiança: 🟢

- [ ] T-05, Implementar suporte a `extra_body` para parâmetros específicos do provedor
  - Origem no legado: `config/modelos_llm.toml` (DeepSeek/Kimi com `chat_template_kwargs.thinking = false`)
  - Critério de pronto: `ModeloConfig.extra_body` populado quando `[modelos.extra_body]` existe; repassado ao LiteLLM
  - Confiança: 🟢

- [ ] T-06, Implementar tratamento de modelo ignorado por env var ausente
  - Origem no legado: `src/classifiers/llm_classifier.py:55-60`
  - Critério de pronto: Log warning com nome do modelo ignorado; continua para o próximo sem erro fatal
  - Confiança: 🟢

## Tarefas de Teste

- [ ] TT-01, Teste de carregamento com TOML válido e todas env vars definidas
- [ ] TT-02, Teste de modelo ignorado quando api_key_env não está no ambiente
- [ ] TT-03, Teste de fallback para Gemini quando TOML não existe
- [ ] TT-04, Teste de fallback quando TOML existe mas nenhum modelo tem API key definida
- [ ] TT-05, Teste de `extra_body` populado corretamente

## Ordem Sugerida

1. T-01 e T-04 (arquivos) → podem ser criados manualmente
2. T-02, T-03, T-05, T-06 (carregamento) → dependem do TOML existir
3. Testes após toda a implementação

## Lacunas Pendentes (🔴)

- Nenhuma lacuna identificada — configuração é direta e confirmada no código