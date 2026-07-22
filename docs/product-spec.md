# Especificación funcional del producto

## 1. Propósito

Agent Control Hub es un panel físico de escritorio para supervisar agentes de inteligencia artificial, controlar su consumo y lanzar acciones frecuentes de forma segura.

El producto debe permitir:

- Saber qué plataformas están conectadas.
- Ver qué agentes están trabajando y qué tarea ejecutan.
- Consultar tokens, cuotas, costes, contexto y fechas de reinicio.
- Detectar consumos anormalmente altos.
- Recibir avisos cuando una tarea termina, falla o necesita intervención.
- Lanzar revisiones y prompts preconfigurados sobre proyectos autorizados.
- Funcionar solo con las plataformas activadas por cada usuario.

El dispositivo no sustituye las interfaces completas de Codex, GitHub Copilot, Hermes, OpenClaw o Qwen. Su función es ofrecer información inmediata, alertas y acciones rápidas.

## 2. Plataformas previstas

La arquitectura debe admitir conectores independientes para:

- OpenAI Codex.
- GitHub Copilot CLI y Copilot coding agent.
- Hermes Agent.
- OpenClaw.
- Qwen Code.
- Alibaba Model Studio.
- Adaptadores locales o personalizados.

Cada conector declara las capacidades que soporta realmente. No se deben mostrar acciones o métricas que la plataforma no exponga.

## 3. Configuración por plataforma

Cada plataforma tendrá cinco controles independientes:

1. `enabled`: permite que el servicio cargue el conector.
2. `monitoring_enabled`: permite consultar estados y consumo.
3. `visible_on_device`: permite mostrarla en el dispositivo.
4. `alerts_enabled`: permite generar avisos.
5. `actions_enabled`: permite lanzar acciones desde el dispositivo.

Ejemplo conceptual:

```yaml
platforms:
  codex:
    enabled: true
    monitoring_enabled: true
    visible_on_device: true
    alerts_enabled: true
    actions_enabled: true
  copilot:
    enabled: true
    monitoring_enabled: true
    visible_on_device: true
    alerts_enabled: true
    actions_enabled: true
  openclaw:
    enabled: true
    monitoring_enabled: true
    visible_on_device: false
    alerts_enabled: errors_only
    actions_enabled: false
```

## 4. Capacidades de conectores

Los conectores podrán declarar las siguientes capacidades:

- Consultar agentes.
- Consultar tareas.
- Consultar tokens.
- Consultar cuota.
- Consultar costes.
- Consultar contexto.
- Consultar fecha de reinicio.
- Lanzar prompts.
- Iniciar tareas remotas.
- Pausar tareas.
- Detener tareas.
- Solicitar aprobación.
- Abrir la plataforma en el ordenador.

La interfaz debe ocultar las funciones no soportadas.

## 5. Estados normalizados

Todas las plataformas traducirán sus estados al siguiente conjunto:

- `offline`: desconectado.
- `available`: conectado y disponible.
- `idle`: inactivo.
- `queued`: en cola.
- `working`: trabajando.
- `waiting_approval`: esperando autorización.
- `waiting_input`: esperando información.
- `paused`: pausado.
- `blocked`: bloqueado.
- `completed`: terminado.
- `completed_with_warnings`: terminado con avisos.
- `error`: error.
- `cancelled`: cancelado.

Colores recomendados:

- Gris: desconectado o inactivo.
- Blanco: disponible.
- Azul: trabajando.
- Morado: en cola.
- Amarillo: esperando intervención.
- Naranja: bloqueado o con avisos.
- Verde: terminado.
- Rojo: error o consumo crítico.

## 6. Métricas de consumo

No se sumarán porcentajes de cuotas incompatibles entre plataformas.

Cada conector entregará únicamente las métricas disponibles:

- Tokens de entrada.
- Tokens de salida.
- Tokens de caché.
- Tokens totales.
- Contexto utilizado y disponible.
- Cuota de ventana corta.
- Cuota semanal o mensual.
- Fecha y hora de reinicio.
- Coste de la tarea actual.
- Coste diario, semanal y mensual.
- Presupuesto restante.

