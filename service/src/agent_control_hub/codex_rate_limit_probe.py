"""Consulta en vivo las cuotas de Codex mediante su app-server oficial."""

# Importa JSON para construir y analizar mensajes JSON-RPC delimitados por línea.
import json
# Importa colas seguras entre hilos para leer stdout sin bloquear el servicio.
import queue
# Importa la resolución del ejecutable de Codex disponible en PATH.
import shutil
# Importa la gestión de procesos utilizada para abrir app-server en modo local.
import subprocess
# Importa hilos para consumir stdout de forma compatible con Windows.
import threading
# Importa tiempo monotónico para aplicar un límite total a la consulta.
import time
# Importa utilidades de contexto para cerrar procesos sin ocultar otros errores.
from contextlib import suppress
# Importa tipos de lectura de texto para mantener el tipado estricto.
from typing import TextIO


# Convierte un objeto arbitrario en un diccionario con claves de texto.
def _as_object_dict(value: object) -> dict[str, object] | None:
    """Acepta únicamente objetos JSON y descarta claves no textuales."""

    # Rechaza estructuras que no sean diccionarios.
    if not isinstance(value, dict):
        # Informa de que el valor no puede interpretarse como objeto JSON.
        return None
    # Conserva únicamente claves textuales para evitar accesos ambiguos.
    return {key: item for key, item in value.items() if isinstance(key, str)}


# Normaliza una ventana recibida desde app-server al contrato interno existente.
def _normalize_window(value: object) -> dict[str, object] | None:
    """Convierte usedPercent, windowDurationMins y resetsAt a snake_case."""

    # Interpreta la ventana como un objeto JSON.
    window = _as_object_dict(value)
    # Rechaza ventanas ausentes o con formato inesperado.
    if window is None:
        # Informa de que no existe una ventana válida.
        return None
    # Recupera el porcentaje usado admitiendo la nomenclatura oficial y la interna.
    used_percent = window.get("usedPercent", window.get("used_percent"))
    # Recupera la duración admitiendo la nomenclatura oficial y la interna.
    window_minutes = window.get("windowDurationMins", window.get("window_minutes"))
    # Recupera el instante de reinicio admitiendo ambas nomenclaturas.
    resets_at = window.get("resetsAt", window.get("resets_at"))
    # Valida el porcentaje sin aceptar booleanos como números.
    if not isinstance(used_percent, (int, float)) or isinstance(used_percent, bool):
        # Rechaza porcentajes no numéricos.
        return None
    # Valida la duración como entero positivo.
    if not isinstance(window_minutes, int) or isinstance(window_minutes, bool):
        # Rechaza duraciones no enteras.
        return None
    # Valida el reinicio como marca Unix entera.
    if not isinstance(resets_at, int) or isinstance(resets_at, bool):
        # Rechaza fechas no compatibles.
        return None
    # Rechaza porcentajes fuera del rango permitido.
    if not 0 <= float(used_percent) <= 100:
        # Evita publicar una cuota corrupta.
        return None
    # Rechaza ventanas sin duración real.
    if window_minutes <= 0:
        # Evita crear una ventana temporal inválida.
        return None
    # Devuelve la forma utilizada por el adaptador local.
    return {
        # Publica el porcentaje usado como decimal estable.
        "used_percent": float(used_percent),
        # Publica la duración en minutos.
        "window_minutes": window_minutes,
        # Publica la siguiente fecha de reinicio en segundos Unix.
        "resets_at": resets_at,
    }


# Normaliza el bloque completo de cuotas recibido desde Codex.
def normalize_rate_limits(value: object) -> dict[str, object] | None:
    """Devuelve un bloque compatible con los eventos JSONL del adaptador."""

    # Interpreta la respuesta como objeto JSON.
    rate_limits = _as_object_dict(value)
    # Rechaza respuestas vacías o no estructuradas.
    if rate_limits is None:
        # Informa de que la lectura no aporta cuotas utilizables.
        return None
    # Normaliza la ventana primaria cuando está disponible.
    primary = _normalize_window(rate_limits.get("primary"))
    # Normaliza la ventana secundaria cuando está disponible.
    secondary = _normalize_window(rate_limits.get("secondary"))
    # Rechaza respuestas que no contienen ninguna ventana real.
    if primary is None and secondary is None:
        # Evita sustituir una lectura JSONL útil por una respuesta incompleta.
        return None
    # Recupera el identificador de cuota con ambas convenciones de nombre.
    limit_id = rate_limits.get("limitId", rate_limits.get("limit_id"))
    # Recupera el tipo de plan con ambas convenciones de nombre.
    plan_type = rate_limits.get("planType", rate_limits.get("plan_type"))
    # Devuelve el contrato compartido por el adaptador.
    return {
        # Conserva el identificador oficial o utiliza el valor estable de Codex.
        "limit_id": limit_id if isinstance(limit_id, str) and limit_id else "codex",
        # Adjunta la ventana primaria ya validada.
        "primary": primary,
        # Adjunta la ventana secundaria ya validada.
        "secondary": secondary,
        # Conserva el plan únicamente cuando es texto no vacío.
        "plan_type": plan_type if isinstance(plan_type, str) and plan_type else None,
    }


