# Auditoría inicial de seguridad

**Proyecto:** Agent Control Hub  
**Fecha:** 24 de julio de 2026  
**Alcance:** servicio Python, visor local, scripts PowerShell, integración Codex/Hermes, transporte USB y firmware M5Stack.  
**Estado:** auditoría interna de línea base; no equivale a certificación ni prueba de penetración externa.

## 1. Resumen ejecutivo

El prototipo utiliza una arquitectura prudente para su fase actual: lectura local, acciones remotas desactivadas, datos normalizados, límites de tamaño y dispositivo físico de solo lectura.

La revisión no ha identificado una ruta directa evidente desde el visor o el M5Stack hacia la ejecución arbitraria de comandos en Windows. Sin embargo, el sistema no debe declararse libre de vulnerabilidades ni preparado para producción.

El riesgo principal detectado es la posible exposición de `snapshot.json` mediante Apache/WAMP a otros equipos de la red local. También quedan pendientes la centralización de la sanitización, la autenticación del canal USB, el endurecimiento de la cadena de suministro y pruebas específicas del parser C++.

### Valoración inicial

| Área | Riesgo antes de esta fase | Riesgo objetivo tras correcciones inmediatas |
|---|---:|---:|
| Exposición del visor | Alto | Bajo, si Apache aplica `.htaccess` |
| Fuga accidental de secretos al repositorio | Alto | Medio, pendiente de Push Protection verificada |
| Servicio Python | Medio | Bajo-medio |
| Firmware y parser JSON | Medio | Medio |
| Canal USB | Medio | Medio aceptado mientras sea solo lectura |
| Cadena de suministro | Medio | Medio |
| Acciones remotas | No aplicable | Deben permanecer desactivadas |

## 2. Metodología

Se ha realizado:

- revisión manual del flujo de datos;
- revisión de permisos y comandos externos;
- revisión de sanitización y minimización;
- revisión del visor frente a XSS básico;
- revisión del protocolo USB y límites de memoria;
- revisión de GitHub Actions, Dependabot y auditoría de dependencias;
- análisis del modelo de amenazas mediante STRIDE;
- comprobación de controles compatibles con OWASP ASVS, CWE, GitHub Code Security y las recomendaciones de seguridad de Espressif.

No se ha realizado todavía:

- prueba de penetración desde otro equipo de la red;
- inspección de alertas privadas de GitHub Security;
- análisis dinámico del binario ESP32 en hardware real;
- fuzzing del parser de firmware;
- evaluación física del dispositivo;
- revisión independiente por un tercero;
- certificación normativa.

## 3. Hallazgos

### ACH-SEC-001 · Posible exposición del visor mediante WAMP

- **Severidad:** Alta.
- **Estado:** Corregido en código; requiere validar `AllowOverride` en Apache.
- **Componente:** `snapshot.json`, visor local y scripts PowerShell.
- **Riesgo:** Apache puede escuchar en interfaces distintas de localhost. Un equipo de la red podría leer nombres de proyectos, conversaciones, actividad y cuotas.
- **Corrección:** copiar una política `.htaccess` con `Require local`, desactivar índices y establecer cabeceras defensivas.
- **Validación pendiente:** comprobar desde otro equipo de la red que la respuesta sea 403 o inaccesible.

### ACH-SEC-002 · Sanitización duplicada e incompleta

- **Severidad:** Media.
- **Estado:** Abierto.
- **Componente:** adaptadores Codex y Hermes.
- **Riesgo:** los filtros actuales cubren rutas, emails, URLs y formatos comunes, pero pueden omitir tokens de otros proveedores, cabeceras Bearer, DSN, rutas UNC o claves privadas.
- **Recomendación:** crear un único módulo de sanitización, añadir patrones por categorías y pruebas de regresión negativas.

### ACH-SEC-003 · Canal USB sin autenticación

- **Severidad:** Media.
- **Estado:** Riesgo aceptado temporalmente.
- **Componente:** NDJSON por puerto COM.
- **Riesgo:** otro proceso local podría enviar telemetría falsa al dispositivo.
- **Impacto actual:** pérdida de integridad visual; no existe ejecución remota.
- **Recomendación antes de acciones remotas:** HMAC, secuencia, timestamp, protección contra repetición y emparejamiento.

### ACH-SEC-004 · Cobertura de seguridad limitada para C++

- **Severidad:** Media.
- **Estado:** Parcial.
- **Componente:** firmware M5Stack.
- **Riesgo:** compilar correctamente no detecta todas las vulnerabilidades de memoria, estados o denegación de servicio.
- **Corrección inmediata:** añadir CodeQL C/C++ y comprobación estática complementaria.
- **Pendiente:** parser extraíble, pruebas nativas y fuzzing con JSON malformado, profundo y sobredimensionado.

### ACH-SEC-005 · Dependencias no completamente reproducibles

- **Severidad:** Media.
- **Estado:** Abierto.
- **Componente:** Python, PlatformIO y GitHub Actions.
- **Riesgo:** rangos amplios o etiquetas de Actions pueden descargar versiones distintas a las auditadas.
- **Recomendación:** lockfile con hashes, versiones exactas de librerías del firmware, Actions fijadas por SHA y SBOM por versión.

### ACH-SEC-006 · Ajustes de seguridad de GitHub no verificados

