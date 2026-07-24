"""Aplica cambios deterministas para cuotas en vivo y alertas de restauración."""

# Importa Path para modificar únicamente archivos conocidos del repositorio.
from pathlib import Path


# Sustituye exactamente una aparición y falla ante divergencias inesperadas.
def replace_once(path: Path, old: str, new: str) -> None:
    """Protege la migración frente a cambios concurrentes en los archivos."""

    # Lee el archivo completo con codificación estable.
    content = path.read_text(encoding="utf-8")
    # Cuenta el ancla antes de modificar para garantizar una sustitución inequívoca.
    occurrences = content.count(old)
    # Detiene la migración cuando el archivo no coincide con la revisión esperada.
    if occurrences != 1:
        # Explica el archivo y el número de coincidencias observadas.
        raise RuntimeError(f"Ancla no única en {path}: {occurrences}")
    # Sustituye únicamente la aparición validada.
    updated = content.replace(old, new, 1)
    # Publica el contenido completo sin alterar la codificación.
    path.write_text(updated, encoding="utf-8")


# Define las rutas del servicio desde la raíz del repositorio.
root = Path(__file__).resolve().parents[1]
# Define el archivo de modelos públicos.
models_path = root / "service/src/agent_control_hub/models.py"
# Define el agregador de capturas.
snapshot_service_path = root / "service/src/agent_control_hub/snapshot_service.py"
# Define el punto de entrada del servicio.
main_path = root / "service/src/agent_control_hub/main.py"
# Define el adaptador de Codex.
codex_path = root / "service/src/agent_control_hub/adapters/codex.py"
# Define el lanzador de la vista local.
preview_path = root / "scripts/run-codex-preview.ps1"
# Define las pruebas existentes del adaptador.
codex_tests_path = root / "service/tests/test_codex_adapter.py"


# Añade el modelo de alerta antes de la plataforma agregada.
replace_once(
    # Modifica exclusivamente el archivo de modelos.
    models_path,
    # Localiza la declaración actual de PlatformSnapshot.
    '''class PlatformSnapshot(BaseModel):
    """Instantánea agregada de una plataforma completa."""
''',
    # Inserta el modelo nuevo y conserva la declaración existente.
    '''class AlertSnapshot(BaseModel):
    """Alerta operativa retenida para Windows, visor y dispositivo físico."""

    # Impide aceptar campos no documentados en el protocolo.
    model_config = ConfigDict(extra="forbid")

    # Identifica el evento para deduplicarlo entre capturas.
    alert_id: str = Field(min_length=1, max_length=120)
    # Define el comportamiento que debe ejecutar cada interfaz.
    alert_type: str = Field(min_length=1, max_length=80)
    # Identifica la plataforma que originó el evento.
    platform_id: str = Field(min_length=1, max_length=40)
    # Publica un título breve y apto para notificaciones.
    title: str = Field(min_length=1, max_length=120)
    # Publica una explicación breve sin datos sensibles.
    message: str = Field(min_length=1, max_length=240)
    # Clasifica la importancia visual del evento.
    severity: str = Field(default="info", min_length=1, max_length=20)
    # Registra el instante real en el que se observó la transición.
    created_at: datetime


class PlatformSnapshot(BaseModel):
    """Instantánea agregada de una plataforma completa."""
''',
)


# Añade las alertas retenidas al contrato del dispositivo.
replace_once(
    # Modifica el archivo de modelos ya ampliado.
    models_path,
    # Localiza el final actual de DeviceSnapshot.
    '''    total_cost_today: float = Field(default=0, ge=0)
    platforms: list[PlatformSnapshot] = Field(default_factory=list)
''',
    # Adjunta una colección opcional compatible hacia atrás.
    '''    total_cost_today: float = Field(default=0, ge=0)
    platforms: list[PlatformSnapshot] = Field(default_factory=list)
    # Retiene eventos recientes para lectores que no consultan cada segundo.
    alerts: list[AlertSnapshot] = Field(default_factory=list, max_length=20)
''',
)


# Importa el detector de transiciones en el agregador.
replace_once(
    # Modifica el agregador principal.
    snapshot_service_path,
    # Localiza el bloque de importaciones internas.
    '''from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.models import AgentState, DeviceSnapshot, PlatformSnapshot
''',
    # Añade el detector sin crear dependencias circulares.
    '''from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.alerts import QuotaAlertTracker
from agent_control_hub.models import AgentState, DeviceSnapshot, PlatformSnapshot
''',
)


