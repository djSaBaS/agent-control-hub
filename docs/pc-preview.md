# Vista en PC con datos reales de Codex

## Flujo comprobado

```text
%USERPROFILE%\.codex\sessions\rollout-*.jsonl
                         ↓
                  CodexAdapter
                         ↓
                  SnapshotService
                         ↓
              snapshot.json sanitizado
                         ↓
                 Visor web local
```

Los JSONL originales no se copian a WAMP. Solo se publica el modelo normalizado y una referencia relativa al archivo de origen.

## Información principal

El visor prioriza la información operativa:

- Estado real: inactivo, trabajando, esperando, completado, error o sin conexión.
- Causa del estado y mensaje breve.
- Proyecto obtenido desde `session_meta.payload.cwd`, reducido a un alias seguro.
- Sesión, origen, versión de la CLI y última actividad.
- Tarea visible derivada del último mensaje del usuario, objetivo útil o actualización del agente.
- Actividad reciente: herramientas, comandos, parches, pruebas, resultados y errores.
- Último resultado técnico disponible.
- Cuotas, duración de cada ventana y fecha de reinicio.

La tarea principal no se presenta como subagente. Los agentes permanecerán vacíos hasta que existan eventos explícitos que permitan identificarlos.

## Consumo

El panel **Diagnóstico de consumo** separa:

- **Hilo acumulado:** todos los tokens declarados durante la vida completa del hilo.
- **Última petición:** tokens declarados para la última interacción con el modelo.
- **Contexto estimado:** porcentaje calculado a partir de los tokens de entrada de la última petición y la ventana máxima.
- **Cuota:** porcentaje oficial consumido y fecha de reinicio.

El contexto es una estimación y aparece identificado como tal. El acumulado del hilo no se denomina contexto ni consumo diario.

`tokens_today` permanece como `null` porque el JSONL no permite asegurar qué parte del acumulado pertenece al día actual.

## Lectura incremental

Cada archivo mantiene un cursor en memoria con:

- Identificador del archivo.
- Tamaño y fecha de modificación.
- Último byte procesado.
- Fragmento pendiente de una línea incompleta.
- Estado agregado de la sesión.

Después del primer análisis solo se leen los bytes añadidos. Si el archivo se trunca, se sustituye o rota, el estado se reconstruye desde el principio. La actividad se limita a doce elementos y las líneas JSON excesivamente grandes se omiten para proteger la memoria.

## Máquina de estados

- `task_started` activa `working`.
- Una herramienta sin resultado mantiene `working` con `status_reason: tool_running`.
- `task_complete` sin error produce `completed`.
- `task_complete.error.codex_error_info: usage_limit_exceeded` produce `waiting`.
- Un fallo explícito de tarea o herramienta produce `error`.
- `idle` solo se utiliza cuando no existe tarea activa, bloqueo ni fallo.
- `offline` indica que la carpeta local de sesiones no está disponible o que Codex no puede detectarse sin sesiones.

## Seguridad

Antes de publicar texto se eliminan o sustituyen:

- Rutas absolutas de Windows, Linux o macOS.
- Correos electrónicos.
- URLs.
- Tokens con formato `sk-*`.
- Valores asociados a claves, contraseñas y secretos.
- Marcado interno y prompts extensos.

El visor muestra un máximo acotado de texto por tarea y actividad. No procesa ni publica contenido de razonamiento.

## Ejecución recomendada con WAMP

Desde la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-codex-preview.ps1
```

El script:

1. Prepara `service\.venv` con Python 3.11 o superior.
2. Instala el servicio en modo editable.
3. Copia el visor a `C:\wamp64\www\agent-control-hub`.
4. Actualiza `snapshot.json` cada cinco segundos.
5. Abre `http://localhost/agent-control-hub/`.

Detén el proceso mediante `Ctrl+C`.

## Captura única

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

El JSON puede revisarse en PowerShell:

```powershell
Get-Content .\snapshot.json |
    ConvertFrom-Json |
    ConvertTo-Json -Depth 30
```

WAMP debe permanecer limitado al equipo o a una red de confianza. La carpeta del visor no debe publicarse directamente en Internet.