- **Severidad:** Alta.
- **Estado:** Acción manual.
- **Componente:** repositorio público.
- **Riesgo:** una configuración incompleta puede permitir secretos, cambios directos en `main` o fusiones sin controles.
- **Requerido:** Secret Scanning, Push Protection, Dependabot alerts, protección de rama, checks obligatorios, private vulnerability reporting y revisión de bypasses.

### ACH-SEC-007 · Riesgo de subir archivos locales sensibles

- **Severidad:** Alta.
- **Estado:** Mitigado parcialmente.
- **Componente:** Git y entorno local.
- **Riesgo:** `state.db`, `.env`, `auth.json`, JSONL o claves privadas pueden añadirse por error.
- **Corrección:** ampliar `.gitignore`, documentar archivos prohibidos y activar Push Protection.
- **Limitación:** `.gitignore` no protege frente a archivos ya rastreados ni frente a un `git add -f`.

### ACH-SEC-008 · CSP requiere `unsafe-inline`

- **Severidad:** Baja.
- **Estado:** Aceptado temporalmente.
- **Componente:** visor web.
- **Riesgo:** el HTML contiene CSS y JavaScript inline, lo que impide una CSP estricta sin `unsafe-inline`.
- **Mitigación:** datos insertados mediante `textContent`, visor limitado a localhost y ausencia de entrada HTML no confiable.
- **Mejora:** mover CSS y JavaScript a archivos separados y eliminar `unsafe-inline`.

### ACH-SEC-009 · HTTP sin TLS

- **Severidad:** Baja en localhost; Alta si se publica en red.
- **Estado:** Aceptado solo bajo `Require local`.
- **Riesgo:** HTTP no protege confidencialidad ni integridad en tránsito.
- **Decisión:** mantener HTTP únicamente en loopback. Para red o Wi-Fi será obligatorio TLS o un canal autenticado equivalente.

### ACH-SEC-010 · Firmware y releases sin firma verificable

- **Severidad:** Media.
- **Estado:** Abierto hasta disponer de hardware.
- **Riesgo:** no existe garantía criptográfica de que el firmware grabado sea el generado por el repositorio.
- **Recomendación:** releases firmadas, hashes publicados, política de claves y evaluación de Secure Boot y cifrado de flash.

## 4. Controles existentes confirmados

- CodeQL para Python con consultas ampliadas.
- `pip-audit` semanal y en cambios relevantes.
- Dependabot para Python y GitHub Actions.
- Ruff, MyPy estricto, Pytest y cobertura por ramas.
- SQLite Hermes en `mode=ro` y `PRAGMA query_only`.
- comandos externos con argumentos fijos y sin `shell=True`.
- visor que utiliza `textContent` para datos recibidos.
- escritura atómica del snapshot con reintentos.
- lectura incremental de JSONL.
- límites de longitud en modelos públicos.
- frame serie fijo de 64 KB y descarte hasta delimitador.
- protocolo 1.x validado.
- acciones remotas desactivadas.

## 5. Plan de remediación

### Bloque A · Línea base segura

- [x] Política de seguridad.
- [x] Modelo de amenazas.
- [x] Auditoría documentada.
- [x] Restricción local del visor mediante `.htaccess`.
- [x] Exclusión de archivos sensibles habituales.
- [x] Ampliación de análisis automático a firmware y workflows.
- [ ] Verificar configuración real de GitHub Security.
- [ ] Probar desde otro equipo que WAMP no publica el visor.

### Bloque B · Protección de datos

- [ ] Sanitizador centralizado.
- [ ] Pruebas para tokens GitHub, AWS, Azure, Slack, Hugging Face, Bearer, DSN, PEM y UNC.
- [ ] Revisión de logs y artefactos.
- [ ] Modo de snapshot mínimo para el dispositivo.

### Bloque C · Firmware robusto

- [ ] Extraer parser a módulo probado en host.
- [ ] Fuzzing de JSON y protocolo.
- [ ] Límites de profundidad y nodos.
- [ ] Pruebas de memoria en Core2 real.
- [ ] Firma de releases y evaluación de Secure Boot.

### Bloque D · Futuras comunicaciones

- [ ] Diseño de emparejamiento.
- [ ] Firma HMAC y protección contra repetición.
- [ ] TLS o canal cifrado para Wi-Fi.
- [ ] Autorización de acciones por lista cerrada.
- [ ] Confirmación local y registro de auditoría.

## 6. Criterios de salida para continuar con nuevas funciones

Antes de añadir Wi-Fi, Bluetooth o acciones remotas deben cumplirse todos:

1. cero hallazgos críticos o altos abiertos;
2. visor inaccesible desde la red local por defecto;
3. Secret Scanning y Push Protection activos;
4. ramas protegidas y CI obligatoria;
5. sanitización centralizada con pruebas;
6. protocolo autenticado diseñado y revisado;
7. parser de firmware probado con entradas hostiles;
8. política de firma y actualización definida.

## 7. Conclusión

El proyecto puede continuar como prototipo local después de aplicar y validar las correcciones del Bloque A. No debe considerarse todavía un producto certificado ni seguro para exposición en red o ejecución de acciones remotas.

La decisión correcta es mantener el alcance actual de solo lectura y cerrar los hallazgos altos antes de ampliar conectividad.