# Escribe un mensaje JSON-RPC completo en stdin del proceso.
def _write_message(process: subprocess.Popen[str], payload: dict[str, object]) -> bool:
    """Envía una línea JSON y confirma que stdin continúa disponible."""

    # Recupera el canal de entrada creado por Popen.
    stdin = process.stdin
    # Rechaza procesos que no expongan stdin.
    if stdin is None:
        # Informa del fallo de transporte sin lanzar una excepción secundaria.
        return False
    # Serializa el mensaje sin caracteres ASCII forzados.
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Escribe una única línea conforme al transporte JSONL oficial.
    stdin.write(serialized + "\n")
    # Fuerza el envío inmediato al proceso hijo.
    stdin.flush()
    # Confirma que el mensaje fue entregado al canal local.
    return True


# Consume stdout en un hilo dedicado y publica cada línea en una cola.
def _read_stdout(stdout: TextIO, messages: queue.Queue[str]) -> None:
    """Evita bloqueos de lectura de tuberías en Windows y Linux."""

    # Recorre las líneas hasta que app-server cierre stdout.
    for line in stdout:
        # Publica cada respuesta para que el hilo principal pueda aplicar timeout.
        messages.put(line)


# Espera una respuesta concreta ignorando notificaciones intermedias.
def _wait_for_response(
    messages: queue.Queue[str],
    request_id: int,
    deadline: float,
) -> dict[str, object] | None:
    """Busca una respuesta por id hasta alcanzar el tiempo máximo compartido."""

    # Mantiene la espera mientras quede tiempo disponible.
    while True:
        # Calcula el margen restante usando un reloj monotónico.
        remaining = deadline - time.monotonic()
        # Abandona cuando se ha consumido el tiempo total de la consulta.
        if remaining <= 0:
            # Informa de que no llegó una respuesta válida.
            return None
        # Espera la siguiente línea sin bloquear más allá del margen restante.
        try:
            # Recupera una línea producida por el hilo lector.
            raw_line = messages.get(timeout=remaining)
        # Controla la ausencia de mensajes dentro del tiempo permitido.
        except queue.Empty:
            # Informa de que app-server no respondió a tiempo.
            return None
        # Intenta interpretar exclusivamente la línea recibida.
        try:
            # Convierte la línea JSONL en un objeto Python.
            parsed: object = json.loads(raw_line)
        # Omite mensajes de diagnóstico que no sean JSON válido.
        except json.JSONDecodeError:
            # Continúa esperando una respuesta JSON-RPC real.
            continue
        # Convierte el mensaje en un objeto con claves de texto.
        response = _as_object_dict(parsed)
        # Omite estructuras JSON que no sean objetos.
        if response is None:
            # Continúa esperando la respuesta solicitada.
            continue
        # Devuelve únicamente la respuesta que coincide con el id esperado.
        if response.get("id") == request_id:
            # Entrega la respuesta completa al llamador.
            return response


