"""Adaptador local para uso real de OpenAI Codex."""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.models import (
    AgentState,
    PlatformSnapshot,
    RateLimitsSnapshot,
    RateLimitWindowSnapshot,
    TokenUsageSnapshot,
)


@dataclass(frozen=True, slots=True)
class _TokenEvent:
    """Evento token_count normalizado antes de construir el modelo público."""

    timestamp: datetime
    source_reference: str
    info: dict[str, object]
    rate_limits: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class _FileFingerprint:
    """Identifica una versión concreta de un archivo de sesión."""

    modified_ns: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class _CachedFileEvents:
    """Conserva el último consumo y los últimos límites de un archivo."""

    fingerprint: _FileFingerprint
    latest_usage: _TokenEvent | None
    latest_rate_limits: _TokenEvent | None


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


def _iter_lines_reverse(path: Path, chunk_size: int = 64 * 1024) -> Iterator[str]:
    """Lee un JSONL desde el final sin cargar el archivo completo en memoria."""

    with path.open("rb") as handle:
        handle.seek(0, 2)
        position = handle.tell()
        buffer = b""
        while position > 0:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            buffer = handle.read(read_size) + buffer
            lines = buffer.split(b"\n")
            buffer = lines[0]
            for raw_line in reversed(lines[1:]):
                if raw_line:
                    yield raw_line.decode("utf-8", errors="replace")
        if buffer:
            yield buffer.decode("utf-8", errors="replace")


def _parse_token_event(line: str, path: Path, sessions_dir: Path) -> _TokenEvent | None:
    """Extrae un evento token_count válido y omite líneas incompletas."""

    if '"token_count"' not in line:
        return None
    try:
        raw_record: object = json.loads(line)
    except json.JSONDecodeError:
        return None
    record = _as_object_dict(raw_record)
    if record is None:
        return None
    payload = _as_object_dict(record.get("payload"))
    if payload is None or payload.get("type") != "token_count":
        return None
    info = _as_object_dict(payload.get("info"))
    timestamp = _parse_timestamp(record.get("timestamp"))
    if info is None or timestamp is None:
        return None

    # Codex actual guarda rate_limits como hermano de info. Se conserva un
    # fallback para archivos antiguos que pudieran haberlo incluido dentro.
    rate_limits = _as_object_dict(payload.get("rate_limits"))
    if rate_limits is None:
        rate_limits = _as_object_dict(info.get("rate_limits"))

    try:
        source_reference = path.relative_to(sessions_dir).as_posix()
    except ValueError:
        source_reference = path.name
    return _TokenEvent(timestamp, source_reference, info, rate_limits)


def _has_rate_windows(event: _TokenEvent) -> bool:
    """Indica si el evento contiene al menos una ventana de cuota real."""

    if event.rate_limits is None:
        return False
    return (
        _as_object_dict(event.rate_limits.get("primary")) is not None
        or _as_object_dict(event.rate_limits.get("secondary")) is not None
    )


def _fingerprint(path: Path) -> _FileFingerprint:
    """Obtiene una huella barata para detectar archivos nuevos o modificados."""

    stat = path.stat()
    return _FileFingerprint(stat.st_mtime_ns, stat.st_size)


def _scan_session_file(
    path: Path,
    sessions_dir: Path,
) -> tuple[_TokenEvent | None, _TokenEvent | None]:
    """Busca desde el final los últimos datos relevantes de una sesión."""

    latest_usage: _TokenEvent | None = None
    latest_rate_limits: _TokenEvent | None = None
    for line in _iter_lines_reverse(path):
        event = _parse_token_event(line, path, sessions_dir)
        if event is None:
            continue
        if latest_usage is None:
            latest_usage = event
        if latest_rate_limits is None and _has_rate_windows(event):
            latest_rate_limits = event
        if latest_usage is not None and latest_rate_limits is not None:
            break
    return latest_usage, latest_rate_limits


