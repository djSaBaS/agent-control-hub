"""Pruebas de validación de los modelos normalizados."""

# Importa fechas conscientes de zona horaria para crear instantáneas válidas.
from datetime import UTC, datetime

# Importa pytest para comprobar errores de validación esperados.
import pytest
# Importa la excepción pública emitida por Pydantic.
from pydantic import ValidationError

# Importa los modelos y estados que forman el contrato del servicio.
from agent_control_hub.models import AgentSnapshot, AgentState, DeviceSnapshot, PlatformSnapshot


# Comprueba que los porcentajes de cuota respeten el rango permitido.
def test_platform_rejects_invalid_weekly_percentage() -> None:
    """Impide transmitir porcentajes inferiores a cero o superiores a cien."""

    # Verifica que Pydantic rechace un porcentaje imposible.
    with pytest.raises(ValidationError):
        # Intenta construir una plataforma con una cuota fuera de rango.
        PlatformSnapshot(
            # Asigna un identificador estable requerido por el contrato.
            platform_id="codex",
            # Asigna el nombre que se mostraría al usuario.
            display_name="Codex",
            # Marca la plataforma como disponible.
            status=AgentState.IDLE,
            # Utiliza un porcentaje inválido para provocar la validación.
            weekly_remaining_pct=101,
        )


# Comprueba que no se acepten propiedades que el protocolo no conoce.
def test_agent_rejects_unknown_fields() -> None:
    """Evita que errores de nombres pasen silenciosamente al firmware."""

    # Verifica que una propiedad accidental produzca un error explícito.
    with pytest.raises(ValidationError):
        # Intenta construir un agente con una propiedad no declarada.
        AgentSnapshot(
            # Asigna el identificador requerido.
            agent_id="security-review",
            # Asigna el nombre visible.
            display_name="Revisión de seguridad",
            # Marca el agente como activo.
            status=AgentState.WORKING,
            # Introduce deliberadamente un campo desconocido.
            unexpected_field="no permitido",  # type: ignore[call-arg]
        )


# Comprueba los valores predeterminados del mensaje enviado al dispositivo.
def test_device_snapshot_uses_protocol_defaults() -> None:
    """Mantiene estable la versión y el tipo de mensaje del protocolo."""

    # Construye una instantánea mínima con una fecha determinista.
    snapshot = DeviceSnapshot(
        # Utiliza UTC para que la serialización sea inequívoca.
        generated_at=datetime(2026, 7, 22, 12, 0, tzinfo=UTC),
    )
    # Verifica la versión esperada por el firmware actual.
    assert snapshot.protocol_version == "1.0"
    # Verifica el discriminador utilizado para identificar instantáneas.
    assert snapshot.type == "snapshot"
    # Verifica que una instantánea vacía no invente plataformas.
    assert snapshot.platforms == []
