"""Servidor HTTP mínimo y restringido para el visor local."""

# Importa argparse para ofrecer una interfaz de línea de comandos controlada.
import argparse
# Importa códigos HTTP normalizados para evitar valores mágicos.
from http import HTTPStatus
# Importa las clases estándar utilizadas por el servidor HTTP local.
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
# Importa Path para resolver los archivos públicos sin concatenaciones inseguras.
from pathlib import Path
# Importa urlsplit para separar la ruta de parámetros y fragmentos.
from urllib.parse import urlsplit


# Define los únicos recursos que el servidor puede publicar.
_ALLOWED_FILES: dict[str, tuple[str, str]] = {
    # Publica la raíz mediante el documento principal del visor.
    "/": ("index.html", "text/html; charset=utf-8"),
    # Permite solicitar expresamente el documento principal.
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    # Publica exclusivamente el snapshot sanitizado generado por el servicio.
    "/snapshot.json": ("snapshot.json", "application/json; charset=utf-8"),
}


# Implementa un manejador sin listado de directorios ni rutas arbitrarias.
class LocalViewerRequestHandler(BaseHTTPRequestHandler):
    """Sirve únicamente el visor, el snapshot y una comprobación de salud."""

    # Evita publicar la versión concreta de Python en las cabeceras.
    server_version = "AgentControlHubLocalViewer/1.0"
    # Elimina el sufijo de versión del intérprete que añade la clase base.
    sys_version = ""
    # Define la carpeta pública que establecerá la factoría de manejadores.
    viewer_directory = Path(".")

    # Sirve peticiones GET permitidas.
    def do_GET(self) -> None:  # noqa: N802
        """Devuelve el recurso solicitado cuando forma parte de la lista cerrada."""

        # Procesa la petición incluyendo el cuerpo de la respuesta.
        self._serve_request(include_body=True)

    # Sirve peticiones HEAD permitidas.
    def do_HEAD(self) -> None:  # noqa: N802
        """Devuelve únicamente cabeceras para comprobaciones locales."""

        # Procesa la petición sin transferir el cuerpo.
        self._serve_request(include_body=False)

    # Rechaza expresamente peticiones POST.
    def do_POST(self) -> None:  # noqa: N802
        """Impide utilizar el visor como receptor de datos o comandos."""

        # Devuelve el código estándar de método no permitido.
        self.send_error(HTTPStatus.METHOD_NOT_ALLOWED)

    # Evita registrar en consola rutas o parámetros potencialmente sensibles.
    def log_message(self, format: str, *args: object) -> None:
        """Desactiva el log HTTP estándar del servidor local."""

        # Descarta el formato porque el servicio no necesita logs de acceso.
        del format
        # Descarta los argumentos por el mismo motivo.
        del args

    # Añade cabeceras defensivas a todas las respuestas.
    def end_headers(self) -> None:
        """Aplica una política defensiva incluso en respuestas de error."""

        # Evita almacenar snapshots o respuestas del visor en caché.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        # Mantiene compatibilidad con clientes HTTP antiguos.
        self.send_header("Pragma", "no-cache")
        # Impide interpretar un tipo de contenido distinto al declarado.
        self.send_header("X-Content-Type-Options", "nosniff")
        # Impide embeber el visor dentro de marcos.
        self.send_header("X-Frame-Options", "DENY")
        # Evita publicar la URL como referencia al navegar fuera del visor.
        self.send_header("Referrer-Policy", "no-referrer")
        # Desactiva capacidades del navegador que el visor no utiliza.
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), usb=()",
        )
        # Limita las fuentes del documento al propio servidor local.
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'none'; object-src 'none'; img-src 'self' data:; "
            "connect-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'",
        )
        # Finaliza las cabeceras mediante la implementación estándar.
        super().end_headers()

    # Procesa una petición GET o HEAD mediante una lista cerrada de rutas.
    def _serve_request(self, include_body: bool) -> None:
        """Rechaza rutas no autorizadas y sirve archivos públicos conocidos."""

        # Separa la ruta de cualquier parámetro de consulta.
        request_path = urlsplit(self.path).path
        # Atiende una comprobación de salud sin acceder al sistema de archivos.
        if request_path == "/health":
            # Define un cuerpo mínimo para confirmar que el servidor está activo.
            payload = b"ok\n"
            # Envía una respuesta correcta.
            self.send_response(HTTPStatus.OK)
            # Declara el tipo de texto utilizado por la sonda.
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            # Declara el tamaño exacto del cuerpo.
            self.send_header("Content-Length", str(len(payload)))
            # Finaliza las cabeceras defensivas.
            self.end_headers()
            # Escribe el cuerpo únicamente para peticiones GET.
            if include_body:
                # Transfiere la respuesta mínima al cliente local.
                self.wfile.write(payload)
            # Finaliza el procesamiento de la petición.
            return
        # Recupera el recurso permitido mediante coincidencia exacta.
        allowed_file = _ALLOWED_FILES.get(request_path)
        # Rechaza cualquier ruta que no esté expresamente permitida.
        if allowed_file is None:
            # Devuelve un error genérico sin revelar archivos existentes.
            self.send_error(HTTPStatus.NOT_FOUND)
            # Finaliza el procesamiento de la petición rechazada.
            return
        # Separa el nombre de archivo y su tipo MIME fijo.
        filename, content_type = allowed_file
        # Resuelve la carpeta pública de forma absoluta.
        viewer_root = self.viewer_directory.resolve()
        # Resuelve el archivo permitido dentro de la carpeta pública.
        candidate = (viewer_root / filename).resolve()
        # Verifica de forma defensiva que el archivo continúe dentro de la raíz.
        if candidate.parent != viewer_root:
            # Rechaza cualquier desviación inesperada de la lista cerrada.
            self.send_error(HTTPStatus.NOT_FOUND)
            # Finaliza sin acceder al archivo.
            return
        # Comprueba que el recurso exista y sea un archivo regular.
        if not candidate.is_file():
            # Devuelve 404 mientras el primer snapshot todavía no exista.
            self.send_error(HTTPStatus.NOT_FOUND)
            # Finaliza el procesamiento.
            return
        # Lee únicamente el archivo público ya validado.
        payload = candidate.read_bytes()
        # Envía una respuesta correcta.
        self.send_response(HTTPStatus.OK)
        # Declara el tipo MIME fijo del recurso.
        self.send_header("Content-Type", content_type)
        # Declara el tamaño exacto del contenido.
        self.send_header("Content-Length", str(len(payload)))
        # Finaliza las cabeceras defensivas.
        self.end_headers()
        # Escribe el cuerpo únicamente cuando corresponde.
        if include_body:
            # Transfiere el contenido al navegador local.
            self.wfile.write(payload)


