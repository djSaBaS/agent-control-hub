"""Adaptador local y de solo lectura para Hermes Agent Desktop."""

from __future__ import annotations

# Importa utilidades asíncronas para no bloquear el servicio principal.
import asyncio

# Importa JSON para interpretar configuración de modelo y llamadas a herramientas.
import json

# Importa variables de entorno para localizar HERMES_HOME de forma portable.
import os

# Importa expresiones regulares para sanitizar contenido antes de publicarlo.
import re

# Importa resolución de ejecutables para consultar el estado del gateway.
import shutil

# Importa el cliente SQLite incluido en Python.
import sqlite3

# Importa procesos controlados para ejecutar únicamente comandos locales conocidos.
import subprocess

# Importa tipos de funciones para permitir pruebas deterministas.
from collections.abc import Callable

# Importa estructuras de datos inmutables para filas normalizadas.
from dataclasses import dataclass

# Importa fechas UTC para comparar actividad y construir el contrato público.
from datetime import UTC, datetime, timedelta

# Importa rutas seguras y compatibles con Windows.
from pathlib import Path

# Importa constantes tipadas para cumplir el análisis estricto.
from typing import Final

# Importa el contrato común de adaptadores.
from agent_control_hub.adapters.base import PlatformAdapter

# Importa los modelos normalizados que consumen el dashboard y el dispositivo.
from agent_control_hub.models import (
    ActivityItem,
    AgentState,
    PlatformRuntimeInfo,
    PlatformSnapshot,
    ProjectInfo,
    SessionInfo,
    TaskInfo,
    TokenUsageSnapshot,
    UsageBreakdown,
)

# Limita el número de mensajes consultados en cada actualización.
_MAX_MESSAGES: Final = 20
# Limita la actividad publicada para no saturar el protocolo.
_MAX_ACTIVITY_ITEMS: Final = 12
# Limita cualquier texto procedente de una conversación.
_MAX_VISIBLE_TEXT: Final = 220
# Define cuánto tiempo se conserva en caché el estado del gateway.
_GATEWAY_CACHE_SECONDS: Final = 30
# Define el nombre estable de la fuente de datos.
_SOURCE_NAME: Final = "hermes_state_db"


# Representa una sesión de Hermes ya validada y sin campos sensibles.
@dataclass(frozen=True, slots=True)
class _HermesSession:
    """Fila principal de sesión preparada para construir modelos públicos."""

    session_id: str
    source: str | None
    model: str | None
    provider: str | None
    started_at: datetime
    ended_at: datetime | None
    end_reason: str | None
    last_activity_at: datetime
    title: str | None
    cwd: str | None
    message_count: int
    tool_call_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    estimated_cost_usd: float | None
    actual_cost_usd: float | None
    cost_status: str | None
    api_call_count: int
    handoff_error: str | None


# Representa un mensaje reducido a los campos necesarios para telemetría.
@dataclass(frozen=True, slots=True)
class _HermesMessage:
    """Mensaje sanitizable sin razonamiento ni metadatos privados."""

    message_id: int
    role: str
    content: str | None
    tool_name: str | None
    tool_names: tuple[str, ...]
    timestamp: datetime
    finish_reason: str | None
    active: bool | None


# Devuelve la ubicación predeterminada utilizada por Hermes Desktop.
def _default_hermes_home() -> Path:
    """Resuelve HERMES_HOME sin depender de una ruta fija del usuario."""

    # Prioriza la variable oficial cuando existe.
    configured_home = os.environ.get("HERMES_HOME")
    # Devuelve la ruta configurada por el usuario.
    if configured_home:
        return Path(configured_home).expanduser()
    # Recupera AppData Local en instalaciones Windows.
    local_app_data = os.environ.get("LOCALAPPDATA")
    # Utiliza la ubicación observada en Hermes Desktop para Windows.
    if local_app_data:
        return Path(local_app_data) / "hermes"
    # Mantiene compatibilidad con instalaciones CLI de Linux y macOS.
    return Path.home() / ".hermes"


