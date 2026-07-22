"""Agregación de adaptadores en instantáneas para el dispositivo."""

# Importa utilidades para ejecutar adaptadores concurrentemente.
import asyncio
# Importa contratos de colecciones de solo lectura.
from collections.abc import Sequence
# Importa fechas conscientes de zona horaria.
from datetime import UTC, datetime

# Importa el contrato de adaptadores aceptado por el servicio.
from agent_control_hub.adapters.base import PlatformAdapter
# Importa los modelos de salida normalizados.
from agent_control_hub.models import AgentState, DeviceSnapshot, PlatformSnapshot


# Coordina la lectura segura de múltiples plataformas.
class SnapshotService:
    """Construye una instantánea global a partir de varios adaptadores."""

    # Inicializa el servicio con adaptadores y visibilidad opcional.
    def __init__(
        # Recibe la instancia actual para guardar dependencias.
        self,
        # Recibe cualquier secuencia estable de adaptadores.
        adapters: Sequence[PlatformAdapter],
        # Recibe los identificadores visibles o todos cuando se omite.
        visible_platform_ids: set[str] | frozenset[str] | None = None,
    ) -> None:
        """Guarda adaptadores monitorizados y el filtro del dispositivo."""

        # Copia la secuencia para evitar mutaciones externas inesperadas.
        self._adapters = tuple(adapters)
        # Conserva ausencia de filtro como visibilidad completa.
        if visible_platform_ids is None:
            # Marca que cualquier plataforma puede enviarse al dispositivo.
            self._visible_platform_ids: frozenset[str] | None = None
        else:
            # Copia el filtro para impedir modificaciones posteriores.
            self._visible_platform_ids = frozenset(visible_platform_ids)

    # Comprueba si una plataforma debe enviarse al dispositivo.
    def _is_visible(self, platform_id: str) -> bool:
        """Aplica el filtro sin impedir la monitorización del conector."""

        # Permite cualquier plataforma cuando no existe filtro explícito.
        if self._visible_platform_ids is None:
            # Informa de que la plataforma puede incluirse.
            return True
        # Comprueba la inclusión en el conjunto configurado.
        return platform_id in self._visible_platform_ids

    # Ejecuta todos los adaptadores y compone un único mensaje.
    async def collect(self) -> DeviceSnapshot:
        """Recoge plataformas concurrentemente y conserva fallos aislados."""

        # Ejecuta las capturas sin permitir que un fallo cancele las demás.
        results = await asyncio.gather(
            # Genera una corrutina por cada adaptador configurado.
            *(adapter.collect() for adapter in self._adapters),
            # Devuelve excepciones como resultados inspeccionables.
            return_exceptions=True,
        )
        # Prepara la lista final de plataformas visibles y normalizadas.
        platforms: list[PlatformSnapshot] = []
        # Recorre adaptadores y resultados manteniendo su asociación.
        for adapter, result in zip(self._adapters, results, strict=True):
            # Omite la salida física cuando la plataforma está oculta.
            if not self._is_visible(adapter.platform_id):
                # Continúa después de haber ejecutado su monitorización.
                continue
            # Convierte cualquier excepción en una plataforma desconectada.
            if isinstance(result, BaseException):
                # Añade un estado degradado sin filtrar detalles sensibles.
                platforms.append(
                    # Construye la instantánea mínima de error.
                    PlatformSnapshot(
                        # Conserva el identificador del adaptador afectado.
                        platform_id=adapter.platform_id,
                        # Utiliza un nombre legible derivado del identificador.
                        display_name=adapter.platform_id.replace("-", " ").title(),
                        # Marca la plataforma como fuera de línea.
                        status=AgentState.OFFLINE,
                    )
                )
                # Continúa procesando el resto de plataformas.
                continue
            # Añade la instantánea válida devuelta por el adaptador.
            platforms.append(result)
        # Suma únicamente costes conocidos de plataformas visibles.
        total_cost_today = sum(
            # Convierte cada coste disponible a valor acumulable.
            platform.cost_today or 0.0
            # Recorre todas las plataformas agregadas.
            for platform in platforms
        )
        # Devuelve el mensaje completo para el dispositivo.
        return DeviceSnapshot(
            # Registra la fecha UTC de creación de la instantánea.
            generated_at=datetime.now(UTC),
            # Redondea el total para evitar artefactos de coma flotante.
            total_cost_today=round(total_cost_today, 6),
            # Adjunta las plataformas en el orden configurado.
            platforms=platforms,
        )