# Construye una clase manejadora asociada a una carpeta concreta.
def build_handler(directory: Path) -> type[LocalViewerRequestHandler]:
    """Evita estado global mutable al configurar la raíz pública."""

    # Define una subclase aislada para esta instancia del servidor.
    class ConfiguredLocalViewerRequestHandler(LocalViewerRequestHandler):
        # Asocia la carpeta validada a la clase manejadora.
        viewer_directory = directory

    # Devuelve la clase que ThreadingHTTPServer instanciará por petición.
    return ConfiguredLocalViewerRequestHandler


# Crea un servidor enlazado exclusivamente a la interfaz loopback IPv4.
def create_server(directory: Path, port: int) -> ThreadingHTTPServer:
    """Devuelve un servidor local preparado para pruebas o ejecución real."""

    # Rechaza puertos fuera del rango TCP permitido.
    if not 0 <= port <= 65535:
        # Informa de un error de configuración antes de abrir sockets.
        raise ValueError("El puerto debe estar entre 0 y 65535.")
    # Resuelve la carpeta pública para impedir cambios relativos posteriores.
    viewer_directory = directory.resolve()
    # Comprueba que la carpeta exista antes de iniciar el servidor.
    if not viewer_directory.is_dir():
        # Informa de una instalación incompleta o una ruta equivocada.
        raise ValueError(f"No existe la carpeta pública: {viewer_directory}")
    # Construye el manejador limitado a la carpeta indicada.
    handler = build_handler(viewer_directory)
    # Crea el servidor exclusivamente en loopback IPv4.
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    # Evita que hilos de peticiones impidan cerrar el proceso.
    server.daemon_threads = True
    # Devuelve la instancia para que el llamador controle su ciclo de vida.
    return server


# Construye el analizador de argumentos de la utilidad local.
def build_parser() -> argparse.ArgumentParser:
    """Define una interfaz mínima sin opciones de enlace a red externa."""

    # Crea el analizador con una descripción operativa.
    parser = argparse.ArgumentParser(description="Servidor local seguro de Agent Control Hub.")
    # Recibe la carpeta donde se encuentran index.html y snapshot.json.
    parser.add_argument("--directory", required=True, type=Path)
    # Recibe un puerto local no privilegiado.
    parser.add_argument("--port", type=int, default=8765)
    # Devuelve el analizador configurado.
    return parser


# Ejecuta el servidor hasta recibir una interrupción local.
def run() -> None:
    """Inicia el visor exclusivamente en http://127.0.0.1."""

    # Interpreta los argumentos proporcionados por el lanzador PowerShell.
    arguments = build_parser().parse_args()
    # Crea el servidor enlazado a loopback.
    server = create_server(arguments.directory, arguments.port)
    # Garantiza el cierre del socket al finalizar.
    with server:
        # Mantiene el servidor activo con una espera breve entre ciclos.
        server.serve_forever(poll_interval=0.25)


# Permite ejecutar el módulo mediante python -m.
if __name__ == "__main__":
    # Inicia el servidor local.
    run()