# Convierte una marca temporal Unix en una fecha UTC válida.
def _datetime_from_epoch(value: object) -> datetime | None:
    """Interpreta segundos Unix sin aceptar booleanos ni valores inválidos."""

    # Rechaza tipos no numéricos y booleanos.
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    # Controla fechas fuera del rango admitido por el sistema.
    try:
        return datetime.fromtimestamp(float(value), UTC)
    # Devuelve ausencia de dato para valores corruptos.
    except (OSError, OverflowError, ValueError):
        return None


# Obtiene texto opcional con longitud acotada.
def _optional_text(value: object, max_length: int) -> str | None:
    """Normaliza texto no vacío antes de incorporarlo al contrato."""

    # Rechaza valores que no sean cadenas.
    if not isinstance(value, str):
        return None
    # Compacta espacios y saltos de línea.
    normalized = re.sub(r"\s+", " ", value).strip()
    # Devuelve nulo para cadenas vacías.
    if not normalized:
        return None
    # Devuelve el texto completo cuando cabe en el límite.
    if len(normalized) <= max_length:
        return normalized
    # Añade una elipsis explícita cuando se recorta.
    return normalized[: max_length - 1].rstrip() + "…"


# Sanitiza contenido de mensajes antes de publicarlo.
def _sanitize_text(value: object, max_length: int = _MAX_VISIBLE_TEXT) -> str | None:
    """Elimina rutas, URLs, correos y secretos de textos de Hermes."""

    # Rechaza valores que no sean texto.
    if not isinstance(value, str):
        return None
    # Elimina etiquetas internas sin conservar su contenido estructural.
    sanitized = re.sub(r"<[^>]+>", " ", value)
    # Sustituye URLs completas.
    sanitized = re.sub(r"https?://\S+", "[url]", sanitized, flags=re.IGNORECASE)
    # Sustituye rutas absolutas de Windows.
    sanitized = re.sub(r"[A-Za-z]:\\[^\r\n\"']+", "[ruta]", sanitized)
    # Sustituye rutas absolutas habituales de Unix.
    sanitized = re.sub(r"(?<!\w)/(?:home|Users|var|tmp)/[^\s\"']+", "[ruta]", sanitized)
    # Sustituye direcciones de correo.
    sanitized = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[email]", sanitized)
    # Sustituye claves con formato frecuente de OpenAI.
    sanitized = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[secreto]", sanitized)
    # Sustituye asignaciones explícitas de credenciales.
    sanitized = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|password|secret)\b\s*[:=]\s*\S+",
        r"\1=[secreto]",
        sanitized,
    )
    # Compacta espacios para evitar bloques visuales innecesarios.
    return _optional_text(sanitized, max_length)


# Extrae un entero no negativo desde una fila SQLite.
def _row_int(row: sqlite3.Row, key: str) -> int:
    """Normaliza contadores SQLite sin aceptar booleanos."""

    # Recupera el valor mediante el nombre de columna.
    value: object = row[key]
    # Devuelve el entero cuando es válido y no negativo.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    # Convierte flotantes enteros usados por algunas migraciones.
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    # Utiliza cero para contadores ausentes o corruptos.
    return 0


# Extrae un decimal no negativo desde una fila SQLite.
def _row_float(row: sqlite3.Row, key: str) -> float | None:
    """Normaliza importes opcionales sin aceptar booleanos."""

    # Recupera el valor de la fila.
    value: object = row[key]
    # Acepta enteros y flotantes no negativos.
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
        return float(value)
    # Devuelve nulo cuando no existe un importe fiable.
    return None


# Interpreta el proveedor seguro guardado en model_config.
def _provider_from_config(value: object, fallback: object) -> str | None:
    """Obtiene únicamente el nombre del proveedor sin publicar base_url."""

    # Intenta interpretar el JSON de configuración de la sesión.
    if isinstance(value, str) and value.strip():
        try:
            parsed: object = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        # Lee exclusivamente la clave provider cuando el JSON es un objeto.
        if isinstance(parsed, dict):
            provider = parsed.get("provider")
            normalized_provider = _optional_text(provider, 80)
            if normalized_provider is not None:
                return normalized_provider
    # Utiliza el proveedor de facturación como alternativa segura.
    return _optional_text(fallback, 80)


