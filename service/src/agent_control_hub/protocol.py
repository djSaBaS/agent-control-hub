"""Codificación del protocolo serie del dispositivo."""

# Importa el modelo que representa una instantánea completa.
from agent_control_hub.models import DeviceSnapshot


# Convierte una instantánea en una línea NDJSON.
def encode_snapshot(snapshot: DeviceSnapshot) -> bytes:
    """Serializa una instantánea como UTF-8 terminada en salto de línea."""

    # Serializa fechas en ISO 8601 y excluye propiedades no definidas.
    payload = snapshot.model_dump_json(exclude_none=False)
    # Añade el separador de mensajes requerido por el firmware.
    framed_payload = f"{payload}\n"
    # Convierte el mensaje completo a bytes UTF-8.
    return framed_payload.encode("utf-8")
