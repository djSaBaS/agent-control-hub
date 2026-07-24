# Changelog

## Unreleased

- Especificación funcional ampliada del producto.
- GitHub Copilot añadido como plataforma independiente.
- Configuración validada para activar, monitorizar, mostrar y limitar plataformas.
- Separación entre plataformas monitorizadas y visibles en el dispositivo.
- Primer adaptador de detección de GitHub Copilot CLI.
- Objetivo de compilación para CoreS3, CoreS3 SE y CoreS3 Lite.
- Capa de entrada portable mediante botones o pantalla táctil.
- Documentación de compatibilidad entre Core2 y familia CoreS3.
- Instrucciones de repositorio para GitHub Copilot.
- Integración continua para Python 3.11, 3.12 y 3.13 con Ruff, MyPy, Pytest y cobertura.
- Compilación automatizada y artefactos para Core2 y CoreS3.
- CodeQL, pip-audit y revisión degradable de dependencias.
- Diagnósticos MyPy, JUnit, cobertura y logs de firmware conservados como artefactos.
- Adaptador local de Codex para tokens y límites reales desde archivos de sesión.
- Exportación atómica de `snapshot.json` y visor local compatible con WAMP.
- Sesión, proyecto, tarea y actividad reciente extraídos de JSONL y sanitizados.
- Máquina de estados real con detección de herramientas, finalización, errores y cuota agotada.
- Consumo separado entre acumulado del hilo, última petición, contexto estimado y cuota oficial.
- Lectura incremental de JSONL con detección de truncado o rotación y memoria acotada.
- Visor local reorganizado para priorizar estado, proyecto, tarea, resultados y actividad.
- Fixtures y pruebas para compatibilidad, sanitización, límite agotado y lectura incremental.
- Conversación, objetivo, actividad actual, último resultado y pendiente separados en el modelo de tarea.
- Envoltorios `codex_internal_context` y plantillas internas descartados antes de generar títulos visibles.
- Objetivos reales extraídos desde `<objective>`, `thread_goal_updated` y herramientas `create_goal`.

## 0.1.0 - 2026-07-22

- Estructura inicial del proyecto.
- Servicio Python modular con adaptador simulado.
- Protocolo NDJSON 1.0.
- Firmware inicial para M5Stack Core2.
- Pantallas de resumen, agentes, configuración y alerta.
- Pruebas unitarias y workflows de CI.
