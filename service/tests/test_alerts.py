"""Pruebas de transición de cuota y notificación local."""

# Importa fechas UTC para construir capturas deterministas.
from datetime import UTC, datetime, timedelta

# Importa el detector y la salida de Windows sometidos a prueba.
from agent_control_hub.alerts import QuotaAlertTracker, WindowsNotificationSink
# Importa los modelos normalizados necesarios para crear escenarios reales.
from agent_control_hub.models import (
    AgentState,
    PlatformSnapshot,
    RateLimitsSnapshot,
    RateLimitWindowSnapshot,
)


# Construye una plataforma Codex con el porcentaje restante indicado.
def _codex_snapshot(remaining_percent: float, status_reason: str | None) -> PlatformSnapshot:
    """Crea una cuota primaria válida para probar transiciones."""

    # Calcula el porcentaje usado complementario.
    used_percent = 100 - remaining_percent
    # Devuelve una captura equivalente a la producida por el adaptador.
    return PlatformSnapshot(
        # Identifica la plataforma monitorizada.
        platform_id="codex",
        # Conserva el nombre visible del panel.
        display_name="OpenAI Codex",
        # Utiliza espera únicamente cuando existe el error explícito.
        status=AgentState.WAITING if status_reason == "usage_limit_exceeded" else AgentState.IDLE,
        # Adjunta la causa de estado proporcionada por el escenario.
        status_reason=status_reason,
        # Publica las ventanas actuales de la cuenta.
        rate_limits=RateLimitsSnapshot(
            # Identifica el conjunto de límites de Codex.
            limit_id="codex",
            # Conserva el plan observado.
            plan_type="plus",
            # Define una única ventana suficiente para este escenario.
            primary=RateLimitWindowSnapshot(
                # Publica el consumo complementario.
                used_percent=used_percent,
                # Publica la disponibilidad que controla la prueba.
                remaining_percent=remaining_percent,
                # Utiliza la ventana semanal observada en el caso real.
                window_minutes=10_080,
                # Define una fecha futura válida.
                resets_at=datetime(2026, 7, 29, 10, 55, 23, tzinfo=UTC),
            ),
            # No necesita una ventana secundaria para esta transición.
            secondary=None,
            # Identifica la lectura oficial en vivo.
            source="codex_app_server",
            # Registra una fecha reciente.
            updated_at=datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
            # Identifica el método oficial utilizado.
            source_reference="account/rateLimits/read",
            # Marca que los datos son actuales.
            is_stale=False,
        ),
    )


# Comprueba que la alerta aparece únicamente tras una restauración real.
def test_quota_tracker_emits_restored_alert_once() -> None:
    """No avisa por la fecha prevista y sí por el cambio observado a disponible."""

    # Define el instante inicial de la prueba.
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    # Crea el detector con retención suficiente.
    tracker = QuotaAlertTracker(retention_seconds=120)

    # Registra primero el estado agotado sin generar un falso aviso inicial.
    exhausted_alerts = tracker.update(
        # Entrega una cuota realmente agotada.
        [_codex_snapshot(0, "usage_limit_exceeded")],
        # Utiliza el instante inicial.
        now,
    )
    # Confirma que el primer estado solo inicializa la máquina.
    assert exhausted_alerts == []

    # Registra después una lectura en vivo con cuota disponible.
    restored_alerts = tracker.update(
        # Entrega una cuota restaurada antes de la fecha anterior.
        [_codex_snapshot(100, "usage_limit_restored")],
        # Avanza un minuto para simular una comprobación posterior.
        now + timedelta(minutes=1),
    )
    # Confirma que se generó exactamente un evento.
    assert len(restored_alerts) == 1
    # Recupera el evento generado.
    alert = restored_alerts[0]
    # Comprueba el tipo que consumirá el prototipo.
    assert alert.alert_type == "quota_restored"
    # Comprueba la plataforma afectada.
    assert alert.platform_id == "codex"

    # Repite la misma captura disponible dentro de la retención.
    repeated_alerts = tracker.update(
        # Mantiene la cuota disponible sin una nueva transición.
        [_codex_snapshot(100, "usage_limit_restored")],
        # Avanza unos segundos.
        now + timedelta(minutes=1, seconds=10),
    )
    # Confirma que se conserva el evento pero no se duplica.
    assert len(repeated_alerts) == 1
    # Confirma que el identificador continúa siendo el original.
    assert repeated_alerts[0].alert_id == alert.alert_id


# Comprueba que Windows recibe cada alerta una sola vez.
def test_windows_notification_sink_deduplicates_alerts() -> None:
    """Lanza un único PowerShell codificado aunque la alerta se retenga."""

    # Prepara una colección para observar los procesos solicitados.
    launched_arguments: list[list[str]] = []
    # Crea el detector y genera una alerta real.
    tracker = QuotaAlertTracker()
    # Define el instante base.
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    # Inicializa el estado agotado.
    tracker.update([_codex_snapshot(0, "usage_limit_exceeded")], now)
    # Genera la restauración observada.
    alerts = tracker.update(
        # Entrega la cuota ya disponible.
        [_codex_snapshot(100, "usage_limit_restored")],
        # Avanza un minuto.
        now + timedelta(minutes=1),
    )
    # Crea una salida Windows con un lanzador controlado.
    sink = WindowsNotificationSink(
        # Activa expresamente las notificaciones.
        enabled=True,
        # Simula el nombre de plataforma utilizado por Windows.
        platform_name="nt",
        # Registra los argumentos en lugar de abrir PowerShell.
        launcher=launched_arguments.append,
    )

    # Entrega la alerta por primera vez.
    sink.dispatch(alerts)
    # Vuelve a entregar la misma lista retenida.
    sink.dispatch(alerts)

    # Confirma que solo se solicitó un proceso.
    assert len(launched_arguments) == 1
    # Recupera la línea de argumentos generada.
    arguments = launched_arguments[0]
    # Comprueba que se utiliza Windows PowerShell.
    assert arguments[0] == "powershell.exe"
    # Comprueba que el contenido viaja mediante EncodedCommand.
    assert "-EncodedCommand" in arguments