# Permite inyectar el detector y conserva uno entre iteraciones.
replace_once(
    # Modifica el constructor del agregador.
    snapshot_service_path,
    # Localiza la firma y el final actual del constructor.
    '''        # Recibe los identificadores visibles o todos cuando se omite.
        visible_platform_ids: set[str] | frozenset[str] | None = None,
    ) -> None:
        """Guarda adaptadores monitorizados y el filtro del dispositivo."""

        # Copia la secuencia para evitar mutaciones externas inesperadas.
        self._adapters = tuple(adapters)
''',
    # Añade el detector opcional y su estado persistente.
    '''        # Recibe los identificadores visibles o todos cuando se omite.
        visible_platform_ids: set[str] | frozenset[str] | None = None,
        # Permite sustituir el detector por un doble controlado en pruebas.
        alert_tracker: QuotaAlertTracker | None = None,
    ) -> None:
        """Guarda adaptadores monitorizados, visibilidad y estado de alertas."""

        # Copia la secuencia para evitar mutaciones externas inesperadas.
        self._adapters = tuple(adapters)
        # Conserva el detector entre capturas para observar transiciones reales.
        self._alert_tracker = alert_tracker or QuotaAlertTracker()
''',
)


# Calcula alertas con la misma fecha utilizada por el snapshot.
replace_once(
    # Modifica el bloque final del agregador.
    snapshot_service_path,
    # Localiza la construcción actual del DeviceSnapshot.
    '''        # Devuelve el mensaje completo para el dispositivo.
        return DeviceSnapshot(
            # Registra la fecha UTC de creación de la instantánea.
            generated_at=datetime.now(UTC),
            # Redondea el total para evitar artefactos de coma flotante.
            total_cost_today=round(total_cost_today, 6),
            # Adjunta las plataformas en el orden configurado.
            platforms=platforms,
        )
''',
    # Añade la retención de eventos operativos.
    '''        # Registra una única fecha para snapshot y alertas.
        generated_at = datetime.now(UTC)
        # Detecta restauraciones reales utilizando el estado de la captura anterior.
        alerts = self._alert_tracker.update(platforms, generated_at)
        # Devuelve el mensaje completo para el dispositivo.
        return DeviceSnapshot(
            # Registra la fecha UTC de creación de la instantánea.
            generated_at=generated_at,
            # Redondea el total para evitar artefactos de coma flotante.
            total_cost_today=round(total_cost_today, 6),
            # Adjunta las plataformas en el orden configurado.
            platforms=platforms,
            # Adjunta alertas recientes para Windows, web y hardware.
            alerts=alerts,
        )
''',
)


# Importa el modelo y la salida de notificación en el punto de entrada.
replace_once(
    # Modifica las importaciones de main.py.
    main_path,
    # Localiza las importaciones internas existentes.
    '''from agent_control_hub.adapter_factory import AdapterSelection, build_adapter_selection
from agent_control_hub.adapters import MockAdapter
from agent_control_hub.config import load_settings
from agent_control_hub.protocol import encode_snapshot
''',
    # Añade la salida nativa y el tipo de snapshot.
    '''from agent_control_hub.adapter_factory import AdapterSelection, build_adapter_selection
from agent_control_hub.adapters import MockAdapter
from agent_control_hub.alerts import WindowsNotificationSink
from agent_control_hub.config import load_settings
from agent_control_hub.models import DeviceSnapshot
from agent_control_hub.protocol import encode_snapshot
''',
)


# Añade una opción explícita para notificaciones de Windows.
replace_once(
    # Modifica el analizador de argumentos.
    main_path,
    # Localiza la opción mock y el retorno del parser.
    '''    parser.add_argument(
        "--mock",
        action="store_true",
        help="Fuerza datos simulados e ignora la selección de plataformas.",
    )
    return parser
''',
    # Inserta el nuevo interruptor sin alterar el comportamiento predeterminado.
    '''    parser.add_argument(
        "--mock",
        action="store_true",
        help="Fuerza datos simulados e ignora la selección de plataformas.",
    )
    parser.add_argument(
        "--notify-windows",
        action="store_true",
        help="Muestra una notificación de Windows cuando se restaura una cuota.",
    )
    return parser
''',
)


