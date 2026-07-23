"""Modelos de datos normalizados del servicio."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AgentState(StrEnum):
    """Estados normalizados de plataformas, tareas y actividades."""

    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    COMPLETED = "completed"
    ERROR = "error"
    OFFLINE = "offline"


class AgentSnapshot(BaseModel):
    """Instantánea de un agente o tarea concreta."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1, max_length=80)
    display_name: str = Field(min_length=1, max_length=80)
    status: AgentState
    task_name: str | None = Field(default=None, max_length=120)
    started_at: datetime | None = None


class TokenUsageSnapshot(BaseModel):
    """Uso real de tokens declarado por una fuente local u oficial."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    cache_write_input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(ge=0)
    reasoning_output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(ge=0)
    model_context_window: int | None = Field(default=None, gt=0)
    scope: str = Field(default="session_total", min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=80)
    updated_at: datetime
    source_reference: str | None = Field(default=None, max_length=240)


class UsageBreakdown(BaseModel):
    """Separa el acumulado del hilo, la última petición y la estimación de contexto."""

    model_config = ConfigDict(extra="forbid")

    thread_total: TokenUsageSnapshot | None = None
    last_request: TokenUsageSnapshot | None = None
    model_context_window: int | None = Field(default=None, gt=0)
    context_used_pct_estimated: float | None = Field(default=None, ge=0, le=100)
    context_used_is_estimated: bool = True


class RateLimitWindowSnapshot(BaseModel):
    """Ventana temporal de cuota informada por una plataforma."""

    model_config = ConfigDict(extra="forbid")

    used_percent: float = Field(ge=0, le=100)
    remaining_percent: float = Field(ge=0, le=100)
    window_minutes: int = Field(gt=0)
    resets_at: datetime


class RateLimitsSnapshot(BaseModel):
    """Límites reales asociados a la cuenta de una plataforma."""

    model_config = ConfigDict(extra="forbid")

    limit_id: str = Field(min_length=1, max_length=80)
    plan_type: str | None = Field(default=None, max_length=40)
    primary: RateLimitWindowSnapshot | None = None
    secondary: RateLimitWindowSnapshot | None = None
    source: str = Field(min_length=1, max_length=80)
    updated_at: datetime
    source_reference: str | None = Field(default=None, max_length=240)
    is_stale: bool = False


class SessionInfo(BaseModel):
    """Metadatos sanitizados de la sesión local seleccionada."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=128)
    started_at: datetime
    last_activity_at: datetime | None = None
    originator: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=80)
    cli_version: str | None = Field(default=None, max_length=40)
    model_provider: str | None = Field(default=None, max_length=40)
    source_reference: str | None = Field(default=None, max_length=240)


class ProjectInfo(BaseModel):
    """Identidad pública del proyecto sin exponer su ruta absoluta."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=120)
    path_alias: str = Field(min_length=1, max_length=160)
    repository: str | None = Field(default=None, max_length=160)
    branch: str | None = Field(default=None, max_length=120)
    dirty_files: int | None = Field(default=None, ge=0)


class TaskInfo(BaseModel):
    """Tarea visible y actividad actual de la sesión seleccionada."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=160)
    status: AgentState
    activity: str | None = Field(default=None, max_length=200)
    started_at: datetime | None = None
    last_activity_at: datetime | None = None


class ActivityItem(BaseModel):
    """Actividad técnica reciente reducida y sanitizada para la interfaz."""

    model_config = ConfigDict(extra="forbid")

    activity_type: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=120)
    status: AgentState
    summary: str | None = Field(default=None, max_length=240)
    timestamp: datetime
    duration_seconds: float | None = Field(default=None, ge=0)
    tool_name: str | None = Field(default=None, max_length=80)


class PlatformSnapshot(BaseModel):
    """Instantánea agregada de una plataforma completa."""

    model_config = ConfigDict(extra="forbid")

    platform_id: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=40)
    status: AgentState
    status_reason: str | None = Field(default=None, max_length=80)
    status_message: str | None = Field(default=None, max_length=200)
    tokens_today: int | None = Field(default=None, ge=0)
    cost_today: float | None = Field(default=None, ge=0)
    weekly_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    rolling_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    next_reset_at: datetime | None = None
    active_agents: int = Field(default=0, ge=0)
    agents: list[AgentSnapshot] = Field(default_factory=list)
    session: SessionInfo | None = None
    project: ProjectInfo | None = None
    task: TaskInfo | None = None
    recent_activity: list[ActivityItem] = Field(default_factory=list)
    token_usage: TokenUsageSnapshot | None = None
    usage_breakdown: UsageBreakdown | None = None
    rate_limits: RateLimitsSnapshot | None = None


class DeviceSnapshot(BaseModel):
    """Instantánea completa transmitida al dispositivo físico."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: str = "1.0"
    type: str = "snapshot"
    generated_at: datetime
    total_cost_today: float = Field(default=0, ge=0)
    platforms: list[PlatformSnapshot] = Field(default_factory=list)
