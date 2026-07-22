"""Adaptadores disponibles para plataformas de agentes."""

# Expone el contrato base y los adaptadores disponibles mediante la API pública del módulo.
from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.adapters.copilot import CopilotAdapter
from agent_control_hub.adapters.mock import MockAdapter

# Define la API pública del módulo.
__all__ = ["CopilotAdapter", "MockAdapter", "PlatformAdapter"]
