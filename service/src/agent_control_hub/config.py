"""Configuración validada del servicio y de sus plataformas."""

# Importa rutas de sistema para cargar archivos locales.
from pathlib import Path

# Importa modelos y constructores de campos de Pydantic.
from pydantic import BaseModel, ConfigDict, Field


# Define las preferencias configurables de una plataforma.
class PlatformSettings(BaseModel):
    """Controla carga, monitorización, visibilidad, alertas y acciones."""

    # Impide aceptar claves desconocidas por error de configuración.
    model_config = ConfigDict(extra="forbid")

    # Controla si el conector puede cargarse.
    enabled: bool = False
    # Controla si el conector debe consultar estados y consumo.
    monitoring_enabled: bool = True
    # Controla si la plataforma debe aparecer en el dispositivo.
    visible_on_device: bool = True
    # Controla si la plataforma puede generar alertas.
    alerts_enabled: bool = True
    # Controla si se pueden lanzar acciones desde el dispositivo.
    actions_enabled: bool = False


# Construye la configuración segura utilizada cuando no existe archivo.
def _default_platforms() -> dict[str, PlatformSettings]:
    """Devuelve únicamente el adaptador simulado habilitado."""

    # Mantiene el modo demostración disponible sin credenciales.
    return {
        # Configura la fuente simulada para el primer arranque.
        "mock": PlatformSettings(
            # Activa el adaptador simulado.
            enabled=True,
            # Permite recoger sus instantáneas deterministas.
            monitoring_enabled=True,
            # Permite mostrarlo en el dispositivo.
            visible_on_device=True,
            # Permite probar alertas visuales.
            alerts_enabled=True,
            # Evita lanzar acciones desde datos simulados.
            actions_enabled=False,
        ),
    }


# Define la configuración raíz del servicio local.
class ServiceSettings(BaseModel):
    """Agrupa preferencias generales y plataformas configuradas."""

    # Impide aceptar secciones desconocidas por accidente.
    model_config = ConfigDict(extra="forbid")

    # Guarda el intervalo general entre actualizaciones.
    update_interval_seconds: float = Field(default=5.0, gt=0, le=3600)
    # Guarda la configuración indexada por identificador de plataforma.
    platforms: dict[str, PlatformSettings] = Field(default_factory=_default_platforms)


# Carga y valida la configuración desde un archivo JSON opcional.
def load_settings(path: Path | None) -> ServiceSettings:
    """Devuelve valores seguros o valida el archivo indicado."""

    # Utiliza la configuración predeterminada cuando no existe ruta.
    if path is None:
        # Devuelve un modelo nuevo para evitar estado compartido.
        return ServiceSettings()
    # Lee el archivo usando codificación explícita y estable.
    raw_content = path.read_text(encoding="utf-8")
    # Valida sintaxis, tipos y claves mediante Pydantic.
    return ServiceSettings.model_validate_json(raw_content)
