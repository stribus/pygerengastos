# ADR-008: Adoção de Spec-Driven Development (SDD)

**Data:** 2025-2026
**Status:** Aceito
**Confiança:** 🟢 CONFIRMADO

## Contexto

O projeto cresceu organicamente com múltiplos contribuidores (inclusive agentes de IA). A falta de especificações claras gerava inconsistências entre implementação e expectativa.

## Decisão

Adotar Spec-Driven Development (SDD) com Spec Kit do GitHub: especificação → implementação → teste. Cada feature começa com uma spec documentada antes da codificação.

## Consequências

- Rastreabilidade entre spec, código e testes
- Documentação viva das funcionalidades
- Facilidade para agentes de IA entenderem o escopo
- Sobrecarga inicial de escrita de specs
- Integração com GitHub Issues via Spec Kit
