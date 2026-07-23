# Protocolo Agent Control Device 1.0

## Transporte

- USB serie.
- 115200 baudios.
- Codificación UTF-8.
- Un objeto JSON por línea.
- Terminador `\n`.

## Mensaje `snapshot`

Los consumidores de la versión 1.0 deben ignorar campos desconocidos. Los campos de telemetría ampliada son opcionales para mantener compatible el firmware existente.

```json
{
  "protocol_version": "1.0",
  "type": "snapshot",
  "generated_at": "2026-07-23T20:07:15+00:00",
  "total_cost_today": 0,
  "platforms": [
    {
      "platform_id": "codex",
      "display_name": "OpenAI Codex",
      "status": "waiting",
      "status_reason": "usage_limit_exceeded",
      "status_message": "Límite de uso agotado",
      "active_agents": 0,
      "agents": [],
      "session": {
        "session_id": "session-sanitizada",
        "started_at": "2026-06-29T07:29:10+00:00",
        "last_activity_at": "2026-07-23T20:07:15+00:00",
        "originator": "Codex Desktop",
        "source": "vscode",
        "cli_version": "0.142.3",
        "model_provider": "openai",
        "source_reference": "2026/06/29/rollout-session.jsonl"
      },
      "project": {
        "display_name": "Agent Control Hub",
        "path_alias": "Agent Control Hub",
        "repository": null,
        "branch": null,
        "dirty_files": null
      },
      "task": {
        "display_name": "Ampliar la telemetría real",
        "status": "waiting",
        "activity": "Esperando el reinicio de la cuota",
        "started_at": "2026-07-23T19:58:00+00:00",
        "last_activity_at": "2026-07-23T20:07:15+00:00"
      },
      "recent_activity": [],
      "usage_breakdown": {
        "thread_total": null,
        "last_request": null,
        "model_context_window": 258400,
        "context_used_pct_estimated": 61.84,
        "context_used_is_estimated": true
      },
      "rate_limits": null
    }
  ]
}
```

## Valores de estado

- `idle`: fuente disponible sin tarea activa ni bloqueo.
- `working`: tarea o herramienta en ejecución.
- `waiting`: ejecución detenida por una condición recuperable.
- `completed`: tarea terminada correctamente.
- `error`: error relevante de tarea o herramienta.
- `offline`: fuente local no disponible.

## Actividad reciente

Cada elemento de `recent_activity` puede contener:

- `activity_type`: tarea, comando, prueba, parche, calidad, Git, progreso, límite o error.
- `label`: descripción breve y sanitizada.
- `status`: estado de la actividad.
- `summary`: resultado reducido, nunca la salida completa.
- `timestamp`: fecha UTC del evento.
- `duration_seconds`: duración cuando la fuente la informa.
- `tool_name`: nombre de herramienta sin argumentos.

## Consumo

- `token_usage`: acumulado del hilo conservado por compatibilidad.
- `usage_breakdown.thread_total`: acumulado completo del hilo.
- `usage_breakdown.last_request`: consumo de la última petición.
- `context_used_pct_estimated`: estimación, no dato oficial.
- `rate_limits`: cuota oficial informada por Codex.

## Datos desconocidos

Un valor no disponible se envía como `null`. Una lista sin elementos se envía como `[]`. No se sustituyen datos desconocidos por estimaciones salvo que el nombre del campo indique expresamente `estimated`.

## Compatibilidad

Los campos nuevos son opcionales dentro de la versión 1.x. Un cambio incompatible incrementará `protocol_version` a `2.0`.
