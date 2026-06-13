# Matriz de Permissões — Gerenciador de despesa

> Gerado pelo Detective em 2026-06-06

## Modelo de Segurança

**Single-user.** A aplicação é desktop local rodando via Streamlit, sem autenticação, login, ou controle de acesso.

| Aspecto | Status |
|---------|--------|
| Autenticação | ❌ Não implementada |
| Login | ❌ Não implementado |
| RBAC | ❌ Não implementado |
| Multi-usuário | ❌ Não implementado |
| Campos de auditoria | ✅ `usuario` em revisoes_manuais e consolidacoes_historico |

## Único Papel

| Papel | Acesso | Origem |
|-------|--------|--------|
| **Operador** | Total — todas as funcionalidades | Implícito (usuário do sistema local) |

## Funcionalidades vs Acesso

| Funcionalidade | Operador |
|----------------|----------|
| Home (KPIs, gráficos) | ✅ |
| Importar nota fiscal | ✅ |
| Reprocessar nota | ✅ |
| Remover nota | ✅ |
| Classificar itens (automático) | ✅ |
| Revisar classificação manualmente | ✅ |
| Normalizar produtos | ✅ |
| Consolidar produtos (merge) | ✅ |
| Buscar produtos | ✅ |
| Visualizar relatórios de preço | ✅ |
| Visualizar inflação acumulada | ✅ |
| Exportar dados (CSV) | ✅ |

## Observação sobre o campo `usuario`

O campo `usuario` nas tabelas `revisoes_manuais` e `consolidacoes_historico` é preenchido via campo de texto livre na interface (`st.text_input`), **sem validação de identidade**. Serve apenas para rastreamento informal de quem fez a operação.
