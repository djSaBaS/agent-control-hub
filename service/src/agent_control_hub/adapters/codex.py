"""Adaptador local para telemetría real y sanitizada de OpenAI Codex."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.adapters.codex_task_metadata import (
    derive_objective_title,
    extract_conversation_title,
    extract_objective_block,
    extract_pending_from_message,
    extract_result_from_message,
    extract_tool_arguments,
    extract_tool_objective,
    is_internal_task_text,
    is_meaningful_result,
    normalize_goal_objective,
    raw_message_text,
)
from agent_control_hub.models import (
    ActivityItem,
    AgentState,
    PlatformSnapshot,
    ProjectInfo,
    RateLimitsSnapshot,
    RateLimitWindowSnapshot,
    SessionInfo,
    TaskInfo,
    TokenUsageSnapshot,
    UsageBreakdown,
)

_READ_CHUNK_BYTES: Final = 256 * 1024
_MAX_JSON_LINE_BYTES: Final = 2 * 1024 * 1024
_MAX_ACTIVITY_ITEMS: Final = 12
_MAX_VISIBLE_TEXT: Final = 220
_TECHNICAL_OBJECTIVE_MARKERS: Final = (
    "goal-objective.md",
    "read the codex goal objective file",
    "before continuing",
)


@dataclass(frozen=True, slots=True)
class _TokenEvent:
    """Evento token_count normalizado antes de construir modelos públicos."""

    timestamp: datetime
    source_reference: str
    info: dict[str, object]
    rate_limits: dict[str, object] | None


@dataclass(slots=True)
class _SessionAccumulator:
    """Estado acumulado y acotado de un archivo JSONL de sesión."""

    source_reference: str
    session_id: str | None = None
    session_started_at: datetime | None = None
    originator: str | None = None
    source: str | None = None
    cli_version: str | None = None
    model_provider: str | None = None
    project_name: str | None = None
    cwd_alias: str | None = None
    latest_event_at: datetime | None = None
    latest_usage: _TokenEvent | None = None
    latest_rate_limits: _TokenEvent | None = None
    latest_user_message: str | None = None
    latest_goal: str | None = None
    conversation_name: str | None = None
    objective: str | None = None
    latest_agent_message: str | None = None
    last_result: str | None = None
    pending: str | None = None
    task_started_at: datetime | None = None
    task_last_activity_at: datetime | None = None
    task_active: bool = False
    task_completed: bool = False
    blocked_reason: str | None = None
    blocked_message: str | None = None
    error_message: str | None = None
    pending_tools: dict[str, str] = field(default_factory=dict)
    activity: deque[ActivityItem] = field(default_factory=lambda: deque(maxlen=_MAX_ACTIVITY_ITEMS))


@dataclass(slots=True)
class _FileCursor:
    """Cursor incremental asociado a una versión concreta de un JSONL."""

    file_id: int | None
    modified_ns: int
    size_bytes: int
    offset: int
    remainder: bytes
    state: _SessionAccumulator


def _as_object_dict(value: object) -> dict[str, object] | None:
    """Convierte diccionarios JSON en mapas con claves de texto."""

    if not isinstance(value, dict):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _parse_timestamp(value: object) -> datetime | None:
    """Interpreta fechas ISO 8601 de los eventos de Codex."""

    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_epoch(value: object) -> datetime | None:
    """Interpreta segundos Unix sin aceptar booleanos."""

    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    try:
        return datetime.fromtimestamp(value, UTC)
    except (OSError, OverflowError, ValueError):
        return None


def _integer(mapping: dict[str, object], key: str, default: int = 0) -> int:
    """Obtiene un entero no negativo sin aceptar booleanos."""

    value = mapping.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return default


def _number(mapping: dict[str, object], key: str) -> float | None:
    """Obtiene un número decimal sin aceptar booleanos."""

    value = mapping.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _optional_text(value: object, max_length: int) -> str | None:
    """Acepta texto no vacío y limita su longitud para el contrato público."""

    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:max_length]


def _sanitize_text(value: object, max_length: int = _MAX_VISIBLE_TEXT) -> str | None:
    """Elimina datos sensibles y limita mensajes destinados a interfaces."""

    if not isinstance(value, str):
        return None
    sanitized = re.sub(r"<[^>]+>", " ", value)
    sanitized = re.sub(r"https?://\S+", "[url]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(
        r"(?i)\b[A-Z]:\\[^\r\n<>|?*]+?\.(?:php|txt|md|jsonl?|log|csv|xlsx?|docx?|pdf|py|js|ts|c|cpp|h)\b",
        "[ruta]",
        sanitized,
    )
    sanitized = re.sub(
        r"[A-Za-z]:\\[^\s\"']+",
        "[ruta]",
        sanitized,
    )
    sanitized = re.sub(r"(?<!\w)/(?:home|Users|var|tmp)/[^\s\"']+", "[ruta]", sanitized)
    sanitized = re.sub(
        r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",
        "[email]",
        sanitized,
    )
    sanitized = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "[secreto]", sanitized)
    sanitized = re.sub(
        r"(?i)\b(api[_-]?key|access[_-]?token|password|secret)\b\s*[:=]\s*\S+",
        r"\1=[secreto]",
        sanitized,
    )
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    if not sanitized:
        return None
    if len(sanitized) <= max_length:
        return sanitized
    return sanitized[: max_length - 1].rstrip() + "…"


def _project_alias(cwd: object) -> tuple[str, str] | None:
    """Convierte una ruta local en un nombre de proyecto sin exponerla."""

    if not isinstance(cwd, str):
        return None
    parts = [part.strip() for part in re.split(r"[\\/]+", cwd) if part.strip()]
    if not parts:
        return None
    display_name = _sanitize_text(parts[-1], 120)
    if display_name is None:
        return None
    return display_name, display_name


def _source_reference(path: Path, sessions_dir: Path) -> str:
    """Genera una referencia relativa que no expone el perfil del usuario."""

    try:
        return path.relative_to(sessions_dir).as_posix()
    except ValueError:
        return path.name


def _is_technical_objective(value: str) -> bool:
    """Descarta objetivos internos que no describen el trabajo del usuario."""

    lowered = value.casefold()
    return is_internal_task_text(value) or any(
        marker in lowered for marker in _TECHNICAL_OBJECTIVE_MARKERS
    )


def _extract_message_text(payload: dict[str, object]) -> str | None:
    """Extrae texto de mensajes estructurados sin conservar otras propiedades."""

    content = payload.get("content")
    if isinstance(content, str):
        return _sanitize_text(content, 180)
    if not isinstance(content, list):
        return None
    fragments: list[str] = []
    for item in content:
        item_dict = _as_object_dict(item)
        if item_dict is None:
            continue
        item_type = item_dict.get("type")
        if item_type not in {"input_text", "output_text", "text"}:
            continue
        text = item_dict.get("text")
        if isinstance(text, str):
            fragments.append(text)
    return _sanitize_text(" ".join(fragments), 180)


def _tool_summary(payload: dict[str, object]) -> str | None:
    """Obtiene una descripción acotada de argumentos de una herramienta."""

    raw_arguments = payload.get("arguments", payload.get("input"))
    if isinstance(raw_arguments, str):
        try:
            parsed: object = json.loads(raw_arguments)
        except json.JSONDecodeError:
            parsed = raw_arguments
    else:
        parsed = raw_arguments
    mapping = _as_object_dict(parsed)
    if mapping is not None:
        for key in ("command", "query", "path", "url", "prompt"):
            candidate = mapping.get(key)
            sanitized = _sanitize_text(candidate, 180)
            if sanitized is not None:
                return sanitized
        try:
            return _sanitize_text(json.dumps(mapping, ensure_ascii=False), 180)
        except (TypeError, ValueError):
            return None
    return _sanitize_text(parsed, 180)


def _tool_label(name: str) -> str:
    """Asigna una etiqueta legible a herramientas habituales de Codex."""

    lowered = name.casefold()
    if lowered in {"shell_command", "exec_command"}:
        return "Ejecutando comando"
    if "patch" in lowered:
        return "Aplicando cambios"
    if "playwright" in lowered or "browser" in lowered:
        return "Validando interfaz"
    return "Ejecutando herramienta"


def _output_failed(output: str) -> bool:
    """Detecta fallos explícitos sin interpretar texto arbitrario como error."""

    if re.search(r"Exit code:\s*[1-9]\d*", output, flags=re.IGNORECASE):
        return True
    if re.search(r'"ok"\s*:\s*false', output, flags=re.IGNORECASE):
        return True
    return bool(re.search(r'"failed"\s*:\s*[1-9]\d*', output, flags=re.IGNORECASE))


def _output_summary(output: object) -> str | None:
    """Resume resultados técnicos frecuentes antes de mostrarlos."""

    if not isinstance(output, str):
        return None
    totals = re.search(
        r'"total"\s*:\s*(\d+).*?"ok"\s*:\s*(\d+).*?"failed"\s*:\s*(\d+)',
        output,
        flags=re.DOTALL,
    )
    if totals is not None:
        total, ok, failed = totals.groups()
        return f"Comprobaciones: {ok}/{total} correctas; {failed} fallidas"
    coverage = re.search(
        r'"playwrightExactCovered"\s*:\s*(\d+).*?"discoveredTotal"\s*:\s*(\d+)',
        output,
        flags=re.DOTALL,
    )
    if coverage is not None:
        covered, total = coverage.groups()
        return f"Cobertura Playwright: {covered}/{total}"
    reverse_coverage = re.search(
        r'"discoveredTotal"\s*:\s*(\d+).*?"playwrightExactCovered"\s*:\s*(\d+)',
        output,
        flags=re.DOTALL,
    )
    if reverse_coverage is not None:
        total, covered = reverse_coverage.groups()
        return f"Cobertura Playwright: {covered}/{total}"
    exit_code = re.search(r"Exit code:\s*(\d+)", output, flags=re.IGNORECASE)
    wall_time = re.search(r"Wall time:\s*([^\r\n]+)", output, flags=re.IGNORECASE)
    if exit_code is not None:
        summary = f"Código de salida {exit_code.group(1)}"
        if wall_time is not None:
            summary += f" · {wall_time.group(1).strip()}"
        return summary
    first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
    return _sanitize_text(first_line, 180)


def _add_activity(
    state: _SessionAccumulator,
    activity_type: str,
    label: str,
    status: AgentState,
    timestamp: datetime,
    summary: str | None = None,
) -> None:
    """Añade actividad reciente evitando duplicados consecutivos."""

    item = ActivityItem(
        activity_type=activity_type,
        label=label,
        status=status,
        summary=summary,
        timestamp=timestamp,
    )
    if state.activity:
        previous = state.activity[-1]
        if (
            previous.activity_type == item.activity_type
            and previous.label == item.label
            and previous.summary == item.summary
        ):
            state.activity[-1] = item
            return
    state.activity.append(item)


def _update_last_activity(state: _SessionAccumulator, timestamp: datetime) -> None:
    """Avanza la marca temporal de actividad sin permitir retrocesos."""

    if state.latest_event_at is None or timestamp > state.latest_event_at:
        state.latest_event_at = timestamp
    if state.task_last_activity_at is None or timestamp > state.task_last_activity_at:
        state.task_last_activity_at = timestamp


def _consume_session_meta(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Extrae metadatos de sesión y proyecto del primer evento del JSONL."""

    session_id = _optional_text(payload.get("session_id", payload.get("id")), 120)
    started_at = _parse_timestamp(payload.get("timestamp")) or timestamp
    project = _project_alias(payload.get("cwd"))
    state.session_id = session_id or state.session_id
    state.session_started_at = started_at
    state.originator = _optional_text(payload.get("originator"), 80)
    state.source = _optional_text(payload.get("source"), 80)
    state.cli_version = _optional_text(payload.get("cli_version"), 40)
    state.model_provider = _optional_text(payload.get("model_provider"), 80)
    conversation_name = _sanitize_text(extract_conversation_title(payload), 120)
    if conversation_name is not None:
        state.conversation_name = conversation_name
    if project is not None:
        state.project_name, state.cwd_alias = project