# Extrae nombres de herramientas sin conservar argumentos.
def _tool_names(value: object) -> tuple[str, ...]:
    """Interpreta llamadas JSON y devuelve únicamente nombres deduplicados."""

    # Rechaza valores no textuales o vacíos.
    if not isinstance(value, str) or not value.strip():
        return ()
    # Convierte el JSON sin publicar su representación original.
    try:
        parsed: object = json.loads(value)
    # Ignora formatos antiguos o incompletos.
    except json.JSONDecodeError:
        return ()
    # Rechaza estructuras distintas de una lista de llamadas.
    if not isinstance(parsed, list):
        return ()
    # Inicializa la lista ordenada de nombres.
    names: list[str] = []
    # Recorre cada llamada registrada.
    for call in parsed:
        # Omite elementos que no sean objetos.
        if not isinstance(call, dict):
            continue
        # Comprueba el formato compatible con OpenAI.
        function = call.get("function")
        # Conserva el nombre anidado cuando existe.
        if isinstance(function, dict):
            name = _optional_text(function.get("name"), 80)
            if name is not None:
                names.append(name)
                continue
        # Comprueba el formato alternativo utilizado por algunas herramientas.
        name = _optional_text(call.get("name"), 80)
        # Conserva el nombre plano cuando existe.
        if name is not None:
            names.append(name)
    # Elimina duplicados manteniendo el orden original.
    return tuple(dict.fromkeys(names))


# Convierte una ruta de proyecto en un alias seguro.
def _project_alias(value: object) -> tuple[str, str] | None:
    """Publica solo el último segmento de cwd y nunca la ruta completa."""

    # Rechaza valores que no sean texto.
    if not isinstance(value, str):
        return None
    # Separa rutas de Windows y Unix.
    parts = [part.strip() for part in re.split(r"[\\/]+", value) if part.strip()]
    # Rechaza rutas vacías.
    if not parts:
        return None
    # Sanitiza el último segmento.
    alias = _sanitize_text(parts[-1], 120)
    # Rechaza alias que hayan quedado vacíos.
    if alias is None:
        return None
    # Utiliza el mismo alias para nombre y ruta pública.
    return alias, alias


# Busca de forma opcional la ventana de contexto conocida para un modelo.
def _context_window_from_cache(path: Path, model: str | None) -> int | None:
    """Lee context_length_cache.yaml sin añadir una dependencia YAML."""

    # Requiere un modelo y un archivo existente.
    if model is None or not path.is_file():
        return None
    # Lee un archivo pequeño con codificación tolerante.
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    # Ignora errores de acceso sin romper la telemetría principal.
    except OSError:
        return None
    # Prepara las variantes habituales de clave YAML.
    prefixes = (f"{model}:", f"'{model}':", f'"{model}":')
    # Recorre el documento buscando el modelo exacto.
    for index, raw_line in enumerate(lines):
        # Elimina espacios laterales para comparar claves.
        stripped = raw_line.strip()
        # Omite líneas que no pertenecen al modelo.
        if not stripped.startswith(prefixes):
            continue
        # Interpreta un valor numérico en la misma línea.
        direct_value = stripped.rsplit(":", maxsplit=1)[-1].strip()
        # Devuelve el valor directo cuando es un entero positivo.
        if direct_value.isdigit() and int(direct_value) > 0:
            return int(direct_value)
        # Revisa un bloque YAML acotado tras la clave del modelo.
        for nested_line in lines[index + 1 : index + 8]:
            # Detiene el bloque cuando aparece una nueva clave de primer nivel.
            if nested_line and not nested_line[0].isspace():
                break
            # Busca nombres habituales para la ventana de contexto.
            match = re.search(
                r"(?:context_length|context_window|max_context_tokens)\s*:\s*(\d+)",
                nested_line,
                flags=re.IGNORECASE,
            )
            # Devuelve el primer entero positivo encontrado.
            if match is not None and int(match.group(1)) > 0:
                return int(match.group(1))
    # Indica que la fuente no ofrece una ventana compatible.
    return None


