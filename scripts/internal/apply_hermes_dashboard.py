"""Aplica cambios deterministas del visor para telemetría de Hermes."""

# Importa Path para modificar archivos conocidos del repositorio.
from pathlib import Path

# Resuelve la raíz del repositorio desde la ubicación del script.
_ROOT = Path(__file__).resolve().parents[2]
# Define el visor que debe modificarse.
_VIEWER = _ROOT / "tools" / "pc-viewer" / "index.html"
# Define el lanzador local que debe actualizar sus mensajes.
_PREVIEW = _ROOT / "scripts" / "run-codex-preview.ps1"


# Sustituye un fragmento exacto y falla si el código esperado ha cambiado.
def _replace_once(text: str, old: str, new: str, label: str) -> str:
    """Evita aplicar migraciones parciales o silenciosas."""

    # Cuenta las coincidencias para detectar divergencias.
    occurrences = text.count(old)
    # Exige una única coincidencia estable.
    if occurrences != 1:
        raise RuntimeError(f"{label}: se esperaban 1 coincidencia y hay {occurrences}")
    # Devuelve el texto actualizado.
    return text.replace(old, new, 1)


# Lee el visor con codificación explícita.
viewer = _VIEWER.read_text(encoding="utf-8")
# Añade formato monetario para costes de sesión.
viewer = _replace_once(
    viewer,
    """    const formatPercent = value => value == null
      ? 'No disponible'
      : `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 }).format(value)} %`;
    const formatDate = value => value
""",
    """    const formatPercent = value => value == null
      ? 'No disponible'
      : `${new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 }).format(value)} %`;
    const formatCurrency = value => value == null
      ? 'No disponible'
      : new Intl.NumberFormat('es-ES', {
        style: 'currency',
        currency: 'USD',
        maximumFractionDigits: 6
      }).format(value);
    const formatDate = value => value
""",
    "formato monetario",
)
# Evita repetir la última solicitud de Hermes en la actividad.
viewer = _replace_once(
    viewer,
    """        if (equivalentText(item.summary, platform.task?.last_result)) return false;
        if (equivalentText(item.summary, platform.task?.activity)) return false;
""",
    """        if (equivalentText(item.summary, platform.task?.last_result)) return false;
        if (equivalentText(item.summary, platform.task?.objective)) return false;
        if (equivalentText(item.summary, platform.task?.activity)) return false;
""",
    "deduplicación de solicitud",
)
# Inserta un panel genérico para datos operativos locales.
viewer = _replace_once(
    viewer,
    """    function renderDiagnostics(platform) {
""",
    """    function renderRuntime(platform) {
      const runtime = platform.runtime;
      if (!runtime) return null;
      const values = [
        runtime.gateway_status != null
          ? ['Gateway', runtime.gateway_status === 'running'
            ? 'En ejecución'
            : runtime.gateway_status === 'stopped' ? 'Detenido' : 'Desconocido']
          : null,
        runtime.session_count != null
          ? ['Sesiones registradas', formatNumber(runtime.session_count)]
          : null,
        runtime.message_count != null
          ? ['Mensajes de la sesión', formatNumber(runtime.message_count)]
          : null,
        runtime.tool_call_count != null
          ? ['Herramientas usadas', formatNumber(runtime.tool_call_count)]
          : null,
        runtime.api_call_count != null
          ? ['Llamadas API', formatNumber(runtime.api_call_count)]
          : null,
        runtime.cron_job_count != null
          ? ['Trabajos cron', formatNumber(runtime.cron_job_count)]
          : null,
        runtime.estimated_cost_usd != null
          ? ['Coste estimado de sesión', formatCurrency(runtime.estimated_cost_usd)]
          : null,
        runtime.actual_cost_usd != null
          ? ['Coste real de sesión', formatCurrency(runtime.actual_cost_usd)]
          : null,
        runtime.cost_status
          ? ['Estado del coste', runtime.cost_status]
          : null
      ].filter(Boolean);
      if (!values.length) return null;
      const wrapper = document.createElement('div');
      wrapper.className = 'limits';
      const heading = document.createElement('h3');
      heading.textContent = 'Estado de la plataforma';
      heading.style.marginTop = '0';
      const grid = document.createElement('div');
      grid.className = 'limits-grid';
      values.forEach(([label, value]) => grid.append(metric(label, value)));
      wrapper.append(heading, grid);
      return wrapper;
    }

    function renderDiagnostics(platform) {
""",
    "panel de runtime",
)
# Oculta el proyecto cuando la plataforma no ofrece cwd.
viewer = _replace_once(
    viewer,
    """      overviewSections.push(section('Proyecto', project?.display_name, projectRoute));

      const task = platform.task;
""",
    """      if (project?.display_name) {
        overviewSections.push(section('Proyecto', project.display_name, projectRoute));
      }

      const task = platform.task;
""",
    "proyecto opcional",
)
# Añade un bloque específico de modelo y proveedor.
viewer = _replace_once(
    viewer,
    """      if (task?.pending) overviewSections.push(section('Pendiente', task.pending));
      if (platform.session) {
""",
    """      if (task?.pending) overviewSections.push(section('Pendiente', task.pending));
      if (platform.session?.model_name) {
        overviewSections.push(section(
          'Modelo',
          platform.session.model_name,
          platform.session.model_provider
            ? `Proveedor: ${platform.session.model_provider}`
            : null
        ));
      }
      if (platform.session) {
""",
    "modelo visible",
)
# Inserta el panel operativo antes de cuotas y actividad.
viewer = _replace_once(
    viewer,
    """      const limits = renderLimits(platform);
      if (limits) card.append(limits);
""",
    """      const runtime = renderRuntime(platform);
      if (runtime) card.append(runtime);
      const limits = renderLimits(platform);
      if (limits) card.append(limits);
""",
    "render de runtime",
)
# Guarda el visor actualizado.
_VIEWER.write_text(viewer, encoding="utf-8")

# Lee el lanzador local.
preview = _PREVIEW.read_text(encoding="utf-8")
# Actualiza la descripción del archivo de configuración.
preview = _replace_once(
    preview,
    "No se encuentra la configuración de Codex en $ConfigPath",
    "No se encuentra la configuración de plataformas en $ConfigPath",
    "mensaje de configuración",
)
# Actualiza el mensaje de lectura principal.
preview = _replace_once(
    preview,
    "[4/4] Leyendo datos reales de Codex...",
    "[4/4] Leyendo datos reales de Codex y Hermes...",
    "mensaje de plataformas",
)
# Añade la fuente SQLite de Hermes al diagnóstico local.
preview = _replace_once(
    preview,
    "Write-Host \"Fuente: $HOME\\.codex\\sessions\" -ForegroundColor DarkGray",
    "Write-Host \"Codex:  $HOME\\.codex\\sessions\" -ForegroundColor DarkGray\nWrite-Host \"Hermes: $env:LOCALAPPDATA\\hermes\\state.db\" -ForegroundColor DarkGray",
    "fuentes locales",
)
# Guarda el lanzador actualizado.
_PREVIEW.write_text(preview, encoding="utf-8")
