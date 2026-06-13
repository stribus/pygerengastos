# Dependências — Gerenciador de despesa

> Gerado pelo Scout em 2026-06-06

## Gerenciador de Pacotes

**uv** — gerenciador de pacotes Python. Dependências declaradas em `pyproject.toml` e compiladas em `requirements.txt`.

## Dependências Principais

| Dependência | Versão | Finalidade |
|-------------|--------|------------|
| Python | >=3.13 | Runtime |
| streamlit | 1.54.0 | Framework de UI web |
| litellm | 1.86.2 | Orquestração de LLMs (Gemini, NVIDIA NIM, OpenAI) |
| chromadb | 1.5.7 | Banco vetorial para embeddings semânticos |
| sentence-transformers | 5.4.0 | Modelo de embeddings |
| pandas | 2.3.3 | Manipulação de dados |
| beautifulsoup4 | 4.14.3 | Parsing de HTML NFC-e |
| httpx | 0.28.1 | Cliente HTTP para scraping |
| rapidfuzz | 3.14.5 | Similaridade fuzzy de strings |
| aiohttp | 3.13.5 | Cliente HTTP assíncrono |
| openai | 2.30.0 | SDK OpenAI (usado via LiteLLM) |
| python-dotenv | 1.2.2 | Carregamento de variáveis de ambiente |
| orjson | 3.11.8 | JSON otimizado |
| requests | 2.33.1 | Cliente HTTP (fallback) |
| pygments | 2.20.0 | Syntax highlighting |
| scikit-learn | 1.8.0 | ML auxiliar |
| torch | 2.11.0 | Framework de deep learning |
| transformers | 5.0.0rc3 | Modelos HuggingFace |
| tornado | 6.5.5 | Servidor ASGI (usado pelo Streamlit) |

## Dependências de Desenvolvimento

| Dependência | Versão  | Finalidade                        |
|-------------|---------|-----------------------------------|
| pytest      | >=9.0.3 | Testes unitários e de integração  |

## Modelos de LLM Configurados

| Modelo | Provedor | API Key |
|--------|----------|---------|
| gemini/gemini-2.5-flash-lite | Google Gemini | GEMINI_API_KEY |
| nvidia_nim/deepseek-ai/deepseek-v4-pro | NVIDIA NIM | NVIDIA_API_KEY |
| nvidia_nim/deepseek-ai/deepseek-v4-flash | NVIDIA NIM | NVIDIA_API_KEY |
| nvidia_nim/moonshotai/kimi-k2.6 | NVIDIA NIM | NVIDIA_API_KEY |

A ordem de prioridade é definida em `config/modelos_llm.toml`. O sistema tenta o primeiro, e em caso de falha, tenta o próximo automaticamente.