# Consulta el estado del gateway mediante la CLI oficial.
def _default_gateway_probe() -> str:
    """Devuelve running, stopped o unknown sin lanzar un shell."""

    # Localiza la CLI instalada en PATH.
    executable = shutil.which("hermes")
    # Indica desconocido cuando la CLI no está disponible.
    if executable is None:
        return "unknown"
    # Ejecuta únicamente el subcomando oficial con tiempo máximo.
    try:
        completed = subprocess.run(
            [executable, "gateway", "status"],
            capture_output=True,
            check=False,
            text=True,
            timeout=3.0,
        )
    # Controla procesos bloqueados o errores del sistema.
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    # Une salida estándar y de error para interpretar ambos códigos de retorno.
    output = f"{completed.stdout}\n{completed.stderr}".casefold()
    # Reconoce la respuesta observada cuando el gateway está detenido.
    if "not running" in output or "stopped" in output:
        return "stopped"
    # Reconoce respuestas positivas sin depender del código de retorno.
    if "running" in output:
        return "running"
    # Evita inventar un estado ante formatos desconocidos.
    return "unknown"


# Cuenta trabajos cron sin publicar sus instrucciones.
def _cron_job_count(path: Path) -> int | None:
    """Cuenta trabajos en jobs.json admitiendo lista o contenedor jobs."""

    # Devuelve cero cuando la carpeta existe pero no hay archivo de trabajos.
    if not path.is_file():
        return 0
    # Interpreta el archivo JSON con límite implícito del sistema de archivos local.
    try:
        parsed: object = json.loads(path.read_text(encoding="utf-8"))
    # Devuelve nulo cuando el archivo no puede leerse o está incompleto.
    except (OSError, json.JSONDecodeError):
        return None
    # Cuenta un formato de lista directa.
    if isinstance(parsed, list):
        return len(parsed)
    # Cuenta el formato de objeto con clave jobs.
    if isinstance(parsed, dict) and isinstance(parsed.get("jobs"), list):
        jobs = parsed["jobs"]
        return len(jobs)
    # No interpreta formatos no confirmados.
    return None


# Abre SQLite mediante URI estrictamente de solo lectura.
def _open_database(path: Path) -> sqlite3.Connection:
    """Configura mode=ro, query_only y un timeout corto para WAL."""

    # Construye una URI de archivo local con prohibición de escritura.
    database_uri = f"{path.resolve().as_uri()}?mode=ro"
    # Abre la conexión sin capacidad de crear o modificar la base.
    connection = sqlite3.connect(database_uri, uri=True, timeout=1.0)
    # Permite acceder a columnas por nombre.
    connection.row_factory = sqlite3.Row
    # Refuerza la protección desde el motor SQLite.
    connection.execute("PRAGMA query_only = ON")
    # Devuelve la conexión preparada.
    return connection


