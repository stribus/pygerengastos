# Configurações de LLM

Este diretório contém os arquivos de configuração para os modelos de LLM do projeto.

## Arquivos

- `modelos_llm.toml`: Configuração centralizada dos modelos disponíveis (Gemini, LLaMA, Kimi, GPT-4o)

## Carregamento de Modelos

### Carregamento em Background

Os modelos são carregados **automaticamente em background** durante a inicialização do Streamlit, garantindo que a interface fique disponível rapidamente sem bloquear a UI.

**Características:**
- **Thread-safe**: Usa locks para garantir carregamento seguro em ambientes concorrentes
- **Cache em memória**: Uma vez carregados, os modelos ficam em cache até o próximo reload
- **Fallback automático**: Se o arquivo TOML estiver com erro ou ausente, usa configuração hardcoded do Gemini
- **Lazy loading**: Só carrega quando efetivamente necessário

### Recarregar Configurações

Você pode **recarregar as configurações sem reiniciar a aplicação**:

1. **Via UI**: Na página "Importar nota", clique no botão "🔄 Recarregar modelos" dentro de "⚙️ Configurações de LLM"
2. **Via código**: Chame `recarregar_modelos()` de `src.classifiers.llm_classifier`

```python
from src.classifiers.llm_classifier import recarregar_modelos

# Invalida cache e recarrega do TOML
modelos_atualizados = recarregar_modelos()
```

## Tratamento de Erros

O sistema é resiliente a erros de configuração:

### Sintaxe TOML malformada
Se o arquivo TOML tiver erro de sintaxe, o sistema:
1. Loga o erro com detalhes (arquivo `logs/app.log`)
2. Retorna configuração fallback (Gemini)
3. Continua funcionando sem interromper a aplicação

### Campos obrigatórios ausentes
Se um modelo não tiver `nome` ou `api_key_env`:
1. O modelo inválido é **pulado**
2. Outros modelos válidos são carregados normalmente
3. Se **nenhum** modelo for válido, usa fallback

### Arquivo inexistente
Se `config/modelos_llm.toml` não existir:
1. Loga erro
2. Usa configuração fallback (Gemini)

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

# Opcional: extra_body simples se o modelo exigir parâmetros específicos
[modelos.extra_body]
custom_param = "value"

# Opcional: extra_body aninhado (ex.: Kimi K2.5)
[modelos.extra_body.chat_template_kwargs]
thinking = false
```

3. Certifique-se de que a variável de ambiente está configurada no `.env`
4. **Recarregue as configurações** via UI ou código (não precisa reiniciar!)

## Segurança

As chaves de API **nunca** devem estar no arquivo TOML. Em vez disso, referencie o nome da variável de ambiente que será carregada do `.env` em tempo de execução.

## Testes

O sistema possui testes abrangentes em `tests/test_llm_config_loading.py`:
- Carregamento de TOML válido e inválido
- Tratamento de campos obrigatórios ausentes
- Carregamento concorrente thread-safe
- Cache e invalidação
- Timeout e exceções em background loading
- Fallback automático