# Conserva el modelo antes de codificarlo para poder entregar sus alertas.
replace_once(
    # Modifica la función asíncrona de captura.
    main_path,
    # Localiza la función que actualmente devuelve bytes.
    '''async def collect_snapshot(service: SnapshotService) -> bytes:
    """Recoge las plataformas configuradas y devuelve NDJSON."""

    snapshot = await service.collect()
    return encode_snapshot(snapshot)
''',
    # Devuelve el modelo validado y deja la codificación al bucle principal.
    '''async def collect_snapshot(service: SnapshotService) -> DeviceSnapshot:
    """Recoge las plataformas configuradas y devuelve el modelo validado."""

    # Conserva alertas y plataformas antes de serializar la captura.
    return await service.collect()
''',
)


# Inicializa la salida de Windows junto al servicio persistente.
replace_once(
    # Modifica la configuración inicial de main.
    main_path,
    # Localiza la creación de SnapshotService y el cálculo del intervalo.
    '''    service = SnapshotService(
        selection.adapters,
        visible_platform_ids=selection.visible_platform_ids,
    )
    interval = args.interval if args.interval is not None else settings.update_interval_seconds
''',
    # Añade una salida deduplicada que permanece durante todo el proceso.
    '''    service = SnapshotService(
        selection.adapters,
        visible_platform_ids=selection.visible_platform_ids,
    )
    # Activa globos nativos únicamente cuando se solicita expresamente.
    notification_sink = WindowsNotificationSink(
        enabled=bool(getattr(args, "notify_windows", False))
    )
    interval = args.interval if args.interval is not None else settings.update_interval_seconds
''',
)


# Despacha alertas antes de codificar y publicar el snapshot.
replace_once(
    # Modifica el bucle principal de captura.
    main_path,
    # Localiza la creación actual del payload.
    '''        while True:
            payload = asyncio.run(collect_snapshot(service))
            if transport is not None:
''',
    # Conserva el snapshot, notifica y después codifica.
    '''        while True:
            # Recoge una captura validada con posibles eventos operativos.
            snapshot = asyncio.run(collect_snapshot(service))
            # Entrega únicamente alertas nuevas al centro de notificaciones.
            notification_sink.dispatch(snapshot.alerts)
            # Codifica el mismo modelo que reciben web y dispositivo físico.
            payload = encode_snapshot(snapshot)
            if transport is not None:
''',
)


# Añade el interruptor de desactivación al lanzador local.
replace_once(
    # Modifica la firma del script PowerShell.
    preview_path,
    # Localiza el último parámetro actual.
    '''    [int]$IntervalSeconds = 5,
    [switch]$Once,
    [switch]$DoNotOpenBrowser
)
''',
    # Añade una opción compatible con ejecuciones silenciosas o pruebas.
    '''    [int]$IntervalSeconds = 5,
    [switch]$Once,
    [switch]$DoNotOpenBrowser,
    [switch]$DisableWindowsNotifications
)
''',
)


# Activa las notificaciones por defecto en la vista local de Windows.
replace_once(
    # Modifica la construcción de argumentos del servicio.
    preview_path,
    # Localiza el final del array de argumentos base.
    '''    "--output",
    $SnapshotPath
)
if ($Once) {
''',
    # Añade el interruptor únicamente cuando el usuario no lo desactiva.
    '''    "--output",
    $SnapshotPath
)
if (-not $DisableWindowsNotifications) {
    # Solicita globos nativos cuando una cuota se restaura realmente.
    $ServiceArguments += "--notify-windows"
}
if ($Once) {
''',
)


# Importa la sonda oficial y el tipo Callable en el adaptador.
replace_once(
    # Modifica las importaciones estándar e internas de codex.py.
    codex_path,
    # Localiza las importaciones actuales de colecciones y tipos.
    '''from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from agent_control_hub.adapters.base import PlatformAdapter
''',
    # Añade la interfaz de función y la sonda en vivo.
    '''from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from agent_control_hub.adapters.base import PlatformAdapter
from agent_control_hub.codex_rate_limit_probe import CodexRateLimitProbe
''',
)


# Identifica la fuente real de las cuotas al construir el modelo público.
replace_once(
    # Modifica la construcción de RateLimitsSnapshot.
    codex_path,
    # Localiza la fuente JSONL fija.
    '''        source="codex_session_jsonl",
        updated_at=event.timestamp,
        source_reference=event.source_reference,
''',
    # Selecciona la fuente oficial en vivo cuando corresponde.
    '''        source=(
            "codex_app_server"
            if event.source_reference == "account/rateLimits/read"
            else "codex_session_jsonl"
        ),
        updated_at=event.timestamp,
        source_reference=event.source_reference,
''',
)