# Carga la sesión no archivada con actividad más reciente.
def _load_latest_session(connection: sqlite3.Connection) -> _HermesSession | None:
    """Selecciona la sesión mediante la última marca real de mensajes."""

    # Consulta exclusivamente columnas seguras y nunca system_prompt o contenido.
    row = connection.execute(
        """
        SELECT
            s.id,
            s.source,
            s.model,
            s.model_config,
            s.started_at,
            s.ended_at,
            s.end_reason,
            s.message_count,
            s.tool_call_count,
            s.input_tokens,
            s.output_tokens,
            s.cache_read_tokens,
            s.cache_write_tokens,
            s.reasoning_tokens,
            s.cwd,
            s.billing_provider,
            s.estimated_cost_usd,
            s.actual_cost_usd,
            s.cost_status,
            s.title,
            s.api_call_count,
            s.handoff_error,
            COALESCE(
                (SELECT MAX(m.timestamp) FROM messages AS m WHERE m.session_id = s.id),
                s.started_at
            ) AS last_activity_at
        FROM sessions AS s
        WHERE COALESCE(s.archived, 0) = 0
        ORDER BY last_activity_at DESC
        LIMIT 1
        """
    ).fetchone()
    # Devuelve ausencia de sesión cuando la tabla está vacía.
    if row is None:
        return None
    # Valida el identificador requerido.
    session_id = _optional_text(row["id"], 120)
    # Valida la fecha de inicio requerida.
    started_at = _datetime_from_epoch(row["started_at"])
    # Valida la última actividad requerida.
    last_activity_at = _datetime_from_epoch(row["last_activity_at"])
    # Rechaza filas incompletas para no fabricar metadatos.
    if session_id is None or started_at is None or last_activity_at is None:
        return None
    # Construye la sesión normalizada.
    return _HermesSession(
        session_id=session_id,
        source=_optional_text(row["source"], 80),
        model=_optional_text(row["model"], 160),
        provider=_provider_from_config(row["model_config"], row["billing_provider"]),
        started_at=started_at,
        ended_at=_datetime_from_epoch(row["ended_at"]),
        end_reason=_optional_text(row["end_reason"], 80),
        last_activity_at=last_activity_at,
        title=_sanitize_text(row["title"], 120),
        cwd=_optional_text(row["cwd"], 500),
        message_count=_row_int(row, "message_count"),
        tool_call_count=_row_int(row, "tool_call_count"),
        input_tokens=_row_int(row, "input_tokens"),
        output_tokens=_row_int(row, "output_tokens"),
        cache_read_tokens=_row_int(row, "cache_read_tokens"),
        cache_write_tokens=_row_int(row, "cache_write_tokens"),
        reasoning_tokens=_row_int(row, "reasoning_tokens"),
        estimated_cost_usd=_row_float(row, "estimated_cost_usd"),
        actual_cost_usd=_row_float(row, "actual_cost_usd"),
        cost_status=_optional_text(row["cost_status"], 40),
        api_call_count=_row_int(row, "api_call_count"),
        handoff_error=_sanitize_text(row["handoff_error"], 180),
    )


# Carga mensajes recientes de la sesión seleccionada.
def _load_messages(
    connection: sqlite3.Connection,
    session_id: str,
) -> list[_HermesMessage]:
    """Lee mensajes activos sin recuperar razonamiento ni estructuras Codex."""

    # Consulta únicamente el contenido visible y metadatos de herramientas.
    rows = connection.execute(
        """
        SELECT
            id,
            role,
            content,
            tool_name,
            tool_calls,
            timestamp,
            finish_reason,
            active
        FROM messages
        WHERE session_id = ?
          AND COALESCE(compacted, 0) = 0
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
        """,
        (session_id, _MAX_MESSAGES),
    ).fetchall()
    # Inicializa la colección validada.
    messages: list[_HermesMessage] = []
    # Recorre cada fila recuperada.
    for row in rows:
        # Valida el identificador del mensaje.
        message_id = _row_int(row, "id")
        # Valida el rol público.
        role = _optional_text(row["role"], 40)
        # Valida la marca temporal.
        timestamp = _datetime_from_epoch(row["timestamp"])
        # Omite filas sin identidad, rol o fecha.
        if message_id <= 0 or role is None or timestamp is None:
            continue
        # Normaliza el indicador activo cuando existe.
        raw_active: object = row["active"]
        # Convierte enteros SQLite en booleanos opcionales.
        active = bool(raw_active) if isinstance(raw_active, int) else None
        # Añade el mensaje reducido.
        messages.append(
            _HermesMessage(
                message_id=message_id,
                role=role,
                content=_sanitize_text(row["content"], 300),
                tool_name=_optional_text(row["tool_name"], 80),
                tool_names=_tool_names(row["tool_calls"]),
                timestamp=timestamp,
                finish_reason=_optional_text(row["finish_reason"], 40),
                active=active,
            )
        )
    # Devuelve mensajes en orden descendente, igual que la consulta.
    return messages


# Cuenta sesiones y mensajes globales sin leer su contenido.
def _load_global_counts(connection: sqlite3.Connection) -> tuple[int, int]:
    """Obtiene totales globales para el panel operativo."""

    # Cuenta sesiones registradas.
    session_count = int(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0])
    # Cuenta mensajes registrados.
    message_count = int(connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0])
    # Devuelve ambos contadores.
    return session_count, message_count


