[CmdletBinding()]
param(
    # Permite definir una carpeta pública alternativa.
    [AllowEmptyString()]
    [string]$WebRoot = "",
    # Recibe el puerto HTTP local del visor seguro.
    [ValidateRange(1024, 65535)]
    [int]$ViewerPort = 8765,
    # Recibe el intervalo entre capturas.
    [ValidateRange(1, 60)]
    [int]$IntervalSeconds = 5,
    # Permite generar una única captura.
    [switch]$Once,
    # Permite evitar que se abra el navegador.
    [switch]$DoNotOpenBrowser,
    # Permite desactivar los avisos nativos de Windows.
    [switch]$DisableWindowsNotifications,
    # Permite utilizar WAMP de forma explícita.
    [switch]$UseWamp,
    # Permite omitir únicamente la comprobación activa por IP en modo WAMP.
    [switch]$SkipNetworkIsolationCheck
)

# Detiene el script ante errores no controlados.
$ErrorActionPreference = "Stop"
# Resuelve la raíz del repositorio desde la ubicación del script.
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
# Agrupa los parámetros sin construir comandos mediante texto.
$PreviewParameters = @{
    RepositoryRoot = $RepositoryRoot
    WebRoot = $WebRoot
    ViewerPort = $ViewerPort
    IntervalSeconds = $IntervalSeconds
    Once = $Once
    DoNotOpenBrowser = $DoNotOpenBrowser
    DisableWindowsNotifications = $DisableWindowsNotifications
    UseWamp = $UseWamp
    SkipNetworkIsolationCheck = $SkipNetworkIsolationCheck
}
# Inicia Agent Control Hub con servidor loopback por defecto.
Invoke-AgentControlPreview @PreviewParameters
