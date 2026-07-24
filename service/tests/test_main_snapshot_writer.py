"""Pruebas del escritor resiliente de snapshots en Windows."""

# Importa Path para simular reemplazos atómicos sobre archivos temporales.
from pathlib import Path

# Importa el módulo completo para sustituir dependencias de forma controlada.
from agent_control_hub import main as main_module


# Comprueba que un bloqueo transitorio no termina el servicio.
def test_write_snapshot_retries_after_transient_permission_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Reintenta os.replace y publica el JSON cuando el bloqueo desaparece."""

    # Define el destino dentro de la carpeta temporal de pytest.
    output_path = tmp_path / "snapshot.json"
    # Conserva la implementación real para completar el segundo intento.
    original_replace = main_module.os.replace
    # Inicializa el contador de llamadas observadas.
    attempts = 0

    # Simula un primer bloqueo de Windows y éxito posterior.
    def flaky_replace(source: str | Path, target: str | Path) -> None:
        # Permite actualizar el contador externo.
        nonlocal attempts
        # Registra cada intento de sustitución.
        attempts += 1
        # Reproduce el bloqueo transitorio del archivo servido por WAMP.
        if attempts == 1:
            raise PermissionError("archivo temporalmente bloqueado")
        # Ejecuta el reemplazo real cuando el bloqueo desaparece.
        original_replace(source, target)

    # Sustituye únicamente os.replace durante esta prueba.
    monkeypatch.setattr(main_module.os, "replace", flaky_replace)
    # Evita esperas reales entre intentos.
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    # Ejecuta la escritura resiliente.
    written = main_module.write_snapshot_file(output_path, b'{"ok":true}\n')

    # Confirma que la captura finalmente se publicó.
    assert written is True
    # Confirma que se produjo al menos un reintento.
    assert attempts == 2
    # Comprueba que el destino contiene el payload completo.
    assert output_path.read_bytes() == b'{"ok":true}\n'


# Comprueba que un bloqueo persistente conserva el snapshot anterior.
def test_write_snapshot_keeps_previous_file_when_replace_remains_locked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Devuelve False sin borrar el último snapshot válido ni dejar temporales."""

    # Define el archivo servido por el visor.
    output_path = tmp_path / "snapshot.json"
    # Guarda una captura previa que debe permanecer disponible.
    output_path.write_bytes(b'{"previous":true}\n')

    # Reproduce un bloqueo persistente del destino en Windows.
    def always_locked(_source: str | Path, _target: str | Path) -> None:
        # Lanza el mismo error observado en el equipo real.
        raise PermissionError("destino bloqueado")

    # Sustituye el reemplazo atómico por el bloqueo controlado.
    monkeypatch.setattr(main_module.os, "replace", always_locked)
    # Evita retrasar la suite de pruebas.
    monkeypatch.setattr(main_module.time, "sleep", lambda _seconds: None)

    # Intenta publicar una captura nueva.
    written = main_module.write_snapshot_file(output_path, b'{"new":true}\n')

    # Informa de que esa iteración no pudo publicarse.
    assert written is False
    # Mantiene disponible el último JSON válido.
    assert output_path.read_bytes() == b'{"previous":true}\n'
    # Elimina todos los temporales creados por el intento fallido.
    assert list(tmp_path.glob(".snapshot.json.*.tmp")) == []
