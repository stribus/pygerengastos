# ADR-004: Configuração de Modelos LLM em Arquivo TOML

**Data:** 2025-2026
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

Inicialmente os modelos LLM eram hardcoded no código Python. Conforme o sistema evoluiu para suportar múltiplos provedores, tornou-se necessário externalizar a configuração para permitir ajustes sem modificar código.

## Decisão

Externalizar a configuração de modelos LLM para um arquivo TOML (`config/modelos_llm.toml`). A ordem dos modelos no TOML define a prioridade de fallback.

Manteve-se fallback hardcoded para Gemini 2.5 Flash Lite caso o TOML não possa ser lido.

## Alternativas consideradas

- **Variáveis de ambiente** (`LLM_MODEL_*`): rejeitada por adicionar complexidade desnecessária (commit message: "A sobrecarga de sobrescrever TOML via variáveis de ambiente adiciona complexidade desnecessária")

## Consequências

- Configuração declarativa e versionável
- Fácil adicionar/remover/reordenar modelos sem modificar código
- Fallback automático para configuração padrão
- `recarregar_modelos()` para hot-reload
