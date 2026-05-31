# Configuração do Modelo de Embeddings

## Visão Geral

A aplicação utiliza o modelo `all-MiniLM-L6-v2` da Hugging Face para busca semântica de produtos.

## Comportamento de Inicialização

### First Run (Primeira Execução)

Na primeira execução, o sistema segue esta estratégia:

1. **Busca no cache local** (`cache/huggingface/`)
   - Se encontrar: Carrega imediatamente (modo offline)
   - Se não encontrar: Procede para etapa 2

2. **Download automático** de Hugging Face
   - Conecta a `https://huggingface.co`
   - Baixa o modelo completo (~23 MB)
   - Armazena em `cache/huggingface/` para reutilização

3. **Modo offline** ativado após cache preenchido
   - Próximas execuções carregam apenas do cache local (rápido)
   - Sem necessidade de internet

### Mensagens de Log

```
Modelo 'all-MiniLM-L6-v2' não encontrado no cache local. Tentando download automático...
Iniciando download do modelo 'all-MiniLM-L6-v2' de Hugging Face...
Modelo 'all-MiniLM-L6-v2' baixado e armazenado em cache em F:\...\cache\huggingface.
```

## Requisitos para Primeira Execução

- **Conexão de internet**: Obrigatória apenas na primeira execução
- **Espaço em disco**: ~100 MB no diretório de cache (modelo + índices HF)
- **Permissões**: Escrita no diretório `cache/huggingface/`

## Offline Mode (Após Cache Preenchido)

Após a primeira execução bem-sucedida:

- ✅ Funciona **100% offline**
- ✅ Carrega modelo do cache em segundos
- ✅ Busca semântica de produtos sem internet

## Troubleshooting

### Erro: "Falha ao baixar o modelo de embeddings"

**Causa**: Sem acesso à internet na primeira execução

**Solução**:
1. Verifique conexão com internet
2. Verifique se `https://huggingface.co` está acessível
3. Verifique firewall/proxy (pode ser necessário configurar `HF_ENDPOINT`)

### Erro: "Verifique permissões de escrita"

**Causa**: Sem permissão de escrita em `cache/huggingface/`

**Solução**:
1. Verifique permissões da pasta `cache/` e seus pais
2. Execute como administrador (Windows) ou use `sudo` (Linux/Mac)
3. Ou mude o cache para pasta com permissões: `export HF_HOME=/seu/caminho/cache`

### Cache Corrompido ou Desatualizado

**Solução**:
```powershell
# Windows: Delete pasta de cache
Remove-Item -Path "cache/huggingface" -Recurse -Force
# Próxima execução baixará novo cache
```

```bash
# Linux/Mac:
rm -rf cache/huggingface/
# Próxima execução baixará novo cache
```

## Distribuição / Build

Ao empacotar a aplicação com `build.ps1`:

- ✅ Pasta `cache/` é incluída no pacote
- ✅ Se o modelo já foi baixado localmente, é empacotado (evita primeiro download)
- ✅ Se ainda não foi baixado, primeira execução do pacote fará download automático

**Dica**: Para distribuições offline, execute uma vez em ambiente com internet para preencher o cache antes de empacotar:

```powershell
streamlit run main.py  # Aguarde "Modelo baixado e armazenado em cache"
.\build.ps1 -PackageName pygerengastos  # Agora pacote inclui modelo em cache
```

## Variáveis de Ambiente

Para customizar o comportamento:

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `HF_HOME` | `cache/huggingface` | Diretório raiz do cache HF |
| `TRANSFORMERS_CACHE` | Mesmo que `HF_HOME` | Cache específico de transformers |
| `SENTENCE_TRANSFORMERS_HOME` | Mesmo que `HF_HOME` | Cache específico de sentence-transformers |
| `HF_HUB_OFFLINE` | Auto (1=offline) | Força modo offline após cache carregado |
| `TRANSFORMERS_OFFLINE` | Auto (1=offline) | Força modo offline para transformers |
| `HF_ENDPOINT` | `https://huggingface.co` | URL customizada para Hugging Face (proxy) |

## Performance

### Cache Local (Modo Offline)
- Tempo de carregamento: ~2-5 segundos
- Sem requisições de rede

### Primeiro Download
- Tempo: ~30-60 segundos (depende da internet)
- Tamanho: ~23 MB (modelo) + 50 MB (índices HF) = ~73 MB

## Referências

- Modelo: [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- Docs HF Offline: [huggingface.co/docs/transformers/installation#offline-mode](https://huggingface.co/docs/transformers/installation#offline-mode)
