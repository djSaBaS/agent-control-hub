"""Lectura incremental y máquina de estados de sesiones locales de Codex."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from agent_control_hub.adapters.codex_sanitizer import (
    as_object_dict,
    call_identifier,
    classify_tool,
    extract_message_text,
    output_result,
    parse_timestamp,
    project_alias,
    sanitize_text,
    source_reference,
    string_value,
    task_candidate,
)
from agent_control_hub.models import ActivityItem, AgentState

_ACTIVITY_LIMIT = 20
_PENDING_CALL_LIMIT = 32
_HEAD_SIGNATURE_BYTES = 128


def _activity_queue() -> deque[ActivityItem]:
    """Crea una cola acotada para la actividad técnica reciente."""

    return deque(maxlen=_ACTIVITY_LIMIT)


@dataclass(frozen=True, slots=True)
class TokenEvent:
    """Evento token_count normalizado antes de construir el modelo público."""

    timestamp: datetime
    source_reference: str
    info: dict[str, object]
    rate_limits: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class _PendingCall:
    """Herramienta iniciada y pendiente de su resultado correspondiente."""

    label: str
    activity_type: str
    tool_name: str
    timestamp: datetime


@dataclass(slots=True)
class SessionState:
    """Estado incremental de un archivo de sesión de Codex."""

    path: Path
    source_reference: str
    offset: int = 0
    partial_line: bytes = b""
    head_signature: bytes = b""
    modified_ns: int = 0
    file_id: int = 0
    session_id: str | None = None
    started_at: datetime | None = None
    last_activity_at: datetime | None = None
    originator: str | None = None
    source: str | None = None
    cli_version: str | None = None
    model_provider: str | None = None
    project_name: str | None = None
    project_alias: str | None = None
    status: AgentState = AgentState.IDLE
    status_reason: str | None = "no_active_task"
    status_message: str | None = None
    status_updated_at: datetime | None = None
    task_started_at: datetime | None = None
    task_activity: str | None = None
    user_task_name: str | None = None
    goal_task_name: str | None = None
    agent_task_name: str | None = None
    latest_usage: TokenEvent | None = None
    latest_rate_limits: TokenEvent | None = None
    recent_activity: deque[ActivityItem] = field(default_factory=_activity_queue)
    pending_calls: dict[str, _PendingCall] = field(default_factory=dict)


def _touch(state: SessionState, timestamp: datetime) -> None:
    """Actualiza la última actividad observada en orden temporal."""

    if state.last_activity_at is None or timestamp > state.last_activity_at:
        state.last_activity_at = timestamp


def _set_status(
    state: SessionState,
    timestamp: datetime,
    status: AgentState,
    reason: str,
    message: str | None,
    activity: str | None,
) -> None:
    """Aplica una transición de estado solo si no retrocede en el tiempo."""

    if state.status_updated_at is not None and timestamp < state.status_updated_at:
        return
    state.status = status
    state.status_reason = reason
    state.status_message = message
    state.task_activity = activity
    state.status_updated_at = timestamp
    _touch(state, timestamp)


def _append_activity(
    state: SessionState,
    timestamp: datetime,
    activity_type: str,
    label: str,
    status: AgentState,
    *,
    summary: str | None = None,
    duration_seconds: float | None = None,
    tool_name: str | None = None,
) -> None:
    """Añade una actividad pública respetando el límite de memoria."""

    state.recent_activity.append(
        ActivityItem(
            activity_type=activity_type,
            label=sanitize_text(label, 120),
            status=status,
            summary=sanitize_text(summary, 240) if summary else None,
            timestamp=timestamp,
            duration_seconds=duration_seconds,
            tool_name=sanitize_text(tool_name, 80) if tool_name else None,
        )
    )
    _touch(state, timestamp)


def _bounded_pending_call(state: SessionState, call_id: str, call: _PendingCall) -> None:
    """Conserva un número acotado de herramientas pendientes."""

    if len(state.pending_calls) >= _PENDING_CALL_LIMIT:
        oldest_key = next(iter(state.pending_calls))
        del state.pending_calls[oldest_key]
    state.pending_calls[call_id] = call


def _parse_token_event(
    payload: dict[str, object],
    timestamp: datetime,
    event_source_reference: str,
) -> TokenEvent | None:
    """Extrae un evento token_count válido y tolera formatos históricos."""

    info = as_object_dict(payload.get("info"))
    if info is None:
        return None
    rate_limits = as_object_dict(payload.get("rate_limits"))
    if rate_limits is None:
        rate_limits = as_object_dict(info.get("rate_limits"))
    return TokenEvent(timestamp, event_source_reference, info, rate_limits)


def has_rate_windows(event: TokenEvent) -> bool:
    """Indica si un evento contiene al menos una ventana de cuota real."""

    if event.rate_limits is None:
        return False
    return (
        as_object_dict(event.rate_limits.get("primary")) is not None
        or as_object_dict(event.rate_limits.get("secondary")) is not None
    )


def _process_session_meta(
    state: SessionState,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Normaliza los metadatos iniciales de una sesión."""

    state.session_id = string_value(payload, "session_id", 128) or string_value(
        payload,
        "id",
        128,
    )
    state.started_at = parse_timestamp(payload.get("timestamp")) or timestamp
    state.originator = string_value(payload, "originator", 80)
    state.source = string_value(payload, "source", 80)
    state.cli_version = string_value(payload, "cli_version", 40)
    state.model_provider = string_value(payload, "model_provider", 40)
    cwd = payload.get("cwd")
    if isinstance(cwd, str):
        alias = project_alias(cwd)
        state.project_name = alias
        state.project_alias = alias
    _touch(state, timestamp)


