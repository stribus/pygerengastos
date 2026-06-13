# Classifiers, Contratos Externos

## LiteLLM (Gateway de LLMs)

**Tecnologia:** LiteLLM 1.86.2
**Interface:** `litellm.completion(model, messages, max_tokens, temperature, timeout, extra_body)`

### Provedores Consumidos

| Provedor | Modelo | Prioridade | Max Itens | Timeout | API Key Env |
|----------|--------|-----------|-----------|---------|-------------|
| Google Gemini | gemini/gemini-2.5-flash-lite | 1ª | 50 | 30s | `GEMINI_API_KEY` |
| NVIDIA NIM | nvidia_nim/deepseek-ai/deepseek-v4-pro | 2ª | 50 | 45s | `NVIDIA_API_KEY` |
| NVIDIA NIM | nvidia_nim/deepseek-v4-flash | 3ª | 20 | 45s | `NVIDIA_API_KEY` |
| NVIDIA NIM | nvidia_nim/kimi-k2.6 | 4ª | 25 | 45s | `NVIDIA_API_KEY` |
| NVIDIA NIM | nvidia_nim/step-3.7-flash | 5ª | 40 | 45s | `NVIDIA_API_KEY` |
| OpenAI | openai/gpt-4o | 6ª | 30 | 30s | `OPENAI_API_KEY` |

### Payload da Chamada

```json
{
  "model": "gemini/gemini-2.5-flash-lite",
  "messages": [
    {"role": "system", "content": "Você é um classificador de itens de supermercado..."},
    {"role": "user", "content": "Classifique os itens abaixo nas categorias disponíveis..."}
  ],
  "max_tokens": 8000,
  "temperature": 0.1
}
```

### Resposta Esperada (JSON)

```json
{
  "itens": [
    {
      "sequencia": 1,
      "categoria": "Laticínios e Frios",
      "confianca": 0.95,
      "justificativa": "Leite longa vida, categoria Laticínios",
      "produto_nome": "Leite Integral",
      "produto_marca": "Piracanjuba"
    }
  ]
}
```

## HuggingFace Hub

**Tecnologia:** HuggingFace Hub (download de modelo)
**Modelo:** `all-MiniLM-L6-v2` (sentence-transformers)
**Cache local:** `~/.cache/huggingface/` (offline-first)

## ChromaDB

**Tecnologia:** ChromaDB 1.5.7
**Coleção:** `produtos`
**Dimensão:** 384
**Função de distância:** cosine (padrão ChromaDB)
**Metadados por documento:**
- `descricao_original`: str — texto exato da NFC-e
- `nome_base`: str — nome normalizado
- `marca_base`: str — marca normalizada
- `categoria`: str — categoria validada
- `produto_id`: str — ID do produto (string para ChromaDB)