# Añade utilidades para interpretar disponibilidad de todas las ventanas.
replace_once(
    # Modifica el espacio anterior a la máquina de estados.
    codex_path,
    # Localiza la declaración de _derive_status.
    '''def _derive_status(state: _SessionAccumulator) -> tuple[AgentState, str | None, str | None]:
''',
    # Inserta helpers reutilizados por la lectura en vivo.
    '''def _remaining_rate_windows(rate_limits: RateLimitsSnapshot | None) -> list[float]:
    """Devuelve únicamente porcentajes restantes de ventanas existentes."""

    # Rechaza ausencia de cuotas sin confundirla con disponibilidad.
    if rate_limits is None:
        return []
    # Inicializa la lista de ventanas observadas.
    remaining: list[float] = []
    # Conserva la ventana primaria cuando existe.
    if rate_limits.primary is not None:
        remaining.append(rate_limits.primary.remaining_percent)
    # Conserva la ventana secundaria cuando existe.
    if rate_limits.secondary is not None:
        remaining.append(rate_limits.secondary.remaining_percent)
    # Devuelve los valores validados por el modelo.
    return remaining


def _quota_exhausted(rate_limits: RateLimitsSnapshot | None) -> bool:
    """Indica si cualquier ventana real impide continuar trabajando."""

    # Recupera las ventanas disponibles.
    remaining = _remaining_rate_windows(rate_limits)
    # Exige datos y detecta cualquier porcentaje agotado.
    return bool(remaining) and any(value <= 0 for value in remaining)


def _quota_available(rate_limits: RateLimitsSnapshot | None) -> bool:
    """Indica si todas las ventanas informadas permiten nuevas tareas."""

    # Recupera las ventanas disponibles.
    remaining = _remaining_rate_windows(rate_limits)
    # Exige datos y confirma que ninguna ventana siga agotada.
    return bool(remaining) and all(value > 0 for value in remaining)


def _derive_status(state: _SessionAccumulator) -> tuple[AgentState, str | None, str | None]:
''',
)


# Amplía el constructor del adaptador con una sonda cacheada e inyectable.
replace_once(
    # Modifica el constructor de CodexAdapter.
    codex_path,
    # Localiza la firma y atributos actuales.
    '''    def __init__(
        self,
        sessions_dir: Path | None = None,
        executable: str = "codex",
    ) -> None:
        """Configura la carpeta local y el ejecutable usado para detección."""

        self._sessions_dir = sessions_dir or Path.home() / ".codex" / "sessions"
        self._executable = executable
        self._file_cache: dict[Path, _FileCursor] = {}
''',
    # Añade la lectura oficial y el estado necesario para detectar restauraciones.
    '''    def __init__(
        self,
        sessions_dir: Path | None = None,
        executable: str = "codex",
        rate_limit_probe: Callable[[], dict[str, object] | None] | None = None,
        rate_limit_probe_interval_seconds: float = 60.0,
    ) -> None:
        """Configura sesiones, ejecutable y lectura oficial cacheada de cuotas."""

        # Conserva la carpeta local de sesiones históricas.
        self._sessions_dir = sessions_dir or Path.home() / ".codex" / "sessions"
        # Conserva el ejecutable utilizado por detección y app-server.
        self._executable = executable
        # Mantiene cursores incrementales por archivo JSONL.
        self._file_cache: dict[Path, _FileCursor] = {}
        # Utiliza la sonda oficial o el doble proporcionado por las pruebas.
        self._rate_limit_probe = rate_limit_probe or CodexRateLimitProbe(executable).read
        # Limita la frecuencia sin impedir un intervalo cero en pruebas.
        self._rate_limit_probe_interval = timedelta(
            seconds=max(0.0, rate_limit_probe_interval_seconds)
        )
        # Conserva la última lectura oficial válida como fallback temporal.
        self._live_rate_event: _TokenEvent | None = None
        # Registra el último intento para respetar el intervalo configurado.
        self._live_rate_checked_at: datetime | None = None
        # Conserva si la última lectura oficial mostraba bloqueo por cuota.
        self._live_quota_exhausted: bool | None = None
''',
)


