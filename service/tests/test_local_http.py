"""Pruebas del servidor HTTP restringido a loopback."""

# Importa threading para ejecutar el servidor durante cada prueba.
import threading
# Importa HTTPConnection para probar el servidor sin dependencias externas.
from http.client import HTTPConnection, HTTPResponse
# Importa Path para tipar la carpeta temporal de pytest.
from pathlib import Path
# Importa cast para concretar el tipo de server_address.
from typing import cast

# Importa pytest para comprobar errores de configuración explícitos.
import pytest

# Importa la factoría pública sometida a prueba.
from agent_control_hub.local_http import create_server


# Envía una petición HTTP al servidor de prueba.
def _request(port: int, method: str, path: str) -> tuple[HTTPResponse, bytes]:
    """Devuelve la respuesta y el cuerpo completo de una petición local."""

    # Abre una conexión únicamente contra loopback.
    connection = HTTPConnection("127.0.0.1", port, timeout=2)
    # Envía el método y la ruta indicados por la prueba.
    connection.request(method, path)
    # Recupera la respuesta del servidor.
    response = connection.getresponse()
    # Lee el cuerpo antes de cerrar el socket.
    payload = response.read()
    # Cierra explícitamente la conexión local.
    connection.close()
    # Devuelve los datos observados.
    return response, payload


# Comprueba que solo se sirven los recursos públicos previstos.
def test_local_http_serves_allowlist_and_security_headers(tmp_path: Path) -> None:
    """Rechaza rutas arbitrarias y añade cabeceras defensivas."""

    # Crea el documento principal del visor.
    (tmp_path / "index.html").write_text("<h1>Agent Control Hub</h1>", encoding="utf-8")
    # Crea un snapshot mínimo para la prueba.
    (tmp_path / "snapshot.json").write_text('{"type":"snapshot"}', encoding="utf-8")
    # Crea un archivo que nunca debe quedar publicado.
    (tmp_path / ".env").write_text("SECRET=value", encoding="utf-8")
    # Crea el servidor con puerto automático del sistema operativo.
    server = create_server(tmp_path, 0)
    # Recupera la dirección asignada por el sistema.
    host, port = cast(tuple[str, int], server.server_address)
    # Confirma que la factoría nunca enlaza una interfaz externa.
    assert host == "127.0.0.1"
    # Prepara el hilo que atenderá las peticiones de prueba.
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    # Inicia el servidor local.
    thread.start()

    # Garantiza la limpieza aunque falle una aserción.
    try:
        # Solicita el documento principal desde la raíz.
        index_response, index_payload = _request(port, "GET", "/")
        # Confirma que el documento se entrega correctamente.
        assert index_response.status == 200
        # Confirma que el cuerpo esperado llega completo.
        assert index_payload == b"<h1>Agent Control Hub</h1>"
        # Confirma que el navegador no debe almacenar la respuesta.
        assert index_response.getheader("Cache-Control") == (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        # Confirma que el visor no puede embeberse en un marco.
        assert index_response.getheader("X-Frame-Options") == "DENY"
        # Confirma que existe una política de contenido defensiva.
        assert index_response.getheader("Content-Security-Policy") is not None

        # Solicita el snapshot permitido.
        snapshot_response, snapshot_payload = _request(port, "GET", "/snapshot.json")
        # Confirma que el snapshot se sirve correctamente.
        assert snapshot_response.status == 200
        # Confirma que el JSON no se transforma.
        assert snapshot_payload == b'{"type":"snapshot"}'

        # Comprueba la ruta de salud utilizada por PowerShell.
        health_response, health_payload = _request(port, "GET", "/health")
        # Confirma que el proceso está listo.
        assert health_response.status == 200
        # Confirma el cuerpo mínimo de la sonda.
        assert health_payload == b"ok\n"

        # Intenta acceder a un archivo oculto existente.
        secret_response, _ = _request(port, "GET", "/.env")
        # Confirma que la lista cerrada oculta el archivo.
        assert secret_response.status == 404

        # Intenta utilizar una ruta transversal.
        traversal_response, _ = _request(port, "GET", "/../.env")
        # Confirma que la ruta no se resuelve fuera de la lista permitida.
        assert traversal_response.status == 404

        # Intenta enviar datos mediante POST.
        post_response, _ = _request(port, "POST", "/snapshot.json")
        # Confirma que el servidor es exclusivamente de lectura.
        assert post_response.status == 405
    # Libera siempre el socket y el hilo del servidor.
    finally:
        # Solicita una parada ordenada.
        server.shutdown()
        # Cierra el socket de escucha.
        server.server_close()
        # Espera la finalización del hilo.
        thread.join(timeout=2)


# Comprueba que una carpeta inexistente no puede publicarse.
def test_local_http_rejects_missing_directory(tmp_path: Path) -> None:
    """Falla antes de abrir el socket cuando la raíz no existe."""

    # Construye una ruta que no se ha creado.
    missing_directory = tmp_path / "missing"

    # Comprueba el error de configuración esperado.
    with pytest.raises(ValueError, match="No existe la carpeta pública"):
        # Intenta crear el servidor sobre una ruta inexistente.
        create_server(missing_directory, 0)
