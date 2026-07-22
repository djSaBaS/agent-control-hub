"""Pruebas de configuración y selección de plataformas."""

# Importa rutas tipadas utilizadas por el directorio temporal.
from pathlib import Path

# Importa la construcción de adaptadores configurados.
from agent_control_hub.adapter_factory import build_adapter_selection
# Importa la carga validada del archivo JSON.
from agent_control_hub.config import load_settings


# Comprueba que una plataforma pueda monitorizarse sin mostrarse.
def test_hidden_platform_is_collected_but_not_visible(tmp_path: Path) -> None:
    """Valida la independencia entre monitorización y visibilidad."""

    # Construye la ruta temporal de configuración.
    config_path = tmp_path / "agent-control.json"
    # Escribe una configuración mínima con Copilot oculto.
    config_path.write_text(
        # Define un documento JSON válido y explícito.
        """
        {
          "update_interval_seconds": 10,
          "platforms": {
            "copilot": {
              "enabled": true,
              "monitoring_enabled": true,
              "visible_on_device": false,
              "alerts_enabled": true,
              "actions_enabled": false
            }
          }
        }
        """,
        # Utiliza la codificación estándar del proyecto.
        encoding="utf-8",
    )
    # Carga y valida la configuración escrita.
    settings = load_settings(config_path)
    # Construye la selección de adaptadores correspondiente.
    selection = build_adapter_selection(settings)
    # Comprueba que Copilot sí será consultado.
    assert len(selection.adapters) == 1
    # Comprueba que el adaptador correcto fue creado.
    assert selection.adapters[0].platform_id == "copilot"
    # Comprueba que no se enviará al dispositivo.
    assert selection.visible_platform_ids == frozenset()
    # Comprueba que se conserva el intervalo configurado.
    assert settings.update_interval_seconds == 10
