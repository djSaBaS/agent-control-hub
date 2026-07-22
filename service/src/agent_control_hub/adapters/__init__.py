"""Adaptadores disponibles para plataformas de agentes."""

# Expone el contrato base para implementaciones externas.
from agent_control_hub.adapters.base import PlatformAdapter
# Expone el adaptador de demostración incluido en el MVP.
from agent_control_hub.adapters.mock import MockAdapter

# Define la API pública del módulo.
__all__ = ["MockAdapter", "PlatformAdapter"]
