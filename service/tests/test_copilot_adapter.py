"""Pruebas del adaptador inicial de GitHub Copilot."""

# Importa el ejecutor asíncrono para las capturas del adaptador.
import asyncio
# Importa el tipo de función utilizado por monkeypatch.
from collections.abc import Callable

# Importa el tipo oficial del fixture de sustitución.
from pytest import MonkeyPatch

# Importa el adaptador sometido a prueba.
from agent_control_hub.adapters.copilot import CopilotAdapter
# Importa los estados normalizados esperados.
from agent_control_hub.models import AgentState


# Comprueba el estado desconectado cuando no existe Copilot CLI.
def test_copilot_is_offline_when_cli_is_missing(
    # Recibe el fixture de sustitución temporal de pytest.
    monkeypatch: MonkeyPatch,
) -> None:
    """Evita presentar Copilot como disponible sin ejecutable local."""

    # Importa el módulo para sustituir únicamente su dependencia local.
    import agent_control_hub.adapters.copilot as copilot_module

    # Define una búsqueda simulada que nunca encuentra el ejecutable.
    missing_executable: Callable[[str], str | None] = lambda _name: None
    # Sustituye la función de búsqueda dentro del módulo.
    monkeypatch.setattr(copilot_module.shutil, "which", missing_executable)
    # Ejecuta la captura asíncrona del adaptador.
    snapshot = asyncio.run(CopilotAdapter().collect())
    # Comprueba que la plataforma queda fuera de línea.
    assert snapshot.status is AgentState.OFFLINE
    # Comprueba que no se inventan agentes activos.
    assert snapshot.active_agents == 0


# Comprueba el estado disponible cuando se localiza Copilot CLI.
def test_copilot_is_idle_when_cli_is_installed(
    # Recibe el fixture de sustitución temporal de pytest.
    monkeypatch: MonkeyPatch,
) -> None:
    """Declara disponibilidad sin inventar sesiones ni consumo."""

    # Importa el módulo para sustituir únicamente su dependencia local.
    import agent_control_hub.adapters.copilot as copilot_module

    # Define una búsqueda simulada que devuelve una ruta válida.
    installed_executable: Callable[[str], str | None] = (
        lambda _name: "C:/Tools/copilot.exe"
    )
    # Sustituye la función de búsqueda dentro del módulo.
    monkeypatch.setattr(copilot_module.shutil, "which", installed_executable)
    # Ejecuta la captura asíncrona del adaptador.
    snapshot = asyncio.run(CopilotAdapter().collect())
    # Comprueba que la plataforma aparece disponible e inactiva.
    assert snapshot.status is AgentState.IDLE
    # Comprueba que no se asignan tokens sin una fuente oficial.
    assert snapshot.tokens_today is None
