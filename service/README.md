# Agent Control Service

Servicio local de Agent Control Hub. Consulta plataformas mediante adaptadores, normaliza su estado y transmite instantáneas NDJSON a un dispositivo físico o a un archivo local.

## Prueba con datos reales de Codex

Desde la raíz del repositorio en Windows:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-codex-preview.ps1
```

El comando lee los eventos reales de `%USERPROFILE%\.codex\sessions`, actualiza un `snapshot.json` sanitizado y abre el visor local mediante WAMP.

La guía completa está en [`docs/pc-preview.md`](../docs/pc-preview.md).
