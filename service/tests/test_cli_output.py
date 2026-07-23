"""Pruebas de exportación de instantáneas para el visor del PC."""

import json
from pathlib import Path

import pytest

from agent_control_hub.main import build_parser, main


def test_cli_writes_valid_snapshot_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Genera un JSON completo mediante la misma CLI que usará WAMP."""

    output_path = tmp_path / "web" / "snapshot.json"
    arguments = build_parser().parse_args(
        ["--once", "--mock", "--output", str(output_path)],
    )

    exit_code = main(arguments)

    assert exit_code == 0
    assert output_path.is_file()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["type"] == "snapshot"
    assert payload["platforms"]
    assert not (output_path.parent / ".snapshot.json.tmp").exists()
    assert json.loads(capsys.readouterr().out)["type"] == "snapshot"
