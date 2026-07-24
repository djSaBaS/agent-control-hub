[CmdletBinding()]
param(
    # Recibe la carpeta publicada por WAMP.
    [string]$WebRoot = "C:\wamp64\www\agent-control-hub",
    # Recibe el intervalo entre capturas.
    [ValidateRange(1, 60)]
    [int]$IntervalSeconds = 5,
    # Permite generar una única captura.
    [switch]$Once,
    # Permite evitar que se abra el navegador.
    [switch]$DoNotOpenBrowser,
    # Permite desactivar los avisos nativos de Windows.
    [switch]$DisableWindowsNotifications,
    # Permite omitir únicamente la comprobación de exposición por IP local.
    [switch]$SkipNetworkIsolationCheck
)

# Detiene el script ante cualquier error no controlado.
$ErrorActionPreference = "Stop"

# Resuelve las rutas del repositorio y del servicio sin depender del directorio actual.
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
# Resuelve la carpeta del servicio Python.
$ServiceRoot = Join-Path $RepositoryRoot "service"
# Resuelve el visor HTML sanitizado.
$ViewerSource = Join-Path $RepositoryRoot "tools\pc-viewer\index.html"
# Resuelve la política Apache que limita el visor al propio equipo.
$ViewerSecuritySource = Join-Path $RepositoryRoot "tools\pc-viewer\.htaccess"
# Resuelve la configuración conjunta de Codex y Hermes.
$ConfigPath = Join-Path $ServiceRoot "config.codex-preview.json"
# Resuelve el entorno virtual aislado.
$VirtualEnvironment = Join-Path $ServiceRoot ".venv"
# Resuelve el ejecutable Python del entorno.
$PythonExecutable = Join-Path $VirtualEnvironment "Scripts\python.exe"
# Resuelve el snapshot publicado por el visor.
$SnapshotPath = Join-Path $WebRoot "snapshot.json"
# Resuelve el destino del HTML.
$ViewerTarget = Join-Path $WebRoot "index.html"
# Resuelve el destino de la política Apache.
$ViewerSecurityTarget = Join-Path $WebRoot ".htaccess"

# Busca un intérprete compatible sin exigir una versión menor concreta.
function Get-CompatiblePythonRuntime {
    # Define los intérpretes que se comprobarán en orden.
    $Candidates = @(
        # Prueba primero el comando Python del sistema.
        [PSCustomObject]@{
            Name = "python del sistema"
            Command = "python"
            PrefixArguments = @()
        },
        # Prueba después el lanzador para Python 3.13.
        [PSCustomObject]@{
            Name = "Python Launcher 3.13"
            Command = "py"
            PrefixArguments = @("-3.13")
        },
        # Prueba después el lanzador para Python 3.12.
        [PSCustomObject]@{
            Name = "Python Launcher 3.12"
            Command = "py"
            PrefixArguments = @("-3.12")
        },
        # Prueba finalmente el lanzador para Python 3.11.
        [PSCustomObject]@{
            Name = "Python Launcher 3.11"
            Command = "py"
            PrefixArguments = @("-3.11")
        }
    )

    # Recorre los candidatos hasta encontrar una versión soportada.
    foreach ($Candidate in $Candidates) {
        # Resuelve el comando sin detener el script cuando no exista.
        $ResolvedCommand = Get-Command $Candidate.Command -ErrorAction SilentlyContinue
        # Omite candidatos no instalados.
        if ($null -eq $ResolvedCommand) {
            continue
        }

        # Inicializa los argumentos de consulta de versión.
        $VersionArguments = @()
        # Añade los argumentos propios del lanzador.
        $VersionArguments += $Candidate.PrefixArguments
        # Añade el script mínimo que imprime la versión exacta.
        $VersionArguments += @(
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"
        )

        # Ejecuta la consulta sin publicar errores de candidatos incompatibles.
        $VersionText = & $ResolvedCommand.Source @VersionArguments 2>$null
        # Omite comandos que no hayan respondido correctamente.
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($VersionText)) {
            continue
        }

        # Intenta convertir la salida a una versión comparable.
        try {
            # Convierte el texto validado.
            $Version = [version]($VersionText.Trim())
        } catch {
            # Omite salidas que no sean versiones válidas.
            continue
        }

        # Acepta cualquier Python 3.11 o superior anterior a Python 4.
        if ($Version -ge [version]"3.11.0" -and $Version -lt [version]"4.0.0") {
            # Devuelve los datos necesarios para crear el entorno.
            return [PSCustomObject]@{
                Name = $Candidate.Name
                Executable = $ResolvedCommand.Source
                PrefixArguments = $Candidate.PrefixArguments
                Version = $Version
            }
        }
    }

    # Detiene la instalación cuando no existe un intérprete compatible.
    throw "No se ha encontrado Python 3.11 o superior. Ejecuta 'python --version' y comprueba que esté disponible en PATH."
}

