[CmdletBinding()]
param(
    # Recibe el puerto serie asignado por Windows al dispositivo.
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^COM\d+$')]
    [string]$Port,
    # Recibe la carpeta publicada por WAMP para conservar el visor web.
    [string]$WebRoot = "C:\wamp64\www\agent-control-hub",
    # Recibe el intervalo de actualización del servicio.
    [ValidateRange(1, 60)]
    [int]$IntervalSeconds = 2,
    # Permite evitar la apertura automática del navegador.
    [switch]$DoNotOpenBrowser,
    # Permite desactivar los avisos nativos de Windows.
    [switch]$DisableWindowsNotifications,
    # Permite omitir únicamente la comprobación activa por IP local.
    [switch]$SkipNetworkIsolationCheck
)

# Detiene el script ante cualquier error no controlado.
$ErrorActionPreference = "Stop"

# Resuelve la raíz del repositorio desde la carpeta del script.
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
# Resuelve la carpeta del servicio Python.
$ServiceRoot = Join-Path $RepositoryRoot "service"
# Resuelve la configuración conjunta de Codex y Hermes.
$ConfigPath = Join-Path $ServiceRoot "config.codex-preview.json"
# Resuelve el entorno virtual utilizado por el proyecto.
$VirtualEnvironment = Join-Path $ServiceRoot ".venv"
# Resuelve el ejecutable Python aislado.
$PythonExecutable = Join-Path $VirtualEnvironment "Scripts\python.exe"
# Resuelve el visor web sanitizado.
$ViewerSource = Join-Path $RepositoryRoot "tools\pc-viewer\index.html"
# Resuelve la política Apache que restringe el visor al propio equipo.
$ViewerSecuritySource = Join-Path $RepositoryRoot "tools\pc-viewer\.htaccess"
# Resuelve el helper común de aislamiento.
$ViewerSecurityHelper = Join-Path $RepositoryRoot "scripts\viewer-security.ps1"
# Resuelve el snapshot servido por WAMP.
$SnapshotPath = Join-Path $WebRoot "snapshot.json"
# Resuelve el destino del visor web.
$ViewerTarget = Join-Path $WebRoot "index.html"

# Comprueba que existe el helper antes de publicar la vista local.
if (-not (Test-Path -LiteralPath $ViewerSecurityHelper)) {
    # Evita ejecutar sin las comprobaciones de aislamiento.
    throw "No se encuentra el helper de seguridad en $ViewerSecurityHelper"
}
# Carga las funciones de seguridad del visor.
. $ViewerSecurityHelper

# Comprueba que existe el entorno creado por el lanzador habitual.
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    # Explica el paso previo necesario sin crear entornos duplicados.
    throw "No existe $PythonExecutable. Ejecuta primero .\scripts\run-codex-preview.ps1 para preparar el entorno."
}

# Comprueba que existe la configuración de plataformas reales.
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    # Detiene una ejecución que no podría cargar adaptadores.
    throw "No se encuentra la configuración de plataformas en $ConfigPath"
}

# Comprueba que existe el visor local antes de copiarlo.
if (-not (Test-Path -LiteralPath $ViewerSource)) {
    # Detiene una ejecución con una instalación incompleta.
    throw "No se encuentra el visor local en $ViewerSource"
}

# Recupera los puertos serie disponibles para validar el dispositivo.
$AvailablePorts = [System.IO.Ports.SerialPort]::GetPortNames()
# Comprueba que el puerto solicitado exista en este momento.
if ($Port -notin $AvailablePorts) {
    # Construye una lista legible de puertos encontrados.
    $AvailableText = if ($AvailablePorts.Count -gt 0) {
        # Une los puertos disponibles mediante comas.
        $AvailablePorts -join ", "
    } else {
        # Informa de que Windows no detecta ningún puerto.
        "ninguno"
    }
    # Detiene la ejecución con un diagnóstico concreto.
    throw "El puerto $Port no está disponible. Puertos detectados: $AvailableText"
}

# Prepara el directorio servido por WAMP.
New-Item -Path $WebRoot -ItemType Directory -Force | Out-Null
# Copia el visor web correspondiente a la rama actual.
Copy-Item -LiteralPath $ViewerSource -Destination $ViewerTarget -Force
# Agrupa los parámetros de instalación de la política Apache.
$ViewerSecurityParameters = @{
    SecuritySource = $ViewerSecuritySource
    WebRoot = $WebRoot
    SkipNetworkIsolationCheck = $SkipNetworkIsolationCheck
}
# Instala la restricción local y comprueba la exposición de red.
Install-AgentControlViewerSecurity @ViewerSecurityParameters

# Define la URL local del visor.
$PreviewUrl = "http://localhost/agent-control-hub/"
# Abre el visor cuando no se ha desactivado expresamente.
if (-not $DoNotOpenBrowser) {
    # Solicita a Windows abrir la URL en el navegador predeterminado.
    Start-Process $PreviewUrl
}

# Informa de las fuentes y transportes que se iniciarán.
Write-Host "Agent Control Hub · dispositivo físico" -ForegroundColor Cyan
# Muestra el puerto serie validado.
Write-Host "M5Stack: $Port · 115200 baudios" -ForegroundColor Green
# Muestra la carpeta de sesiones de Codex.
Write-Host "Codex:   $HOME\.codex\sessions" -ForegroundColor DarkGray
# Muestra la base local de Hermes.
Write-Host "Hermes:  $env:LOCALAPPDATA\hermes\state.db" -ForegroundColor DarkGray
# Muestra el snapshot servido por WAMP.
Write-Host "JSON:    $SnapshotPath" -ForegroundColor DarkGray
# Muestra la URL de diagnóstico.
Write-Host "Web:     $PreviewUrl" -ForegroundColor DarkGray
# Explica cómo detener el proceso persistente.
Write-Host "Pulsa Ctrl+C para detener la transmisión." -ForegroundColor Yellow

# Construye los argumentos comunes del servicio.
$ServiceArguments = @(
    # Ejecuta el módulo principal del paquete instalado.
    "-m",
    # Identifica el punto de entrada Python.
    "agent_control_hub.main",
    # Solicita la configuración conjunta.
    "--config",
    # Entrega la ruta de configuración.
    $ConfigPath,
    # Solicita publicación del snapshot web.
    "--output",
    # Entrega la ruta del archivo JSON.
    $SnapshotPath,
    # Solicita transmisión serie al dispositivo.
    "--port",
    # Entrega el puerto COM validado.
    $Port,
    # Solicita el intervalo de captura.
    "--interval",
    # Entrega el intervalo como texto compatible con argparse.
    $IntervalSeconds.ToString()
)

# Activa notificaciones nativas salvo desactivación explícita.
if (-not $DisableWindowsNotifications) {
    # Añade el interruptor soportado por el servicio.
    $ServiceArguments += "--notify-windows"
}

# Ejecuta el servicio desde su carpeta para conservar rutas relativas conocidas.
Push-Location $ServiceRoot
# Garantiza la restauración de la carpeta anterior.
try {
    # Inicia la captura conjunta, el visor y la transmisión serie.
    & $PythonExecutable @ServiceArguments
} finally {
    # Restaura la carpeta inicial incluso después de Ctrl+C.
    Pop-Location
}
