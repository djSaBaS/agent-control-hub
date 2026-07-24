"""Modelos de datos normalizados del servicio."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AgentState(StrEnum):
    """Estados normalizados de plataformas y agentes."""

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
    """Separa acumulado del hilo, última petición y contexto estimado."""

    model_config = ConfigDict(extra="forbid")

    thread_total: TokenUsageSnapshot | None = None
    last_request: TokenUsageSnapshot | None = None
    context_used_tokens_estimated: int | None = Field(default=None, ge=0)
    context_used_percent_estimated: float | None = Field(default=None, ge=0, le=100)
    context_estimation_method: str | None = Field(default=None, max_length=80)


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
    """Metadatos sanitizados de una sesión local de una plataforma."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1, max_length=120)
    started_at: datetime
    last_activity_at: datetime | None = None
    originator: str | None = Field(default=None, max_length=80)
    source: str | None = Field(default=None, max_length=80)
    cli_version: str | None = Field(default=None, max_length=40)
    model_provider: str | None = Field(default=None, max_length=80)
    model_name: str | None = Field(default=None, max_length=160)


class ProjectInfo(BaseModel):
    """Identidad sanitizada del proyecto asociado a una sesión."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=120)
    cwd_alias: str = Field(min_length=1, max_length=160)
    repository: str | None = Field(default=None, max_length=160)
    branch: str | None = Field(default=None, max_length=120)
    dirty_files: int | None = Field(default=None, ge=0)


class TaskInfo(BaseModel):
    """Tarea visible y actividad actual sin conservar el prompt completo."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=180)
    conversation_name: str | None = Field(default=None, max_length=120)
    objective: str | None = Field(default=None, max_length=500)
    status: AgentState
    activity: str | None = Field(default=None, max_length=180)
    last_result: str | None = Field(default=None, max_length=220)
    pending: str | None = Field(default=None, max_length=220)
    started_at: datetime | None = None
    last_activity_at: datetime | None = None


class ActivityItem(BaseModel):
    """Actividad técnica reciente preparada para interfaces y alertas."""

    model_config = ConfigDict(extra="forbid")

    activity_type: str = Field(min_length=1, max_length=40)
    label: str = Field(min_length=1, max_length=100)
    status: AgentState
    summary: str | None = Field(default=None, max_length=220)
    timestamp: datetime


class PlatformRuntimeInfo(BaseModel):
    """Metadatos operativos opcionales compartidos por plataformas locales."""

    model_config = ConfigDict(extra="forbid")

    gateway_status: str | None = Field(default=None, max_length=40)
    session_count: int | None = Field(default=None, ge=0)
    message_count: int | None = Field(default=None, ge=0)
    tool_call_count: int | None = Field(default=None, ge=0)
    api_call_count: int | None = Field(default=None, ge=0)
    cron_job_count: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    actual_cost_usd: float | None = Field(default=None, ge=0)
    cost_status: str | None = Field(default=None, max_length=40)


class PlatformSnapshot(BaseModel):
    """Instantánea agregada de una plataforma completa."""

    model_config = ConfigDict(extra="forbid")

    platform_id: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=40)
    status: AgentState
    status_reason: str | None = Field(default=None, max_length=80)
    status_message: str | None = Field(default=None, max_length=180)
    tokens_today: int | None = Field(default=None, ge=0)
    cost_today: float | None = Field(default=None, ge=0)
    weekly_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    rolling_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    next_reset_at: datetime | None = None
    active_agents: int = Field(default=0, ge=0)
    agents: list[AgentSnapshot] = Field(default_factory=list)
    token_usage: TokenUsageSnapshot | None = None
    usage: UsageBreakdown | None = None
    rate_limits: RateLimitsSnapshot | None = None
    session: SessionInfo | None = None
    project: ProjectInfo | None = None
    task: TaskInfo | None = None
    runtime: PlatformRuntimeInfo | None = None
    recent_activity: list[ActivityItem] = Field(default_factory=list, max_length=20)


class DeviceSnapshot(BaseModel):
    """Instantánea completa transmitida al dispositivo físico."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: str = "1.0"
    type: str = "snapshot"
    generated_at: datetime
    total_cost_today: float = Field(default=0, ge=0)
    platforms: list[PlatformSnapshot] = Field(default_factory=list)
