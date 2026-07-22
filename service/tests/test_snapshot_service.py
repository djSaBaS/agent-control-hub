"""Pruebas unitarias del agregador de adaptadores."""

# Importa el ejecutor asíncrono estándar utilizado por la prueba.
import asyncio

# Importa el adaptador simulado, el estado esperado y el servicio sometido a prueba.
from agent_control_hub.adapters.mock import MockAdapter
from agent_control_hub.models import AgentState
from agent_control_hub.snapshot_service import SnapshotService


# Comprueba que la plataforma simulada se agregue correctamente.
def test_collect_builds_device_snapshot() -> None:
    """Valida plataformas, agentes y coste agregado."""

    # Construye el servicio con una única fuente determinista.
    service = SnapshotService([MockAdapter()])
    # Ejecuta la captura asíncrona dentro de la prueba.
    snapshot = asyncio.run(service.collect())
    # Verifica la versión inicial del protocolo.
    assert snapshot.protocol_version == "1.0"
    # Verifica que se haya agregado una única plataforma.
    assert len(snapshot.platforms) == 1
    # Recupera la plataforma agregada para comprobaciones detalladas.
    platform = snapshot.platforms[0]
    # Verifica el identificador de la plataforma simulada.
    assert platform.platform_id == "codex"
    # Verifica que el servicio conserve el estado activo.
    assert platform.status is AgentState.WORKING
    # Verifica el número de agentes simulados.
    assert len(platform.agents) == 4
    # Verifica que costes desconocidos no incrementen el total.
    assert snapshot.total_cost_today == 0