# Comprueba si Apache publica el visor mediante una dirección IPv4 no local.
function Assert-ViewerIsLocalOnly {
    # Recibe la ruta relativa utilizada por el visor.
    param(
        # Define la ruta HTTP que se probará en cada interfaz local.
        [string]$RelativePath = "agent-control-hub/"
    )

    # Recupera direcciones IPv4 utilizables distintas de loopback.
    $Addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        # Conserva únicamente direcciones preferidas y no locales.
        Where-Object {
            $_.AddressState -eq "Preferred" -and
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -ne "0.0.0.0"
        } |
        # Elimina direcciones duplicadas.
        Select-Object -ExpandProperty IPAddress -Unique

    # Informa cuando el equipo no tiene una interfaz de red comprobable.
    if ($null -eq $Addresses -or @($Addresses).Count -eq 0) {
        # Mantiene la ejecución porque no existe una superficie de red detectada.
        Write-Host "No se detectaron direcciones IPv4 de red para comprobar WAMP." -ForegroundColor DarkYellow
        # Finaliza la comprobación.
        return
    }

    # Recorre cada dirección asignada al equipo.
    foreach ($Address in @($Addresses)) {
        # Construye una URL usando exclusivamente una dirección local detectada.
        $ProbeUrl = "http://${Address}/${RelativePath}"
        # Intenta recuperar el visor con un timeout breve.
        try {
            # Realiza la petición sin usar contenido almacenado en caché.
            $Response = Invoke-WebRequest \
                -Uri $ProbeUrl \
                -UseBasicParsing \
                -TimeoutSec 2 \
                -MaximumRedirection 0 \
                -Headers @{ "Cache-Control" = "no-cache" }
            # Detiene el arranque cuando Apache devuelve contenido a la red local.
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300) {
                # Explica el riesgo y la forma de continuar tras corregir Apache.
                throw "SEGURIDAD: el visor responde desde $ProbeUrl. Activa AllowOverride para $WebRoot o limita Apache a localhost antes de continuar."
            }
        } catch {
            # Recupera una posible respuesta HTTP del error.
            $ErrorResponse = $_.Exception.Response
            # Continúa cuando Apache aplica correctamente la prohibición.
            if ($null -ne $ErrorResponse -and [int]$ErrorResponse.StatusCode -eq 403) {
                # Confirma la interfaz protegida.
                Write-Host "Visor protegido frente a $Address (HTTP 403)." -ForegroundColor Green
                # Continúa con la siguiente interfaz.
                continue
            }
            # Propaga expresamente el fallo de exposición generado arriba.
            if ($_.Exception.Message -like "SEGURIDAD:*") {
                # Conserva el mensaje completo de la comprobación.
                throw
            }
            # Informa de que la interfaz no respondió o no pudo verificarse.
            Write-Host "No se pudo publicar el visor mediante $Address; comprobación sin exposición confirmada." -ForegroundColor DarkGray
        }
    }
}

# Comprueba que el visor existe antes de modificar el entorno local.
if (-not (Test-Path -LiteralPath $ViewerSource)) {
    # Detiene una instalación incompleta.
    throw "No se encuentra el visor local en $ViewerSource"
}
# Comprueba que existe la política de seguridad del visor.
if (-not (Test-Path -LiteralPath $ViewerSecuritySource)) {
    # Evita publicar el visor sin la restricción local esperada.
    throw "No se encuentra la política Apache en $ViewerSecuritySource"
}
# Comprueba que existe la configuración de plataformas.
if (-not (Test-Path -LiteralPath $ConfigPath)) {
    # Detiene una instalación incompleta.
    throw "No se encuentra la configuración de plataformas en $ConfigPath"
}

# Crea un entorno Python aislado con cualquier versión compatible instalada.
if (-not (Test-Path -LiteralPath $PythonExecutable)) {
    # Informa del primer paso de preparación.
    Write-Host "[1/4] Preparando el entorno virtual de Python..." -ForegroundColor Cyan
    # Localiza un intérprete válido.
    $PythonRuntime = Get-CompatiblePythonRuntime
    # Muestra la versión sin exponer datos sensibles.
    Write-Host (
        "Python detectado: {0} ({1})" -f $PythonRuntime.Version, $PythonRuntime.Executable
    ) -ForegroundColor DarkGray

    # Elimina una creación anterior incompleta antes de volver a generar el entorno.
    if (Test-Path -LiteralPath $VirtualEnvironment) {
        # Borra únicamente el entorno local del servicio.
        Remove-Item -LiteralPath $VirtualEnvironment -Recurse -Force
    }

    # Inicializa los argumentos de creación del entorno.
    $VenvArguments = @()
    # Añade los argumentos del lanzador seleccionado.
    $VenvArguments += $PythonRuntime.PrefixArguments
    # Solicita la creación del entorno en la ruta conocida.
    $VenvArguments += @("-m", "venv", $VirtualEnvironment)
    # Ejecuta el intérprete seleccionado sin shell adicional.
    & $PythonRuntime.Executable @VenvArguments

    # Valida que el entorno se haya creado correctamente.
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $PythonExecutable)) {
        # Detiene una instalación parcial.
        throw "No se pudo crear el entorno virtual en $VirtualEnvironment"
    }
} else {
    # Consulta la versión del entorno ya existente.
    $ExistingVersion = & $PythonExecutable --version
    # Informa de que no se recreará el entorno.
    Write-Host "[1/4] Entorno virtual existente: $ExistingVersion" -ForegroundColor Cyan
}

