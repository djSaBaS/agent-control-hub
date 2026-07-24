# Instrucciones de desarrollo para GitHub Copilot

## Idioma y estilo

- Responde y documenta el proyecto en español.
- Mantén nombres técnicos, APIs y términos de código en su forma oficial.
- Añade comentarios profesionales antes de cada bloque lógico cuando aporten contexto real.
- No insertes comentarios entre importaciones individuales.
- Agrupa los imports en biblioteca estándar, dependencias externas y módulos internos.
- Mantén los imports ordenados según Ruff.
- Utiliza docstrings profesionales en módulos, clases y funciones.
- Evita comentarios que solo repitan la sintaxis de la línea siguiente.

## Calidad

- Mantén compatibilidad con Python 3.11 o superior.
- Cumple Ruff, Ruff Format y MyPy estricto.
- Ejecuta `ruff check .`, `ruff format --check .`, `mypy src` y `pytest` antes de terminar una tarea.
- Evita duplicación, complejidad innecesaria, código muerto y funciones demasiado largas.
- Añade o actualiza pruebas para cualquier comportamiento nuevo.
- No introduzcas dependencias sin justificar su necesidad.

## Arquitectura del servicio

- Implementa cada plataforma mediante un adaptador independiente.
- Un adaptador no puede dibujar pantallas ni escribir directamente en el puerto serie.
- El firmware no debe conocer detalles internos de las plataformas.
- Mantén separados los datos monitorizados de las plataformas visibles en el dispositivo.
- Diferencia métricas oficiales, calculadas, estimadas y no disponibles.
- No inventes tokens, cuotas, costes ni fechas de reinicio.

## Protección de datos

- Mantén las credenciales exclusivamente en el ordenador.
- No registres prompts completos ni contenido privado por defecto.
- Las acciones iniciadas desde el dispositivo deben usar modo de solo análisis por defecto.
- No añadas operaciones destructivas ni comandos arbitrarios al dispositivo.

## Firmware

- Mantén la lógica portable entre Core2 y la familia CoreS3.
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
