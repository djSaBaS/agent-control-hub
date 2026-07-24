# Agent Control Hub

Controlador físico y servicio local para supervisar agentes de inteligencia artificial desde dispositivos M5Stack.

![Concepto de interfaz](docs/assets/interface-concept.png)

## Objetivo

Agent Control Hub reúne en una sola pantalla el estado de plataformas como Codex, GitHub Copilot, Hermes, OpenClaw, Qwen Code y otros agentes locales o remotos. El dispositivo muestra actividad, consumo, costes, límites y alertas sin obligar al usuario a mantener abierto un panel adicional.

También permitirá lanzar revisiones preconfiguradas sobre proyectos autorizados, por ejemplo:

- Revisar seguridad.
- Buscar posibles errores.
- Revisar documentación.
- Proponer mejoras futuras.
- Revisar pruebas y dependencias.
- Preparar una versión.

El proyecto se divide en dos piezas:

- **Agent Control Service**: servicio local modular que normaliza los datos de cada plataforma, aplica configuración y los envía por USB serie.
- **Firmware M5Stack**: interfaz física con resumen, consumo elevado, agentes, alertas, acciones y configuración local.

## Estado actual

La rama principal contiene el MVP técnico inicial. El desarrollo activo incorpora:

- Arquitectura desacoplada por adaptadores.
- Adaptador de demostración con datos simulados.
- Primer adaptador de detección de GitHub Copilot CLI.
- Configuración independiente por plataforma.
- Separación entre plataformas monitorizadas y visibles.
- Protocolo NDJSON versionado entre ordenador y dispositivo.
- Servicio Python ejecutable desde consola.
- Firmware mediante PlatformIO.
- Compilación prevista para M5Stack Core2 y familia CoreS3.
- Navegación portable mediante botones o pantalla táctil.
- Pruebas unitarias del protocolo, configuración y agregación.
- Flujo de integración continua para Python y firmware.

Los conectores reales se incorporarán de forma independiente. El proyecto no inventará datos cuando una plataforma no exponga cuota, coste, tokens o fecha de reinicio.

## Arquitectura

```text
Codex ───────────┐
GitHub Copilot ──┤
Hermes ──────────┤
OpenClaw ────────┤   Adaptadores       Modelo común       USB serie
Qwen/Alibaba ────┼───────────────► Agent Control Service ───────────► M5Stack
Otros ───────────┘
```

Consulta:

- [Arquitectura técnica](docs/architecture.md).
- [Especificación funcional](docs/product-spec.md).
- [Compatibilidad de hardware](docs/hardware-compatibility.md).
- [Protocolo del dispositivo](docs/protocol.md).

## Inicio rápido del servicio

Requiere Python 3.11 o superior.

```powershell
cd service
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
agent-control --once --mock
```

Para utilizar configuración por plataforma:

```powershell
copy config.example.json config.local.json
agent-control --config config.local.json --once
```

Para transmitir datos a un dispositivo conectado:

```powershell
agent-control --config config.local.json --port COM5
```

## Configuración de plataformas

Cada plataforma puede controlar de forma independiente:

- Carga del conector.
- Monitorización.
- Visibilidad en el dispositivo.
- Alertas.
- Lanzamiento de acciones.

Las credenciales no se incluyen en el archivo del dispositivo ni se envían al microcontrolador.

## Compilar el firmware

Requiere Visual Studio Code con PlatformIO o PlatformIO CLI.

### M5Stack Core2

```powershell
cd firmware/core2
pio run -e m5stack-core2
pio run -e m5stack-core2 --target upload
pio device monitor --baud 115200
```

### CoreS3, CoreS3 SE o CoreS3 Lite

```powershell
cd firmware/core2
pio run -e m5stack-cores3
pio run -e m5stack-cores3 --target upload
pio device monitor --baud 115200
```

El nombre actual del directorio se conserva temporalmente por compatibilidad. La lógica de aplicación será común y las diferencias permanecerán en la capa de hardware.

## Principios del proyecto

- Los datos oficiales se diferencian siempre de las estimaciones.
- Las credenciales permanecen en el ordenador y nunca se envían al microcontrolador.
- El firmware no conoce detalles internos de cada plataforma.
- Los conectores pueden activarse, ocultarse o limitarse de forma independiente.
- El modo demostración permite desarrollar la interfaz sin cuentas reales.
- El dispositivo debe seguir siendo útil aunque una integración deje de funcionar.
- Las acciones iniciadas desde el dispositivo usan solo análisis por defecto.
- Las operaciones destructivas no se ofrecen desde el dispositivo.

## Hardware objetivo

Primera versión:

- M5Stack Core2.
- Cable USB-C.
- Ordenador Windows con el servicio local.

Versiones compatibles previstas:

- M5Stack CoreS3.
- M5Stack CoreS3 Lite.
- M5Stack CoreS3 SE.
- PCB propia basada en ESP32-S3.

CoreS3 SE es el candidato preferente para una pequeña serie comercial, acompañado de una base propia con botones, encoder y LED.

## Licencia

Apache License 2.0. Consulta [LICENSE](LICENSE).