def _process_patch(state: SessionState, timestamp: datetime) -> None:
    """Registra un parche aplicado sin publicar archivos ni contenido."""

    _set_status(
        state,
        timestamp,
        AgentState.WORKING,
        "patch_applied",
        None,
        "Cambios aplicados",
    )
    _append_activity(
        state,
        timestamp,
        "patch",
        "Cambios aplicados",
        AgentState.COMPLETED,
    )


def _process_event_message(
    state: SessionState,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Procesa eventos de ciclo de vida, uso y progreso de Codex."""

    event_type = payload.get("type")
    if event_type == "token_count":
        token_event = _parse_token_event(payload, timestamp, state.source_reference)
        if token_event is not None:
            state.latest_usage = token_event
            if has_rate_windows(token_event):
                state.latest_rate_limits = token_event
            _touch(state, timestamp)
        return
    if event_type == "thread_goal_updated":
        goal = as_object_dict(payload.get("goal"))
        objective = goal.get("objective") if goal is not None else None
        if isinstance(objective, str):
            state.goal_task_name = task_candidate(objective)
        _touch(state, timestamp)
        return
    if event_type == "user_message":
        text = extract_message_text(payload)
        if text:
            state.user_task_name = task_candidate(text)
        _touch(state, timestamp)
        return
    if event_type == "task_started":
        state.task_started_at = parse_timestamp(payload.get("started_at")) or timestamp
        _set_status(
            state,
            timestamp,
            AgentState.WORKING,
            "task_started",
            None,
            "Procesando tarea",
        )
        _append_activity(
            state,
            timestamp,
            "task",
            "Tarea iniciada",
            AgentState.WORKING,
        )
        return
    if event_type == "task_complete":
        _set_status(
            state,
            timestamp,
            AgentState.COMPLETED,
            "task_complete",
            "Tarea completada",
            "Tarea completada",
        )
        _append_activity(
            state,
            timestamp,
            "task",
            "Tarea completada",
            AgentState.COMPLETED,
        )
        return
    if event_type == "usage_limit_exceeded":
        _set_status(
            state,
            timestamp,
            AgentState.WAITING,
            "usage_limit_exceeded",
            "Límite de uso agotado",
            "Esperando el reinicio de la cuota",
        )
        _append_activity(
            state,
            timestamp,
            "limit",
            "Límite de uso agotado",
            AgentState.WAITING,
        )
        return
    if event_type == "patch_apply_end":
        _process_patch(state, timestamp)
        return
    if event_type == "agent_message":
        message = payload.get("message")
        if isinstance(message, str):
            sanitized = sanitize_text(message)
            state.agent_task_name = task_candidate(message)
            _set_status(
                state,
                timestamp,
                AgentState.WORKING,
                "agent_message",
                None,
                sanitized[:200],
            )
            _append_activity(
                state,
                timestamp,
                "progress",
                "Progreso actualizado",
                AgentState.WORKING,
                summary=sanitized,
            )
        return
    if event_type in {"error", "task_failed"}:
        reason = event_type if isinstance(event_type, str) else "task_error"
        _set_status(
            state,
            timestamp,
            AgentState.ERROR,
            reason,
            "Codex informó de un error",
            "Error en la tarea",
        )
        _append_activity(
            state,
            timestamp,
            "error",
            "Error en la tarea",
            AgentState.ERROR,
        )


def _process_message_item(
    state: SessionState,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Extrae candidatos de tarea de mensajes de usuario y progreso."""

    role = payload.get("role")
    text = extract_message_text(payload)
    if not text:
        return
    if role == "user":
        state.user_task_name = task_candidate(text)
        _touch(state, timestamp)
    elif role == "assistant" and payload.get("phase") == "commentary":
        state.agent_task_name = task_candidate(text)
        _touch(state, timestamp)


def _process_tool_call(
    state: SessionState,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Registra una herramienta pendiente sin exponer argumentos sensibles."""

    raw_name = payload.get("name")
    name = raw_name if isinstance(raw_name, str) and raw_name else "herramienta"
    arguments = payload.get("arguments") or payload.get("input")
    activity_type, label = classify_tool(name, arguments)
    call_id = call_identifier(payload)
    if call_id:
        _bounded_pending_call(
            state,
            call_id,
            _PendingCall(label, activity_type, name[:80], timestamp),
        )
    _set_status(
        state,
        timestamp,
        AgentState.WORKING,
        "tool_running",
        None,
        label,
    )
    _append_activity(
        state,
        timestamp,
        activity_type,
        label,
        AgentState.WORKING,
        tool_name=name,
    )


def _process_tool_output(
    state: SessionState,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Relaciona la salida con su llamada y publica solo un resultado reducido."""

    call_id = call_identifier(payload)
    pending = state.pending_calls.pop(call_id, None) if call_id else None
    output = payload.get("output")
    output_text = output if isinstance(output, str) else ""
    succeeded, summary, duration = output_result(output_text)
    result_status = AgentState.COMPLETED if succeeded else AgentState.ERROR
    label = pending.label if pending is not None else "Herramienta finalizada"
    activity_type = pending.activity_type if pending is not None else "tool"
    tool_name = pending.tool_name if pending is not None else None
    if succeeded:
        _set_status(
            state,
            timestamp,
            AgentState.WORKING,
            "tool_completed",
            None,
            label,
        )
    else:
        _set_status(
            state,
            timestamp,
            AgentState.ERROR,
            "tool_error",
            summary,
            label,
        )
    _append_activity(
        state,
        timestamp,
        activity_type,
        label,
        result_status,
        summary=summary,
        duration_seconds=duration,
        tool_name=tool_name,
    )


def _process_response_item(
    state: SessionState,
    payload: dict[str, object],
    timestamp: datetime,
) -> None:
    """Procesa mensajes y herramientas almacenadas como response_item."""

    item_type = payload.get("type")
    if item_type == "message":
        _process_message_item(state, payload, timestamp)
    elif item_type in {"function_call", "custom_tool_call"}:
        _process_tool_call(state, payload, timestamp)
    elif item_type in {"function_call_output", "custom_tool_call_output"}:
        _process_tool_output(state, payload, timestamp)


def _process_record(state: SessionState, record: dict[str, object]) -> None:
    """Actualiza una sesión a partir de un registro JSONL válido."""

    timestamp = parse_timestamp(record.get("timestamp"))
    payload = as_object_dict(record.get("payload"))
    record_type = record.get("type")
    if timestamp is None or payload is None:
        return
    if record_type == "session_meta":
        _process_session_meta(state, payload, timestamp)
    elif record_type == "event_msg":
        _process_event_message(state, payload, timestamp)
    elif record_type == "response_item":
        _process_response_item(state, payload, timestamp)
    elif record_type == "patch_apply_end":
        _process_patch(state, timestamp)


def _process_line(state: SessionState, raw_line: bytes) -> None:
    """Decodifica una línea completa y omite JSON corrupto o incompleto."""

    try:
        raw_record: object = json.loads(raw_line.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return
    record = as_object_dict(raw_record)
    if record is not None:
        _process_record(state, record)


def _reset_state(state: SessionState) -> None:
    """Reinicia el estado cuando el archivo se trunca o rota."""

    state.offset = 0
    state.partial_line = b""
    state.head_signature = b""
    state.modified_ns = 0
    state.file_id = 0
    state.session_id = None
    state.started_at = None
    state.last_activity_at = None
    state.originator = None
    state.source = None
    state.cli_version = None
    state.model_provider = None
    state.project_name = None
    state.project_alias = None
    state.status = AgentState.IDLE
    state.status_reason = "no_active_task"
    state.status_message = None
    state.status_updated_at = None
    state.task_started_at = None
    state.task_activity = None
    state.user_task_name = None
    state.goal_task_name = None
    state.agent_task_name = None
    state.latest_usage = None
    state.latest_rate_limits = None
    state.recent_activity.clear()
    state.pending_calls.clear()


def _refresh_session_file(state: SessionState) -> None:
    """Lee únicamente los bytes añadidos y detecta truncado o sustitución."""

    stat = state.path.stat()
    with state.path.open("rb") as handle:
        head_signature = handle.read(_HEAD_SIGNATURE_BYTES)
        replaced = bool(state.file_id and state.file_id != stat.st_ino)
        rotated = bool(state.head_signature and not head_signature.startswith(state.head_signature))
        truncated = stat.st_size < state.offset
        if replaced or rotated or truncated:
            _reset_state(state)
        state.head_signature = head_signature
        state.file_id = stat.st_ino
        if stat.st_size == state.offset and stat.st_mtime_ns == state.modified_ns:
            return
        handle.seek(state.offset)
        new_bytes = handle.read()
        state.offset = handle.tell()
    state.modified_ns = stat.st_mtime_ns
    if not new_bytes:
        return
    combined = state.partial_line + new_bytes
    lines = combined.split(b"\n")
    if combined.endswith(b"\n"):
        state.partial_line = b""
    else:
        state.partial_line = lines.pop()
    for line in lines:
        if line:
            _process_line(state, line)


def refresh_sessions(
    sessions_dir: Path,
    file_cache: dict[Path, SessionState],
) -> list[SessionState]:
    """Actualiza el inventario de sesiones y elimina archivos desaparecidos."""

    try:
        paths = list(sessions_dir.rglob("rollout-*.jsonl"))
    except OSError:
        paths = []
    active_paths = set(paths)
    for path in paths:
        state = file_cache.get(path)
        if state is None:
            state = SessionState(path=path, source_reference=source_reference(path, sessions_dir))
            file_cache[path] = state
        try:
            _refresh_session_file(state)
        except OSError:
            continue
    for deleted_path in set(file_cache) - active_paths:
        del file_cache[deleted_path]
    return list(file_cache.values())


def _state_timestamp(state: SessionState) -> datetime:
    """Obtiene una marca comparable incluso en sesiones sin actividad completa."""

    return state.last_activity_at or state.started_at or datetime.min.replace(tzinfo=UTC)


def select_active_session(states: list[SessionState]) -> SessionState | None:
    """Selecciona la sesión con actividad real más reciente."""

    candidates = [state for state in states if state.session_id or state.last_activity_at]
    return max(candidates, key=_state_timestamp, default=None)


def select_latest_limits(states: list[SessionState]) -> TokenEvent | None:
    """Conserva las ventanas oficiales más recientes entre todas las sesiones."""

    events: list[TokenEvent] = []
    for state in states:
        if state.latest_rate_limits is not None:
            events.append(state.latest_rate_limits)
    return max(events, key=lambda event: event.timestamp, default=None)
