"""Punto de entrada del servicio Agent Control Hub."""

# Importa herramientas para definir argumentos de línea de comandos.
import argparse
# Importa el motor asíncrono utilizado por adaptadores.
import asyncio
# Importa rutas para localizar la configuración local.
from pathlib import Path
# Importa utilidades de tiempo para el modo continuo.
import time

# Importa la selección validada de conectores.
from agent_control_hub.adapter_factory import AdapterSelection, build_adapter_selection
# Importa el adaptador de demostración forzado por consola.
from agent_control_hub.adapters import MockAdapter
# Importa la carga validada de preferencias.
from agent_control_hub.config import load_settings
# Importa el codificador del protocolo serie.
from agent_control_hub.protocol import encode_snapshot
# Importa el agregador de plataformas.
from agent_control_hub.snapshot_service import SnapshotService
# Importa el transporte USB serie.
from agent_control_hub.transports import SerialTransport


# Construye el analizador de argumentos de consola.
def build_parser() -> argparse.ArgumentParser:
    """Crea y configura el analizador de la aplicación."""

    # Crea el analizador con una descripción breve.
    parser = argparse.ArgumentParser(
        # Explica la función principal del proceso.
        description="Monitoriza agentes de IA y envía su estado a un dispositivo físico.",
    )
    # Añade el archivo JSON opcional de configuración.
    parser.add_argument(
        # Define el nombre largo del argumento.
        "--config",
        # Convierte el valor recibido en una ruta local.
        type=Path,
        # Utiliza valores seguros cuando no se facilita archivo.
        default=None,
        # Documenta el propósito de la opción.
        help="Archivo JSON con plataformas y preferencias del servicio.",
    )
    # Añade el puerto serie opcional del dispositivo.
    parser.add_argument(
        # Define el nombre largo del argumento.
        "--port",
        # Declara que el valor recibido será texto.
        type=str,
        # No utiliza puerto serie cuando se omite.
        default=None,
        # Documenta un ejemplo válido para Windows.
        help="Puerto serie del dispositivo, por ejemplo COM5.",
    )
    # Añade una posible sustitución del intervalo configurado.
    parser.add_argument(
        # Define el nombre largo del argumento.
        "--interval",
        # Convierte el valor a número decimal.
        type=float,
        # Utiliza la configuración cuando se omite.
        default=None,
        # Documenta la unidad del intervalo.
        help="Segundos entre actualizaciones; sustituye el archivo de configuración.",
    )
    # Añade el modo de una sola ejecución.
    parser.add_argument(
        # Define el nombre largo del argumento.
        "--once",
        # Activa una bandera booleana sin valor adicional.
        action="store_true",
        # Documenta que el proceso terminará tras una captura.
        help="Genera una instantánea y finaliza.",
    )
    # Añade explícitamente el adaptador simulado.
    parser.add_argument(
        # Define el nombre largo del argumento.
        "--mock",
        # Activa una bandera booleana sin valor adicional.
        action="store_true",
        # Documenta el propósito de desarrollo.
        help="Fuerza datos simulados e ignora la selección de plataformas.",
    )
    # Devuelve el analizador configurado.
    return parser


# Construye una selección exclusiva para el modo de demostración.
def _build_mock_selection() -> AdapterSelection:
    """Devuelve un único conector simulado y visible."""

    # Crea una selección inmutable compatible con el servicio.
    return AdapterSelection(
        # Añade una única instancia del adaptador simulado.
        adapters=(MockAdapter(),),
        # Permite que la plataforma simulada aparezca en el dispositivo.
        visible_platform_ids=frozenset({"mock"}),
    )


# Obtiene una instantánea completa mediante el servicio configurado.
async def collect_snapshot(service: SnapshotService) -> bytes:
    """Recoge las plataformas configuradas y devuelve NDJSON."""

    # Obtiene el modelo normalizado de todas las plataformas visibles.
    snapshot = await service.collect()
    # Codifica el modelo para consola o dispositivo.
    return encode_snapshot(snapshot)


# Ejecuta el bucle principal según los argumentos recibidos.
def main(args: argparse.Namespace) -> int:
    """Ejecuta una captura única o un bucle de transmisión."""

    # Carga y valida preferencias antes de iniciar conectores.
    settings = load_settings(args.config)
    # Fuerza la demostración cuando se solicita expresamente.
    if args.mock:
        # Utiliza únicamente datos simulados.
        selection = _build_mock_selection()
    else:
        # Construye conectores según la configuración validada.
        selection = build_adapter_selection(settings)
    # Construye el agregador con monitorización y visibilidad separadas.
    service = SnapshotService(
        # Inyecta todos los conectores que deben consultarse.
        selection.adapters,
        # Filtra la información enviada al dispositivo.
        visible_platform_ids=selection.visible_platform_ids,
    )
    # Utiliza el valor de consola cuando fue facilitado.
    interval = args.interval if args.interval is not None else settings.update_interval_seconds
    # Rechaza intervalos nulos o negativos antes de abrir dispositivos.
    if interval <= 0:
        # Informa del error mediante una excepción de uso.
        raise ValueError("El intervalo debe ser mayor que cero.")
    # Mantiene el transporte vacío cuando solo se imprime por consola.
    transport: SerialTransport | None = None
    # Crea el transporte cuando el usuario facilita un puerto.
    if args.port is not None:
        # Configura la conexión USB serie seleccionada.
        transport = SerialTransport(port=args.port)
    # Inicia el bucle controlado por la opción de una sola ejecución.
    try:
        # Repite hasta que se solicite finalizar.
        while True:
            # Ejecuta la captura asíncrona desde el proceso síncrono.
            payload = asyncio.run(collect_snapshot(service))
            # Envía el mensaje al dispositivo cuando existe transporte.
            if transport is not None:
                # Transmite la instantánea NDJSON completa.
                transport.send(payload)
            # Imprime el mensaje para facilitar desarrollo y diagnóstico.
            print(payload.decode("utf-8"), end="")
            # Finaliza inmediatamente en modo de una sola captura.
            if args.once:
                # Rompe el bucle principal.
                break
            # Espera el intervalo configurado antes de la siguiente captura.
            time.sleep(interval)
    # Garantiza la liberación del puerto ante cualquier salida.
    finally:
        # Cierra el transporte cuando fue creado.
        if transport is not None:
            # Libera el puerto serie para otros procesos.
            transport.close()
    # Devuelve un código de salida correcto.
    return 0


# Expone el punto de entrada configurado en pyproject.toml.
def run() -> None:
    """Analiza argumentos y termina con el código de la aplicación."""

    # Construye el analizador de opciones.
    parser = build_parser()
    # Analiza los argumentos facilitados por el usuario.
    args = parser.parse_args()
    # Ejecuta la aplicación y captura su código final.
    exit_code = main(args)
    # Finaliza el proceso con el código calculado.
    raise SystemExit(exit_code)


# Permite ejecutar el módulo directamente durante desarrollo.
if __name__ == "__main__":
    # Inicia la aplicación de consola.
    run()
