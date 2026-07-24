# Detiene el helper ante errores no controlados.
$ErrorActionPreference = "Stop"

# Localiza un intérprete Python compatible para crear el entorno virtual.
function Get-AgentControlPythonRuntime {
    [CmdletBinding()]
    param()

    # Define los comandos que se probarán en orden.
    $Candidates = @(
        # Prueba primero Python disponible directamente en PATH.
        [PSCustomObject]@{ Command = "python"; Prefix = @() },
        # Prueba el lanzador de Python 3.13.
        [PSCustomObject]@{ Command = "py"; Prefix = @("-3.13") },
        # Prueba el lanzador de Python 3.12.
        [PSCustomObject]@{ Command = "py"; Prefix = @("-3.12") },
        # Prueba el lanzador de Python 3.11.
        [PSCustomObject]@{ Command = "py"; Prefix = @("-3.11") }
    )

    # Recorre los candidatos hasta encontrar una versión soportada.
    foreach ($Candidate in $Candidates) {
        # Resuelve el ejecutable sin detener el proceso cuando no exista.
        $Resolved = Get-Command $Candidate.Command -ErrorAction SilentlyContinue
        # Omite comandos no instalados.
        if ($null -eq $Resolved) {
            continue
        }
        # Construye los argumentos de consulta de versión.
        $Arguments = @($Candidate.Prefix) + @(
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
        )
        # Ejecuta la consulta sin publicar diagnósticos de candidatos incompatibles.
        $VersionText = & $Resolved.Source @Arguments 2>$null
        # Omite comandos que no respondan correctamente.
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($VersionText)) {
            continue
        }
        # Intenta convertir la salida a una versión comparable.
        try {
            # Convierte la versión recibida.
            $Version = [version]$VersionText.Trim()
        } catch {
            # Omite salidas no válidas.
            continue
        }
        # Acepta Python 3.11 o superior anterior a Python 4.
        if ($Version -ge [version]"3.11.0" -and $Version -lt [version]"4.0.0") {
            # Devuelve la configuración necesaria para crear el entorno.
            return [PSCustomObject]@{
                Executable = $Resolved.Source
                Prefix = @($Candidate.Prefix)
                Version = $Version
            }
        }
    }

    # Detiene el arranque cuando no existe un intérprete compatible.
    throw "No se ha encontrado Python 3.11 o superior en PATH."
}

