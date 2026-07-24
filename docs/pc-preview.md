# Vista en PC con datos reales de Codex y Hermes

## Flujo comprobado

```text
%USERPROFILE%\.codex\sessions\rollout-*.jsonl
                         ↓
                  CodexAdapter
                         ↓
                  SnapshotService
                         ↑
                  HermesAdapter
                         ↑
%LOCALAPPDATA%\hermes\state.db
                         ↓
              snapshot.json sanitizado
                         ↓
                 Visor web local
```

Los JSONL y la base SQLite originales no se copian a WAMP. Solo se publica el modelo normalizado, sanitizado y limitado.

## Información principal

El visor prioriza la información operativa:

- Estado real: inactivo, trabajando, esperando, completado, error o sin conexión.
- Causa del estado y mensaje breve.
- Proyecto reducido a un alias seguro cuando la fuente contiene `cwd`.
- Sesión, origen y última actividad.
- Conversación o título oficial cuando la fuente lo incluye.
- Objetivo o última solicitud separados del título de conversación.
- Actividad actual separada del último resultado.
- Pendiente o bloqueo operativo cuando existe evidencia explícita.
- Actividad reciente: herramientas, comandos, parches, pruebas, resultados y errores.
- Modelo y proveedor asociados a la sesión.
- Estado del gateway, contadores operativos, cron y coste cuando la plataforma los ofrece.
- Cuotas y fecha de reinicio cuando existe una fuente oficial.

La tarea principal no se presenta como subagente. Los agentes permanecen vacíos hasta que existan eventos o sesiones hijas que permitan identificarlos sin inferencias.

## Codex

### Conversación, objetivo y resultado

El modelo `TaskInfo` diferencia cinco conceptos:

- `conversation_name`: título breve informado por Codex cuando existe.
- `objective`: objetivo persistente y sanitizado del hilo.
- `activity`: estado operativo actual, por ejemplo ejecutar una herramienta o esperar cuota.
- `last_result`: último resultado técnico útil anterior al estado actual.
- `pending`: bloqueo o trabajo pendiente declarado explícitamente.

La prioridad del nombre visible es:

1. Título oficial de conversación.
2. Primera frase del objetivo como título determinista.
3. Último mensaje real del usuario.
4. Objetivo útil o actualización del agente como compatibilidad.

Los envoltorios internos que contienen frases como `Continue working toward the active thread goal` no se consideran mensajes del usuario. El adaptador extrae únicamente el contenido de `<objective>...</objective>` o el argumento `objective` de herramientas `create_goal` y `update_goal`.

Un límite agotado modifica el estado actual, pero no sustituye `last_result`. Así el visor puede mostrar a la vez que Codex está esperando cuota y que la última regresión terminó correctamente.

### Consumo de Codex

El panel **Diagnóstico de consumo** separa:

- **Hilo acumulado:** todos los tokens declarados durante la vida completa del hilo.
- **Última petición:** tokens declarados para la última interacción con el modelo.
- **Contexto estimado:** porcentaje calculado a partir de los tokens de entrada de la última petición y la ventana máxima.
- **Cuota:** porcentaje oficial consumido y fecha de reinicio.

El contexto es una estimación y aparece identificado como tal. El acumulado del hilo no se denomina contexto ni consumo diario.

`tokens_today` permanece como `null` porque el JSONL no permite asegurar qué parte del acumulado pertenece al día actual.

### Lectura incremental de Codex

Cada archivo mantiene un cursor en memoria con:

- Identificador del archivo.
- Tamaño y fecha de modificación.
- Último byte procesado.
- Fragmento pendiente de una línea incompleta.
- Estado agregado de la sesión.

Después del primer análisis solo se leen los bytes añadidos. Si el archivo se trunca, se sustituye o rota, el estado se reconstruye desde el principio. La actividad se limita a doce elementos y las líneas JSON excesivamente grandes se omiten para proteger la memoria.

### Máquina de estados de Codex

