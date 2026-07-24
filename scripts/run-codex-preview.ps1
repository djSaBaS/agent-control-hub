[CmdletBinding()]
param(
    [string]$WebRoot = "C:\wamp64\www\agent-control-hub",
    [int]$IntervalSeconds = 5,
    [switch]$Once,
    [switch]$DoNotOpenBrowser,
    [switch]$DisableWindowsNotifications
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

# Busca un intérprete compatible sin exigir una versión menor concreta.
function Get-CompatiblePythonRuntime {
    $Candidates = @(
        [PSCustomObject]@{
            Name = "python del sistema"
            Command = "python"
            PrefixArguments = @()
        },
        [PSCustomObject]@{
            Name = "Python Launcher 3.13"
            Command = "py"
            PrefixArguments = @("-3.13")
        },
        [PSCustomObject]@{
            Name = "Python Launcher 3.12"
            Command = "py"
            PrefixArguments = @("-3.12")
        },
        [PSCustomObject]@{
            Name = "Python Launcher 3.11"
            Command = "py"
            PrefixArguments = @("-3.11")
        }
    )

    foreach ($Candidate in $Candidates) {
        $ResolvedCommand = Get-Command $Candidate.Command -ErrorAction SilentlyContinue
        if ($null -eq $ResolvedCommand) {
            continue
        }

        $VersionArguments = @()
        $VersionArguments += $Candidate.PrefixArguments
        $VersionArguments += @(
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
        )

        $VersionText = & $ResolvedCommand.Source @VersionArguments 2>$null
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($VersionText)) {
            continue
        }

        try {
            $Version = [version]($VersionText.Trim())
        } catch {
            continue
        }

        if ($Version -ge [version]"3.11.0" -and $Version -lt [version]"4.0.0") {
            return [PSCustomObject]@{
                Name = $Candidate.Name
                Executable = $ResolvedCommand.Source
                PrefixArguments = $Candidate.PrefixArguments
                Version = $Version
            }
        }
    }

    throw "No se ha encontrado Python 3.11 o superior. Ejecuta 'python --version' y comprueba que esté disponible en PATH."
}

# Valida los parámetros antes de instalar o ejecutar componentes.
if ($IntervalSeconds -lt 1) {
    throw "El intervalo debe ser de al menos un segundo."
}
if (-not (Test-Path $ViewerSource)) {
    throw "No se encuentra el visor local en $ViewerSource"
}
if (-not (Test-Path $ConfigPath)) {
    throw "No se encuentra la configuración de plataformas en $ConfigPath"
}

# Crea un entorno Python aislado con cualquier versión compatible instalada.
if (-not (Test-Path $PythonExecutable)) {
    Write-Host "[1/4] Preparando el entorno virtual de Python..." -ForegroundColor Cyan
    $PythonRuntime = Get-CompatiblePythonRuntime
    Write-Host (
        "Python detectado: {0} ({1})" -f $PythonRuntime.Version, $PythonRuntime.Executable
    ) -ForegroundColor DarkGray

    # Elimina una creación anterior incompleta antes de volver a generar el entorno.
    if (Test-Path $VirtualEnvironment) {
        Remove-Item -Path $VirtualEnvironment -Recurse -Force
    }

    $VenvArguments = @()
    $VenvArguments += $PythonRuntime.PrefixArguments
    $VenvArguments += @("-m", "venv", $VirtualEnvironment)
    & $PythonRuntime.Executable @VenvArguments

    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $PythonExecutable)) {
        throw "No se pudo crear el entorno virtual en $VirtualEnvironment"
    }
} else {
    $ExistingVersion = & $PythonExecutable --version
    Write-Host "[1/4] Entorno virtual existente: $ExistingVersion" -ForegroundColor Cyan
}

# Instala o actualiza el paquete editable para utilizar el código de la rama actual.
Write-Host "[2/4] Instalando Agent Control Hub en el entorno local..." -ForegroundColor Cyan
& $PythonExecutable -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo actualizar pip dentro del entorno virtual."
}
& $PythonExecutable -m pip install --editable $ServiceRoot
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo instalar Agent Control Hub en el entorno virtual."
}

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
Write-Host "[4/4] Leyendo datos reales de Codex y Hermes..." -ForegroundColor Cyan
Write-Host "Codex:  $HOME\.codex\sessions" -ForegroundColor DarkGray
Write-Host "Hermes: $env:LOCALAPPDATA\hermes\state.db" -ForegroundColor DarkGray
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
if (-not $DisableWindowsNotifications) {
    # Solicita globos nativos cuando una cuota se restaura realmente.
    $ServiceArguments += "--notify-windows"
}
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
