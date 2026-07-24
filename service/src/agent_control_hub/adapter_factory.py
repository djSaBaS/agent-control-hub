"""Creación controlada de adaptadores a partir de configuración validada."""

from collections.abc import Callable
from dataclasses import dataclass

from agent_control_hub.adapters import (
    CodexAdapter,
    CopilotAdapter,
    HermesAdapter,
    MockAdapter,
    PlatformAdapter,
)
from agent_control_hub.config import ServiceSettings


@dataclass(frozen=True, slots=True)
class AdapterSelection:
    """Agrupa adaptadores monitorizados e identificadores visibles."""

    adapters: tuple[PlatformAdapter, ...]
    visible_platform_ids: frozenset[str]


_ADAPTER_FACTORIES: dict[str, Callable[[], PlatformAdapter]] = {
    "mock": MockAdapter,
    "codex": CodexAdapter,
    "copilot": CopilotAdapter,
    "hermes": HermesAdapter,
}


def build_adapter_selection(settings: ServiceSettings) -> AdapterSelection:
    """Crea únicamente conectores habilitados para monitorización."""

    adapters: list[PlatformAdapter] = []
    visible_platform_ids: set[str] = set()
    for platform_id, platform_settings in settings.platforms.items():
        if not platform_settings.enabled or not platform_settings.monitoring_enabled:
            continue
        factory = _ADAPTER_FACTORIES.get(platform_id)
        if factory is None:
            raise ValueError(f"Plataforma no soportada: {platform_id}")
        adapters.append(factory())
        if platform_settings.visible_on_device:
            visible_platform_ids.add(platform_id)
    return AdapterSelection(
        adapters=tuple(adapters),
        visible_platform_ids=frozenset(visible_platform_ids),
    )
