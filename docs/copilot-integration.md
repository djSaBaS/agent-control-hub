# Integración con GitHub Copilot

## Objetivo

GitHub Copilot se integrará como una plataforma independiente dentro de Agent Control Hub.

La integración debe permitir, según licencia y políticas disponibles:

- Detectar GitHub Copilot CLI.
- Mostrar disponibilidad y estado de sesiones locales.
- Consultar uso y contexto de sesiones cuando exista una fuente estructurada.
- Lanzar prompts preconfigurados sobre proyectos autorizados.
- Iniciar y consultar tareas de Copilot coding agent asociadas a repositorios.
- Mostrar tareas en cola, trabajando, esperando revisión, terminadas o fallidas.
- Abrir la sesión o pull request correspondiente en el ordenador.

## Fase 1: detección local

La primera implementación:

- Localiza el ejecutable `copilot`.
- Muestra estado desconectado cuando no está instalado.
- Muestra estado disponible cuando está instalado.
- No inventa tokens, sesiones, agentes ni consumo.

## Fase 2: Copilot CLI

Se estudiará la ejecución programática mediante prompts no interactivos y la lectura de datos de sesión.

Funciones previstas:

- Ejecutar plantillas en modo de solo análisis.
- Seleccionar proyecto y agente personalizado.
- Aplicar un límite de créditos por sesión cuando esté disponible.
- Registrar duración, resultado y consumo comunicado por la CLI.
- Detectar si la sesión necesita intervención.
- Abrir o reanudar una sesión en el ordenador.

No se utilizarán permisos globales o modo autónomo sin límites desde el dispositivo.

## Fase 3: Copilot coding agent

La integración remota podrá:

- Iniciar una tarea mediante la API oficial.
- Consultar tareas existentes.
- Mostrar el repositorio y estado de la tarea.
- Detectar la creación de un pull request.
- Abrir el pull request para revisión.
- Mostrar errores de ejecución.

La API está sujeta a disponibilidad, licencia y cambios de versión. El conector deberá declarar dinámicamente sus capacidades.

## Seguridad

- La autenticación permanece en GitHub CLI, Copilot CLI o el almacén seguro de Windows.
- El dispositivo nunca recibe tokens de GitHub.
- Los repositorios permitidos se configuran mediante lista explícita.
- Las acciones usan solo análisis por defecto.
- La modificación de archivos requiere confirmación.
- No se permitirá `force push`, borrado de ramas ni publicación automática desde el dispositivo.
- Los prompts completos permanecerán en el ordenador.

## Datos mostrados

Cuando estén disponibles y sean fiables:

- Estado de la plataforma.
- Sesiones locales activas.
- Tareas remotas activas.
- Repositorio.
- Rama.
- Título sanitizado de la tarea.
- Duración.
- Contexto utilizado.
- Créditos o consumo comunicado.
- Pull request generado.
- Acción requerida.

Los valores no expuestos oficialmente se marcarán como no disponibles.
