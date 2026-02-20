# Estratégia de Branching - PyGerenGastos

## 📋 Branches Principais

### `main` (Production)
- Código estável e testado em produção
- Apenas aceita merges de Pull Requests da branch `desenv`
- **Protegido**: requer aprovação de code review antes de merge
- Deploys automáticos (se houver CI/CD configurado)
- **Tag de release**: `v1.0.0`, `v1.1.0`, etc

### `desenv` (Development/Staging)
- Branch de integração para desenvolvimento em equipe
- Aceita merges de feature branches via Pull Requests
- Testes são rodados antes de merge para `main`
- Base para criação de novas features e bugfixes
- **Estado**: pode conter features em desenvolvimento

## 🚀 Branches de Feature

### Nomenclatura

```
feature/<nome-descritivo>     # Novas funcionalidades
bugfix/<issue-id>-descricao   # Correções de bugs
chore/<tarefa>                # Tarefas de manutenção
docs/<secao>                  # Documentação
hotfix/<issue-id>-descricao   # Correções urgentes em produção
```

### Exemplos

- ✅ `feature/normalizacao-produtos`
- ✅ `feature/filtro-por-categoria`
- ✅ `bugfix/123-erro-ao-salvar-nota`
- ✅ `chore/atualizar-dependencias`
- ✅ `docs/guia-usuario`
- ✅ `hotfix/456-crash-ao-importar`

## 🔄 Workflow de Desenvolvimento

### 1. Criar Feature Branch

```bash
# Atualizar desenv
git checkout desenv
git pull origin desenv

# Criar branch de feature
git checkout -b feature/sua-feature
```

### 2. Desenvolver e Commitar

```bash
# Fazer mudanças no código
git add .
git commit -m "feat: descrição clara da mudança"

# Ou para bugfix
git commit -m "fix: corrigir problema específico"

# Ou para documentação
git commit -m "docs: atualizar guia de instalação"
```

**Commit Message Format (Conventional Commits):**

```
<tipo>(<escopo>): <assunto>

<corpo>

<rodapé>
```

Tipos:
- `feat:` - Nova funcionalidade
- `fix:` - Correção de bug
- `docs:` - Documentação
- `test:` - Adição/modificação de testes
- `refactor:` - Refatoração sem mudança de comportamento
- `chore:` - Tarefas de manutenção (deps, build, etc)
- `perf:` - Melhorias de performance

Exemplos:
```bash
git commit -m "feat(normalizacao): adiciona detecção de produtos duplicados"
git commit -m "fix(embeddings): corrigir atualização de produto_id"
git commit -m "docs(branching): documentar estratégia de branch"
git commit -m "test(consolidacao): adicionar testes de migração de itens"
```

### 3. Push e Criar Pull Request

```bash
# Push para remoto
git push origin feature/sua-feature

# No GitHub, criar Pull Request
# - Base: desenv
# - Compare: feature/sua-feature
# - Adicionar descrição e checklist de testes
```

### 4. Code Review e Merge

```bash
# Após aprovação no PR, um dos seguintes:

# Opção A: Merge no GitHub UI (recomendado para auditoria)
# Aqui no GitHub: Botão "Merge pull request"

# Opção B: Merge local
git checkout desenv
git pull origin desenv
git merge feature/sua-feature
git push origin desenv
```

### 5. Cleanup

```bash
# Deletar branch local
git branch -d feature/sua-feature

# Deletar branch remota
git push origin --delete feature/sua-feature
```

## 📦 Release para Production (main)

Quando `desenv` estiver estável e pronto para produção:

```bash
# Atualizar branches locais
git checkout main
git pull origin main
git checkout desenv
git pull origin desenv

# Verificar que tudo está em ordem
# - Todos os testes passam
# - Documentation atualizada
# - CHANGELOG atualizado

# Criar Pull Request desenv → main no GitHub
# (recomendado para auditoria de release)

# Ou fazer merge local (se tiver permissão)
git checkout main
git merge desenv
git push origin main

# Criar tag de release
git tag -a v1.2.0 -m "Release 1.2.0: Normalização de produtos"
git push origin v1.2.0
```

