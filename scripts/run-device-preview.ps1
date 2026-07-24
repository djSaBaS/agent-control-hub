[CmdletBinding()]
param(
    # Recibe el puerto serie asignado por Windows al dispositivo.
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^COM\d+$')]
    [string]$Port,
    # Permite definir una carpeta pública alternativa.
    [AllowEmptyString()]
    [string]$WebRoot = "",
    # Recibe el puerto HTTP local del visor seguro.
    [ValidateRange(1024, 65535)]
    [int]$ViewerPort = 8765,
    # Recibe el intervalo de actualización del servicio.
    [ValidateRange(1, 60)]
    [int]$IntervalSeconds = 2,
    # Permite evitar la apertura automática del navegador.
    [switch]$DoNotOpenBrowser,
    # Permite desactivar los avisos nativos de Windows.
    [switch]$DisableWindowsNotifications,
    # Permite utilizar WAMP de forma explícita.
    [switch]$UseWamp,
    # Permite omitir únicamente la comprobación activa por IP en modo WAMP.
    [switch]$SkipNetworkIsolationCheck
)

# Detiene el script ante cualquier error no controlado.
$ErrorActionPreference = "Stop"
# Resuelve la raíz del repositorio desde la carpeta del script.
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
# Resuelve el lanzador común del servicio y el visor.
$PreviewServiceHelper = Join-Path $RepositoryRoot "scripts\preview-service.ps1"
# Comprueba que exista el lanzador común.
if (-not (Test-Path -LiteralPath $PreviewServiceHelper)) {
    # Evita continuar con una instalación incompleta.
    throw "No se encuentra el lanzador seguro en $PreviewServiceHelper"
}
# Carga la función de arranque segura.
. $PreviewServiceHelper

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

# Informa del dispositivo que recibirá la telemetría.
Write-Host "Agent Control Hub · dispositivo físico" -ForegroundColor Cyan
# Muestra el puerto serie validado.
Write-Host "M5Stack: $Port · 115200 baudios" -ForegroundColor Green

# Agrupa los parámetros sin construir comandos mediante texto.
$PreviewParameters = @{
    RepositoryRoot = $RepositoryRoot
    WebRoot = $WebRoot
    ViewerPort = $ViewerPort
    IntervalSeconds = $IntervalSeconds
    DoNotOpenBrowser = $DoNotOpenBrowser
    DisableWindowsNotifications = $DisableWindowsNotifications
    UseWamp = $UseWamp
    SkipNetworkIsolationCheck = $SkipNetworkIsolationCheck
    SerialPort = $Port
}
# Inicia el servicio, el visor loopback y la transmisión serie.
Invoke-AgentControlPreview @PreviewParameters
