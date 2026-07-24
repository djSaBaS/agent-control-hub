# Detiene el helper ante errores de programación o parámetros inválidos.
$ErrorActionPreference = "Stop"

# Inicia el servidor HTTP propio enlazado exclusivamente a 127.0.0.1.
function Start-AgentControlLoopbackViewer {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Low")]
    param(
        # Recibe el intérprete Python del entorno virtual del servicio.
        [Parameter(Mandatory = $true)]
        [string]$PythonExecutable,
        # Recibe la carpeta que contiene index.html y snapshot.json.
        [Parameter(Mandatory = $true)]
        [string]$WebRoot,
        # Recibe el puerto local utilizado por el navegador.
        [ValidateRange(1024, 65535)]
        [int]$Port = 8765
    )

    # Comprueba que el intérprete exista antes de iniciar un proceso auxiliar.
    if (-not (Test-Path -LiteralPath $PythonExecutable)) {
        # Evita un error posterior menos claro de Start-Process.
        throw "No se encuentra el intérprete Python en $PythonExecutable"
    }
    # Comprueba que la carpeta pública exista antes de abrir el puerto.
    if (-not (Test-Path -LiteralPath $WebRoot -PathType Container)) {
        # Detiene una instalación incompleta.
        throw "No existe la carpeta pública del visor en $WebRoot"
    }

    # Construye la URL de salud únicamente sobre loopback.
    $HealthUrl = "http://127.0.0.1:$Port/health"
    # Comprueba si ya existe un proceso escuchando en el puerto solicitado.
    $ExistingListener = Get-NetTCPConnection `
        -LocalPort $Port `
        -State Listen `
        -ErrorAction SilentlyContinue |
        # Conserva únicamente escuchas en loopback o en todas las interfaces.
        Where-Object {
            $_.LocalAddress -eq "127.0.0.1" -or
            $_.LocalAddress -eq "0.0.0.0" -or
            $_.LocalAddress -eq "::"
        } |
        # Solo necesitamos diagnosticar el primer proceso encontrado.
        Select-Object -First 1
    # Detiene el arranque cuando el puerto ya está ocupado.
    if ($null -ne $ExistingListener) {
        # Explica qué proceso debe cerrarse o qué puerto debe cambiarse.
        throw (
            "El puerto local $Port ya está ocupado por el proceso " +
            "$($ExistingListener.OwningProcess). Cierra ese proceso o utiliza -ViewerPort con otro valor."
        )
    }

    # Permite que -WhatIf muestre la acción sin iniciar procesos.
    if (-not $PSCmdlet.ShouldProcess("127.0.0.1:$Port", "Iniciar servidor HTTP local")) {
        # Finaliza sin modificar el estado del sistema.
        return
    }

    # Protege la ruta pública con comillas para Start-Process.
    $QuotedWebRoot = '"' + $WebRoot.Replace('"', '\"') + '"'
    # Construye una lista cerrada de argumentos para el módulo local.
    $ViewerArguments = @(
        # Ejecuta el módulo seguro incluido en el paquete.
        "-m",
        # Identifica el módulo HTTP local.
        "agent_control_hub.local_http",
        # Entrega la carpeta pública validada.
        "--directory",
        # Conserva espacios mediante comillas explícitas.
        $QuotedWebRoot,
        # Entrega el puerto local validado.
        "--port",
        # Convierte el puerto a texto para el proceso hijo.
        $Port.ToString()
    )

    # Inicia el servidor sin abrir una ventana de consola adicional.
    $ViewerProcess = Start-Process `
        -FilePath $PythonExecutable `
        -ArgumentList $ViewerArguments `
        -PassThru `
        -WindowStyle Hidden

    # Intenta confirmar que el servidor responde durante un máximo aproximado de cinco segundos.
    for ($Attempt = 1; $Attempt -le 50; $Attempt++) {
        # Comprueba si el proceso terminó antes de estar preparado.
        if ($ViewerProcess.HasExited) {
            # Informa del código de salida observado.
            throw "El servidor local terminó antes de iniciar. Código: $($ViewerProcess.ExitCode)"
        }
        # Intenta consultar la ruta de salud.
        try {
            # Realiza una petición breve únicamente contra loopback.
            $HealthResponse = Invoke-WebRequest `
                -Uri $HealthUrl `
                -UseBasicParsing `
                -TimeoutSec 1 `
                -ErrorAction Stop
            # Confirma que el servidor responde correctamente.
            if ($HealthResponse.StatusCode -eq 200) {
                # Devuelve el proceso para que el lanzador controle su cierre.
                return $ViewerProcess
            }
        } catch {
            # Registra únicamente en modo detallado el fallo transitorio esperado.
            Write-Verbose "El visor aún no responde: $($_.Exception.Message)"
        }
        # Espera cien milisegundos antes del siguiente intento.
        Start-Sleep -Milliseconds 100
    }

    # Cierra el proceso auxiliar cuando no llegó a estar preparado.
    Stop-AgentControlLoopbackViewer -ViewerProcess $ViewerProcess -Confirm:$false
    # Informa de que la ruta de salud no respondió a tiempo.
    throw "El servidor local no respondió en $HealthUrl"
}

# Detiene únicamente el proceso del visor iniciado por el lanzador actual.
function Stop-AgentControlLoopbackViewer {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "Low")]
    param(
        # Recibe el proceso devuelto por Start-AgentControlLoopbackViewer.
        [Parameter(Mandatory = $true)]
        [System.Diagnostics.Process]$ViewerProcess
    )

    # Evita actuar sobre un proceso que ya haya terminado.
    if ($ViewerProcess.HasExited) {
        # Finaliza sin generar errores innecesarios.
        return
    }
    # Permite que -WhatIf muestre la acción sin detener procesos.
    if (-not $PSCmdlet.ShouldProcess("PID $($ViewerProcess.Id)", "Detener servidor HTTP local")) {
        # Finaliza sin modificar el proceso.
        return
    }
    # Solicita la terminación del proceso auxiliar concreto.
    Stop-Process -Id $ViewerProcess.Id -Force -ErrorAction SilentlyContinue
    # Espera brevemente para liberar el puerto local.
    $ViewerProcess.WaitForExit(2000) | Out-Null
}
