# Protocolo Agent Control Device 1.0

## Transporte

- USB serie.
- 115200 baudios.
- Codificación UTF-8.
- Un objeto JSON por línea.
- Terminador `\n`.

## Mensaje `snapshot`

```json
{
  "protocol_version": "1.0",
  "type": "snapshot",
  "generated_at": "2026-07-22T10:00:00+00:00",
  "total_cost_today": 1.42,
  "platforms": [
    {
      "platform_id": "codex",
      "display_name": "Codex",
      "status": "working",
      "tokens_today": 184200,
      "cost_today": null,
      "weekly_remaining_pct": 30,
      "rolling_remaining_pct": 72,
      "next_reset_at": "2026-07-29T13:28:00+00:00",
      "active_agents": 1,
      "agents": [
        {
          "agent_id": "seo-python",
          "display_name": "SEO Python",
          "status": "working",
          "task_name": "Herramienta SEO",
          "started_at": "2026-07-22T08:15:00+00:00"
        }
      ]
    }
  ]
}
```

## Valores de estado

- `idle`
- `working`
- `waiting`
- `completed`
- `error`
- `offline`

## Datos desconocidos

Un valor no disponible debe enviarse como `null`. El firmware mostrará `--` o `No disponible`.

## Compatibilidad

Los campos nuevos serán opcionales dentro de una misma versión mayor. Un cambio incompatible incrementará `protocol_version` a `2.0`.
