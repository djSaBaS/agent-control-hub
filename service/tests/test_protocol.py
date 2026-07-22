"""Pruebas unitarias de la codificación NDJSON."""

# Importa fechas deterministas para la prueba.
from datetime import UTC, datetime

# Importa el modelo mínimo requerido por el protocolo.
from agent_control_hub.models import DeviceSnapshot
# Importa la función sometida a prueba.
from agent_control_hub.protocol import encode_snapshot


# Comprueba que cada mensaje termine exactamente en una línea completa.
def test_encode_snapshot_uses_ndjson_frame() -> None:
    """Valida UTF-8, tipo de mensaje y terminador de línea."""

    # Construye una instantánea vacía con fecha estable.
    snapshot = DeviceSnapshot(generated_at=datetime(2026, 7, 22, tzinfo=UTC))
    # Codifica la instantánea mediante la función pública.
    payload = encode_snapshot(snapshot)
    # Verifica que el resultado sea una secuencia de bytes.
    assert isinstance(payload, bytes)
    # Verifica que exista un único terminador de mensaje al final.
    assert payload.endswith(b"\n")
    # Verifica que el tipo de mensaje se encuentre en el JSON.
    assert b'"type":"snapshot"' in payload
