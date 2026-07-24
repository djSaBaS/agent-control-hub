# Modelo de amenazas de Agent Control Hub

## 1. Objetivo

Este documento define las fronteras de confianza, activos y amenazas del prototipo antes de añadir conectividad inalámbrica o acciones remotas.

El modelo actual se limita a telemetría local de Codex y Hermes, publicación de un snapshot sanitizado, visor web local y envío por USB serie a un M5Stack de solo lectura.

## 2. Activos protegidos

### Críticos

- credenciales de Codex, Hermes y proveedores de modelos;
- archivos `.env`, `auth.json` y configuración privada;
- historial de sesiones de Codex;
- base `state.db` de Hermes;
- claves privadas futuras para firma de firmware;
- acceso al equipo Windows del usuario.

### Sensibles

- nombres de proyectos;
- títulos y objetivos de conversaciones;
- actividad de herramientas;
- rutas locales;
- nombres de usuario, correos y URLs;
- métricas de cuota y consumo;
- estado operativo de agentes.

### Operativos

- disponibilidad del servicio;
- integridad del snapshot;
- integridad de la información mostrada en el dispositivo;
- continuidad de las notificaciones de cuota.

## 3. Componentes y fronteras de confianza

```text
Codex JSONL ─┐
             ├─ [Proceso Python local] ── snapshot.json ── [Apache/WAMP local]
Hermes DB  ──┘             │
                            ├─ notificación de Windows
                            └─ USB serie ── [M5Stack]

GitHub ── Actions ── dependencias Python, acciones y toolchain de firmware
```

Fronteras principales:

1. archivos privados de Codex y Hermes → servicio Python;
2. servicio Python → directorio servido por Apache;
3. servicio Python → puerto USB serie;
4. repositorio → GitHub Actions y registros externos de dependencias;
5. firmware compilado → dispositivo físico.

## 4. Actores de amenaza

- usuario de la misma red local que intenta leer el visor;
- proceso local sin autorización que accede al snapshot o al puerto COM;
- contenido malicioso o corrupto dentro de un mensaje de Codex o Hermes;
- dependencia comprometida;
- workflow de GitHub modificado maliciosamente;
- atacante con acceso físico al ESP32;
- error humano al subir credenciales al repositorio;
- fallo de disponibilidad por JSON, SQLite o frames serie especialmente construidos.

## 5. Amenazas por categoría STRIDE

### Suplantación

- un proceso local puede abrir el puerto COM y enviar snapshots falsos;
- una futura conexión Wi-Fi podría aceptar un servidor no autenticado;
- una alerta podría ser reproducida si no se controla su identificador y secuencia.

Control actual: el dispositivo es de solo lectura y deduplica alertas. Riesgo residual: medio.

### Manipulación

- modificación local de `snapshot.json`;
- manipulación de JSONL o `state.db` por otro proceso;
- dependencia o Action comprometida durante la construcción;
- firmware modificado antes de grabarlo.

Controles actuales: modelos Pydantic, validación de protocolo, límites de tamaño, CI y CodeQL para Python. Riesgo residual: medio.

### Repudio

- no existe todavía un registro firmado de quién generó un snapshot o firmware;
- las notificaciones locales no tienen auditoría persistente.

Riesgo residual: bajo para el prototipo, medio si se habilitan acciones.

### Divulgación de información

- Apache/WAMP puede exponer el visor a la red local;
- la sanitización puede no reconocer todos los formatos de secreto;
- logs, excepciones o artefactos pueden incluir contenido privado;
- un snapshot puede revelar proyectos y actividad aunque no contenga credenciales.

Control requerido: visor restringido a localhost, sanitización centralizada, secret scanning y minimización de logs. Riesgo inicial: alto.

### Denegación de servicio

- JSONL de gran tamaño;
- líneas JSON corruptas o enormes;
- bloqueo temporal de `snapshot.json`;
- SQLite bloqueada o truncada;
- frame serie superior al límite;
- JSON con profundidad o número de nodos excesivo;
- proceso externo de Codex o Hermes que no responde.

Controles actuales: lectura incremental, límites de líneas, timeouts, reintentos de Windows y frame serie fijo. Riesgo residual: medio.

### Elevación de privilegios

- actualmente no existe una ruta remota que ejecute comandos desde el dispositivo;
- los subprocesos utilizan comandos y argumentos fijos;
- una futura función de acciones remotas podría convertir el dispositivo en un punto de ejecución.

Control obligatorio antes de activar acciones: autenticación mutua, autorización por lista cerrada, confirmación local y protección contra repetición. Riesgo actual: bajo; riesgo futuro sin controles: crítico.

## 6. Supuestos de seguridad

- el equipo Windows está actualizado y no está comprometido;
- Codex y Hermes son instalaciones confiables del usuario;
- WAMP no debe publicar Agent Control Hub fuera del equipo;
- el puerto USB requiere acceso local;
- el dispositivo no almacena credenciales;
- `actions_enabled` permanece en `false`;
- no se expone el snapshot en Internet.

Cuando uno de estos supuestos deje de cumplirse, debe revisarse el modelo.

## 7. Controles obligatorios antes de ampliar alcance

### Antes de Wi-Fi o Bluetooth

- autenticación mutua;
- cifrado en tránsito;
- emparejamiento explícito;
- rotación y revocación de claves;
- protección contra repetición;
- actualización segura.

### Antes de acciones remotas

- protocolo firmado;
- permisos por acción;
- lista cerrada de comandos;
- confirmación en el ordenador para acciones sensibles;
- registro de auditoría;
- límites de frecuencia;
- pruebas negativas y de abuso.

### Antes de distribución de hardware

- versiones exactas y reproducibles;
- firmware firmado;
- política de custodia de claves;
- Secure Boot evaluado y probado;
- cifrado de flash cuando existan datos sensibles;
- mecanismo de actualización y recuperación;
- pruebas físicas sobre el dispositivo real.

## 8. Riesgo aceptado durante el prototipo

Se acepta temporalmente que USB serie no tenga firma porque:

- requiere acceso al equipo;
- el dispositivo no ejecuta acciones;
- no almacena secretos;
- el impacto principal es mostrar telemetría falsa.

Esta aceptación deja de ser válida al incorporar acciones, Wi-Fi, Bluetooth o información sensible persistente.