def _consume_token_count(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Conserva el último consumo y la última cuota completa de la sesión."""

    info = _as_object_dict(payload.get("info"))
    if info is None:
        return
    rate_limits = _as_object_dict(payload.get("rate_limits"))
    if rate_limits is None:
        rate_limits = _as_object_dict(info.get("rate_limits"))
    event = _TokenEvent(timestamp, state.source_reference, info, rate_limits)
    state.latest_usage = event
    if _has_rate_windows(event):
        state.latest_rate_limits = event


def _consume_task_started(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Abre una tarea y limpia bloqueos pertenecientes al turno anterior."""

    state.task_started_at = _parse_epoch(payload.get("started_at")) or timestamp
    state.task_active = True
    state.task_completed = False
    state.blocked_reason = None
    state.blocked_message = None
    state.error_message = None
    state.pending_tools.clear()
    _add_activity(state, "task", "Tarea iniciada", AgentState.WORKING, timestamp)


def _consume_task_complete(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Cierra una tarea distinguiendo éxito, fallo y límite agotado."""

    error = _as_object_dict(payload.get("error"))
    raw_last_message = payload.get("last_agent_message")
    last_message = _sanitize_text(raw_last_message, 180)
    objective = _sanitize_text(extract_objective_block(raw_last_message), 500)
    result = _sanitize_text(extract_result_from_message(raw_last_message), 220)
    pending = _sanitize_text(extract_pending_from_message(raw_last_message), 220)
    if last_message is not None and not is_internal_task_text(raw_last_message):
        state.latest_agent_message = last_message
    if objective is not None:
        state.objective = objective
        state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)
    if result is not None:
        state.last_result = result
    if pending is not None:
        state.pending = pending
    state.task_active = False
    state.pending_tools.clear()
    if error is None:
        state.task_completed = True
        state.error_message = None
        if state.last_result is None and last_message is not None:
            state.last_result = last_message
        _add_activity(
            state,
            "task",
            "Tarea completada",
            AgentState.COMPLETED,
            timestamp,
            last_message,
        )
        return
    error_code = _optional_text(error.get("codex_error_info"), 80)
    error_message = _sanitize_text(error.get("message"), 180)
    if error_code == "usage_limit_exceeded":
        state.task_completed = False
        state.blocked_reason = "usage_limit_exceeded"
        state.blocked_message = "Límite de uso agotado; consulta el reinicio de cuota."
        state.error_message = None
        _add_activity(
            state,
            "limit",
            "Límite de uso agotado",
            AgentState.WAITING,
            timestamp,
            state.blocked_message,
        )
        return
    state.task_completed = False
    state.error_message = error_message or error_code or "La tarea terminó con un error."
    _add_activity(
        state,
        "error",
        "Tarea con error",
        AgentState.ERROR,
        timestamp,
        state.error_message,
    )


def _consume_event_message(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Procesa eventos de estado emitidos por Codex Desktop."""

    event_type = payload.get("type")
    if event_type == "token_count":
        _consume_token_count(state, payload, timestamp)
        return
    if event_type == "task_started":
        _consume_task_started(state, payload, timestamp)
        return
    if event_type == "task_complete":
        _consume_task_complete(state, payload, timestamp)
        return
    if event_type == "thread_goal_updated":
        goal = _as_object_dict(payload.get("goal"))
        raw_objective = goal.get("objective") if goal is not None else None
        objective = _sanitize_text(normalize_goal_objective(raw_objective), 500)
        if objective is not None and not _is_technical_objective(objective):
            state.objective = objective
            state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)
        return
    if event_type in {"thread_title_updated", "thread_name_updated"}:
        conversation_name = _sanitize_text(extract_conversation_title(payload), 120)
        if conversation_name is not None:
            state.conversation_name = conversation_name
        return
    if event_type == "agent_message":
        raw_message = payload.get("message")
        message = _sanitize_text(raw_message, 180)
        objective = _sanitize_text(extract_objective_block(raw_message), 500)
        result = _sanitize_text(extract_result_from_message(raw_message), 220)
        pending = _sanitize_text(extract_pending_from_message(raw_message), 220)
        if objective is not None:
            state.objective = objective
            state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)
        if result is not None:
            state.last_result = result
        if pending is not None:
            state.pending = pending
        if message is not None and not is_internal_task_text(raw_message):
            state.latest_agent_message = message
            _add_activity(
                state,
                "message",
                "Actualización de Codex",
                AgentState.WORKING,
                timestamp,
                message,
            )
        return
    if event_type == "usage_limit_exceeded":
        state.task_active = False
        state.blocked_reason = "usage_limit_exceeded"
        state.blocked_message = "Límite de uso agotado; consulta el reinicio de cuota."
        _add_activity(
            state,
            "limit",
            "Límite de uso agotado",
            AgentState.WAITING,
            timestamp,
            state.blocked_message,
        )
        return
    if event_type == "patch_apply_end":
        _add_activity(
            state,
            "patch",
            "Cambios aplicados",
            AgentState.COMPLETED,
            timestamp,
        )