# Define una sonda reutilizable y sustituible en pruebas.
class CodexRateLimitProbe:
    """Lee cuotas actuales sin iniciar tareas ni consumir tokens de modelo."""

    # Configura el ejecutable y el tiempo máximo de la operación.
    def __init__(self, executable: str = "codex", timeout_seconds: float = 10.0) -> None:
        """Conserva parámetros seguros para abrir app-server bajo demanda."""

        # Guarda el nombre o ruta del ejecutable solicitado.
        self._executable = executable
        # Limita el tiempo total a un valor positivo y razonable.
        self._timeout_seconds = max(1.0, timeout_seconds)

    # Ejecuta la lectura oficial de cuotas.
    def read(self) -> dict[str, object] | None:
        """Consulta account/rateLimits/read mediante el transporte stdio oficial."""

        # Localiza el ejecutable real antes de abrir un proceso.
        executable = shutil.which(self._executable)
        # Evita ejecutar la sonda cuando Codex no está instalado.
        if executable is None:
            # Informa de que no existe una fuente en vivo disponible.
            return None
        # Inicializa la referencia para garantizar su cierre en finally.
        process: subprocess.Popen[str] | None = None
        # Ejecuta la comunicación controlada con app-server.
        try:
            # Abre app-server con transporte JSONL local y sin shell.
            process = subprocess.Popen(
                # Ejecuta únicamente el binario resuelto y el subcomando oficial.
                [executable, "app-server", "--stdio"],
                # Habilita el canal de solicitudes JSON-RPC.
                stdin=subprocess.PIPE,
                # Habilita el canal de respuestas JSON-RPC.
                stdout=subprocess.PIPE,
                # Descarta trazas internas que no forman parte del protocolo.
                stderr=subprocess.DEVNULL,
                # Trabaja directamente con texto Unicode.
                text=True,
                # Fuerza una codificación estable en Windows.
                encoding="utf-8",
                # Sustituye caracteres inválidos sin romper la consulta.
                errors="replace",
                # Solicita entrega inmediata de mensajes delimitados por línea.
                bufsize=1,
            )
            # Recupera stdout para iniciar el consumidor dedicado.
            stdout = process.stdout
            # Rechaza procesos que no expongan el canal de salida.
            if stdout is None:
                # Informa de que no puede completarse el protocolo.
                return None
            # Crea la cola utilizada para transferir respuestas entre hilos.
            messages: queue.Queue[str] = queue.Queue()
            # Prepara un lector que finalizará automáticamente con el proceso.
            reader = threading.Thread(
                # Ejecuta la función de consumo de stdout.
                target=_read_stdout,
                # Entrega el canal y la cola como argumentos inmutables.
                args=(stdout, messages),
                # Evita que un lector bloqueado impida terminar la aplicación.
                daemon=True,
            )
            # Inicia la lectura antes de enviar la primera solicitud.
            reader.start()
            # Calcula un único límite temporal para todo el intercambio.
            deadline = time.monotonic() + self._timeout_seconds
            # Envía la inicialización obligatoria del protocolo.
            initialized = _write_message(
                # Utiliza el proceso recién abierto.
                process,
                # Identifica Agent Control Hub sin enviar datos del usuario.
                {
                    "method": "initialize",
                    "id": 1,
                    "params": {
                        "clientInfo": {
                            "name": "agent_control_hub",
                            "title": "Agent Control Hub",
                            "version": "0.1.0",
                        }
                    },
                },
            )
            # Abandona cuando no pudo escribirse la solicitud inicial.
            if not initialized:
                # Informa de que la conexión local no está operativa.
                return None
            # Espera la confirmación de inicialización antes de continuar.
            initialize_response = _wait_for_response(messages, 1, deadline)
            # Rechaza errores o respuestas ausentes de inicialización.
            if initialize_response is None or "error" in initialize_response:
                # Evita enviar métodos sobre una conexión no inicializada.
                return None
            # Envía la notificación de inicialización requerida por app-server.
            if not _write_message(process, {"method": "initialized", "params": {}}):
                # Informa de que el canal se cerró durante el handshake.
                return None
            # Solicita exclusivamente las cuotas actuales de la cuenta autenticada.
            if not _write_message(
                # Utiliza la misma conexión inicializada.
                process,
                # Invoca el método oficial sin crear hilos ni turnos.
                {"method": "account/rateLimits/read", "id": 2, "params": {}},
            ):
                # Informa de que no se pudo enviar la lectura.
                return None
            # Espera la respuesta concreta de cuotas.
            rate_response = _wait_for_response(messages, 2, deadline)
            # Rechaza ausencias y errores JSON-RPC.
            if rate_response is None or "error" in rate_response:
                # Conserva el fallback de telemetría JSONL del adaptador.
                return None
            # Interpreta el objeto resultante de la solicitud.
            result = _as_object_dict(rate_response.get("result"))
            # Rechaza respuestas sin bloque result.
            if result is None:
                # Evita publicar una lectura incompleta.
                return None
            # Normaliza la cuota principal devuelta por app-server.
            return normalize_rate_limits(result.get("rateLimits"))
        # Convierte fallos locales de proceso, E/S o protocolo en fallback silencioso.
        except (OSError, BrokenPipeError, ValueError):
            # Informa de que la sonda en vivo no está disponible en esta iteración.
            return None
        # Garantiza que app-server no permanezca abierto tras la lectura.
        finally:
            # Comprueba que el proceso llegó a crearse.
            if process is not None:
                # Solicita primero una terminación ordenada.
                with suppress(OSError):
                    # Envía la señal local de terminación.
                    process.terminate()
                # Espera brevemente para liberar tuberías y archivos.
                try:
                    # Da al proceso un segundo para finalizar.
                    process.wait(timeout=1.0)
                # Fuerza el cierre cuando app-server no termina a tiempo.
                except (OSError, subprocess.TimeoutExpired):
                    # Evita que un proceso bloqueado permanezca en segundo plano.
                    with suppress(OSError):
                        # Finaliza inmediatamente el proceso restante.
                        process.kill()
