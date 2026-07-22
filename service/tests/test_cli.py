"""Pruebas de humo del punto de entrada de consola."""

# Importa el analizador JSON para validar la salida de demostración.
import json

# Importa pytest para comprobar errores de uso esperados.
import pytest

# Importa el parser y la función principal sin ejecutar SystemExit.
from agent_control_hub.main import build_parser, main


# Comprueba que el modo de demostración produzca una instantánea completa.
def test_cli_mock_once_prints_valid_snapshot(capsys: pytest.CaptureFixture[str]) -> None:
    """Valida el recorrido mínimo desde la CLI hasta el protocolo NDJSON."""

    # Construye argumentos equivalentes a una ejecución manual de una sola captura.
    arguments = build_parser().parse_args(["--once", "--mock"])
    # Ejecuta el servicio sin abrir un puerto serie.
    exit_code = main(arguments)
    # Recupera la salida escrita en la consola.
    captured = capsys.readouterr()
    # Verifica que el proceso informe de una finalización correcta.
    assert exit_code == 0
    # Convierte la línea NDJSON en un objeto inspeccionable.
    payload = json.loads(captured.out.strip())
    # Verifica el discriminador principal del protocolo.
    assert payload["type"] == "snapshot"
    # Verifica que la demostración incluya al menos una plataforma.
    assert len(payload["platforms"]) >= 1


# Comprueba que un intervalo inválido se rechace antes de abrir dispositivos.
def test_cli_rejects_non_positive_interval() -> None:
    """Evita bucles agresivos o configuraciones imposibles."""

    # Construye una ejecución simulada con intervalo igual a cero.
    arguments = build_parser().parse_args(
        # Utiliza una lista explícita de parámetros de consola.
        ["--once", "--mock", "--interval", "0"],
    )
    # Verifica que el servicio produzca un error de uso claro.
    with pytest.raises(ValueError, match="mayor que cero"):
        # Ejecuta la función principal con la configuración inválida.
        main(arguments)
