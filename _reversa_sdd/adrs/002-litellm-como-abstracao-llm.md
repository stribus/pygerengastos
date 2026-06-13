# ADR-002: LiteLLM como Abstração de Provedores LLM

**Data:** 2024 (inferido do histórico Git)
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

O sistema inicialmente integrava diretamente com a API Groq para classificação de itens. A necessidade de suportar múltiplos provedores (Gemini, NVIDIA NIM, OpenAI) e gerenciar fallbacks entre eles criou complexidade na integração direta.

## Decisão

Substituir chamadas diretas à API Groq pelo LiteLLM, uma biblioteca que abstrai chamadas a múltiplos provedores LLM com interface unificada.

## Consequências

- Suporte a múltiplos provedores: Google Gemini, NVIDIA NIM, OpenAI
- Fallback automático entre provedores em ordem de prioridade
- Interface unificada: `litellm.completion()` independente do provedor
- Código mais limpo e manutenível
- Dependência externa adicional (`litellm`)