# Añade la lectura cacheada antes de construir la captura síncrona.
replace_once(
    # Modifica el cuerpo de CodexAdapter.
    codex_path,
    # Localiza el inicio de _collect_sync.
    '''    def _collect_sync(self) -> PlatformSnapshot:
        """Actualiza cursores y construye una instantánea sanitizada."""
''',
    # Inserta el método auxiliar y conserva _collect_sync.
    '''    def _read_live_rate_event(
        self,
        now: datetime,
        executable_available: bool,
    ) -> tuple[_TokenEvent | None, bool]:
        """Consulta app-server con caché y devuelve si hubo una lectura nueva."""

        # Evita abrir app-server cuando Codex no está disponible.
        if not executable_available:
            return None, False
        # Reutiliza la última lectura dentro del intervalo configurado.
        if (
            self._live_rate_checked_at is not None
            and now - self._live_rate_checked_at < self._rate_limit_probe_interval
        ):
            return self._live_rate_event, False
        # Registra el intento antes de ejecutar una operación potencialmente lenta.
        self._live_rate_checked_at = now
        # Ejecuta la sonda sustituible y tolera fallos locales controlados.
        try:
            live_limits = self._rate_limit_probe()
        except (OSError, RuntimeError, ValueError):
            return self._live_rate_event, False
        # Conserva el último valor válido cuando app-server no responde.
        if live_limits is None:
            return self._live_rate_event, False
        # Convierte la respuesta oficial al evento compartido por el adaptador.
        self._live_rate_event = _TokenEvent(
            timestamp=now,
            source_reference="account/rateLimits/read",
            info={},
            rate_limits=live_limits,
        )
        # Informa de que existe una observación nueva para la máquina de estados.
        return self._live_rate_event, True

    def _collect_sync(self) -> PlatformSnapshot:
        """Actualiza cursores y construye una instantánea sanitizada."""
''',
)


# Prioriza la lectura oficial y deriva estados de cuota reales.
replace_once(
    # Modifica el núcleo de _collect_sync.
    codex_path,
    # Localiza la selección actual de eventos y estado.
    '''        now = datetime.now(UTC)
        usage_event = active_state.latest_usage or _latest_usage_event(self._file_cache)
        rate_event = _latest_rate_event(self._file_cache)
        usage = _build_usage_breakdown(usage_event) if usage_event is not None else None
        thread_total = usage.thread_total if usage is not None else None
        rate_limits = _build_rate_limits(rate_event, now) if rate_event is not None else None
        primary = rate_limits.primary if rate_limits is not None else None
        secondary = rate_limits.secondary if rate_limits is not None else None
        status, status_reason, status_message = _derive_status(active_state)
        return PlatformSnapshot(
''',
    # Añade la consulta oficial y la transición restaurada.
    '''        now = datetime.now(UTC)
        usage_event = active_state.latest_usage or _latest_usage_event(self._file_cache)
        # Consulta cuotas actuales sin iniciar tareas ni consumir tokens de modelo.
        live_rate_event, live_rate_refreshed = self._read_live_rate_event(
            now,
            executable_available,
        )
        # Utiliza JSONL únicamente cuando no existe una lectura oficial válida.
        rate_event = live_rate_event or _latest_rate_event(self._file_cache)
        usage = _build_usage_breakdown(usage_event) if usage_event is not None else None
        thread_total = usage.thread_total if usage is not None else None
        rate_limits = _build_rate_limits(rate_event, now) if rate_event is not None else None
        primary = rate_limits.primary if rate_limits is not None else None
        secondary = rate_limits.secondary if rate_limits is not None else None
        status, status_reason, status_message = _derive_status(active_state)
        # Aplica estados de cuota solo cuando la fuente oficial acaba de responder.
        if (
            live_rate_refreshed
            and rate_limits is not None
            and rate_limits.source == "codex_app_server"
            and not rate_limits.is_stale
        ):
            # Calcula el bloqueo actual de todas las ventanas informadas.
            current_live_exhausted = _quota_exhausted(rate_limits)
            # Mantiene espera cuando cualquier ventana continúa agotada.
            if current_live_exhausted:
                status = AgentState.WAITING
                status_reason = "usage_limit_exceeded"
                status_message = "Límite de uso agotado; consulta el reinicio de cuota."
            # Publica restauración cuando antes existía un bloqueo confirmado.
            elif _quota_available(rate_limits) and (
                self._live_quota_exhausted is True
                or status_reason == "usage_limit_exceeded"
            ):
                status = AgentState.IDLE
                status_reason = "usage_limit_restored"
                status_message = "La cuota de Codex vuelve a estar disponible."
            # Conserva el resultado para detectar la siguiente transición.
            self._live_quota_exhausted = current_live_exhausted
        # Construye la tarea con el estado de cuota ya actualizado.
        task = _build_task(active_state, status)
        # Sustituye el mensaje antiguo de límite cuando la cuota fue restaurada.
        if task is not None and status_reason == "usage_limit_restored":
            task = task.model_copy(update={"activity": status_message})
        return PlatformSnapshot(
''',
)