# Deriva el estado actual desde la última secuencia de mensajes.
def _derive_status(
    session: _HermesSession,
    messages: list[_HermesMessage],
    now: datetime,
) -> tuple[AgentState, str | None, str | None]:
    """Distingue espera de respuesta, herramienta, error, completado e inactividad."""

    # Prioriza errores de handoff guardados explícitamente por Hermes.
    if session.handoff_error is not None:
        return AgentState.ERROR, "handoff_error", session.handoff_error
    # Prioriza cierres con motivo de error.
    if session.end_reason is not None and "error" in session.end_reason.casefold():
        return AgentState.ERROR, "session_error", "La sesión de Hermes terminó con un error."
    # Devuelve inactividad cuando la sesión no contiene mensajes.
    if not messages:
        return AgentState.IDLE, "session_empty", "La sesión no contiene actividad todavía."
    # Recupera el mensaje más reciente.
    latest = messages[0]
    # Una petición del usuario sin respuesta posterior indica trabajo en curso.
    if latest.role == "user":
        return AgentState.WORKING, "response_pending", "Hermes está procesando la solicitud."
    # Una llamada de herramienta pendiente indica ejecución activa.
    if latest.role == "assistant" and latest.tool_names:
        return AgentState.WORKING, "tool_running", "Hermes está ejecutando herramientas."
    # Un mensaje de herramienta reciente espera continuación del asistente.
    if latest.role in {"tool", "function"}:
        return AgentState.WORKING, "tool_result_pending", "Hermes está procesando un resultado."
    # Una sesión cerrada correctamente se considera completada.
    if session.ended_at is not None:
        return AgentState.COMPLETED, "session_complete", "La sesión terminó correctamente."
    # Mantiene completado durante cinco minutos tras una respuesta final.
    if latest.role == "assistant" and latest.finish_reason == "stop":
        if now - latest.timestamp <= timedelta(minutes=5):
            return (
                AgentState.COMPLETED,
                "response_complete",
                "La última respuesta terminó correctamente.",
            )
        # Tras el periodo reciente, la sesión continúa disponible pero inactiva.
        return AgentState.IDLE, "session_idle", "Hermes está preparado para una nueva solicitud."
    # Evita inventar trabajo cuando el formato no es concluyente.
    return AgentState.IDLE, "session_idle", "Hermes está preparado para una nueva solicitud."


# Construye actividad reciente a partir de mensajes visibles.
def _build_activity(messages: list[_HermesMessage]) -> list[ActivityItem]:
    """Transforma mensajes en eventos breves sin mostrar razonamiento interno."""

    # Inicializa la actividad en orden cronológico descendente.
    activity: list[ActivityItem] = []
    # Recorre mensajes recientes ya ordenados.
    for message in messages:
        # Omite mensajes de sistema y desarrollador.
        if message.role in {"system", "developer"}:
            continue
        # Etiqueta solicitudes del usuario.
        if message.role == "user":
            label = "Solicitud del usuario"
            activity_type = "message"
            status = AgentState.WORKING
            summary = message.content
        # Etiqueta respuestas del asistente.
        elif message.role == "assistant":
            label = "Respuesta de Hermes"
            activity_type = "message"
            status = AgentState.COMPLETED
            summary = message.content
            # Prioriza los nombres de herramientas cuando existen.
            if message.tool_names:
                label = "Herramientas solicitadas"
                activity_type = "tool"
                status = AgentState.WORKING
                summary = ", ".join(message.tool_names)
        # Etiqueta resultados de herramientas.
        elif message.role in {"tool", "function"}:
            tool_name = message.tool_name or "herramienta"
            label = f"Herramienta completada: {tool_name[:60]}"
            activity_type = "tool_result"
            status = AgentState.COMPLETED
            summary = message.content
        # Omite roles internos no confirmados.
        else:
            continue
        # Añade el evento normalizado.
        activity.append(
            ActivityItem(
                activity_type=activity_type,
                label=label,
                status=status,
                summary=summary,
                timestamp=message.timestamp,
            )
        )
        # Respeta el límite de memoria y protocolo.
        if len(activity) >= _MAX_ACTIVITY_ITEMS:
            break
    # Devuelve la actividad acotada.
    return activity


