# Detiene el helper ante errores de programación o parámetros inválidos.
$ErrorActionPreference = "Stop"

# Comprueba si Apache publica el visor mediante una dirección IPv4 no local.
function Assert-AgentControlViewerIsLocalOnly {
    [CmdletBinding()]
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
        # Mantiene la ejecución porque no existe una superficie IPv4 detectada.
        Write-Host "No se detectaron direcciones IPv4 de red para comprobar WAMP." -ForegroundColor DarkYellow
        # Finaliza la comprobación.
        return
    }

    # Recorre cada dirección asignada al equipo.
    foreach ($Address in @($Addresses)) {
        # Construye una URL usando exclusivamente una dirección local detectada.
        $ProbeUrl = "http://${Address}/${RelativePath}"
        # Prepara los parámetros sin interpolar contenido externo en un comando.
        $RequestParameters = @{
            Uri = $ProbeUrl
            UseBasicParsing = $true
            TimeoutSec = 2
            MaximumRedirection = 0
            Headers = @{ "Cache-Control" = "no-cache" }
            ErrorAction = "Stop"
        }
        # Intenta recuperar el visor con un timeout breve.
        try {
            # Realiza la petición sin contenido almacenado en caché.
            $Response = Invoke-WebRequest @RequestParameters
            # Detiene el arranque cuando Apache devuelve contenido a la red local.
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 300) {
                # Explica el riesgo y la forma de continuar tras corregir Apache.
                throw "SEGURIDAD: el visor responde desde $ProbeUrl. Activa AllowOverride para el directorio del visor o limita Apache a localhost antes de continuar."
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
            Write-Host "La interfaz $Address no publicó el visor durante la comprobación." -ForegroundColor DarkGray
        }
    }
}

# Copia la política Apache y comprueba el aislamiento de red.
function Install-AgentControlViewerSecurity {
    [CmdletBinding()]
    param(
        # Recibe el archivo .htaccess versionado en el repositorio.
        [Parameter(Mandatory = $true)]
        [string]$SecuritySource,
        # Recibe la carpeta publicada por Apache.
        [Parameter(Mandatory = $true)]
        [string]$WebRoot,
        # Permite omitir solo la comprobación activa de red.
        [switch]$SkipNetworkIsolationCheck
    )

    # Comprueba que la política exista antes de publicar el visor.
    if (-not (Test-Path -LiteralPath $SecuritySource)) {
        # Evita continuar con una instalación incompleta.
        throw "No se encuentra la política Apache en $SecuritySource"
    }

    # Resuelve el archivo de destino dentro del directorio servido.
    $SecurityTarget = Join-Path $WebRoot ".htaccess"
    # Copia la política versionada y sustituye una versión anterior.
    Copy-Item -LiteralPath $SecuritySource -Destination $SecurityTarget -Force

    # Ejecuta la comprobación salvo omisión explícita del usuario.
    if (-not $SkipNetworkIsolationCheck) {
        # Verifica que ninguna dirección IPv4 local reciba una respuesta correcta.
        Assert-AgentControlViewerIsLocalOnly
    } else {
        # Deja constancia visible de la comprobación omitida.
        Write-Host "AVISO: se ha omitido la comprobación de aislamiento de WAMP." -ForegroundColor Yellow
    }
}
