"""Detección de alertas operativas y entrega local en Windows."""

# Importa Base64 para transportar texto Unicode de forma segura a PowerShell.
import base64
# Importa el nombre de plataforma actual para limitar las notificaciones a Windows.
import os
# Importa procesos para lanzar la notificación sin bloquear el bucle principal.
import subprocess
# Importa fechas UTC para caducar eventos retenidos para el dispositivo.
from datetime import UTC, datetime, timedelta
# Importa tipos invocables para facilitar pruebas sin procesos reales.
from typing import Callable

# Importa los modelos públicos utilizados por el visor y el prototipo.
from agent_control_hub.models import AlertSnapshot, PlatformSnapshot


# Devuelve las ventanas de cuota realmente presentes en una plataforma.
def _rate_windows(platform: PlatformSnapshot) -> list[float]:
    """Recupera porcentajes restantes sin inventar ventanas ausentes."""

    # Recupera el bloque de cuotas publicado por el adaptador.
    rate_limits = platform.rate_limits
    # Devuelve una lista vacía cuando la plataforma no informa de cuotas.
    if rate_limits is None:
        # Evita confundir ausencia de datos con disponibilidad.
        return []
    # Inicializa la colección de porcentajes restantes.
    remaining: list[float] = []
    # Añade la ventana primaria cuando existe.
    if rate_limits.primary is not None:
        # Conserva el porcentaje validado por Pydantic.
        remaining.append(rate_limits.primary.remaining_percent)
    # Añade la ventana secundaria cuando existe.
    if rate_limits.secondary is not None:
        # Conserva el porcentaje validado por Pydantic.
        remaining.append(rate_limits.secondary.remaining_percent)
    # Devuelve únicamente las ventanas confirmadas.
    return remaining


# Determina si una plataforma está bloqueada por alguna cuota.
def _is_quota_exhausted(platform: PlatformSnapshot) -> bool:
    """Prioriza el error explícito y después comprueba todas las ventanas."""

    # Reconoce el motivo real publicado al agotarse Codex.
    if platform.status_reason == "usage_limit_exceeded":
        # Confirma que la plataforma estaba bloqueada por cuota.
        return True
    # Recupera las ventanas disponibles en la captura.
    remaining = _rate_windows(platform)
    # Considera agotada la plataforma cuando cualquier ventana llega a cero.
    return bool(remaining) and any(value <= 0 for value in remaining)


# Determina si todas las cuotas informadas vuelven a permitir trabajo.
def _is_quota_available(platform: PlatformSnapshot) -> bool:
    """Exige datos reales y evita avisar por una simple fecha prevista."""

    # Acepta el estado explícito generado tras una lectura en vivo satisfactoria.
    if platform.status_reason == "usage_limit_restored":
        # Confirma la restauración observada por el adaptador.
        return True
    # Recupera las ventanas actuales de la plataforma.
    remaining = _rate_windows(platform)
    # Requiere al menos una ventana y que ninguna continúe agotada.
    return bool(remaining) and all(value > 0 for value in remaining)