# Instala o actualiza el paquete editable para utilizar el código de la rama actual.
Write-Host "[2/4] Instalando Agent Control Hub en el entorno local..." -ForegroundColor Cyan
# Actualiza pip dentro del entorno aislado.
& $PythonExecutable -m pip install --upgrade pip
# Detiene el proceso cuando pip no puede actualizarse.
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo actualizar pip dentro del entorno virtual."
}
# Instala el servicio desde la ruta local.
& $PythonExecutable -m pip install --editable $ServiceRoot
# Detiene el proceso cuando la instalación falla.
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo instalar Agent Control Hub en el entorno virtual."
}

# Prepara el directorio servido por WAMP y copia solo los archivos públicos esperados.
Write-Host "[3/4] Preparando la vista web protegida en $WebRoot..." -ForegroundColor Cyan
# Crea el directorio cuando todavía no existe.
New-Item -Path $WebRoot -ItemType Directory -Force | Out-Null
# Copia el visor HTML.
Copy-Item -LiteralPath $ViewerSource -Destination $ViewerTarget -Force
# Copia la política que restringe Apache al propio equipo.
Copy-Item -LiteralPath $ViewerSecuritySource -Destination $ViewerSecurityTarget -Force
# Comprueba la exposición por interfaces de red salvo omisión explícita.
if (-not $SkipNetworkIsolationCheck) {
    # Ejecuta una comprobación defensiva antes de iniciar la captura.
    Assert-ViewerIsLocalOnly
} else {
    # Deja constancia de que el usuario omitió una verificación de seguridad.
    Write-Host "AVISO: se ha omitido la comprobación de aislamiento de WAMP." -ForegroundColor Yellow
}

# Define la URL loopback del visor.
$PreviewUrl = "http://localhost/agent-control-hub/"
# Abre el visor cuando no se ha desactivado expresamente.
if (-not $DoNotOpenBrowser) {
    # Solicita a Windows abrir la URL local.
    Start-Process $PreviewUrl
}

# Ejecuta la misma aplicación que alimentará posteriormente el dispositivo físico.
Write-Host "[4/4] Leyendo datos reales de Codex y Hermes..." -ForegroundColor Cyan
# Muestra la fuente local de Codex.
Write-Host "Codex:  $HOME\.codex\sessions" -ForegroundColor DarkGray
# Muestra la fuente local de Hermes.
Write-Host "Hermes: $env:LOCALAPPDATA\hermes\state.db" -ForegroundColor DarkGray
# Muestra el snapshot público sanitizado.
Write-Host "JSON:   $SnapshotPath" -ForegroundColor DarkGray
# Muestra la URL loopback.
Write-Host "Web:    $PreviewUrl" -ForegroundColor DarkGray
# Explica cómo detener un bucle persistente.
if (-not $Once) {
    Write-Host "Pulsa Ctrl+C para detener la actualización." -ForegroundColor Yellow
}

# Construye los argumentos comunes del servicio.
$ServiceArguments = @(
    # Ejecuta el módulo principal.
    "-m",
    # Identifica el punto de entrada.
    "agent_control_hub.main",
    # Solicita la configuración real.
    "--config",
    # Entrega la ruta de configuración.
    $ConfigPath,
    # Solicita publicación del snapshot.
    "--output",
    # Entrega la ruta de salida.
    $SnapshotPath
)
# Activa notificaciones nativas salvo desactivación explícita.
if (-not $DisableWindowsNotifications) {
    # Solicita globos cuando una cuota se restaura realmente.
    $ServiceArguments += "--notify-windows"
}
# Configura una ejecución única o persistente.
if ($Once) {
    # Solicita una sola captura.
    $ServiceArguments += "--once"
} else {
    # Añade el intervalo validado.
    $ServiceArguments += @("--interval", $IntervalSeconds.ToString())
}

# Cambia temporalmente a la carpeta del servicio.
Push-Location $ServiceRoot
# Garantiza que la carpeta inicial se restaure al finalizar.
try {
    # Ejecuta el servicio con argumentos separados.
    & $PythonExecutable @ServiceArguments
} finally {
    # Restaura siempre la carpeta anterior.
    Pop-Location
}
