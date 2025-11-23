param(
	[string]$PackageName = "pygerengastos",
	[string]$OutputDir = "dist",
	[switch]$SkipVenv,
	[switch]$SkipZip,
	[switch]$IncludeRawData
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step {
	param([string]$Message)
	Write-Host "==> $Message" -ForegroundColor Cyan
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$distPath = Join-Path $repoRoot $OutputDir
$packagePath = Join-Path $distPath $PackageName
$venvPath = Join-Path $packagePath ".venv"

Write-Step "Preparando diretórios"
if (-not (Test-Path $distPath)) {
	New-Item -ItemType Directory -Path $distPath | Out-Null
}
if (Test-Path $packagePath) {
	Remove-Item -Path $packagePath -Recurse -Force
}
New-Item -ItemType Directory -Path $packagePath | Out-Null

Write-Step "Copiando arquivos necessários"
$itemsToCopy = @(
	"main.py",
	"requirements.txt",
	"README.md",
	"src",
	"data",
	"debug_product_update.py",
	"verify_logging.py",
	"verify_seeding.py"
)

foreach ($item in $itemsToCopy) {
	$source = Join-Path $repoRoot $item
	if (-not (Test-Path $source)) {
		continue
	}
	$destination = Join-Path $packagePath $item
	Copy-Item -Path $source -Destination $destination -Recurse -Force
}

# limpar dados pesados
$dataPath = Join-Path $packagePath "data"
if (Test-Path $dataPath) {
	Get-ChildItem -Path $dataPath -Recurse -Include *.duckdb, *.sqlite3 | Remove-Item -Force -ErrorAction SilentlyContinue
	$chromaPath = Join-Path $dataPath "chroma"
	if (Test-Path $chromaPath) {
		Remove-Item -Path $chromaPath -Recurse -Force
	}
	if (-not $IncludeRawData) {
		$rawPath = Join-Path $dataPath "raw_nfce"
		if (Test-Path $rawPath) {
			Remove-Item -Path $rawPath -Recurse -Force
		}
	}
}

# remover __pycache__
Get-ChildItem -Path $packagePath -Recurse -Directory -Filter "__pycache__" |
	Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Step "Gerando scripts auxiliares"
$setupScript = @'
param(
	[string]$Python = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvDir = Join-Path $root ".venv"
$requirements = Join-Path $root "requirements.txt"

Write-Host "Preparando ambiente virtual em $venvDir"
if (Test-Path $venvDir) {
	Remove-Item -Path $venvDir -Recurse -Force
}

& $Python "-m" "venv" $venvDir
$venvPython = Join-Path $venvDir "Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
	throw "Falha ao criar ambiente virtual."
}

Write-Host "Instalando dependências"
& $venvPython "-m" pip install --upgrade pip
& $venvPython "-m" pip install -r $requirements

Write-Host "Ambiente pronto. Use start.ps1 para executar o Streamlit."
'@

$runScript = @'
param(
	[switch]$Headless
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$activate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $activate)) {
	throw "Ambiente virtual não encontrado. Execute setup.ps1 primeiro."
}

. $activate

$args = "run main.py"
if ($Headless) {
	$args += " --server.headless true --server.enableCORS false"
}

streamlit $args
'@

$runBatch = @'
@echo off
setlocal
cd /d %~dp0
if not exist .venv (
	echo Ambiente virtual nao encontrado. Execute setup.ps1 primeiro.
	set /p DUMMY=Pressione ENTER para sair...
	goto :eof
)
call .venv\Scripts\activate.bat
streamlit run main.py
'@

Set-Content -Path (Join-Path $packagePath "setup.ps1") -Value $setupScript -Encoding UTF8
Set-Content -Path (Join-Path $packagePath "start.ps1") -Value $runScript -Encoding UTF8
Set-Content -Path (Join-Path $packagePath "start.bat") -Value $runBatch -Encoding ASCII

if (-not $SkipVenv) {
	Write-Step "Criando ambiente virtual dentro do pacote"
	& "python" "-m" "venv" $venvPath
	$venvPython = Join-Path $venvPath "Scripts\python.exe"
	if (-not (Test-Path $venvPython)) {
		throw "Não foi possível criar o ambiente virtual do build."
	}

	Write-Step "Instalando dependências dentro do pacote"
	$uv = Get-Command uv -ErrorAction SilentlyContinue
	$requirementsInPackage = Join-Path $packagePath "requirements.txt"
	if ($uv) {
		& $uv.Source "pip" "install" "--python" $venvPython "-r" $requirementsInPackage
	} else {
		& $venvPython "-m" pip install --upgrade pip
		& $venvPython "-m" pip install -r $requirementsInPackage
	}
}

if (-not $SkipZip) {
	Write-Step "Compactando pacote"
	$zipPath = Join-Path $distPath ("{0}.zip" -f $PackageName)
	if (Test-Path $zipPath) {
		Remove-Item -Path $zipPath -Force
	}
	Compress-Archive -Path $packagePath -DestinationPath $zipPath
}

Write-Step "Build finalizado em $packagePath"