# Utiliza la tarea ajustada y una fecha de reinicio disponible.
replace_once(
    # Modifica dos campos de la construcción final.
    codex_path,
    # Localiza next_reset_at y task actuales.
    '''            next_reset_at=primary.resets_at if primary is not None else None,
            active_agents=0,
            agents=[],
            token_usage=thread_total,
            usage=usage,
            rate_limits=rate_limits,
            session=_build_session(active_state),
            project=_build_project(active_state),
            task=_build_task(active_state, status),
''',
    # Añade fallback a secundaria y utiliza la tarea ya corregida.
    '''            next_reset_at=(
                primary.resets_at
                if primary is not None
                else secondary.resets_at if secondary is not None else None
            ),
            active_agents=0,
            agents=[],
            token_usage=thread_total,
            usage=usage,
            rate_limits=rate_limits,
            session=_build_session(active_state),
            project=_build_project(active_state),
            task=task,
''',
)


# Añade una regresión que simula agotamiento y restauración anticipada.
replace_once(
    # Modifica el archivo de pruebas del adaptador.
    codex_tests_path,
    # Localiza el final de la última prueba existente.
    '''    assert snapshot.status == AgentState.OFFLINE
    assert snapshot.token_usage is None
    assert snapshot.rate_limits is None
''',
    # Conserva la prueba y añade el nuevo escenario.
    '''    assert snapshot.status == AgentState.OFFLINE
    assert snapshot.token_usage is None
    assert snapshot.rate_limits is None


def test_codex_adapter_detects_early_live_quota_reset(tmp_path: Path) -> None:
    """Prioriza app-server y distingue agotamiento de restauración real."""

    # Crea una sesión mínima para conservar metadatos de la plataforma.
    session = tmp_path / "rollout-live-rate.jsonl"
    # Escribe un consumo sin ventanas para obligar a utilizar la sonda oficial.
    session.write_text(
        _record("2026-07-24T12:00:00Z", 1_000, None, None) + "\n",
        encoding="utf-8",
    )
    # Prepara dos respuestas consecutivas: agotada y restaurada.
    live_responses = iter(
        [
            {
                "limit_id": "codex",
                "plan_type": "plus",
                "primary": {
                    "used_percent": 100.0,
                    "window_minutes": 10_080,
                    "resets_at": 1_785_322_523,
                },
                "secondary": None,
            },
            {
                "limit_id": "codex",
                "plan_type": "plus",
                "primary": {
                    "used_percent": 0.0,
                    "window_minutes": 10_080,
                    "resets_at": 1_785_927_323,
                },
                "secondary": None,
            },
        ]
    )
    # Construye el adaptador con una sonda determinista y sin caché temporal.
    adapter = CodexAdapter(
        sessions_dir=tmp_path,
        executable="python",
        rate_limit_probe=lambda: next(live_responses),
        rate_limit_probe_interval_seconds=0,
    )

    # Ejecuta la primera lectura oficial agotada.
    exhausted = asyncio.run(adapter.collect())
    # Ejecuta una segunda lectura que se restaura antes de la fecha anterior.
    restored = asyncio.run(adapter.collect())

    # Confirma que la primera lectura bloquea nuevas tareas.
    assert exhausted.status == AgentState.WAITING
    # Confirma el motivo explícito del bloqueo.
    assert exhausted.status_reason == "usage_limit_exceeded"
    # Confirma que la segunda lectura detecta la restauración real.
    assert restored.status == AgentState.IDLE
    # Confirma el motivo utilizado por alertas y prototipo.
    assert restored.status_reason == "usage_limit_restored"
    # Confirma que se utiliza la fuente oficial en vivo.
    assert restored.rate_limits is not None
    # Comprueba la identidad de la fuente.
    assert restored.rate_limits.source == "codex_app_server"
    # Comprueba que la cuota vuelve a estar disponible.
    assert restored.rolling_remaining_pct == 100
''',
)
