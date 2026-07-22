"""Transportes disponibles para comunicar el servicio con dispositivos."""

# Expone el transporte serie del MVP.
from agent_control_hub.transports.serial_transport import SerialTransport

# Define la API pública del módulo.
__all__ = ["SerialTransport"]