def _find_latest_events(
    sessions_dir: Path,
    file_cache: dict[Path, _CachedFileEvents],
) -> tuple[_TokenEvent | None, _TokenEvent | None]:
    """Localiza datos recientes y reutiliza resultados de archivos sin cambios."""

    active_paths: set[Path] = set()
    try:
        paths = list(sessions_dir.rglob("rollout-*.jsonl"))
    except OSError:
        paths = []

    for path in paths:
        active_paths.add(path)
        try:
            fingerprint = _fingerprint(path)
        except OSError:
            continue
        cached = file_cache.get(path)
        if cached is not None and cached.fingerprint == fingerprint:
            continue
        try:
            file_usage, file_rate_limits = _scan_session_file(path, sessions_dir)
        except OSError:
            continue
        file_cache[path] = _CachedFileEvents(
            fingerprint=fingerprint,
            latest_usage=file_usage,
            latest_rate_limits=file_rate_limits,
        )

    for deleted_path in set(file_cache) - active_paths:
        del file_cache[deleted_path]

    latest_usage: _TokenEvent | None = None
    latest_rate_limits: _TokenEvent | None = None
    for cached in file_cache.values():
        usage = cached.latest_usage
        limits = cached.latest_rate_limits
        if usage is not None and (latest_usage is None or usage.timestamp > latest_usage.timestamp):
            latest_usage = usage
        if limits is not None and (
            latest_rate_limits is None or limits.timestamp > latest_rate_limits.timestamp
        ):
            latest_rate_limits = limits
    return latest_usage, latest_rate_limits


def _build_usage(event: _TokenEvent) -> TokenUsageSnapshot | None:
    """Convierte el acumulado real de la sesión en un modelo normalizado."""

    total_usage = _as_object_dict(event.info.get("total_token_usage"))
    if total_usage is None:
        return None
    context_window = _integer(event.info, "model_context_window")
    return TokenUsageSnapshot(
        input_tokens=_integer(total_usage, "input_tokens"),
        cached_input_tokens=_integer(total_usage, "cached_input_tokens"),
        cache_write_input_tokens=_integer(total_usage, "cache_write_input_tokens"),
        output_tokens=_integer(total_usage, "output_tokens"),
        reasoning_output_tokens=_integer(total_usage, "reasoning_output_tokens"),
        total_tokens=_integer(total_usage, "total_tokens"),
        model_context_window=context_window or None,
        scope="session_total",
        source="codex_session_jsonl",
        updated_at=event.timestamp,
        source_reference=event.source_reference,
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


class CodexAdapter(PlatformAdapter):
    """Lee métricas reales desde los archivos JSONL locales de Codex."""

    def __init__(
        self,
        sessions_dir: Path | None = None,
        executable: str = "codex",
    ) -> None:
        """Configura la carpeta local y el ejecutable usado para detección."""

        self._sessions_dir = sessions_dir or Path.home() / ".codex" / "sessions"
        self._executable = executable
        self._file_cache: dict[Path, _CachedFileEvents] = {}

    @property
    def platform_id(self) -> str:
        """Devuelve el identificador estable de OpenAI Codex."""

        return "codex"

    async def collect(self) -> PlatformSnapshot:
        """Obtiene el último consumo real sin bloquear el bucle asíncrono."""

        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> PlatformSnapshot:
        """Escanea sesiones locales y construye una instantánea sanitizada."""

        latest_usage, latest_rate_limits = _find_latest_events(
            self._sessions_dir,
            self._file_cache,
        )
        executable_available = shutil.which(self._executable) is not None
        if latest_usage is None:
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="OpenAI Codex",
                status=AgentState.IDLE if executable_available else AgentState.OFFLINE,
            )
        now = datetime.now(UTC)
        usage = _build_usage(latest_usage)
        rate_limits = (
            _build_rate_limits(latest_rate_limits, now) if latest_rate_limits is not None else None
        )
        primary = rate_limits.primary if rate_limits is not None else None
        secondary = rate_limits.secondary if rate_limits is not None else None
        return PlatformSnapshot(
            platform_id=self.platform_id,
            display_name="OpenAI Codex",
            status=AgentState.IDLE,
            tokens_today=None,
            weekly_remaining_pct=(
                round(secondary.remaining_percent) if secondary is not None else None
            ),
            rolling_remaining_pct=(
                round(primary.remaining_percent) if primary is not None else None
            ),
            next_reset_at=primary.resets_at if primary is not None else None,
            active_agents=0,
            token_usage=usage,
            rate_limits=rate_limits,
        )
