[CmdletBinding()]
param(
    [string]$WebRoot = "C:\wamp64\www\agent-control-hub",
    [int]$IntervalSeconds = 5,
    [switch]$Once,
    [switch]$DoNotOpenBrowser
)

$ErrorActionPreference = "Stop"

# Resuelve las rutas del repositorio y del servicio sin depender del directorio actual.
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ServiceRoot = Join-Path $RepositoryRoot "service"
$ViewerSource = Join-Path $RepositoryRoot "tools\pc-viewer\index.html"
$ConfigPath = Join-Path $ServiceRoot "config.codex-preview.json"
$VirtualEnvironment = Join-Path $ServiceRoot ".venv"
$PythonExecutable = Join-Path $VirtualEnvironment "Scripts\python.exe"
$SnapshotPath = Join-Path $WebRoot "snapshot.json"
$ViewerTarget = Join-Path $WebRoot "index.html"

# Valida los parámetros antes de instalar o ejecutar componentes.
if ($IntervalSeconds -lt 1) {
    throw "El intervalo debe ser de al menos un segundo."
}
if (-not (Test-Path $ViewerSource)) {
    throw "No se encuentra el visor local en $ViewerSource"
}
if (-not (Test-Path $ConfigPath)) {
    throw "No se encuentra la configuración de Codex en $ConfigPath"
}

# Crea un entorno Python aislado en la carpeta del servicio cuando no existe.
if (-not (Test-Path $PythonExecutable)) {
    Write-Host "[1/4] Creando el entorno virtual de Python..." -ForegroundColor Cyan
    py -3.11 -m venv $VirtualEnvironment
}

# Instala o actualiza el paquete editable para utilizar el código de la rama actual.
Write-Host "[2/4] Instalando Agent Control Hub en el entorno local..." -ForegroundColor Cyan
& $PythonExecutable -m pip install --upgrade pip
& $PythonExecutable -m pip install --editable $ServiceRoot

# Prepara el directorio servido por WAMP y copia únicamente el visor sanitizado.
Write-Host "[3/4] Preparando la vista web en $WebRoot..." -ForegroundColor Cyan
New-Item -Path $WebRoot -ItemType Directory -Force | Out-Null
Copy-Item -Path $ViewerSource -Destination $ViewerTarget -Force

# Abre el visor antes de iniciar el bucle; mostrará el primer dato cuando se genere.
$PreviewUrl = "http://localhost/agent-control-hub/"
if (-not $DoNotOpenBrowser) {
    Start-Process $PreviewUrl
}

# Ejecuta la misma aplicación que alimentará posteriormente el dispositivo físico.
Write-Host "[4/4] Leyendo datos reales de Codex..." -ForegroundColor Cyan
Write-Host "Fuente: $HOME\.codex\sessions" -ForegroundColor DarkGray
Write-Host "JSON:   $SnapshotPath" -ForegroundColor DarkGray
Write-Host "Web:    $PreviewUrl" -ForegroundColor DarkGray
if (-not $Once) {
    Write-Host "Pulsa Ctrl+C para detener la actualización." -ForegroundColor Yellow
}

$ServiceArguments = @(
    "-m",
    "agent_control_hub.main",
    "--config",
    $ConfigPath,
    "--output",
    $SnapshotPath
)
if ($Once) {
    $ServiceArguments += "--once"
} else {
    $ServiceArguments += @("--interval", $IntervalSeconds.ToString())
}

Push-Location $ServiceRoot
try {
    & $PythonExecutable @ServiceArguments
} finally {
    Pop-Location
}
