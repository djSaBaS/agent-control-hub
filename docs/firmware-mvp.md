# Firmware MVP multiplaforma

## Alcance

El firmware físico muestra la misma información operativa que el servicio local, pero adaptada a una pantalla de 320 × 240 píxeles:

- Hasta cuatro plataformas visibles.
- Estado operativo por plataforma.
- Proyecto, conversación, objetivo, actividad y último resultado.
- Modelo activo y próxima fecha de reinicio.
- Hasta tres actividades recientes por plataforma.
- Diagnóstico de conexión USB y antigüedad del snapshot.
- Alertas emergentes deduplicadas mediante `alert_id`.

El dispositivo no recibe credenciales, prompts completos, razonamiento ni rutas privadas.

## Navegación

Los tres controles inferiores del Core2 y las tres zonas táctiles inferiores utilizan la misma distribución:

| Control | Función |
|---|---|
| A / izquierda | Plataforma anterior |
| B / centro | Abrir o avanzar de vista |
| C / derecha | Plataforma siguiente |

La acción central recorre estas vistas:

```text
Resumen → Detalle → Actividad → Sistema → Resumen
```

Durante una alerta, cualquier control la cierra y restaura la pantalla anterior.

## Compilar y grabar

### M5Stack Core2

```powershell
cd C:\dev\agent-control-hub\firmware\core2
pio run -e m5stack-core2
pio run -e m5stack-core2 --target upload
pio device monitor --baud 115200
```

### M5Stack CoreS3

```powershell
cd C:\dev\agent-control-hub\firmware\core2
pio run -e m5stack-cores3
pio run -e m5stack-cores3 --target upload
pio device monitor --baud 115200
```

No debe mantenerse abierto el monitor serie cuando el servicio intenta utilizar el mismo puerto COM.

## Localizar el puerto COM

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
```

También puede consultarse desde Administrador de dispositivos → Puertos (COM y LPT).

## Iniciar el servicio y el dispositivo

Después de grabar el firmware y cerrar el monitor serie:

```powershell
cd C:\dev\agent-control-hub
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\run-device-preview.ps1 -Port COM5
```

Debe sustituirse `COM5` por el puerto real.

El script mantiene simultáneamente:

- Captura local de Codex y Hermes.
- Consulta real de cuotas de Codex.
- Notificaciones de Windows.
- Publicación del visor en WAMP.
- Transmisión NDJSON al M5Stack.

## Prueba de aceptación

1. Iniciar el servicio con Codex y Hermes visibles.
2. Confirmar que el resumen muestra ambas plataformas.
3. Cambiar entre plataformas mediante A y C.
4. Abrir Detalle, Actividad y Sistema mediante B.
5. Ejecutar una herramienta de Hermes durante al menos quince segundos.
6. Confirmar la transición `working → completed`.
7. Desconectar el servicio y comprobar el indicador rojo tras quince segundos.
8. Reiniciar el servicio y comprobar la recuperación sin reiniciar el dispositivo.
9. Simular o esperar un evento `quota_restored`.
10. Confirmar alerta visual, señal sonora, cierre manual y ausencia de duplicados.

## Límites del MVP

- Transporte exclusivamente USB serie.
- Cuatro plataformas visibles como máximo.
- Tres actividades por plataforma.
- Un único aviso emergente simultáneo.
- Sin acciones remotas ni comandos desde el dispositivo.
- Sin Wi-Fi, modo reposo, encoder externo ni configuración persistente.
