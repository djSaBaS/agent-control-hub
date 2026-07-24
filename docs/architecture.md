# Arquitectura técnica

## 1. Componentes

### Agent Control Service

Proceso local que se ejecuta en Windows. Su responsabilidad es consultar plataformas, normalizar resultados, calcular agregados, aplicar reglas de seguridad y transmitir instantáneas al dispositivo.

### Adaptadores

Cada plataforma implementa un adaptador independiente:

```text
CodexAdapter
CopilotAdapter
HermesAdapter
OpenClawAdapter
QwenAdapter
MockAdapter
```

Un adaptador no puede escribir directamente en el puerto serie ni dibujar pantallas.

Cada adaptador declara además sus capacidades, por ejemplo:

```text
READ_AGENTS
READ_TASKS
READ_TOKENS
READ_QUOTA
READ_COST
READ_CONTEXT
LAUNCH_PROMPT
START_REMOTE_TASK
PAUSE_TASK
STOP_TASK
OPEN_DESKTOP
```

La interfaz solo ofrece las capacidades presentes en el conector activo.

### GitHub Copilot

GitHub Copilot se tratará como una plataforma independiente.

El conector podrá evolucionar en dos líneas:

1. Copilot CLI local para lanzar prompts, revisar código y consultar sesiones locales.
2. Copilot coding agent para iniciar y consultar tareas remotas asociadas a repositorios de GitHub.

El conector no asumirá que todas las licencias o políticas permiten ambas modalidades. Detectará las capacidades disponibles para la cuenta y ocultará las no autorizadas.

### Modelo común

Todos los adaptadores producen una `PlatformSnapshot`. El agregador compone una `DeviceSnapshot` con los datos globales.

Las métricas deberán conservar su calidad de origen:

```text
official
calculated
estimated
unavailable
```

### Configuración

La configuración del servicio define por plataforma:

```text
enabled
monitoring_enabled
visible_on_device
alerts_enabled
actions_enabled
```

La configuración compleja permanece en el ordenador. El dispositivo recibe solo información sanitizada y acciones autorizadas.

### Transporte

La primera versión utiliza USB serie y mensajes NDJSON. Cada línea contiene un objeto JSON completo. Esto simplifica la depuración con un monitor serie y evita mantener estados parciales.

### Firmware

El firmware recibe instantáneas y decide qué dibujar. No almacena credenciales ni conoce las APIs de Codex, GitHub Copilot, Hermes, OpenClaw o Alibaba.

El firmware se divide en dos capas:

```text
Application
├── protocolo
├── modelos de vista
├── navegación
├── pantallas
└── reglas visuales

Hardware abstraction
├── pantalla
├── entrada táctil o botones
├── vibración
├── sonido
├── batería
└── transporte USB
```

La capa de aplicación debe ser compartida por Core2, CoreS3, CoreS3 SE y CoreS3 Lite. Las diferencias se concentran en la capa de hardware y en la configuración de compilación.

## 2. Flujo de monitorización

```text
Temporizador
   │
   ▼
SnapshotService
   │
   ├── CodexAdapter.collect()
   ├── CopilotAdapter.collect()
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
M5Stack Core2 o CoreS3
```

## 3. Flujo de acciones rápidas

```text
Usuario selecciona plantilla
   │
   ▼
Dispositivo envía ActionRequest
   │
   ▼
ActionPolicy valida
   ├── plataforma autorizada
   ├── proyecto autorizado
   ├── modo permitido
   ├── presupuesto disponible
   └── confirmación requerida
   │
   ▼
PromptLibrary recupera el prompt local
   │
   ▼
Adapter ejecuta la acción
   │
   ▼
TaskSnapshot actualiza el dispositivo
```

El dispositivo nunca transmite un prompt completo ni un comando arbitrario.

## 4. Seguridad

- Las claves permanecen en el almacén seguro del sistema operativo o en variables de entorno.
- El dispositivo solo recibe métricas, identificadores y nombres sanitizados.
- Las acciones destructivas requieren confirmación explícita y no se habilitan por defecto.
- Las acciones iniciadas desde el dispositivo usan modo de solo análisis por defecto.
- El protocolo deberá incorporar autenticación si se añade transporte por red.
- Los registros no deben contener prompts completos por defecto.
- El servicio debe aplicar una lista explícita de proyectos y plantillas autorizadas.
- Los límites de coste o cuota se validan antes de iniciar una acción cuando el conector aporte esos datos.

## 5. Portabilidad de hardware

La resolución objetivo compartida es 320 × 240 píxeles. Core2 y la familia CoreS3 usan pantallas de esta resolución, por lo que el diseño visual puede reutilizarse.

Las diferencias principales son:

- Core2 utiliza ESP32 clásico y puerto USB serie mediante conversor.
- CoreS3 utiliza ESP32-S3 y USB CDC nativo.
- Core2 dispone de tres zonas capacitivas inferiores compatibles con `BtnA`, `BtnB` y `BtnC`.
- CoreS3 no ofrece los mismos tres controles físicos y debe usar zonas táctiles dibujadas o una base externa.
- La gestión de energía, batería, vibración y periféricos varía según el modelo.

La lógica de negocio, protocolo y pantallas no debe depender directamente de esos periféricos.

## 6. Evolución prevista

La arquitectura permite sustituir el transporte USB por WebSocket, MQTT o Bluetooth sin modificar los adaptadores. También permite sustituir el Core2 por CoreS3 o una PCB propia manteniendo el protocolo y el modelo de datos.
