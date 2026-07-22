"""Pruebas completas del contrato NDJSON enviado al dispositivo."""

# Importa el analizador JSON de la biblioteca estándar.
import json
# Importa fechas conscientes de zona horaria para datos deterministas.
from datetime import UTC, datetime

# Importa los modelos utilizados para construir una instantánea realista.
from agent_control_hub.models import AgentSnapshot, AgentState, DeviceSnapshot, PlatformSnapshot
# Importa la función pública que codifica el protocolo.
from agent_control_hub.protocol import encode_snapshot


# Comprueba estructura, codificación y delimitación del mensaje.
def test_encode_snapshot_produces_valid_single_line_ndjson() -> None:
    """Garantiza que el Core2 pueda leer una instantánea completa por línea."""

    # Construye un agente con caracteres Unicode para validar UTF-8.
    agent = AgentSnapshot(
        # Define un identificador estable sin información sensible.
        agent_id="revision-documentacion",
        # Incluye acentos para verificar la codificación.
        display_name="Revisión de documentación",
        # Marca el agente como trabajando.
        status=AgentState.WORKING,
        # Define una tarea breve y sanitizada.
        task_name="Comprobar documentación técnica",
    )
    # Construye la plataforma que contiene el agente.
    platform = PlatformSnapshot(
        # Utiliza el identificador definido para GitHub Copilot.
        platform_id="github-copilot",
        # Define el nombre visible de la plataforma.
        display_name="GitHub Copilot",
        # Marca la plataforma como activa.
        status=AgentState.WORKING,
        # Añade una métrica oficial de prueba.
        tokens_today=12_345,
        # Evita inventar una cuota semanal no disponible.
        weekly_remaining_pct=None,
        # Declara un agente activo.
        active_agents=1,
        # Adjunta la colección normalizada.
        agents=[agent],
    )
    # Construye el mensaje completo con fecha estable.
    snapshot = DeviceSnapshot(
        # Utiliza una fecha fija para que la prueba sea reproducible.
        generated_at=datetime(2026, 7, 22, 12, 30, tzinfo=UTC),
        # Adjunta la plataforma de prueba.
        platforms=[platform],
    )
    # Codifica el mensaje mediante la API pública.
    payload = encode_snapshot(snapshot)
    # Verifica que el transporte reciba bytes y no texto ambiguo.
    assert isinstance(payload, bytes)
    # Verifica que exista exactamente un salto de línea delimitador al final.
    assert payload.endswith(b"\n")
    # Verifica que el mensaje no contenga líneas internas adicionales.
    assert payload.count(b"\n") == 1
    # Decodifica la línea para inspeccionar su contrato JSON.
    decoded = json.loads(payload.decode("utf-8"))
    # Verifica el tipo de mensaje esperado por el firmware.
    assert decoded["type"] == "snapshot"
    # Verifica la versión de protocolo acordada.
    assert decoded["protocol_version"] == "1.0"
    # Verifica que la plataforma conserve su identificador.
    assert decoded["platforms"][0]["platform_id"] == "github-copilot"
    # Verifica que los caracteres Unicode sobrevivan a la ida y vuelta.
    assert decoded["platforms"][0]["agents"][0]["display_name"] == "Revisión de documentación"
