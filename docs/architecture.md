# Arquitectura técnica

## 1. Componentes

### Agent Control Service

Proceso local que se ejecuta en Windows. Su responsabilidad es consultar plataformas, normalizar resultados, calcular agregados y transmitir instantáneas al dispositivo.

### Adaptadores

Cada plataforma implementa un adaptador independiente:

```text
CodexAdapter
HermesAdapter
OpenClawAdapter
QwenAdapter
MockAdapter
```

Un adaptador no puede escribir directamente en el puerto serie ni dibujar pantallas.

### Modelo común

Todos los adaptadores producen una `PlatformSnapshot`. El agregador compone una `DeviceSnapshot` con los datos globales.

### Transporte

La primera versión utiliza USB serie y mensajes NDJSON. Cada línea contiene un objeto JSON completo. Esto simplifica la depuración con un monitor serie y evita mantener estados parciales.

### Firmware

El firmware recibe instantáneas y decide qué dibujar. No almacena credenciales ni conoce las APIs de Codex, Hermes, OpenClaw o Alibaba.

## 2. Flujo

```text
Temporizador
   │
   ▼
SnapshotService
   │
   ├── CodexAdapter.collect()
   ├── HermesAdapter.collect()
   ├── OpenClawAdapter.collect()
   └── QwenAdapter.collect()
   │
   ▼
DeviceSnapshot
   │
   ▼
ProtocolEncoder
   │
   ▼
SerialTransport
   │
   ▼
M5Stack Core2
```

## 3. Seguridad

- Las claves permanecen en el almacén seguro del sistema operativo o en variables de entorno.
- El dispositivo solo recibe métricas y nombres sanitizados.
- Las acciones destructivas requieren confirmación explícita.
- El protocolo deberá incorporar autenticación si se añade transporte por red.
- Los registros no deben contener prompts completos por defecto.

## 4. Evolución prevista

La arquitectura permite sustituir el transporte USB por WebSocket, MQTT o Bluetooth sin modificar los adaptadores. También permite sustituir el Core2 por CoreS3 o una PCB propia manteniendo el modelo de datos.
