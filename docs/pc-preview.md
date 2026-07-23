# Vista en PC con telemetría real de Codex

## Qué comprueba

Esta prueba utiliza la misma cadena de datos que alimentará posteriormente al dispositivo físico:

```text
Archivos JSONL reales de Codex
        ↓
CodexAdapter incremental
        ↓
SnapshotService
        ↓
snapshot.json sanitizado
        ↓
Visor web local
```

El adaptador lee las sesiones de:

```text
%USERPROFILE%\.codex\sessions
```

Los archivos originales no se copian a WAMP. Solo se publica el modelo normalizado, con referencias relativas y textos sanitizados.

## Información operativa

Cuando los eventos existen, el visor muestra primero:

- Estado de Codex: inactivo, trabajando, esperando, completado, error o desconectado.
- Motivo técnico del estado, por ejemplo `usage_limit_exceeded`.
- Proyecto obtenido de `session_meta.payload.cwd`, reducido al nombre de la carpeta.
- Tarea visible y actividad actual.
- Inicio de la sesión y última actividad.
- Herramientas, pruebas, parches, resultados y errores recientes.
- Límites oficiales y fecha de reinicio.

Los subagentes solo se publican cuando un evento explícito permite acreditarlos. Una tarea principal o una herramienta no se contabilizan como subagentes.

## Significado del consumo

El visor diferencia cuatro conceptos que no deben mezclarse:

| Campo | Significado |
|---|---|
| `usage_breakdown.thread_total` | Acumulado histórico de todo el hilo informado por `total_token_usage`. |
| `usage_breakdown.last_request` | Consumo de la última petición informado por `last_token_usage`. |
| `context_used_pct_estimated` | Estimación basada en la entrada de la última petición y la ventana del modelo. No es un porcentaje oficial de ocupación. |
| `rate_limits` | Cuota oficial de la cuenta y sus fechas de reinicio. |

`token_usage` se conserva por compatibilidad con los consumidores existentes y contiene el mismo acumulado que `usage_breakdown.thread_total`.

`tokens_today` permanece como `null`: los JSONL observados no garantizan un total diario completo.

## Máquina de estados

- `working`: se inició una tarea o existe una herramienta en ejecución.
- `completed`: Codex registró `task_complete`.
- `waiting`: la ejecución necesita esperar; `usage_limit_exceeded` utiliza este estado.
- `error`: una tarea o herramienta terminó con error relevante.
- `idle`: existe Codex o una sesión, pero no hay tarea activa ni bloqueo.
- `offline`: no existen sesiones legibles y tampoco está disponible el ejecutable configurado.

`status_reason` conserva el motivo normalizado. `status_message` contiene una explicación breve y publicable.

## Lectura incremental

Cada archivo se procesa completamente una sola vez. Después, el adaptador conserva:

- Offset de lectura.
- Firma inicial del archivo.
- Identidad del archivo.
- Fragmento final incompleto.
- Estado normalizado de la sesión.
- Hasta veinte actividades recientes.
- Hasta treinta y dos herramientas pendientes.

En las siguientes actualizaciones solo se leen los bytes añadidos. Si el archivo se trunca, se reemplaza o rota, el estado se reconstruye desde el principio.

## Ejecución recomendada con WAMP

Abre PowerShell en la raíz del repositorio:

```powershell
git fetch origin
git switch feature/real-codex-usage-preview
git pull --ff-only origin feature/real-codex-usage-preview
```

Ejecuta:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-codex-preview.ps1
```

El script:

1. Crea `service\.venv` con Python 3.11 o superior cuando no existe.
2. Instala el servicio en modo editable.
3. Copia el visor a `C:\wamp64\www\agent-control-hub`.
4. Genera `snapshot.json` de forma atómica cada cinco segundos.
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

## Seguridad

El JSON publicado no contiene deliberadamente:

- Prompts completos.
- Respuestas completas.
- Rutas absolutas de proyectos o perfiles.
- Comandos completos ni argumentos de herramientas.
- Correos detectados.
- Claves, tokens Bearer o credenciales reconocibles.
- Código de los proyectos.

Los textos visibles se limitan y sanitizan. WAMP debe mantenerse limitado al equipo o a una red de confianza.