# Mantiene estado entre capturas para detectar transiciones reales.
class QuotaAlertTracker:
    """Genera una alerta cuando una plataforma pasa de agotada a disponible."""

    # Configura el tiempo durante el que el prototipo puede recuperar una alerta.
    def __init__(self, retention_seconds: float = 120.0) -> None:
        """Inicializa estados previos y una retención acotada."""

        # Guarda una retención positiva para evitar eventos permanentes.
        self._retention = timedelta(seconds=max(1.0, retention_seconds))
        # Conserva el último estado de agotamiento por plataforma.
        self._exhausted_by_platform: dict[str, bool] = {}
        # Conserva alertas recientes para lectores que no consultan cada segundo.
        self._alerts: list[AlertSnapshot] = []

    # Actualiza estados y devuelve las alertas todavía vigentes.
    def update(
        self,
        platforms: list[PlatformSnapshot],
        generated_at: datetime,
    ) -> list[AlertSnapshot]:
        """Detecta restauraciones observadas y conserva el evento dos minutos."""

        # Normaliza la fecha a UTC cuando llega sin zona por una prueba externa.
        now = generated_at if generated_at.tzinfo is not None else generated_at.replace(tzinfo=UTC)
        # Elimina eventos cuya ventana de entrega ya ha finalizado.
        self._alerts = [
            # Conserva cada evento todavía recuperable por el dispositivo.
            alert
            # Recorre la colección retenida de capturas anteriores.
            for alert in self._alerts
            # Compara la antigüedad con la retención configurada.
            if now - alert.created_at <= self._retention
        ]
        # Recorre todas las plataformas visibles de la captura.
        for platform in platforms:
            # Calcula el estado actual desde la causa y las ventanas reales.
            exhausted = _is_quota_exhausted(platform)
            # Recupera el estado observado en la captura anterior.
            previous_exhausted = self._exhausted_by_platform.get(platform.platform_id)
            # Genera un evento únicamente en la transición agotada a disponible.
            if previous_exhausted is True and not exhausted and _is_quota_available(platform):
                # Construye un identificador estable y único por instante observado.
                alert_id = (
                    f"{platform.platform_id}-quota-restored-"
                    f"{int(now.timestamp() * 1_000_000)}"
                )
                # Añade el evento que consumen Windows, el visor y el prototipo.
                self._alerts.append(
                    # Construye la alerta con contenido breve y no sensible.
                    AlertSnapshot(
                        # Publica el identificador deduplicable.
                        alert_id=alert_id,
                        # Define el tipo funcional esperado por el dispositivo.
                        alert_type="quota_restored",
                        # Identifica la plataforma que recuperó disponibilidad.
                        platform_id=platform.platform_id,
                        # Publica un título adecuado para una notificación local.
                        title=f"{platform.display_name} vuelve a estar disponible",
                        # Explica que la detección procede de una lectura real.
                        message="La cuota se ha restablecido y ya puede volver a utilizarse.",
                        # Marca la alerta como información operativa.
                        severity="info",
                        # Registra el instante observado por el servicio.
                        created_at=now,
                    )
                )
            # Guarda el estado actual para la siguiente iteración.
            self._exhausted_by_platform[platform.platform_id] = exhausted
        # Devuelve una copia para impedir mutaciones externas.
        return list(self._alerts)


# Codifica texto UTF-8 para insertarlo en un script PowerShell seguro.
def _text_to_base64(value: str) -> str:
    """Evita interpolar directamente títulos o mensajes en PowerShell."""

    # Convierte el texto a bytes UTF-8.
    encoded = value.encode("utf-8")
    # Devuelve una representación ASCII apta para el comando codificado.
    return base64.b64encode(encoded).decode("ascii")


# Construye el script encargado de mostrar un globo del área de notificación.
def _build_powershell_script(alert: AlertSnapshot) -> str:
    """Genera una notificación nativa sin módulos externos como BurntToast."""

    # Codifica el título para impedir problemas de comillas o caracteres especiales.
    title = _text_to_base64(alert.title)
    # Codifica el mensaje por el mismo motivo.
    message = _text_to_base64(alert.message)
    # Devuelve un script autocontenido compatible con Windows PowerShell 5.1.
    return (
        # Carga los ensamblados estándar necesarios para NotifyIcon.
        "Add-Type -AssemblyName System.Windows.Forms;"
        # Carga los iconos del sistema incluidos en Windows.
        "Add-Type -AssemblyName System.Drawing;"
        # Reconstruye el título desde Base64.
        f"$title=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{title}'));"
        # Reconstruye el mensaje desde Base64.
        f"$message=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{message}'));"
        # Crea el icono temporal del área de notificación.
        "$notification=New-Object System.Windows.Forms.NotifyIcon;"
        # Utiliza un icono informativo del propio sistema.
        "$notification.Icon=[System.Drawing.SystemIcons]::Information;"
        # Configura el tipo visual del globo.
        "$notification.BalloonTipIcon=[System.Windows.Forms.ToolTipIcon]::Info;"
        # Asigna el título ya decodificado.
        "$notification.BalloonTipTitle=$title;"
        # Asigna el mensaje ya decodificado.
        "$notification.BalloonTipText=$message;"
        # Hace visible el icono durante la notificación.
        "$notification.Visible=$true;"
        # Solicita una duración visible de diez segundos.
        "$notification.ShowBalloonTip(10000);"
        # Mantiene vivo el proceso para que Windows presente el globo.
        "Start-Sleep -Seconds 11;"
        # Libera el icono temporal al finalizar.
        "$notification.Dispose();"
    )