Cada métrica tendrá una procedencia:

- `official`: devuelta por la plataforma.
- `calculated`: calculada con datos oficiales.
- `estimated`: estimada mediante historial.
- `unavailable`: no disponible.

Una estimación nunca debe presentarse como dato oficial.

## 7. Pantallas del dispositivo

### 7.1. Resumen global

Muestra hasta cuatro plataformas por página con:

- Estado.
- Agentes activos.
- Tareas esperando atención.
- Métrica principal configurable.
- Alertas pendientes.

### 7.2. Detalle de plataforma

Muestra:

- Cuotas y reinicios.
- Tokens y costes.
- Contexto utilizado.
- Agentes activos.
- Estado de conexión.

### 7.3. Agentes y tareas

Cada fila muestra:

- Plataforma.
- Agente.
- Proyecto.
- Tarea resumida.
- Estado.
- Duración.
- Última actividad.

El dispositivo no recibe prompts completos. Solo recibe títulos sanitizados.

### 7.4. Consumo global

Presenta una lista de métricas por plataforma sin mezclar límites incompatibles.

### 7.5. Consumo elevado

Se abre automáticamente cuando se detecta:

- Caída rápida de cuota.
- Riesgo de agotar un límite.
- Coste superior al presupuesto.
- Contexto próximo a agotarse.
- Tarea con consumo anómalo respecto al historial.

### 7.6. Centro de alertas

Permite consultar, marcar como leídas, silenciar o abrir en el ordenador las alertas pendientes.

### 7.7. Acciones rápidas

Permite lanzar plantillas autorizadas sobre proyectos favoritos.

### 7.8. Estado del dispositivo

Muestra conexión, servicio, firmware, última sincronización, batería, memoria y errores de comunicación.

### 7.9. Configuración local

Incluye solo ajustes cotidianos:

- Brillo.
- Volumen.
- Vibración.
- Tema.
- Tiempo de apagado de pantalla.
- Plataforma principal.
- Perfil activo.
- Silencio temporal.

La configuración avanzada se realizará desde el ordenador.

## 8. Acciones rápidas iniciales

La biblioteca inicial incluirá:

1. Revisar seguridad.
2. Buscar posibles errores.
3. Revisar documentación.
4. Proponer futuras mejoras.
5. Revisar pruebas.
6. Revisar dependencias.
7. Revisar rendimiento.
8. Revisar accesibilidad.
9. Preparar una versión.
10. Analizar cambios actuales.

Cada plantilla tendrá:

- Nombre y descripción.
- Plataforma preferida.
- Proyecto o repositorio.
- Rama.
- Modelo.
- Nivel de razonamiento.
- Modo de ejecución.
- Presupuesto y tiempo máximos.
- Rutas incluidas y excluidas.
- Prompt completo.
- Permisos solicitados.
- Confirmación requerida.

El dispositivo enviará el identificador de la plantilla. El prompt completo permanecerá en el ordenador.

## 9. Modos de ejecución

### Solo análisis

Puede leer y analizar, pero no modificar archivos. Es el modo predeterminado para acciones iniciadas desde el dispositivo.

### Proponer cambios

Puede preparar recomendaciones o parches, pero requiere revisión antes de aplicarlos.

### Aplicar cambios

Puede modificar archivos y ejecutar pruebas. Requiere una confirmación prolongada y una advertencia visible.

### Acciones prohibidas desde el dispositivo

- Eliminar proyectos.
- Borrar ramas.
- Hacer `force push`.
- Publicar en producción.
- Modificar credenciales.
- Ejecutar comandos arbitrarios.
- Aprobar gasto sin límite.

## 10. Flujo para lanzar una acción

1. Seleccionar plantilla.
2. Seleccionar proyecto.
3. Seleccionar plataforma.
4. Mostrar cuota o presupuesto disponible.
5. Mostrar modo y permisos.
6. Mantener pulsado para confirmar.
7. Enviar la orden al servicio.
8. Mostrar la tarea en cola.
9. Cambiar a la pantalla de seguimiento.

