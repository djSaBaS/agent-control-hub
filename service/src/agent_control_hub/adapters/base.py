"""Contrato común para adaptadores de plataformas."""

# Importa el contrato abstracto de clases.
from abc import ABC, abstractmethod

# Importa el modelo normalizado que debe producir cada adaptador.
from agent_control_hub.models import PlatformSnapshot


# Define la interfaz obligatoria para cualquier integración.
class PlatformAdapter(ABC):
    """Contrato de lectura de una plataforma de agentes."""

    # Obliga a exponer un identificador estable.
    @property
    # Declara el tipo de retorno del identificador.
    @abstractmethod
    # Define la firma de la propiedad de plataforma.
    def platform_id(self) -> str:
        """Devuelve el identificador estable de la plataforma."""

    # Obliga a implementar la captura de una instantánea.
    @abstractmethod
    # Define la firma asíncrona para permitir APIs y procesos lentos.
    async def collect(self) -> PlatformSnapshot:
        """Obtiene y normaliza el estado actual de la plataforma."""
