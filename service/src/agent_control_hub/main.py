"""Punto de entrada del servicio Agent Control Hub."""

import argparse
import asyncio
import time
from pathlib import Path

from agent_control_hub.adapter_factory import AdapterSelection, build_adapter_selection
from agent_control_hub.adapters import MockAdapter
from agent_control_hub.config import load_settings
from agent_control_hub.protocol import encode_snapshot
from agent_control_hub.snapshot_service import SnapshotService
from agent_control_hub.transports import SerialTransport


def build_parser() -> argparse.ArgumentParser:
    """Crea y configura el analizador de la aplicación."""

    parser = argparse.ArgumentParser(
        description="Monitoriza agentes de IA y publica su estado normalizado.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Archivo JSON con plataformas y preferencias del servicio.",
    )
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Puerto serie del dispositivo, por ejemplo COM5.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Segundos entre actualizaciones; sustituye el archivo de configuración.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Archivo JSON que se actualizará de forma atómica en cada captura.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Genera una instantánea y finaliza.",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Fuerza datos simulados e ignora la selección de plataformas.",
    )
    return parser


def _build_mock_selection() -> AdapterSelection:
    """Devuelve un único conector simulado y visible."""

    return AdapterSelection(
        adapters=(MockAdapter(),),
        visible_platform_ids=frozenset({"mock"}),
    )


async def collect_snapshot(service: SnapshotService) -> bytes:
    """Recoge las plataformas configuradas y devuelve NDJSON."""

    snapshot = await service.collect()
    return encode_snapshot(snapshot)


def write_snapshot_file(path: Path, payload: bytes) -> None:
    """Sustituye el JSON de salida sin dejar archivos parciales."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_bytes(payload)
    temporary_path.replace(path)


def main(args: argparse.Namespace) -> int:
    """Ejecuta una captura única o un bucle de transmisión."""

    settings = load_settings(args.config)
    selection = _build_mock_selection() if args.mock else build_adapter_selection(settings)
    service = SnapshotService(
        selection.adapters,
        visible_platform_ids=selection.visible_platform_ids,
    )
    interval = args.interval if args.interval is not None else settings.update_interval_seconds
    if interval <= 0:
        raise ValueError("El intervalo debe ser mayor que cero.")

    transport: SerialTransport | None = None
    if args.port is not None:
        transport = SerialTransport(port=args.port)

    try:
        while True:
            payload = asyncio.run(collect_snapshot(service))
            if transport is not None:
                transport.send(payload)
            if args.output is not None:
                write_snapshot_file(args.output, payload)
            print(payload.decode("utf-8"), end="")
            if args.once:
                break
            time.sleep(interval)
    finally:
        if transport is not None:
            transport.close()
    return 0


def run() -> None:
    """Analiza argumentos y termina con el código de la aplicación."""

    parser = build_parser()
    args = parser.parse_args()
    exit_code = main(args)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    run()