- `task_started` activa `working`.
- Una herramienta sin resultado mantiene `working` con `status_reason: tool_running`.
- `task_complete` sin error produce `completed`.
- `task_complete.error.codex_error_info: usage_limit_exceeded` produce `waiting`.
- Un fallo explícito de tarea o herramienta produce `error`.
- `idle` solo se utiliza cuando no existe tarea activa, bloqueo ni fallo.
- `offline` indica que la carpeta local de sesiones no está disponible o que Codex no puede detectarse sin sesiones.

## Hermes

### Fuente SQLite

`HermesAdapter` localiza la carpeta de datos en este orden:

1. Variable `HERMES_HOME`.
2. `%LOCALAPPDATA%\hermes` en Windows.
3. `~/.hermes` como alternativa portable.

La base `state.db` se abre mediante una URI SQLite con `mode=ro`. Además se ejecuta `PRAGMA query_only = ON`. La conexión es efímera y compatible con el modo WAL utilizado por Hermes Desktop.

El adaptador no consulta ni publica:

- `.env`.
- `auth.json`.
- `config.yaml`.
- `system_prompt`.
- Razonamiento y campos internos de razonamiento.
- Argumentos completos de herramientas.

### Información extraída de Hermes

De la sesión no archivada con actividad más reciente se obtienen:

- Identificador y título real.
- Origen TUI o plataforma declarada.
- Modelo y proveedor guardados en `model_config`.
- Inicio y última actividad.
- Proyecto desde `cwd`, reducido al último segmento.
- Contadores de mensajes, herramientas y llamadas API.
- Tokens de entrada, salida, caché, escritura de caché y razonamiento.
- Coste estimado o real y su estado.
- Última solicitud y última respuesta sanitizadas.
- Nombres de herramientas recientes sin argumentos.

El cambio temporal de modelo queda aislado por sesión. El visor muestra el modelo almacenado en la sesión seleccionada y no el último modelo probado globalmente.

### Estado de Hermes

- El último mensaje de usuario sin respuesta posterior produce `working`.
- Una respuesta con herramientas pendientes produce `working` con `tool_running`.
- Un resultado de herramienta pendiente de continuación produce `working`.
- Una respuesta final reciente produce `completed`.
- Una respuesta final antigua mantiene la sesión como `idle`.
- Un error de handoff o cierre con error produce `error`.
- La ausencia de `state.db` produce `offline`.

El estado del gateway se consulta mediante `hermes gateway status`, sin shell, con un tiempo máximo de tres segundos y una caché de treinta segundos. El gateway detenido no convierte Hermes en `offline`; solo indica que la integración de mensajería no está activa.

### Contexto de Hermes

El acumulado de tokens de sesión procede directamente de `state.db`. La caché se muestra como parte diferenciada de la entrada y no se suma dos veces al total.

La ventana máxima del modelo se lee de forma opcional desde `context_length_cache.yaml`. El contexto usado no se estima porque `state.db` no contiene una métrica exacta equivalente a la barra de la interfaz TUI.

## Seguridad común

Antes de publicar texto se eliminan o sustituyen:

- Rutas absolutas de Windows, Linux o macOS.
- Correos electrónicos.
- URLs.
- Tokens con formato `sk-*`.
- Valores asociados a claves, contraseñas y secretos.
- Marcado interno y textos excesivamente largos.

El visor muestra un máximo acotado de texto por tarea y actividad. No procesa ni publica contenido de razonamiento.

## Ejecución recomendada con WAMP

Desde la raíz del repositorio:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-codex-preview.ps1
```

El nombre del script se conserva por compatibilidad, pero ahora:

1. Prepara `service\.venv` con Python 3.11 o superior.
2. Instala el servicio en modo editable.
3. Copia el visor a `C:\wamp64\www\agent-control-hub`.
4. Lee Codex y Hermes cada cinco segundos.
5. Actualiza `snapshot.json` de forma atómica.
6. Abre `http://localhost/agent-control-hub/`.

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
