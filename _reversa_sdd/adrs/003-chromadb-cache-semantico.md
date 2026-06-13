# ADR-003: ChromaDB para Cache Semântico de Classificação

**Data:** 2024 (inferido do histórico Git)
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

Toda importação de nota fiscal exigia chamada ao LLM para classificar cada item. Isso gerava custo recorrente, latência e dependência de API externa para operações repetitivas (itens já classificados anteriormente com descrições similares).

## Decisão

Adicionar ChromaDB com modelo de embeddings `all-MiniLM-L6-v2` como camada de cache semântico anterior à chamada de LLM. Descrições similares a itens já classificados retornam categoria do cache sem buscar LLM.

## Alternativas consideradas

- **Cache exato por texto**: frágil contra variações mínimas na descrição
- **Cache por regex**: complexo e não escala
- **Sem cache (sempre LLM)**: custo e latência elevados

## Consequências

- Redução drástica de chamadas LLM para itens recorrentes
- Aprendizado contínuo: toda classificação confirmada vira embedding
- Threshold de similaridade configurável (0.82)
- Dependência adicional: ChromaDB + sentence-transformers (~2-3GB de modelo)
- Necessidade de gerenciamento de cache offline
