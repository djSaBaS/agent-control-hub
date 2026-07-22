"""Pruebas de separación entre monitorización y salida física."""

# Importa el ejecutor asíncrono estándar utilizado por el servicio.
import asyncio

# Importa el adaptador determinista y el agregador sometido a prueba.
from agent_control_hub.adapters.mock import MockAdapter
from agent_control_hub.snapshot_service import SnapshotService


# Comprueba que una plataforma oculta se consulta pero no se transmite.
def test_hidden_platform_is_not_in_device_snapshot() -> None:
    """Valida el filtro explícito de visibilidad del dispositivo."""

    # Construye el servicio con la plataforma simulada monitorizada.
    service = SnapshotService(
        # Añade el adaptador que debe ejecutar su captura.
        [MockAdapter()],
        # Configura un conjunto visible vacío.
        visible_platform_ids=frozenset(),
    )
    # Ejecuta la captura normalizada.
    snapshot = asyncio.run(service.collect())
    # Comprueba que no se envían plataformas ocultas al dispositivo.
    assert snapshot.platforms == []
    # Comprueba que el coste visible permanece a cero.
    assert snapshot.total_cost_today == 0