# Ejecuta Agent Control Hub con visor loopback o WAMP validado.
function Invoke-AgentControlPreview {
    [CmdletBinding()]
    param(
        # Recibe la raíz absoluta del repositorio.
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot,
        # Permite definir una carpeta pública alternativa.
        [AllowEmptyString()]
        [string]$WebRoot = "",
        # Recibe el puerto HTTP local del visor.
        [ValidateRange(1024, 65535)]
        [int]$ViewerPort = 8765,
        # Recibe el intervalo de captura.
        [ValidateRange(1, 60)]
        [int]$IntervalSeconds = 5,
        # Permite generar una única captura.
        [switch]$Once,
        # Permite evitar que se abra el navegador.
        [switch]$DoNotOpenBrowser,
        # Permite desactivar notificaciones nativas.
        [switch]$DisableWindowsNotifications,
        # Permite usar WAMP de forma explícita.
        [switch]$UseWamp,
        # Permite omitir únicamente la prueba de red de WAMP.
        [switch]$SkipNetworkIsolationCheck,
        # Permite añadir un puerto serie para el dispositivo físico.
        [AllowEmptyString()]
        [string]$SerialPort = ""
    )

    # Resuelve la carpeta del servicio Python.
    $ServiceRoot = Join-Path $RepositoryRoot "service"
    # Resuelve el entorno virtual aislado.
    $VirtualEnvironment = Join-Path $ServiceRoot ".venv"
    # Resuelve el intérprete del entorno virtual.
    $PythonExecutable = Join-Path $VirtualEnvironment "Scripts\python.exe"
    # Resuelve la configuración conjunta de Codex y Hermes.
    $ConfigPath = Join-Path $ServiceRoot "config.codex-preview.json"
    # Resuelve el visor HTML versionado.
    $ViewerSource = Join-Path $RepositoryRoot "tools\pc-viewer\index.html"
    # Resuelve la política Apache opcional.
    $ViewerSecuritySource = Join-Path $RepositoryRoot "tools\pc-viewer\.htaccess"
    # Resuelve el helper de WAMP opcional.
    $ViewerSecurityHelper = Join-Path $RepositoryRoot "scripts\viewer-security.ps1"
    # Resuelve el helper del servidor loopback predeterminado.
    $LoopbackViewerHelper = Join-Path $RepositoryRoot "scripts\loopback-viewer.ps1"

    # Comprueba los archivos requeridos antes de modificar el entorno local.
    foreach ($RequiredPath in @($ConfigPath, $ViewerSource, $LoopbackViewerHelper)) {
        # Detiene una instalación incompleta.
        if (-not (Test-Path -LiteralPath $RequiredPath)) {
            throw "No se encuentra el archivo requerido: $RequiredPath"
        }
    }
    # Carga las funciones del servidor loopback.
    . $LoopbackViewerHelper

    # Carga el helper de Apache únicamente en modo WAMP.
    if ($UseWamp) {
        # Comprueba que exista el helper de aislamiento.
        if (-not (Test-Path -LiteralPath $ViewerSecurityHelper)) {
            throw "No se encuentra el helper de seguridad: $ViewerSecurityHelper"
        }
        # Carga las funciones de WAMP.
        . $ViewerSecurityHelper
    }

    # Selecciona una carpeta segura cuando no se proporciona una ruta.
    if ([string]::IsNullOrWhiteSpace($WebRoot)) {
        # Conserva WAMP únicamente cuando se solicita expresamente.
        if ($UseWamp) {
            $WebRoot = "C:\wamp64\www\agent-control-hub"
        } else {
            # Utiliza una carpeta privada del perfil local.
            $WebRoot = Join-Path $env:LOCALAPPDATA "AgentControlHub\viewer"
        }
    }

    # Resuelve los archivos públicos dentro de la carpeta seleccionada.
    $SnapshotPath = Join-Path $WebRoot "snapshot.json"
    # Resuelve el destino del documento principal.
    $ViewerTarget = Join-Path $WebRoot "index.html"

    # Crea el entorno virtual cuando todavía no existe.
    if (-not (Test-Path -LiteralPath $PythonExecutable)) {
        # Informa del paso de preparación.
        Write-Host "[1/4] Preparando el entorno virtual de Python..." -ForegroundColor Cyan
        # Localiza un intérprete compatible.
        $Runtime = Get-AgentControlPythonRuntime
        # Construye los argumentos de creación del entorno.
        $VenvArguments = @($Runtime.Prefix) + @("-m", "venv", $VirtualEnvironment)
        # Crea el entorno aislado.
        & $Runtime.Executable @VenvArguments
        # Comprueba que la creación terminara correctamente.
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $PythonExecutable)) {
            throw "No se pudo crear el entorno virtual en $VirtualEnvironment"
        }
    } else {
        # Consulta la versión del entorno existente.
        $ExistingVersion = & $PythonExecutable --version
        # Informa de que no se recreará el entorno.
        Write-Host "[1/4] Entorno virtual existente: $ExistingVersion" -ForegroundColor Cyan
    }

    # Instala la revisión actual del servicio.
    Write-Host "[2/4] Instalando Agent Control Hub en el entorno local..." -ForegroundColor Cyan
    # Actualiza pip dentro del entorno aislado.
    & $PythonExecutable -m pip install --upgrade pip
    # Detiene el proceso cuando pip falla.
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo actualizar pip dentro del entorno virtual."
    }
    # Instala el paquete editable desde el repositorio.
    & $PythonExecutable -m pip install --editable $ServiceRoot
    # Detiene el proceso cuando la instalación falla.
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar Agent Control Hub."
    }

    # Prepara la carpeta pública seleccionada.
    Write-Host "[3/4] Preparando la vista web protegida en $WebRoot..." -ForegroundColor Cyan
    # Crea la carpeta cuando todavía no existe.
    New-Item -Path $WebRoot -ItemType Directory -Force | Out-Null
    # Copia únicamente el documento público versionado.
    Copy-Item -LiteralPath $ViewerSource -Destination $ViewerTarget -Force

    # Inicializa la referencia al servidor auxiliar.
    $ViewerProcess = $null
    # Configura WAMP solo cuando se solicita expresamente.
    if ($UseWamp) {
        # Agrupa los parámetros de validación de Apache.
        $SecurityParameters = @{
            SecuritySource = $ViewerSecuritySource
            WebRoot = $WebRoot
            SkipNetworkIsolationCheck = $SkipNetworkIsolationCheck
        }
        # Instala la política y comprueba la exposición de red.
        Install-AgentControlViewerSecurity @SecurityParameters
        # Conserva la URL histórica validada.
        $PreviewUrl = "http://localhost/agent-control-hub/"
    } else {
        # Inicia el servidor propio enlazado únicamente a 127.0.0.1.
        $ViewerProcess = Start-AgentControlLoopbackViewer `
            -PythonExecutable $PythonExecutable `
            -WebRoot $WebRoot `
            -Port $ViewerPort
        # Construye la URL local independiente de Apache.
        $PreviewUrl = "http://127.0.0.1:$ViewerPort/"
    }

    # Abre el visor cuando no se ha desactivado expresamente.
    if (-not $DoNotOpenBrowser) {
        # Solicita a Windows abrir la URL segura.
        Start-Process $PreviewUrl
    }

    # Informa de las fuentes y destinos activos.
    Write-Host "[4/4] Leyendo datos reales de Codex y Hermes..." -ForegroundColor Cyan
    # Muestra la fuente local de Codex.
    Write-Host "Codex:  $HOME\.codex\sessions" -ForegroundColor DarkGray
    # Muestra la fuente local de Hermes.
    Write-Host "Hermes: $env:LOCALAPPDATA\hermes\state.db" -ForegroundColor DarkGray
    # Muestra el snapshot sanitizado.
    Write-Host "JSON:   $SnapshotPath" -ForegroundColor DarkGray
    # Muestra la URL segura seleccionada.
    Write-Host "Web:    $PreviewUrl" -ForegroundColor Green
    # Informa del modo de servidor activo.
    Write-Host (
        "Servidor: {0}" -f $(if ($UseWamp) { "WAMP validado" } else { "loopback propio" })
    ) -ForegroundColor DarkGray

    # Construye los argumentos del servicio mediante una lista cerrada.
    $ServiceArguments = @(
        "-m",
        "agent_control_hub.main",
        "--config",
        $ConfigPath,
        "--output",
        $SnapshotPath
    )
    # Añade el puerto serie únicamente cuando se proporciona.
    if (-not [string]::IsNullOrWhiteSpace($SerialPort)) {
        $ServiceArguments += @("--port", $SerialPort)
    }
    # Activa notificaciones salvo desactivación expresa.
    if (-not $DisableWindowsNotifications) {
        $ServiceArguments += "--notify-windows"
    }
    # Configura una ejecución única o persistente.
    if ($Once) {
        $ServiceArguments += "--once"
    } else {
        $ServiceArguments += @("--interval", $IntervalSeconds.ToString())
        Write-Host "Pulsa Ctrl+C para detener la actualización." -ForegroundColor Yellow
    }

    # Cambia temporalmente a la carpeta del servicio.
    Push-Location $ServiceRoot
    # Garantiza la limpieza del proceso auxiliar y de la carpeta actual.
    try {
        # Ejecuta el servicio con argumentos separados.
        & $PythonExecutable @ServiceArguments
    } finally {
        # Restaura la carpeta desde la que se inició el script.
        Pop-Location
        # Detiene únicamente el servidor iniciado por esta ejecución.
        if ($null -ne $ViewerProcess) {
            Stop-AgentControlLoopbackViewer -ViewerProcess $ViewerProcess
        }
    }
}
