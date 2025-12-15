# Instruções de Instalação - PyGerenGastos

## Pré-requisitos

- Python 3.13 ou superior instalado
- Windows PowerShell 5.1 ou superior

## Instalação via Pacote Pré-compilado

Se você recebeu o arquivo `pygerengastos.zip`:

1. **Extraia o arquivo ZIP** em uma pasta de sua escolha (ex: `C:\Apps\pygerengastos`)

2. **Configure a API do Gemini**:
   - Acesse https://aistudio.google.com/apikey e crie uma chave API
   - Copie o arquivo `.env.example` para `.env`
   - Edite `.env` e cole sua chave API no campo `GEMINI_API_KEY`

3. **Execute a aplicação**:
   - Clique duas vezes em `start.bat` OU
   - Abra PowerShell na pasta e execute: `.\start.ps1`

4. A aplicação abrirá automaticamente no seu navegador padrão em `http://localhost:8501`

## Instalação Manual (Para Desenvolvedores)

Se você clonou o repositório ou quer instalar do zero:

1. **Clone o repositório** (se aplicável):
   ```powershell
   git clone https://github.com/stribus/pygerengastos.git
   cd pygerengastos
   ```

2. **Execute o script de setup**:
   ```powershell
   .\setup.ps1
   ```

3. **Configure a API do Gemini** (mesmo processo acima)

4. **Execute a aplicação**:
   ```powershell
   .\start.ps1
   ```

## Solução de Problemas

### Erro: "Ambiente virtual não encontrado"
Execute `.\setup.ps1` para criar o ambiente virtual e instalar as dependências.

### Erro: "GEMINI_API_KEY não configurada"
Verifique se você criou o arquivo `.env` com a chave API válida.

### Erro de porta já em uso
Use o modo headless: `.\start.ps1 -Headless`

### Erros de importação de módulos
Reinstale as dependências:
```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Uso Básico

1. **Importar Notas Fiscais**:
   - Vá para a aba "Importar notas"
   - Digite ou cole a chave de acesso da NFC-e (44 dígitos)
   - Clique em "Buscar nota"

2. **Classificar Itens**:
   - Os itens serão classificados automaticamente usando IA
   - Você pode revisar e corrigir as classificações na aba "Analisar notas"

3. **Visualizar Dashboards**:
   - Acesse a aba "Home" para ver gráficos e estatísticas dos seus gastos

## Estrutura de Dados

- **Banco de dados**: `data/gastos.db` (SQLite3)
- **HTMLs das notas**: `data/raw_nfce/` (backup dos HTMLs originais)
- **Índice semântico**: `data/chroma/` (embeddings para classificação)
- **Logs**: `logs/app.log` (logs rotativos, máx 5MB)

## Suporte

Para reportar bugs ou solicitar recursos, abra uma issue em:
https://github.com/stribus/pygerengastos/issues
