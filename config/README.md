# Configurações de LLM

Este diretório contém os arquivos de configuração para os modelos de LLM do projeto.

## Arquivos

- `modelos_llm.toml`: Configuração centralizada dos modelos disponíveis (Gemini, LLaMA, Kimi, GPT-4o)

## Como adicionar um novo modelo

1. Abra `modelos_llm.toml`
2. Adicione um novo bloco `[[modelos]]` com a configuração:

```toml
[[modelos]]
nome = "seu/modelo-id"
nome_amigavel = "Nome Amigável para UI"
api_key_env = "SUA_API_KEY_ENV"
max_tokens = 4096
max_itens = 30
timeout = 30.0
# Opcional: adicionar extra_body se o modelo exigir parâmetros específicos
[modelos.extra_body]
custom_param = "value"
```

3. Certifique-se de que a variável de ambiente está configurada no `.env`

## Segurança

As chaves de API **nunca** devem estar no arquivo TOML. Em vez disso, referencie o nome da variável de ambiente que será carregada do `.env` em tempo de execução.
