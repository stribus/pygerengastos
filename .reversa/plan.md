# Plano de Exploração — Gerenciador de despesa

> Criado pelo Reversa em 2026-06-06
> Marque cada tarefa com ✅ quando concluída.
> Você pode editar este plano antes de iniciar: adicione, remova ou reordene tarefas conforme necessário.

---

## Fase 1: Reconhecimento 🔍

- [X] **Scout** — Mapeamento de estrutura de pastas e tecnologias
- [X] **Scout** — Análise de dependências e gerenciadores de pacotes
- [X] **Scout** — Identificação de entry points, CI/CD e configurações

## Decisão de organização das specs 🗂️

> Entre o Scout e o Arqueólogo, o Reversa pergunta como você quer organizar as specs (por módulo, caso de uso, endpoint, híbrida, por features ou customizada). A escolha fica persistida em `.reversa/config.toml` na seção `[specs]` e não será reperguntada em execuções futuras. Para reapresentar o menu, remova manualmente a seção.

## Fase 2: Escavação 🏗️

> O Reversa preenche esta seção com os módulos reais após o Scout concluir o reconhecimento.

- [X] **Archaeologist** — Análise do módulo `classifiers`
- [X] **Archaeologist** — Análise do módulo `database`
- [X] **Archaeologist** — Análise do módulo `scrapers`
- [X] **Archaeologist** — Análise do módulo `ui`
- [X] **Archaeologist** — Análise do módulo `config`

## Fase 3: Interpretação 🧠

- [X] **Detetive** — Arqueologia Git e ADRs retroativos (8 ADRs)
- [X] **Detetive** — Regras de negócio implícitas e máquinas de estado
- [X] **Detetive** — Matriz de permissões (single-user, sem RBAC)
- [X] **Arquiteto** — Diagramas C4 (Contexto, Containers, Componentes)
- [X] **Arquiteto** — ERD completo e integrações externas
- [X] **Arquiteto** — Spec Impact Matrix

## Fase 4: Geração 📝

- [X] **Redator** — Specs SDD por componente
- [ ] **Redator** — OpenAPI (se aplicável)
- [ ] **Redator** — User Stories (se aplicável)
- [X] **Redator** — Code/Spec Matrix

## Fase 5: Revisão ✅

- [X] **Revisor** — Revisão cruzada de specs
- [X] **Revisor** — Resolução de lacunas com o usuário
- [X] **Revisor** — Relatório de confiança final

---

## Agentes Independentes

> Execute estes agentes quando os recursos estiverem disponíveis — podem rodar em qualquer fase.

- [ ] **Visor** — Análise de interface via screenshots
- [ ] **Data Master** — Análise completa do banco de dados
- [ ] **Design System** — Extração de tokens de design
- [ ] **Tracer** — Análise dinâmica (requer sistema acessível)

---

## Próximo passo

Após o Time de Descoberta concluir e o `_reversa_sdd/` estar populado, você pode disparar um dos fluxos seguintes:

- `/reversa-migrate`: orquestrador do **Time de Migração** (Paradigm Advisor → Curator → Strategist → Designer → Screen Translator → Inspector). Gera as specs do sistema novo. Saída em `_reversa_sdd/migration/` e `_reversa_sdd/screens/`.
- `/reversa-reconstructor`: gera plano bottom-up para reimplementar o software a partir das specs do legado (uma tarefa por sessão).
