# Vista en PC con datos reales de Codex

## Qué comprueba

Esta prueba utiliza la misma cadena que alimentará posteriormente al dispositivo físico:

```text
Archivos reales de Codex
        ↓
CodexAdapter
        ↓
SnapshotService
        ↓
snapshot.json sanitizado
        ↓
Visor web local
```

No utiliza el adaptador simulado. El conector lee eventos `token_count` de:

```text
%USERPROFILE%\.codex\sessions
```

Los archivos originales no se copian a WAMP. Solo se publica un JSON que contiene métricas normalizadas y una ruta relativa de referencia.

## Datos obtenidos

Cuando Codex los haya registrado, se muestran:

- Tokens de entrada acumulados en la sesión.
- Tokens de entrada recuperados desde caché.
- Tokens escritos en caché.
- Tokens de salida.
- Tokens de razonamiento.
- Tokens totales acumulados en la sesión.
- Tamaño de la ventana de contexto.
- Porcentaje utilizado y restante de la ventana corta.
- Porcentaje utilizado y restante de la ventana semanal.
- Fecha de reinicio de cada ventana.
- Tipo de plan informado por Codex.
- Fecha de actualización del consumo y de los límites.

`tokens_today` permanece como `null` porque el evento local representa un acumulado de sesión, no necesariamente todo el consumo del día.

## Diferencia entre consumo y límites

El adaptador busca dos eventos independientes:

1. El evento `token_count` más reciente para obtener el consumo de la sesión.
2. El evento más reciente que contenga ventanas `primary` o `secondary` completas.

Esto evita perder los últimos límites válidos cuando un evento posterior, por ejemplo de tipo `premium`, incluye créditos pero deja las ventanas en `null`.

Cuando los límites tienen más de treinta minutos, se marcan como antiguos. Siguen siendo datos reales, pero el visor solicita ejecutar una nueva tarea en Codex para refrescarlos.

## Ejecución recomendada con WAMP

Abre PowerShell en la raíz del repositorio y cambia a la rama de la prueba:

```powershell
git fetch origin
git switch feature/real-codex-usage-preview
git pull
```

Ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-codex-preview.ps1
```

El script:

1. Crea `service\.venv` con Python 3.11 cuando no existe.
2. Instala el servicio en modo editable.
3. Copia el visor a `C:\wamp64\www\agent-control-hub`.
4. Genera y actualiza `snapshot.json` cada cinco segundos.
5. Abre `http://localhost/agent-control-hub/`.

Detén el proceso mediante `Ctrl+C`.

## Captura única

Para generar una sola instantánea:

```powershell
.\scripts\run-codex-preview.ps1 -Once
```

Para utilizar otra carpeta web:

```powershell
.\scripts\run-codex-preview.ps1 `
    -WebRoot "D:\wamp\www\agent-control-hub" `
    -IntervalSeconds 10
```

## Ejecución sin WAMP

Desde `service`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --editable .
.\.venv\Scripts\python.exe -m agent_control_hub.main `
    --config .\config.codex-preview.json `
    --once `
    --output .\snapshot.json
```

El archivo puede abrirse con cualquier editor o formatearse en PowerShell:

```powershell
Get-Content .\snapshot.json |
    ConvertFrom-Json |
    ConvertTo-Json -Depth 20
```

## Interpretación de estados

- `status: idle`: se han encontrado datos o la CLI de Codex está instalada, pero el servicio todavía no determina si existe una tarea activa.
- `status: offline`: no se encontraron sesiones ni el comando `codex` en el sistema.
- `token_usage: null`: no existe todavía un evento `token_count` legible.
- `rate_limits: null`: no existe ningún evento con ventanas de cuota completas.
- `rate_limits.is_stale: true`: el límite es real, pero no ha sido actualizado recientemente.

## Seguridad

El JSON publicado no contiene:

- Prompts.
- Respuestas.
- Código de los proyectos.
- Tokens de autenticación.
- Cookies.
- La ruta absoluta del perfil de Windows.

WAMP debe mantenerse limitado al equipo o a una red de confianza. No se debe publicar la carpeta del visor directamente en Internet.
