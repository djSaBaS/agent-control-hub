# Compatibilidad de hardware

## Resumen

Agent Control Hub debe mantener una única lógica de aplicación para M5Stack Core2 y la familia CoreS3.

La compatibilidad se divide en tres niveles:

| Componente | Reutilización prevista |
|---|---:|
| Servicio de Windows | 100 % |
| Adaptadores de plataformas | 100 % |
| Protocolo NDJSON | 100 % |
| Modelos de datos | 100 % |
| Diseño de pantallas 320 × 240 | 90-100 % |
| Navegación | 70-90 % |
| Entrada, energía, vibración y USB | Específica por hardware |

## Hardware objetivo

### M5Stack Core2

Uso previsto:

- Primer prototipo físico.
- Validación de pantallas y protocolo.
- Uso personal estable.

Características relevantes:

- ESP32 clásico.
- 16 MB de flash.
- 8 MB de PSRAM.
- Pantalla táctil de 320 × 240.
- Tres zonas capacitivas inferiores.
- USB serie mediante conversor.
- Batería y motor de vibración.

### M5Stack CoreS3

Uso previsto:

- Desarrollo de una segunda versión.
- Validación de USB CDC nativo.
- Prototipos con batería y base de expansión.

Características relevantes:

- ESP32-S3.
- 16 MB de flash.
- 8 MB de PSRAM.
- Pantalla táctil de 320 × 240.
- USB OTG y CDC.
- Batería en la base incluida.
- Sensores adicionales no necesarios para el MVP.

### M5Stack CoreS3 Lite

Uso previsto:

- Dispositivo compacto con batería.
- Posible producto personal o demostrador portátil.

Mantiene el mismo procesador, memoria, pantalla y tacto que CoreS3. Incluye batería y sensores que no son necesarios para Agent Control Hub, pero no impiden reutilizar el firmware.

### M5Stack CoreS3 SE

Uso previsto:

- Mejor candidato para una pequeña serie comercial.
- Montaje sobre una base propia con botones, encoder y LED.

Mantiene:

- ESP32-S3.
- 16 MB de flash.
- 8 MB de PSRAM.
- Pantalla táctil de 320 × 240.
- USB CDC y OTG.
- Altavoz, micrófonos, RTC y microSD.

Elimina cámara, IMU, magnetómetro, sensor de proximidad y batería. Estos componentes no son necesarios para el producto.

## Diferencias que requieren adaptación

### Entrada

Core2 permite usar `BtnA`, `BtnB` y `BtnC` mediante las zonas capacitivas inferiores.

CoreS3, CoreS3 Lite y CoreS3 SE deben utilizar:

- Zonas táctiles dibujadas en pantalla.
- Gestos táctiles.
- Botones conectados a una base externa.
- Encoder opcional.

La aplicación consumirá eventos abstractos:

```text
PREVIOUS
SELECT
NEXT
BACK
OPEN_ACTIONS
REFRESH
CONFIRM
```

Cada implementación de hardware traduce botones o gestos a esos eventos.

### USB

Core2 utiliza un puerto serie creado por el conversor USB integrado.

CoreS3 utiliza USB CDC nativo. El protocolo NDJSON no cambia; solo cambia la configuración de compilación y detección del puerto en Windows.

### Energía y batería

La lectura de batería y el control de energía dependen del modelo.

El firmware expondrá valores opcionales:

```text
battery_supported
battery_percentage
vibration_supported
speaker_supported
```

La interfaz ocultará valores no disponibles.

### Vibración

Core2 puede utilizar vibración integrada.

CoreS3 SE no debe asumir que existe vibración. Una futura base propia podrá añadirla.

### Pantalla

Todos los modelos objetivo usan 320 × 240 píxeles. La misma composición visual será válida, aunque deberán revisarse:

- Zonas táctiles.
- Área inferior reservada para navegación.
- Brillo.
- Orientación.
- Márgenes físicos de cada carcasa.

## Estrategia de compilación

PlatformIO mantendrá varios entornos:

```text
m5stack-core2
m5stack-cores3
```

CoreS3, CoreS3 Lite y CoreS3 SE compartirán inicialmente el mismo entorno y la biblioteca M5Unified. Si se detectan diferencias de energía o periféricos, se añadirán banderas específicas sin duplicar la aplicación.

## Regla de diseño

Ninguna pantalla, modelo o adaptador puede depender de un modelo concreto de M5Stack.

Solo la capa `hardware` puede conocer:

- Tipo de placa.
- Botones o tacto.
- Batería.
- Vibración.
- Altavoz.
- Implementación USB.

## Recomendación actual

- Desarrollar y probar inicialmente con Core2.
- Mantener desde ahora compilación para ESP32-S3.
- Diseñar navegación táctil común.
- Elegir CoreS3 SE si se valida una versión comercial.
- Añadir botones físicos y LED mediante una base propia en la versión comercial.
