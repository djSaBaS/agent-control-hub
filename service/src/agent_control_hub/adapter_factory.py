"""Creación controlada de adaptadores a partir de configuración validada."""

# Importa tipos de función para registrar constructores de adaptadores.
from collections.abc import Callable
# Importa utilidades para declarar resultados inmutables.
from dataclasses import dataclass

# Importa adaptadores disponibles en la primera fase.
from agent_control_hub.adapters import CopilotAdapter, MockAdapter, PlatformAdapter
# Importa la configuración raíz del servicio.
from agent_control_hub.config import ServiceSettings


# Declara el resultado inmutable de seleccionar plataformas configuradas.
@dataclass(frozen=True, slots=True)
class AdapterSelection:
    """Agrupa adaptadores monitorizados e identificadores visibles."""

    # Guarda los adaptadores que deben consultarse.
    adapters: tuple[PlatformAdapter, ...]
    # Guarda las plataformas que pueden enviarse al dispositivo.
    visible_platform_ids: frozenset[str]


# Registra constructores permitidos sin admitir importaciones arbitrarias.
_ADAPTER_FACTORIES: dict[str, Callable[[], PlatformAdapter]] = {
    # Registra la fuente simulada de desarrollo.
    "mock": MockAdapter,
    # Registra la detección inicial de GitHub Copilot CLI.
    "copilot": CopilotAdapter,
}


# Construye adaptadores y visibilidad a partir de preferencias validadas.
def build_adapter_selection(settings: ServiceSettings) -> AdapterSelection:
    """Crea únicamente conectores habilitados para monitorización."""

    # Prepara la colección ordenada de adaptadores activos.
    adapters: list[PlatformAdapter] = []
    # Prepara la colección de plataformas visibles en el dispositivo.
    visible_platform_ids: set[str] = set()
    # Recorre la configuración en el orden declarado por el usuario.
    for platform_id, platform_settings in settings.platforms.items():
        # Omite conectores completamente deshabilitados.
        if not platform_settings.enabled:
            # Continúa con la siguiente plataforma configurada.
            continue
        # Omite conectores cuya monitorización esté deshabilitada.
        if not platform_settings.monitoring_enabled:
            # Continúa sin iniciar procesos ni consultas.
            continue
        # Busca únicamente constructores registrados por la aplicación.
        factory = _ADAPTER_FACTORIES.get(platform_id)
        # Rechaza identificadores activos que el servicio no sabe cargar.
        if factory is None:
            # Informa del error de configuración sin ejecutar código externo.
            raise ValueError(f"Plataforma no soportada: {platform_id}")
        # Crea una instancia independiente del conector.
        adapters.append(factory())
        # Registra la plataforma cuando debe aparecer en el dispositivo.
        if platform_settings.visible_on_device:
            # Añade el identificador al filtro de salida.
            visible_platform_ids.add(platform_id)
    # Devuelve una selección inmutable para el servicio.
    return AdapterSelection(
        # Conserva el orden de los adaptadores configurados.
        adapters=tuple(adapters),
        # Evita modificaciones accidentales del filtro de visibilidad.
        visible_platform_ids=frozenset(visible_platform_ids),
    )
