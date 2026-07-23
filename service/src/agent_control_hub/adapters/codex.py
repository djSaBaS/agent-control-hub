"""Adaptador local para telemetría real y sanitizada de OpenAI Codex."""

from __future__ import annotations

import asyncio
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.adapters.codex_events import (
    SessionState,
    TokenEvent,
    refresh_sessions,
    select_active_session,
    select_latest_limits,
)
from agent_control_hub.adapters.codex_sanitizer import (
    as_object_dict,
    integer,
    number,
    parse_timestamp,
)
from agent_control_hub.models import (
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


def _build_token_usage(
    usage: dict[str, object],
    event: TokenEvent,
    scope: str,
    context_window: int | None,
) -> TokenUsageSnapshot:
    """Convierte un bloque de tokens real en el modelo público común."""

    input_tokens = integer(usage, "input_tokens")
    output_tokens = integer(usage, "output_tokens")
    total_tokens = integer(usage, "total_tokens", input_tokens + output_tokens)
    return TokenUsageSnapshot(
        input_tokens=input_tokens,
        cached_input_tokens=integer(usage, "cached_input_tokens"),
        cache_write_input_tokens=integer(usage, "cache_write_input_tokens"),
        output_tokens=output_tokens,
        reasoning_output_tokens=integer(usage, "reasoning_output_tokens"),
        total_tokens=total_tokens,
        model_context_window=context_window,
        scope=scope,
        source="codex_session_jsonl",
        updated_at=event.timestamp,
        source_reference=event.source_reference,
    )


def _build_usage_breakdown(event: TokenEvent) -> UsageBreakdown | None:
    """Diferencia acumulado histórico, última petición y contexto estimado."""

    total_usage = as_object_dict(event.info.get("total_token_usage"))
    last_usage = as_object_dict(event.info.get("last_token_usage"))
    context_window_value = integer(event.info, "model_context_window")
    context_window = context_window_value or None
    thread_total = (
        _build_token_usage(total_usage, event, "thread_total", context_window)
        if total_usage is not None
        else None
    )
    last_request = (
        _build_token_usage(last_usage, event, "last_request", context_window)
        if last_usage is not None
        else None
    )
    if thread_total is None and last_request is None:
        return None
    estimated_pct: float | None = None
    if last_request is not None and context_window is not None:
        estimated_pct = round(min(100, last_request.input_tokens / context_window * 100), 2)
    return UsageBreakdown(
        thread_total=thread_total,
        last_request=last_request,
        model_context_window=context_window,
        context_used_pct_estimated=estimated_pct,
        context_used_is_estimated=True,
    )


def _build_window(value: object) -> RateLimitWindowSnapshot | None:
    """Convierte una ventana primaria o secundaria cuando está completa."""

    window = as_object_dict(value)
    if window is None:
        return None
    used_percent = number(window, "used_percent")
    window_minutes = integer(window, "window_minutes")
    resets_at = parse_timestamp(window.get("resets_at"))
    if (
        used_percent is None
        or not 0 <= used_percent <= 100
        or window_minutes <= 0
        or resets_at is None
    ):
        return None
    return RateLimitWindowSnapshot(
        used_percent=used_percent,
        remaining_percent=round(100 - used_percent, 2),
        window_minutes=window_minutes,
        resets_at=resets_at,
    )


def _build_rate_limits(event: TokenEvent, now: datetime) -> RateLimitsSnapshot | None:
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


def _build_session(state: SessionState) -> SessionInfo | None:
    """Publica metadatos de sesión solo cuando los campos mínimos son reales."""

    if state.session_id is None or state.started_at is None:
        return None
    return SessionInfo(
        session_id=state.session_id,
        started_at=state.started_at,
        last_activity_at=state.last_activity_at,
        originator=state.originator,
        source=state.source,
        cli_version=state.cli_version,
        model_provider=state.model_provider,
        source_reference=state.source_reference,
    )


def _build_project(state: SessionState) -> ProjectInfo | None:
    """Publica el alias del proyecto sin la ruta absoluta original."""

    if state.project_name is None or state.project_alias is None:
        return None
    return ProjectInfo(
        display_name=state.project_name,
        path_alias=state.project_alias,
    )


def _build_task(state: SessionState) -> TaskInfo:
    """Selecciona el nombre visible según la prioridad documentada."""

    display_name = state.user_task_name or state.goal_task_name or state.agent_task_name
    return TaskInfo(
        display_name=display_name,
        status=state.status,
        activity=state.task_activity,
        started_at=state.task_started_at,
        last_activity_at=state.last_activity_at,
    )


class CodexAdapter(PlatformAdapter):
    """Lee telemetría real desde los archivos JSONL locales de Codex."""

    def __init__(
        self,
        sessions_dir: Path | None = None,
        executable: str = "codex",
    ) -> None:
        """Configura la carpeta local y el ejecutable usado para detección."""

        self._sessions_dir = sessions_dir or Path.home() / ".codex" / "sessions"
        self._executable = executable
        self._file_cache: dict[Path, SessionState] = {}

    @property
    def platform_id(self) -> str:
        """Devuelve el identificador estable de OpenAI Codex."""

        return "codex"

    async def collect(self) -> PlatformSnapshot:
        """Obtiene la telemetría real sin bloquear el bucle asíncrono."""

        return await asyncio.to_thread(self._collect_sync)

    def _collect_sync(self) -> PlatformSnapshot:
        """Actualiza sesiones y construye una instantánea sanitizada."""

        states = refresh_sessions(self._sessions_dir, self._file_cache)
        active = select_active_session(states)
        executable_available = shutil.which(self._executable) is not None
        if active is None:
            status = AgentState.IDLE if executable_available else AgentState.OFFLINE
            reason = "no_sessions" if executable_available else "source_unavailable"
            return PlatformSnapshot(
                platform_id=self.platform_id,
                display_name="OpenAI Codex",
                status=status,
                status_reason=reason,
                status_message=(
                    "No se encontraron sesiones locales"
                    if executable_available
                    else "Codex no está disponible"
                ),
            )

        now = datetime.now(UTC)
        usage_breakdown = (
            _build_usage_breakdown(active.latest_usage)
            if active.latest_usage is not None
            else None
        )
        legacy_usage = usage_breakdown.thread_total if usage_breakdown is not None else None
        latest_limits = select_latest_limits(states)
        rate_limits = _build_rate_limits(latest_limits, now) if latest_limits is not None else None
        primary = rate_limits.primary if rate_limits is not None else None
        secondary = rate_limits.secondary if rate_limits is not None else None
        return PlatformSnapshot(
            platform_id=self.platform_id,
            display_name="OpenAI Codex",
            status=active.status,
            status_reason=active.status_reason,
            status_message=active.status_message,
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
            session=_build_session(active),
            project=_build_project(active),
            task=_build_task(active),
            recent_activity=list(reversed(active.recent_activity)),
            token_usage=legacy_usage,
            usage_breakdown=usage_breakdown,
            rate_limits=rate_limits,
        )
