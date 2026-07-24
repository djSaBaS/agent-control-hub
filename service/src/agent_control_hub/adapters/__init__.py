"""Adaptadores disponibles para plataformas de agentes."""

from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.adapters.codex import CodexAdapter
from agent_control_hub.adapters.copilot import CopilotAdapter
from agent_control_hub.adapters.mock import MockAdapter

__all__ = ["CodexAdapter", "CopilotAdapter", "MockAdapter", "PlatformAdapter"]