# Localiza el último mensaje de un rol concreto.
def _latest_message(
    messages: list[_HermesMessage],
    roles: set[str],
) -> _HermesMessage | None:
    """Devuelve el primer mensaje descendente cuyo rol sea visible."""

    # Recorre mensajes desde el más reciente.
    for message in messages:
        # Devuelve la primera coincidencia.
        if message.role in roles:
            return message
    # Indica ausencia de coincidencias.
    return None


# Construye el uso de tokens de la sesión.
def _build_usage(
    session: _HermesSession,
    context_window: int | None,
) -> UsageBreakdown:
    """Publica acumulado de sesión sin confundirlo con contexto actual."""

    # Calcula el total sin sumar la caché, que forma parte de la entrada.
    total_tokens = session.input_tokens + session.output_tokens
    # Construye el bloque compatible de uso acumulado.
    thread_total = TokenUsageSnapshot(
        input_tokens=session.input_tokens,
        cached_input_tokens=session.cache_read_tokens,
        cache_write_input_tokens=session.cache_write_tokens,
        output_tokens=session.output_tokens,
        reasoning_output_tokens=session.reasoning_tokens,
        total_tokens=total_tokens,
        model_context_window=context_window,
        scope="session_total",
        source=_SOURCE_NAME,
        updated_at=session.last_activity_at,
        source_reference="state.db",
    )
    # No estima contexto usado porque state.db no contiene esa métrica exacta.
    return UsageBreakdown(thread_total=thread_total)


