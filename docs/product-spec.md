# Especificación de producto inicial

## Propuesta de valor

Una pantalla física que permite conocer de un vistazo qué agentes están activos, cuánto están consumiendo y cuándo se restablecen sus límites.

## Pantallas MVP

1. Resumen global.
2. Consumo elevado.
3. Agentes y actividad.
4. Configuración local.
5. Estado de conexión.

## Alertas

- Aviso al bajar del 30 % semanal.
- Alerta crítica al bajar del 15 %.
- Alerta por caída rápida de cuota durante una tarea.
- Aviso cuando un agente espera autorización.
- Aviso cuando una tarea termina o falla.

## Requisitos no funcionales

- Inicio automático del servicio con Windows.
- Consumo bajo en reposo.
- Sin credenciales almacenadas en el dispositivo.
- Funcionamiento degradado con el último estado conocido.
- Actualización de pantalla sin parpadeos completos.
- Actualización de firmware recuperable.
