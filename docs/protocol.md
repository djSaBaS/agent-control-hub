# Protocolo Agent Control Device 1.0

## Transporte

- USB serie.
- 115200 baudios.
- Codificación UTF-8.
- Un objeto JSON por línea.
- Terminador `\n`.
- Tamaño máximo admitido por el firmware MVP: 64 KB por línea.

El firmware conserva el último snapshot válido cuando recibe JSON incompleto, una versión incompatible o un frame que supera el límite. Después de un frame excesivo descarta bytes hasta el siguiente salto de línea para recuperar la sincronización.

## Compatibilidad

La versión permanece en `1.0`. Los campos añadidos son opcionales y el firmware puede ignorarlos. Los campos anteriores `token_usage`, `rate_limits`, `weekly_remaining_pct`, `rolling_remaining_pct` y `next_reset_at` se mantienen.

Un valor no disponible se envía como `null`. No se inventan costes, cuotas, agentes ni porcentajes de progreso.

## Estado de plataforma

Los valores permitidos son:

- `idle`: plataforma disponible sin tarea activa ni bloqueo conocido.
- `working`: tarea activa o herramienta pendiente de resultado.
- `waiting`: la tarea necesita una condición externa; por ejemplo, cuota agotada.
- `completed`: la última tarea terminó correctamente.
- `error`: la última tarea o herramienta terminó con un fallo relevante.
- `offline`: la fuente local de sesiones no está disponible.

`status_reason` ofrece una causa estable para lógica de interfaz. `status_message` contiene una explicación breve y sanitizada.

## Telemetría operativa opcional

Cada plataforma puede añadir:

```json
{
  "status_reason": "usage_limit_exceeded",
  "status_message": "Límite de uso agotado; consulta el reinicio de cuota.",
  "session": {
    "session_id": "019f1248-2551-7381-a565-61bf092b5a3e",
    "started_at": "2026-06-29T07:29:10.895Z",
    "last_activity_at": "2026-07-23T20:07:15.661Z",
    "originator": "Codex Desktop",
    "source": "vscode",
    "cli_version": "0.142.3",
    "model_provider": "openai",
    "model_name": null
  },
  "project": {
    "display_name": "Prometeo 7.2 - 8.4",
    "cwd_alias": "Prometeo 7.2 - 8.4",
    "repository": null,
    "branch": null,
    "dirty_files": null
  },
  "task": {
    "display_name": "Revisar el módulo de alumnos",
    "conversation_name": null,
    "objective": "Revisar el módulo de alumnos antes de producción.",
    "status": "waiting",
    "activity": "Límite de uso agotado; consulta el reinicio de cuota.",
    "last_result": "174 de 174 rutas verificadas.",
    "pending": null,
    "started_at": "2026-07-23T20:07:10Z",
    "last_activity_at": "2026-07-23T20:07:15.661Z"
  },
  "recent_activity": [
    {
      "activity_type": "limit",
      "label": "Límite de uso agotado",
      "status": "waiting",
      "summary": "Límite de uso agotado; consulta el reinicio de cuota.",
      "timestamp": "2026-07-23T20:07:15.661Z"
    }
  ]
}
```

Las rutas completas, correos, URLs, secretos y prompts extensos se eliminan o sustituyen antes de construir estos modelos.

El firmware MVP conserva como máximo cuatro plataformas y tres actividades recientes por plataforma. El resto continúa disponible en el visor web, pero no se copia a la memoria visual del dispositivo.

## Alertas operativas

La raíz del snapshot puede incluir una colección `alerts` compatible hacia atrás:

```json
{
  "alerts": [
    {
      "alert_id": "codex-quota-restored-1784899200000000",
      "alert_type": "quota_restored",
      "platform_id": "codex",
      "title": "OpenAI Codex vuelve a estar disponible",
      "message": "La cuota se ha restablecido y ya puede volver a utilizarse.",
      "severity": "info",
      "created_at": "2026-07-24T12:00:00Z"
    }
  ]
}
```

`alert_id` es obligatorio para deduplicar. El servicio retiene cada evento durante dos minutos y el firmware guarda el último identificador mostrado. Una alerta nueva interrumpe la vista actual, reproduce una señal breve, permanece visible durante quince segundos y puede cerrarse mediante cualquier control. La vista anterior se restaura después del cierre.

El dispositivo no calcula el restablecimiento a partir de `resets_at`. Reacciona únicamente a eventos observados por el servicio, como `quota_restored`.

## Significado del consumo

`token_usage` se conserva por compatibilidad y representa el acumulado del hilo cuando `scope` vale `session_total`. No representa el contexto actual ni el consumo diario.

El bloque `usage` separa conceptos:

```json
{
  "usage": {
    "thread_total": {
      "scope": "session_total",
      "total_tokens": 1134025885
    },
    "last_request": {
      "scope": "last_request",
      "input_tokens": 166271,
      "total_tokens": 166717
    },
    "context_used_tokens_estimated": 166271,
    "context_used_percent_estimated": 64.35,
    "context_estimation_method": "last_request_input_tokens"
  }
}
```

- `thread_total`: acumulado histórico completo del hilo.
- `last_request`: consumo declarado para la última petición.
- `context_used_tokens_estimated`: estimación limitada a la ventana máxima del modelo.
- `context_used_percent_estimated`: estimación, nunca dato oficial.
- `context_estimation_method`: método utilizado para hacer explícita la estimación.

`tokens_today` sigue siendo `null` cuando la fuente local no permite separar el consumo del día.

## Límites

`rate_limits` conserva las últimas ventanas completas informadas por Codex. Un evento posterior con ventanas `null` no elimina el último valor oficial conocido.

- `used_percent` y `remaining_percent` proceden de la misma ventana.
- `window_minutes` identifica la duración real; la interfaz no debe asumir que `primary` siempre es una ventana corta.
- `resets_at` es la fecha oficial disponible.
- `is_stale` indica que la última actualización supera treinta minutos.

## Agentes

La tarea principal no se convierte automáticamente en un subagente. `active_agents` permanece en `0` y `agents` permanece vacío mientras los JSONL no incluyan eventos inequívocos de creación y estado de subagentes.
