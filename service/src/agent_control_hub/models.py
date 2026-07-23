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


class PlatformSnapshot(BaseModel):
    """Instantánea agregada de una plataforma completa."""

    model_config = ConfigDict(extra="forbid")

    platform_id: str = Field(min_length=1, max_length=40)
    display_name: str = Field(min_length=1, max_length=40)
    status: AgentState
    tokens_today: int | None = Field(default=None, ge=0)
    cost_today: float | None = Field(default=None, ge=0)
    weekly_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    rolling_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    next_reset_at: datetime | None = None
    active_agents: int = Field(default=0, ge=0)
    agents: list[AgentSnapshot] = Field(default_factory=list)
    token_usage: TokenUsageSnapshot | None = None
    rate_limits: RateLimitsSnapshot | None = None


class DeviceSnapshot(BaseModel):
    """Instantánea completa transmitida al dispositivo físico."""

    model_config = ConfigDict(extra="forbid")

    protocol_version: str = "1.0"
    type: str = "snapshot"
    generated_at: datetime
    total_cost_today: float = Field(default=0, ge=0)
    platforms: list[PlatformSnapshot] = Field(default_factory=list)
