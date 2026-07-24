# Modo reposo y pantalla ambiental

## Objetivo

Cuando el dispositivo permanezca sin interacción y no exista ninguna alerta o acción que requiera atención, Agent Control Hub mostrará una pantalla ambiental útil en lugar de mantener permanentemente el panel de agentes.

El modo reposo debe:

- Reducir distracciones cuando no hay incidencias.
- Mantener el dispositivo útil como reloj de escritorio.
- Evitar consumo y redibujados innecesarios.
- Recuperar inmediatamente la pantalla operativa cuando cambie el estado.
- Funcionar igual en Core2 y CoreS3 mediante la capa común de interfaz.

## Prioridad de pantallas

El modo reposo solo puede activarse cuando no exista una pantalla de mayor prioridad.

Orden de prioridad:

1. Alerta crítica o error.
2. Solicitud de autorización o información.
3. Advertencia de consumo.
4. Notificación de tarea terminada.
5. Seguimiento de tarea activa configurada como prioritaria.
6. Interfaz normal de navegación.
7. Pantalla ambiental o reloj.

Una alerta nueva debe interrumpir inmediatamente el modo reposo.

## Condiciones de entrada

El dispositivo entrará en reposo cuando se cumplan todas estas condiciones:

- Ha transcurrido el tiempo de inactividad configurado.
- No hay alertas críticas pendientes.
- No hay una confirmación abierta.
- No se está realizando el emparejamiento o la configuración del dispositivo.
- El usuario no ha fijado manualmente una pantalla operativa.

Tiempos configurables iniciales:

- 30 segundos.
- 1 minuto.
- 2 minutos.
- 5 minutos.
- 10 minutos.
- Nunca.

## Condiciones de salida

El modo reposo finalizará por cualquiera de estos eventos:

- Toque en la pantalla.
- Pulsación de un botón.
- Giro o pulsación del encoder cuando exista.
- Llegada de una alerta.
- Solicitud de autorización.
- Cambio a error o desconexión crítica.
- Inicio de una tarea marcada como prioritaria.
- Orden enviada desde el servicio de Windows.

El primer toque o giro despertará la pantalla. Por seguridad, no ejecutará también una acción sobre el elemento que quede debajo.

## Estilos iniciales

### Reloj digital

Mostrará:

- Hora en formato de 24 o 12 horas.
- Fecha opcional.
- Segundos opcionales.
- Estado de conexión mediante un icono discreto.
- Número de agentes activos mediante un indicador pequeño opcional.

### Reloj analógico

Mostrará una esfera sencilla optimizada para 320 × 240 píxeles.

Debe evitar redibujar toda la pantalla en cada actualización. Solo se actualizarán las zonas modificadas cuando sea posible.

### Reloj mecánico de láminas

Simulará un reloj `split-flap` o de paletas, con cada dígito dividido en una mitad superior y una mitad inferior.

La transición de minuto utilizará una animación breve de cambio de paleta. El efecto debe ser ligero y no bloquear la recepción de mensajes o alertas.

### Animación ambiental

Permitirá animaciones de bajo consumo visual, por ejemplo:

- Partículas lentas.
- Ondas suaves.
- Líneas de actividad.
- Pulso del estado global.
- Animación temática seleccionable.

Las animaciones no deben dificultar la aparición inmediata de una alerta.

## Configuración

El panel local permitirá configurar:

- Activar o desactivar el modo reposo.
- Tiempo de espera.
- Estilo predeterminado.
- Formato de hora.
- Mostrar u ocultar fecha.
- Mostrar u ocultar segundos.
- Mostrar indicadores discretos de conexión y agentes.
- Brillo normal.
- Brillo del modo reposo.
- Apagar completamente la retroiluminación después de un segundo periodo.
- Horario nocturno.
- Estilo distinto por perfil.

Configuración conceptual:

```yaml
idle_mode:
  enabled: true
  timeout_seconds: 120
  style: split_flap
  clock_format: 24h
  show_date: true
  show_seconds: false
  show_connection: true
  show_active_agents: true
  brightness_percent: 20
  screen_off_after_minutes: 30
  wake_on_alert: true
```

## Hora y funcionamiento sin conexión

La hora se obtendrá por este orden:

1. Servicio Agent Control Hub en Windows.
2. Sincronización NTP mediante Wi-Fi.
3. RTC del dispositivo.

El dispositivo debe conservar una hora aproximada aunque pierda temporalmente la conexión con el ordenador.

## Rendimiento

La implementación deberá:

- Evitar asignaciones dinámicas continuas.
- Evitar redibujados completos innecesarios.
- Mantener activo el procesamiento del protocolo mientras se muestra la animación.
- Limitar la frecuencia de refresco según el estilo.
- Interrumpir la animación inmediatamente cuando llegue una alerta.
- Desplazar ligeramente elementos estáticos de forma periódica.

Frecuencias orientativas:

- Reloj sin segundos: actualización cada minuto.
- Reloj con segundos: actualización cada segundo.
- Animación `split-flap`: solo durante el cambio de dígito.
- Animaciones ambientales: entre 10 y 20 fotogramas por segundo como máximo.

## Encoder e iluminación ambiental futura

La futura base física podrá incorporar un encoder rotatorio con pulsación.

Acciones previstas:

- Giro a la izquierda: elemento anterior o desplazamiento hacia arriba.
- Giro a la derecha: elemento siguiente o desplazamiento hacia abajo.
- Pulsación corta: seleccionar.
- Pulsación larga: volver o abrir acciones rápidas, según la pantalla.

La capa de entrada del firmware deberá tratar estas acciones de forma abstracta para compartir la misma navegación con botones y pantalla táctil.

La futura iluminación LED ambiental podrá indicar estado sin encender la pantalla principal:

- Azul: agente trabajando.
- Amarillo: atención requerida.
- Verde: tarea terminada.
- Rojo: error o consumo crítico.
- Blanco tenue: disponible.
- Luz apagada: modo nocturno o configuración del usuario.

El LED podrá utilizar pulsos y transiciones suaves, pero nunca depender únicamente del color para comunicar una alerta.

## Alcance recomendado

### Siguiente iteración de firmware

- Máquina de estados de actividad y reposo.
- Reloj digital.
- Reloj mecánico `split-flap` básico.
- Configuración de tiempo de espera y brillo.
- Despertar por tacto, botones y alertas.
- Pruebas de prioridad de pantallas.

### Iteración posterior

- Reloj analógico.
- Animaciones ambientales configurables.
- Encoder físico.
- Iluminación LED ambiental.
- Horario nocturno avanzado.
- Apagado completo y reactivación de retroiluminación.

## Decisión de planificación

La especificación se incorpora al pull request de definición del producto. La implementación se realizará después de fusionar ese pull request, dentro de una rama independiente, para no mezclar nuevas funciones con la estabilización actual de arquitectura, conectores y CI.