## 11. Proyectos favoritos

Cada proyecto registrado podrá definir:

- Nombre visible.
- Ruta local.
- Repositorio Git.
- Rama predeterminada.
- Plataformas permitidas.
- Acciones disponibles.
- Carpetas excluidas.
- Nivel de sensibilidad.
- Presupuesto máximo por tarea.

El dispositivo mostrará únicamente proyectos marcados como favoritos.

## 12. Alertas configurables

### Consumo

- Cuota inferior al umbral.
- Caída superior a un porcentaje en un periodo.
- Coste diario o mensual superado.
- Consumo inesperado durante una tarea.
- Contexto superior al umbral.
- Previsión de agotar la cuota antes del reinicio.

### Agentes

- Tarea iniciada.
- Tarea terminada.
- Tarea terminada con avisos.
- Error.
- Esperando autorización.
- Esperando información.
- Agente bloqueado.
- Tarea sin actividad durante demasiado tiempo.

### Sistema

- Plataforma desconectada.
- Servicio detenido.
- Dispositivo desconectado.
- Actualización disponible.
- Error de sincronización.
- Firmware incompatible.

## 13. Perfiles

Perfiles iniciales:

- Normal.
- Ahorro.
- Concentración.
- Personal.
- Trabajo.
- Demostración.

Cada perfil puede definir plataformas visibles, proyectos, acciones, alertas, límites, sonido, brillo y orden de pantallas.

## 14. Configuración en el ordenador

La configuración avanzada se realizará mediante una aplicación de bandeja y un panel local.

Secciones previstas:

1. Estado general.
2. Dispositivos.
3. Plataformas.
4. Agentes.
5. Proyectos.
6. Acciones y prompts.
7. Consumo y presupuestos.
8. Alertas.
9. Perfiles.
10. Apariencia.
11. Privacidad e historial.
12. Actualizaciones.
13. Diagnóstico.

## 15. Historial y privacidad

El servicio podrá guardar localmente:

- Tareas ejecutadas.
- Plataforma.
- Proyecto.
- Inicio y final.
- Estado final.
- Tokens.
- Coste.
- Impacto sobre cuota.
- Alertas y errores.

No guardará por defecto:

- Prompts completos ejecutados.
- Respuestas completas.
- Contenido de archivos.
- Credenciales.
- Conversaciones privadas.

## 16. Alcance del primer MVP funcional

- Core2 conectado por USB.
- Servicio automático en Windows.
- Panel de configuración local.
- Plataformas activables y ocultables.
- Adaptador simulado.
- Primer adaptador real de Codex.
- Adaptador inicial de GitHub Copilot.
- Un conector adicional entre Qwen, Hermes u OpenClaw.
- Resumen global.
- Detalle de plataforma.
- Lista de agentes.
- Consumo y alertas.
- Historial básico.
- Proyectos favoritos.
- Seis acciones rápidas.
- Lanzamiento en modo solo análisis.
- Perfiles Normal y Ahorro.
- Último estado conocido sin conexión.

## 17. Funciones aplazadas

- Control remoto desde Internet.
- Aplicación móvil.
- Sincronización en la nube.
- Gestión multiusuario.
- Marketplace de conectores.
- Chat completo desde el dispositivo.
- Logs extensos en pantalla.
- Aprobación de operaciones peligrosas.
- Control de producción.

## 18. Decisiones fijadas

1. El producto será multiplataforma.
2. GitHub Copilot será un conector independiente.
3. Cada plataforma podrá activarse, ocultarse o limitarse.
4. La configuración avanzada permanecerá en el ordenador.
5. Las cuotas incompatibles no se mezclarán.
6. Los datos oficiales, calculados y estimados estarán diferenciados.
7. Los prompts completos permanecerán en el ordenador.
8. El modo predeterminado será solo análisis.
9. Las acciones destructivas no estarán disponibles desde el dispositivo.
10. Las credenciales nunca llegarán al microcontrolador.
11. El firmware deberá ser portable entre Core2 y CoreS3 mediante una capa de hardware.
