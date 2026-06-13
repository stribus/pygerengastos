
## Arquitetura do Projeto
Este é um sistema de gerenciamento de despesas mensais em Python que implementa um pipeline completo com intuito de gerar relatorios de inflação:
1. **Web Scraping**: Extrai NFC-e do site da SEFAZ-RS via POST request com cabeçalhos específicos
2. **Classificação Híbrida**: Usa busca semântica (ChromaDB + SentenceTransformers) com fallback para LLM (Gemini via LiteLLM)
3. **Persistência**: SQLite3 com schema dimensional (datas, estabelecimentos, produtos, categorias)
4. **Interface**: Streamlit com 3 abas (Home/Importação/Análise) e navegação com redirecionamento



# Reversa

> Framework de Engenharia Reversa instalado neste projeto.

## Como usar

Digite `/reversa` para ativar o Reversa e iniciar ou retomar a análise do projeto.

## Comportamento ao ativar

Quando o usuário digitar `/reversa` ou a palavra `reversa` sozinha em uma mensagem:

1. Ative o skill `reversa` disponível em `.claude/skills/reversa/SKILL.md`
2. Se não encontrar em `.claude/skills/`, tente `.agents/skills/reversa/SKILL.md`
3. Leia o SKILL.md na íntegra e siga exatamente as instruções do Reversa

## Regra não-negociável

Nunca apague, modifique ou sobrescreva arquivos pré-existentes do projeto legado.
O Reversa escreve **apenas** em `.reversa/` e `_reversa_sdd/`.
