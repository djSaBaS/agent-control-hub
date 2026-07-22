"""Adaptador inicial para detectar GitHub Copilot CLI."""

# Importa utilidades estándar para localizar ejecutables instalados.
import shutil

# Importa el contrato común y los modelos normalizados del servicio.
from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.models import AgentState, PlatformSnapshot


# Implementa la primera fase de integración con GitHub Copilot.
class CopilotAdapter(PlatformAdapter):
    """Detecta Copilot CLI sin inventar sesiones ni consumo."""

    # Inicializa el nombre del ejecutable configurable para pruebas.
    def __init__(self, executable: str = "copilot") -> None:
        """Guarda el comando que debe localizarse en el sistema."""

        # Conserva el nombre o ruta facilitados por configuración.
        self._executable = executable

    # Expone el identificador estable del adaptador.
    @property
    # Declara el tipo de retorno del identificador.
    def platform_id(self) -> str:
        """Devuelve el identificador interno de GitHub Copilot."""

        # Devuelve el nombre utilizado por configuración y protocolo.
        return "copilot"

    # Detecta la disponibilidad local sin solicitar credenciales.
    async def collect(self) -> PlatformSnapshot:
        """Devuelve disponibilidad básica de Copilot CLI."""

        # Busca el ejecutable en las rutas disponibles para el servicio.
        executable_path = shutil.which(self._executable)
        # Marca la plataforma como desconectada cuando no está instalada.
        if executable_path is None:
            # Devuelve una instantánea mínima y explícita.
            return PlatformSnapshot(
                # Identifica el conector afectado.
                platform_id=self.platform_id,
                # Define el nombre visible en el dispositivo.
                display_name="GitHub Copilot",
                # Informa de que la CLI no está disponible localmente.
                status=AgentState.OFFLINE,
            )
        # Declara disponibilidad sin inferir sesiones activas ni consumo.
        return PlatformSnapshot(
            # Identifica la plataforma normalizada.
            platform_id=self.platform_id,
            # Define el nombre visible para el usuario.
            display_name="GitHub Copilot",
            # Utiliza estado inactivo hasta implementar telemetría de sesiones.
            status=AgentState.IDLE,
            # No declara agentes activos sin una fuente oficial.
            active_agents=0,
        )