# Define el adaptador público de Hermes.
class HermesAdapter(PlatformAdapter):
    """Lee state.db en modo seguro y construye una instantánea normalizada."""

    # Configura rutas y dependencias sustituibles para pruebas.
    def __init__(
        self,
        hermes_home: Path | None = None,
        gateway_probe: Callable[[], str] | None = None,
    ) -> None:
        """Prepara la fuente local sin abrir conexiones persistentes."""

        # Resuelve la carpeta de datos efectiva.
        self._hermes_home = hermes_home or _default_hermes_home()
        # Construye la ruta canónica de SQLite.
        self._database_path = self._hermes_home / "state.db"
        # Conserva la función de estado del gateway.
        self._gateway_probe = gateway_probe or _default_gateway_probe
        # Inicializa la caché de gateway.
        self._gateway_status = "unknown"
        # Inicializa la fecha de la última consulta.
        self._gateway_checked_at: datetime | None = None

    # Expone el identificador estable del protocolo.
    @property
    def platform_id(self) -> str:
        """Devuelve el identificador normalizado de Hermes."""

        # Mantiene un valor corto y estable.
        return "hermes"

    # Ejecuta la lectura SQLite fuera del bucle asíncrono.
    async def collect(self) -> PlatformSnapshot:
        """Obtiene la telemetría de Hermes sin bloquear otras plataformas."""

        # Delega el trabajo de disco en un hilo.
        return await asyncio.to_thread(self._collect_sync)

    # Actualiza el estado del gateway con una frecuencia acotada.
    def _cached_gateway_status(self, now: datetime) -> str:
        """Evita ejecutar hermes gateway status cada cinco segundos."""

        # Comprueba si la caché sigue vigente.
        if self._gateway_checked_at is not None and now - self._gateway_checked_at < timedelta(
            seconds=_GATEWAY_CACHE_SECONDS
        ):
            return self._gateway_status
        # Ejecuta la sonda controlada.
        self._gateway_status = self._gateway_probe()
        # Guarda la fecha de actualización.
        self._gateway_checked_at = now
        # Devuelve el estado observado.
        return self._gateway_status

    # Construye una instantánea completa desde una conexión efímera.
    def _collect_sync(self) -> PlatformSnapshot:
        """Abre SQLite en modo ro, consulta datos y cierra la conexión."""

        # Comprueba la existencia de la base antes de abrirla.
        if not self._database_path.is_file():
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="Hermes Agent",
                status=AgentState.OFFLINE,
                status_reason="state_db_unavailable",
                status_message="No se encuentra state.db de Hermes.",
            )
        # Obtiene la hora actual una sola vez para mantener coherencia.
        now = datetime.now(UTC)
        # Abre la conexión protegida.
        try:
            connection = _open_database(self._database_path)
            try:
                # Carga la sesión principal.
                session = _load_latest_session(connection)
                # Carga contadores globales.
                session_count, global_message_count = _load_global_counts(connection)
                # Carga mensajes únicamente cuando hay una sesión.
                messages = _load_messages(connection, session.session_id) if session else []
            # Garantiza el cierre incluso cuando una consulta falle.
            finally:
                connection.close()
        # Convierte cualquier error SQLite en estado operativo visible.
        except sqlite3.Error as error:
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="Hermes Agent",
                status=AgentState.ERROR,
                status_reason="state_db_error",
                status_message=_sanitize_text(str(error), 180) or "No se pudo leer state.db.",
            )
        # Representa una base válida pero sin sesiones.
        if session is None:
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="Hermes Agent",
                status=AgentState.IDLE,
                status_reason="no_sessions",
                status_message="Hermes no tiene sesiones registradas.",
                runtime=PlatformRuntimeInfo(
                    gateway_status=self._cached_gateway_status(now),
                    session_count=session_count,
                    message_count=global_message_count,
                    cron_job_count=_cron_job_count(self._hermes_home / "cron" / "jobs.json"),
                ),
            )
        # Deriva estado y explicación desde datos reales.
        status, status_reason, status_message = _derive_status(session, messages, now)
        # Recupera la última solicitud visible.
        latest_user = _latest_message(messages, {"user"})
        # Recupera la última respuesta visible.
        latest_assistant = _latest_message(messages, {"assistant"})
        # Construye el alias de proyecto cuando cwd existe.
        project_alias = _project_alias(session.cwd)
        # Construye el proyecto opcional.
        project = (
            ProjectInfo(display_name=project_alias[0], cwd_alias=project_alias[1])
            if project_alias is not None
            else None
        )
        # Busca la ventana conocida del modelo sin estimar uso actual.
        context_window = _context_window_from_cache(
            self._hermes_home / "context_length_cache.yaml",
            session.model,
        )
        # Construye el uso de tokens de la sesión.
        usage = _build_usage(session, context_window)
        # Construye la tarea visible con título real de Hermes.
        task = TaskInfo(
            display_name=session.title
            or (latest_user.content if latest_user is not None else None),
            conversation_name=session.title,
            objective=latest_user.content if latest_user is not None else None,
            status=status,
            activity=status_message,
            last_result=latest_assistant.content if latest_assistant is not None else None,
            started_at=session.started_at,
            last_activity_at=session.last_activity_at,
        )
        # Construye la instantánea final sin inventar cuotas o agentes.
        return PlatformSnapshot(
            platform_id=self.platform_id,
            display_name="Hermes Agent",
            status=status,
            status_reason=status_reason,
            status_message=status_message,
            tokens_today=None,
            cost_today=None,
            active_agents=0,
            agents=[],
            token_usage=usage.thread_total,
            usage=usage,
            session=SessionInfo(
                session_id=session.session_id,
                started_at=session.started_at,
                last_activity_at=session.last_activity_at,
                originator="Hermes Desktop" if session.source == "tui" else "Hermes Agent",
                source=session.source,
                model_provider=session.provider,
                model_name=session.model,
            ),
            project=project,
            task=task,
            runtime=PlatformRuntimeInfo(
                gateway_status=self._cached_gateway_status(now),
                session_count=session_count,
                message_count=session.message_count,
                tool_call_count=session.tool_call_count,
                api_call_count=session.api_call_count,
                cron_job_count=_cron_job_count(self._hermes_home / "cron" / "jobs.json"),
                estimated_cost_usd=session.estimated_cost_usd,
                actual_cost_usd=session.actual_cost_usd,
                cost_status=session.cost_status,
            ),
            recent_activity=_build_activity(messages),
        )
