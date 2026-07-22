"""Punto de entrada del servicio Agent Control Hub."""

# Importa herramientas para definir argumentos de línea de comandos.
import argparse
# Importa el motor asíncrono utilizado por adaptadores.
import asyncio
# Importa utilidades de tiempo para el modo continuo.
import time

# Importa el adaptador de demostración del MVP.
from agent_control_hub.adapters import MockAdapter
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
    # Añade el intervalo entre instantáneas.
    parser.add_argument(
        # Define el nombre largo del argumento.
        "--interval",
        # Convierte el valor a número decimal.
        type=float,
        # Utiliza cinco segundos por defecto.
        default=5.0,
        # Documenta la unidad del intervalo.
        help="Segundos entre actualizaciones.",
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
        help="Utiliza datos simulados para desarrollar la interfaz.",
    )
    # Devuelve el analizador configurado.
    return parser


# Obtiene una instantánea completa mediante el servicio.
async def collect_snapshot() -> bytes:
    """Recoge el adaptador de demostración y devuelve NDJSON."""

    # Crea el agregador con el adaptador disponible en el MVP.
    service = SnapshotService([MockAdapter()])
    # Obtiene el modelo normalizado de todas las plataformas.
    snapshot = await service.collect()
    # Codifica el modelo para consola o dispositivo.
    return encode_snapshot(snapshot)


# Ejecuta el bucle principal según los argumentos recibidos.
def main(args: argparse.Namespace) -> int:
    """Ejecuta una captura única o un bucle de transmisión."""

    # Rechaza intervalos nulos o negativos antes de abrir dispositivos.
    if args.interval <= 0:
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
            payload = asyncio.run(collect_snapshot())
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
            time.sleep(args.interval)
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