**Formato de versão**: `vX.Y.Z` (SemVer)
- `X`: Major (breaking changes)
- `Y`: Minor (novas features)
- `Z`: Patch (bugfixes)

## ⚠️ Hotfixes (Correções Urgentes em Produção)

Se houver bug crítico em `main` que precisa correção imediata:

```bash
# Criar branch de hotfix de main
git checkout main
git pull origin main
git checkout -b hotfix/bug-critico-descricao

# Fazer correção
git add .
git commit -m "fix: corrigir bug crítico em produção"

# Push
git push origin hotfix/bug-critico-descricao

# Criar Pull Request: hotfix → main
# Após merge em main, fazer TAMBÉM merge em desenv

git checkout desenv
git pull origin main
git push origin desenv

# Cleanup
git branch -d hotfix/bug-critico-descricao
git push origin --delete hotfix/bug-critico-descricao
```

## 📝 Convenções de Commit

### Exemplo Completo

```bash
feat(normalizacao): adiciona interface de consolidação de produtos

- Implementa normalização universal de nomes
- Move tamanhos para final do nome (ex: "2L", "500ml")
- Remove unidades órfãs sem número
- Ignora números isolados que não são tamanhos

Testes:
- test_normaliza_move_tamanho_para_final
- test_normaliza_preserva_multiplos_tamanhos
- test_consolida_itens
- test_registra_auditoria

Refs #42
```

### Comandos Úteis

```bash
# Ver histórico de commits
git log --oneline --graph --all

# Ver commits da feature
git log desenv..feature/sua-feature

# Ver mudanças antes de commitar
git diff

# Ver mudanças preparadas (staged)
git diff --staged

# Amend último commit (cuidado!)
git commit --amend
```

## 🔍 Boas Práticas

### ✅ Fazer

- ✅ Criar uma branch para cada feature/bugfix
- ✅ Commitar frequentemente com mensagens claras
- ✅ Fazer push regularmente para não perder trabalho
- ✅ Descrever bem o PR antes de reviewers
- ✅ Testar localmente antes de fazer push
- ✅ Atualizar `desenv` antes de abrir PR
- ✅ Rebase/squash commits se necessário antes de merge
- ✅ Usar conventional commits

### ❌ Não Fazer

- ❌ Commitar diretamente em `main` ou `desenv`
- ❌ Fazer force push em branches compartilhadas
- ❌ Misturar múltiplas features em um único commit
- ❌ Deixar branches pendentes por muito tempo (> 1 semana)
- ❌ Commitar senhas, chaves, ou dados sensíveis
- ❌ Fazer merge sem pelo menos 1 aprovação
- ❌ Resolver conflitos sem testar

## 📚 Referências

- [Conventional Commits](https://www.conventionalcommits.org/)
- [Git Flow](https://github.com/nvie/gitflow)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [SemVer](https://semver.org/)

## ❓ FAQ

### P: Como desfazer um commit que já foi feito push?

R: Se foi para uma feature branch (não public):
```bash
git revert <commit-hash>  # Cria novo commit que desfaz
# ou
git reset --soft HEAD~1   # Desfaz mas mantém mudanças
```

### P: Como rebase minha branch em desenv?

R:
```bash
git fetch origin
git rebase origin/desenv
git push -f origin feature/sua-feature  # Force push OK em feature branch
```

### P: Conflict ao fazer merge?

R:
```bash
# Resolver conflitos manualmente nos arquivos
git add <arquivos-resolvidos>
git commit -m "Resolver conflitos com desenv"
```

### P: Como ver todas as branches remotas?

R:
```bash
git branch -r           # Apenas nomes
git branch -rv          # Com último commit
```

### P: Posso trabalhar em múltiplas features simultaneamente?

R: Sim! Crie branches separadas:
```bash
git worktree add ../work-feature-2 origin/desenv
```

---

**Última atualização**: 17 de Fevereiro de 2026
**Versão do projeto**: v0.1.0-desenv
