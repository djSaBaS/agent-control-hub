# Instrucciones de desarrollo para GitHub Copilot

## Idioma y estilo

- Responde y documenta el proyecto en español.
- Mantén nombres técnicos, APIs y términos de código en su forma oficial.
- Antes de cada línea de código añadida, incluye un comentario profesional en la línea anterior cuando el lenguaje lo permita.
- Utiliza docstrings profesionales en clases, funciones y módulos.
- Evita comentarios redundantes que solo repitan literalmente la sintaxis.

## Calidad

- Mantén compatibilidad con Python 3.11 o superior.
- Cumple las reglas configuradas de Ruff y MyPy estricto.
- Evita duplicación, complejidad innecesaria y funciones demasiado largas.
- Aplica principios compatibles con Sonar: validación explícita, manejo seguro de errores y ausencia de código muerto.
- Añade o actualiza pruebas para cualquier comportamiento nuevo.
- No introduzcas dependencias sin justificar su necesidad.

## Arquitectura del servicio

- Cada plataforma debe implementarse mediante un adaptador independiente.
- Un adaptador no puede dibujar pantallas ni escribir directamente en el puerto serie.
- El firmware no debe conocer APIs, credenciales o detalles internos de plataformas.
- Mantén separados los datos monitorizados de las plataformas visibles en el dispositivo.
- Diferencia métricas oficiales, calculadas, estimadas y no disponibles.
- No inventes tokens, cuotas, costes o fechas de reinicio.

## Seguridad

- Nunca escribas claves API, tokens de acceso, contraseñas o secretos en el repositorio.
- Las credenciales deben permanecer en el ordenador y usar almacenes seguros o variables de entorno.
- No registres prompts completos ni contenido privado por defecto.
- Las acciones iniciadas desde el dispositivo deben usar modo de solo análisis por defecto.
- No añadas acciones destructivas o comandos arbitrarios al dispositivo.

## Firmware

- Mantén la lógica de aplicación portable entre Core2 y la familia CoreS3.
- Usa M5Unified para pantalla y periféricos comunes.
- Encapsula botones, tacto, batería, vibración, sonido y USB en una capa de hardware.
- Diseña las pantallas para 320 × 240 píxeles.
- Evita redibujados completos innecesarios y asignaciones dinámicas sin límite.
- Protege el protocolo ante mensajes demasiado grandes o malformados.

## Flujo de cambios

- No realices refactorizaciones ajenas a la tarea solicitada.
- Conserva compatibilidad con el protocolo existente salvo cambio versionado.
- Actualiza documentación y changelog cuando una modificación afecte al usuario.
- Explica las limitaciones reales de cada conector.
