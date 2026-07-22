"""Pruebas de aislamiento de fallos y visibilidad de plataformas."""

# Importa asyncio para ejecutar las capturas asíncronas desde pytest.
import asyncio

# Importa el contrato, los modelos normalizados y el agregador sometido a prueba.
from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.models import AgentState, PlatformSnapshot
from agent_control_hub.snapshot_service import SnapshotService


# Implementa un adaptador estable para validar el caso correcto.
class HealthyAdapter(PlatformAdapter):
    """Adaptador de prueba que devuelve siempre una plataforma disponible."""

    # Expone el identificador estable exigido por el contrato.
    @property
    def platform_id(self) -> str:
        """Devuelve el identificador de la plataforma sana."""

        # Devuelve un nombre determinista para las aserciones.
        return "healthy"

    # Genera una instantánea válida sin acceder a servicios externos.
    async def collect(self) -> PlatformSnapshot:
        """Devuelve una plataforma inactiva pero disponible."""

        # Construye la respuesta normalizada esperada.
        return PlatformSnapshot(
            # Conserva el identificador declarado por el adaptador.
            platform_id=self.platform_id,
            # Define un nombre legible.
            display_name="Healthy",
            # Marca la plataforma como disponible.
            status=AgentState.IDLE,
        )


# Implementa un adaptador que falla para comprobar el aislamiento.
class BrokenAdapter(PlatformAdapter):
    """Adaptador de prueba que simula una integración averiada."""

    # Expone el identificador estable de la plataforma defectuosa.
    @property
    def platform_id(self) -> str:
        """Devuelve el identificador del adaptador roto."""

        # Devuelve un nombre determinista para la plataforma degradada.
        return "broken"

    # Simula un error producido por una API o proceso externo.
    async def collect(self) -> PlatformSnapshot:
        """Interrumpe su captura sin afectar a otros adaptadores."""

        # Lanza un error controlado que el agregador debe aislar.
        raise RuntimeError("Fallo simulado del conector")


# Comprueba que un conector averiado no cancele los demás.
def test_snapshot_service_isolates_adapter_failures() -> None:
    """Convierte el fallo individual en estado offline y conserva el resto."""

    # Construye el servicio con un adaptador sano y otro defectuoso.
    service = SnapshotService([HealthyAdapter(), BrokenAdapter()])
    # Ejecuta la captura concurrente.
    snapshot = asyncio.run(service.collect())
    # Indexa las plataformas por identificador para facilitar las comprobaciones.
    platforms = {platform.platform_id: platform for platform in snapshot.platforms}
    # Verifica que la plataforma sana permanezca disponible.
    assert platforms["healthy"].status is AgentState.IDLE
    # Verifica que el fallo se traduzca a un estado seguro y visible.
    assert platforms["broken"].status is AgentState.OFFLINE


# Comprueba que una plataforma monitorizada pueda ocultarse del dispositivo.
def test_snapshot_service_filters_hidden_platforms() -> None:
    """Separa la monitorización interna de la información visible en pantalla."""

    # Construye el servicio ocultando deliberadamente la única plataforma.
    service = SnapshotService(
        # Inyecta el adaptador que se seguirá consultando.
        [HealthyAdapter()],
        # No autoriza ninguna plataforma para el dispositivo.
        visible_platform_ids=frozenset(),
    )
    # Ejecuta la captura normalizada.
    snapshot = asyncio.run(service.collect())
    # Verifica que el mensaje físico no incluya plataformas ocultas.
    assert snapshot.platforms == []