def _consume_tool_call(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Registra una herramienta pendiente sin exponer argumentos completos."""

    name = _optional_text(payload.get("name"), 80) or "herramienta"
    arguments = extract_tool_arguments(payload)
    if arguments is not None:
        conversation_name = _sanitize_text(extract_conversation_title(arguments), 120)
        if conversation_name is not None:
            state.conversation_name = conversation_name
    if name.casefold() in {"create_goal", "update_goal"}:
        objective = _sanitize_text(extract_tool_objective(payload), 500)
        if objective is not None:
            state.objective = objective
            state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)
    call_id = _optional_text(payload.get("call_id", payload.get("id")), 160)
    if call_id is not None:
        state.pending_tools[call_id] = name
    state.task_active = True
    state.task_completed = False
    state.error_message = None
    _add_activity(
        state,
        "tool",
        _tool_label(name),
        AgentState.WORKING,
        timestamp,
        _tool_summary(payload),
    )


def _consume_tool_output(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Cierra una herramienta y resume su resultado de forma acotada."""

    call_id = _optional_text(payload.get("call_id"), 160)
    name = state.pending_tools.pop(call_id, "herramienta") if call_id is not None else "herramienta"
    output = payload.get("output")
    output_text = output if isinstance(output, str) else ""
    failed = _output_failed(output_text)
    status = AgentState.ERROR if failed else AgentState.COMPLETED
    label = "Herramienta con error" if failed else "Herramienta completada"
    if name != "herramienta":
        label = f"{label}: {name[:60]}"
    summary = _output_summary(output)
    if not failed and is_meaningful_result(summary):
        state.last_result = summary
    if failed:
        state.error_message = summary or "Una herramienta devolvió un error."
    _add_activity(state, "tool_result", label, status, timestamp, summary)


def _consume_response_item(
    state: _SessionAccumulator,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Procesa mensajes y herramientas, omitiendo razonamiento cifrado."""

    item_type = payload.get("type")
    if item_type == "message":
        role = payload.get("role")
        if role == "user":
            raw_message = raw_message_text(payload)
            objective = _sanitize_text(extract_objective_block(raw_message), 500)
            if objective is not None:
                state.objective = objective
                state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)
            if raw_message is not None and not is_internal_task_text(raw_message):
                message = _sanitize_text(raw_message, 180)
                if message is not None:
                    state.latest_user_message = message
        return
    if item_type in {"function_call", "custom_tool_call"}:
        _consume_tool_call(state, payload, timestamp)
        return
    if item_type in {"function_call_output", "custom_tool_call_output"}:
        _consume_tool_output(state, payload, timestamp)
        return
    if item_type == "patch_apply_end":
        _add_activity(
            state,
            "patch",
            "Cambios aplicados",
            AgentState.COMPLETED,
            timestamp,
        )


def _consume_record(state: _SessionAccumulator, raw_line: bytes) -> None:
    """Actualiza un acumulador a partir de una línea JSONL válida."""

    if not raw_line or len(raw_line) > _MAX_JSON_LINE_BYTES:
        return
    try:
        raw_record: object = json.loads(raw_line.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return
    record = _as_object_dict(raw_record)
    if record is None:
        return
    timestamp = _parse_timestamp(record.get("timestamp"))
    if timestamp is None:
        return
    _update_last_activity(state, timestamp)
    payload = _as_object_dict(record.get("payload"))
    if payload is None:
        return
    record_type = record.get("type")
    if record_type == "session_meta":
        _consume_session_meta(state, payload, timestamp)
        return
    if record_type == "event_msg":
        _consume_event_message(state, payload, timestamp)
        return
    if record_type == "response_item":
        _consume_response_item(state, payload, timestamp)


def _new_cursor(path: Path, sessions_dir: Path, stat_result: os.stat_result) -> _FileCursor:
    """Crea un cursor vacío para un archivo nuevo o rotado."""

    file_id = stat_result.st_ino
    modified_ns = int(stat_result.st_mtime_ns)
    size_bytes = int(stat_result.st_size)
    return _FileCursor(
        file_id=file_id,
        modified_ns=modified_ns,
        size_bytes=size_bytes,
        offset=0,
        remainder=b"",
        state=_SessionAccumulator(source_reference=_source_reference(path, sessions_dir)),
    )


def _requires_reset(cursor: _FileCursor, stat_result: os.stat_result) -> bool:
    """Detecta truncado, sustitución o reescritura de tamaño estable."""

    file_id = stat_result.st_ino
    modified_ns = int(stat_result.st_mtime_ns)
    size_bytes = int(stat_result.st_size)
    if isinstance(file_id, int) and cursor.file_id is not None and file_id != cursor.file_id:
        return True
    if size_bytes < cursor.offset:
        return True
    return modified_ns != cursor.modified_ns and size_bytes == cursor.offset


def _read_incremental(path: Path, cursor: _FileCursor, stat_result: os.stat_result) -> None:
    """Lee únicamente bytes nuevos y mantiene memoria limitada por línea."""

    with path.open("rb") as handle:
        handle.seek(cursor.offset)
        remainder = cursor.remainder
        while True:
            chunk = handle.read(_READ_CHUNK_BYTES)
            if not chunk:
                break
            cursor.offset += len(chunk)
            combined = remainder + chunk
            lines = combined.split(b"\n")
            remainder = lines.pop()
            for raw_line in lines:
                _consume_record(cursor.state, raw_line.rstrip(b"\r"))
            if len(remainder) > _MAX_JSON_LINE_BYTES:
                remainder = b""
        cursor.remainder = remainder
    file_id = stat_result.st_ino
    cursor.file_id = file_id
    cursor.modified_ns = int(stat_result.st_mtime_ns)
    cursor.size_bytes = int(stat_result.st_size)


def _refresh_file_cache(
    sessions_dir: Path,
    file_cache: dict[Path, _FileCursor],
) -> None:
    """Actualiza cursores, reinicia archivos rotados y elimina entradas borradas."""

    active_paths: set[Path] = set()
    try:
        paths = list(sessions_dir.rglob("rollout-*.jsonl"))
    except OSError:
        paths = []
    for path in paths:
        active_paths.add(path)
        try:
            stat_result = path.stat()
        except OSError:
            continue
        cursor = file_cache.get(path)
        if cursor is None or _requires_reset(cursor, stat_result):
            cursor = _new_cursor(path, sessions_dir, stat_result)
        if int(stat_result.st_size) > cursor.offset:
            try:
                _read_incremental(path, cursor, stat_result)
            except OSError:
                continue
        else:
            cursor.modified_ns = int(stat_result.st_mtime_ns)
            cursor.size_bytes = int(stat_result.st_size)
        file_cache[path] = cursor
    for deleted_path in set(file_cache) - active_paths:
        del file_cache[deleted_path]


def _has_rate_windows(event: _TokenEvent) -> bool:
    """Indica si el evento contiene al menos una ventana de cuota real."""

    if event.rate_limits is None:
        return False
    return (
        _as_object_dict(event.rate_limits.get("primary")) is not None
        or _as_object_dict(event.rate_limits.get("secondary")) is not None
    )


def _latest_active_state(file_cache: dict[Path, _FileCursor]) -> _SessionAccumulator | None:
    """Selecciona la sesión con el evento más reciente de todos los archivos."""

    candidates = [
        cursor.state for cursor in file_cache.values() if cursor.state.latest_event_at is not None
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda state: state.latest_event_at or datetime.min.replace(tzinfo=UTC),
    )


def _latest_usage_event(file_cache: dict[Path, _FileCursor]) -> _TokenEvent | None:
    """Localiza el consumo más reciente disponible entre todas las sesiones."""

    events: list[_TokenEvent] = []
    for cursor in file_cache.values():
        event = cursor.state.latest_usage
        if event is not None:
            events.append(event)
    return max(events, key=lambda event: event.timestamp) if events else None


def _latest_rate_event(file_cache: dict[Path, _FileCursor]) -> _TokenEvent | None:
    """Localiza las últimas ventanas completas entre todas las sesiones."""

    events: list[_TokenEvent] = []
    for cursor in file_cache.values():
        event = cursor.state.latest_rate_limits
        if event is not None:
            events.append(event)
    return max(events, key=lambda event: event.timestamp) if events else None


def _build_token_usage(
    event: _TokenEvent,
    usage_key: str,
    scope: str,
) -> TokenUsageSnapshot | None:
    """Convierte un bloque de uso real en el modelo compatible existente."""

    usage = _as_object_dict(event.info.get(usage_key))
    if usage is None:
        return None
    context_window = _integer(event.info, "model_context_window")
    return TokenUsageSnapshot(
        input_tokens=_integer(usage, "input_tokens"),
        cached_input_tokens=_integer(usage, "cached_input_tokens"),
        cache_write_input_tokens=_integer(usage, "cache_write_input_tokens"),
        output_tokens=_integer(usage, "output_tokens"),
        reasoning_output_tokens=_integer(usage, "reasoning_output_tokens"),
        total_tokens=_integer(usage, "total_tokens"),
        model_context_window=context_window or None,
        scope=scope,
        source="codex_session_jsonl",
        updated_at=event.timestamp,
        source_reference=event.source_reference,
    )


def _build_usage_breakdown(event: _TokenEvent) -> UsageBreakdown | None:
    """Separa acumulado histórico, última petición y contexto estimado."""

    thread_total = _build_token_usage(event, "total_token_usage", "session_total")
    last_request = _build_token_usage(event, "last_token_usage", "last_request")
    context_tokens: int | None = None
    context_percent: float | None = None
    method: str | None = None
    if (
        last_request is not None
        and last_request.model_context_window is not None
        and last_request.model_context_window > 0
    ):
        context_tokens = min(last_request.input_tokens, last_request.model_context_window)
        context_percent = round(
            context_tokens / last_request.model_context_window * 100,
            2,
        )
        method = "last_request_input_tokens"
    if thread_total is None and last_request is None:
        return None
    return UsageBreakdown(
        thread_total=thread_total,
        last_request=last_request,
        context_used_tokens_estimated=context_tokens,
        context_used_percent_estimated=context_percent,
        context_estimation_method=method,
    )


def _build_window(value: object) -> RateLimitWindowSnapshot | None:
    """Convierte una ventana primaria o secundaria cuando está completa."""

    window = _as_object_dict(value)
    if window is None:
        return None
    used_percent = _number(window, "used_percent")
    window_minutes = _integer(window, "window_minutes")
    resets_at_raw = window.get("resets_at")
    if (
        used_percent is None
        or not 0 <= used_percent <= 100
        or window_minutes <= 0
        or not isinstance(resets_at_raw, int)
        or isinstance(resets_at_raw, bool)
    ):
        return None
    return RateLimitWindowSnapshot(
        used_percent=used_percent,
        remaining_percent=round(100 - used_percent, 2),
        window_minutes=window_minutes,
        resets_at=datetime.fromtimestamp(resets_at_raw, UTC),
    )


def _build_rate_limits(event: _TokenEvent, now: datetime) -> RateLimitsSnapshot | None:
    """Construye las cuotas reales y marca datos antiguos."""

    raw_limits = event.rate_limits
    if raw_limits is None:
        return None
    primary = _build_window(raw_limits.get("primary"))
    secondary = _build_window(raw_limits.get("secondary"))
    if primary is None and secondary is None:
        return None
    limit_id = raw_limits.get("limit_id")
    plan_type = raw_limits.get("plan_type")
    return RateLimitsSnapshot(
        limit_id=limit_id if isinstance(limit_id, str) and limit_id else "codex",
        plan_type=plan_type if isinstance(plan_type, str) and plan_type else None,
        primary=primary,
        secondary=secondary,
        source="codex_session_jsonl",
        updated_at=event.timestamp,
        source_reference=event.source_reference,
        is_stale=now - event.timestamp > timedelta(minutes=30),
    )


def _derive_status(state: _SessionAccumulator) -> tuple[AgentState, str | None, str | None]:
    """Aplica la máquina de estados a la sesión activa."""

    if state.blocked_reason is not None:
        return AgentState.WAITING, state.blocked_reason, state.blocked_message
    if state.error_message is not None:
        return AgentState.ERROR, "task_error", state.error_message
    if state.pending_tools:
        return AgentState.WORKING, "tool_running", "Codex está ejecutando una herramienta."
    if state.task_active:
        return AgentState.WORKING, "task_active", "Codex está trabajando en la tarea."
    if state.task_completed:
        return AgentState.COMPLETED, "task_complete", "La última tarea terminó correctamente."
    return AgentState.IDLE, None, None


def _build_session(state: _SessionAccumulator) -> SessionInfo | None:
    """Construye metadatos públicos cuando la sesión está identificada."""

    if state.session_id is None or state.session_started_at is None:
        return None
    return SessionInfo(
        session_id=state.session_id,
        started_at=state.session_started_at,
        last_activity_at=state.latest_event_at,
        originator=state.originator,
        source=state.source,
        cli_version=state.cli_version,
        model_provider=state.model_provider,
    )


def _build_project(state: _SessionAccumulator) -> ProjectInfo | None:
    """Construye la identidad del proyecto sin publicar la ruta completa."""

    if state.project_name is None or state.cwd_alias is None:
        return None
    return ProjectInfo(display_name=state.project_name, cwd_alias=state.cwd_alias)


def _task_display_name(state: _SessionAccumulator) -> str | None:
    """Prioriza petición del usuario, objetivo útil y actualización del agente."""

    if state.conversation_name is not None:
        return state.conversation_name
    if state.objective is not None:
        return _sanitize_text(derive_objective_title(state.objective), 180)
    return state.latest_user_message or state.latest_goal or state.latest_agent_message


def _task_activity(state: _SessionAccumulator, status: AgentState) -> str | None:
    """Describe la actividad actual sin confundirla con el nombre de la tarea."""

    if state.blocked_message is not None:
        return state.blocked_message
    if state.pending_tools:
        tool_name = next(reversed(state.pending_tools.values()))
        return f"Ejecutando {tool_name[:140]}"
    if state.activity:
        latest = state.activity[-1]
        return latest.summary or latest.label
    if status == AgentState.COMPLETED:
        return "Tarea completada"
    return None


def _build_task(state: _SessionAccumulator, status: AgentState) -> TaskInfo | None:
    """Construye la tarea principal con texto sanitizado y fechas reales."""

    display_name = _task_display_name(state)
    activity = _task_activity(state, status)
    if display_name is None and activity is None and state.task_started_at is None:
        return None
    return TaskInfo(
        display_name=display_name,
        conversation_name=state.conversation_name,
        objective=state.objective,
        status=status,
        activity=activity,
        last_result=state.last_result,
        pending=state.pending,
        started_at=state.task_started_at,
        last_activity_at=state.task_last_activity_at,
    )


class CodexAdapter(PlatformAdapter):
    """Lee sesiones JSONL reales mediante cursores incrementales por archivo."""

    def __init__(
        self,
        sessions_dir: Path | None = None,
        executable: str = "codex",
    ) -> None:
        """Configura la carpeta local y el ejecutable usado para detección."""

        self._sessions_dir = sessions_dir or Path.home() / ".codex" / "sessions"
        self._executable = executable
        self._file_cache: dict[Path, _FileCursor] = {}

    @property
    def platform_id(self) -> str:
        """Devuelve el identificador estable de OpenAI Codex."""

        return "codex"

    async def collect(self) -> PlatformSnapshot:
        """Obtiene la telemetría real sin bloquear el bucle asíncrono."""

        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> PlatformSnapshot:
        """Actualiza cursores y construye una instantánea sanitizada."""

        executable_available = shutil.which(self._executable) is not None
        if not self._sessions_dir.is_dir():
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="OpenAI Codex",
                status=AgentState.OFFLINE,
                status_reason="session_source_unavailable",
                status_message="No se encuentra la carpeta local de sesiones de Codex.",
            )
        _refresh_file_cache(self._sessions_dir, self._file_cache)
        active_state = _latest_active_state(self._file_cache)
        if active_state is None:
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="OpenAI Codex",
                status=AgentState.IDLE if executable_available else AgentState.OFFLINE,
                status_reason=None if executable_available else "codex_unavailable",
            )
        now = datetime.now(UTC)
        usage_event = active_state.latest_usage or _latest_usage_event(self._file_cache)
        rate_event = _latest_rate_event(self._file_cache)
        usage = _build_usage_breakdown(usage_event) if usage_event is not None else None
        thread_total = usage.thread_total if usage is not None else None
        rate_limits = _build_rate_limits(rate_event, now) if rate_event is not None else None
        primary = rate_limits.primary if rate_limits is not None else None
        secondary = rate_limits.secondary if rate_limits is not None else None
        status, status_reason, status_message = _derive_status(active_state)
        return PlatformSnapshot(
            platform_id=self.platform_id,
            display_name="OpenAI Codex",
            status=status,
            status_reason=status_reason,
            status_message=status_message,
            tokens_today=None,
            weekly_remaining_pct=(
                round(secondary.remaining_percent) if secondary is not None else None
            ),
            rolling_remaining_pct=(
                round(primary.remaining_percent) if primary is not None else None
            ),
            next_reset_at=primary.resets_at if primary is not None else None,
            active_agents=0,
            agents=[],
            token_usage=thread_total,
            usage=usage,
            rate_limits=rate_limits,
            session=_build_session(active_state),
            project=_build_project(active_state),
            task=_build_task(active_state, status),
            recent_activity=list(reversed(active_state.activity)),
        )
