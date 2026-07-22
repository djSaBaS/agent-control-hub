"""Modelos de datos normalizados del servicio."""

# Importa enumeraciones de texto para estados interoperables.
from enum import StrEnum
# Importa fechas con zona horaria para métricas y reinicios.
from datetime import datetime

# Importa la clase base de validación de Pydantic.
from pydantic import BaseModel, ConfigDict, Field


# Define los estados compatibles en todas las plataformas.
class AgentState(StrEnum):
    """Estados normalizados de plataformas y agentes."""

    # Representa un recurso disponible sin trabajo activo.
    IDLE = "idle"
    # Representa un recurso que está ejecutando una tarea.
    WORKING = "working"
    # Representa un recurso que espera entrada o autorización.
    WAITING = "waiting"
    # Representa una tarea finalizada correctamente.
    COMPLETED = "completed"
    # Representa un fallo en la plataforma o tarea.
    ERROR = "error"
    # Representa una plataforma no accesible.
    OFFLINE = "offline"


# Define el estado normalizado de un agente individual.
class AgentSnapshot(BaseModel):
    """Instantánea de un agente o tarea concreta."""

    # Impide aceptar propiedades desconocidas por accidente.
    model_config = ConfigDict(extra="forbid")

    # Guarda el identificador estable del agente.
    agent_id: str = Field(min_length=1, max_length=80)
    # Guarda el nombre que verá el usuario.
    display_name: str = Field(min_length=1, max_length=80)
    # Guarda el estado actual normalizado.
    status: AgentState
    # Guarda el nombre opcional de la tarea activa.
    task_name: str | None = Field(default=None, max_length=120)
    # Guarda la fecha opcional de comienzo de la tarea.
    started_at: datetime | None = None


# Define el estado normalizado de una plataforma completa.
class PlatformSnapshot(BaseModel):
    """Instantánea agregada de una plataforma de agentes."""

    # Impide aceptar propiedades desconocidas por accidente.
    model_config = ConfigDict(extra="forbid")

    # Guarda el identificador estable de la plataforma.
    platform_id: str = Field(min_length=1, max_length=40)
    # Guarda el nombre mostrado al usuario.
    display_name: str = Field(min_length=1, max_length=40)
    # Guarda el estado global de la plataforma.
    status: AgentState
    # Guarda los tokens consumidos durante el día cuando estén disponibles.
    tokens_today: int | None = Field(default=None, ge=0)
    # Guarda el coste diario estimado u oficial cuando esté disponible.
    cost_today: float | None = Field(default=None, ge=0)
    # Guarda el porcentaje semanal restante cuando sea oficial o calculable.
    weekly_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    # Guarda el porcentaje restante de la ventana corta.
    rolling_remaining_pct: int | None = Field(default=None, ge=0, le=100)
    # Guarda el siguiente reinicio conocido de cuota.
    next_reset_at: datetime | None = None
    # Guarda el número de agentes activos declarado por el adaptador.
    active_agents: int = Field(default=0, ge=0)
    # Guarda las instantáneas de agentes disponibles.
    agents: list[AgentSnapshot] = Field(default_factory=list)


# Define el mensaje completo que recibirá el dispositivo.
class DeviceSnapshot(BaseModel):
    """Instantánea completa transmitida al dispositivo físico."""

    # Impide aceptar propiedades desconocidas por accidente.
    model_config = ConfigDict(extra="forbid")

    # Identifica la versión mayor y menor del protocolo.
    protocol_version: str = "1.0"
    # Identifica el tipo de mensaje para el firmware.
    type: str = "snapshot"
    # Guarda la fecha de generación del mensaje.
    generated_at: datetime
    # Guarda el coste total diario de plataformas con dato disponible.
    total_cost_today: float = Field(default=0, ge=0)
    # Guarda las plataformas agregadas.
    platforms: list[PlatformSnapshot] = Field(default_factory=list)