# Lanza una notificación de PowerShell en segundo plano.
def _default_launcher(arguments: list[str]) -> None:
    """Inicia el proceso oculto y devuelve el control inmediatamente."""

    # Recupera la bandera de ventana oculta únicamente cuando existe en la plataforma.
    creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    # Abre el proceso sin shell para evitar interpretaciones adicionales.
    subprocess.Popen(
        # Utiliza argumentos separados y previamente codificados.
        arguments,
        # Evita heredar una entrada que pueda mantener bloqueado el proceso.
        stdin=subprocess.DEVNULL,
        # Descarta cualquier salida del script de presentación.
        stdout=subprocess.DEVNULL,
        # Descarta diagnósticos no críticos del sistema de notificaciones.
        stderr=subprocess.DEVNULL,
        # Oculta la consola auxiliar en Windows.
        creationflags=creation_flags,
    )


# Entrega alertas nuevas al centro de notificaciones de Windows.
class WindowsNotificationSink:
    """Deduplica eventos y muestra globos nativos sin dependencias externas."""

    # Configura activación, plataforma y lanzador sustituible.
    def __init__(
        self,
        enabled: bool,
        platform_name: str | None = None,
        launcher: Callable[[list[str]], None] | None = None,
    ) -> None:
        """Mantiene el comportamiento desactivado fuera de Windows."""

        # Resuelve la plataforma efectiva o utiliza la del proceso actual.
        effective_platform = platform_name or os.name
        # Habilita la salida únicamente cuando se solicitó sobre Windows.
        self._enabled = enabled and effective_platform == "nt"
        # Conserva el lanzador real o el doble utilizado por las pruebas.
        self._launcher = launcher or _default_launcher
        # Registra identificadores ya entregados para evitar globos repetidos.
        self._seen_alert_ids: set[str] = set()

    # Publica únicamente alertas todavía no notificadas.
    def dispatch(self, alerts: list[AlertSnapshot]) -> None:
        """Muestra una notificación por transición real de cuota."""

        # Omite todo trabajo cuando la función está desactivada.
        if not self._enabled:
            # Evita lanzar procesos en Linux, macOS o ejecuciones sin avisos.
            return
        # Recorre las alertas retenidas en la captura.
        for alert in alerts:
            # Omite tipos que no corresponden a una restauración de cuota.
            if alert.alert_type != "quota_restored":
                # Continúa con el siguiente evento operativo.
                continue
            # Omite eventos ya entregados en iteraciones anteriores.
            if alert.alert_id in self._seen_alert_ids:
                # Evita repetir el mismo globo durante la retención.
                continue
            # Construye el script PowerShell con contenido codificado.
            script = _build_powershell_script(alert)
            # Codifica el script completo según el formato de -EncodedCommand.
            encoded_command = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
            # Ejecuta Windows PowerShell sin perfil ni interacción.
            self._launcher(
                # Entrega cada argumento como elemento independiente.
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-EncodedCommand",
                    encoded_command,
                ]
            )
            # Marca el evento después de entregarlo al lanzador.
            self._seen_alert_ids.add(alert.alert_id)
