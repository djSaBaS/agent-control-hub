"""Aplica cambios acotados para eliminar duplicados en la telemetría de Codex."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CODEX_PATH = _ROOT / "service/src/agent_control_hub/adapters/codex.py"
_VIEWER_PATH = _ROOT / "tools/pc-viewer/index.html"


def _replace_once(content: str, old: str, new: str, label: str) -> str:
    """Sustituye un bloque exacto y falla si el código esperado ha cambiado."""

    if content.count(old) != 1:
        raise RuntimeError(f"No se pudo localizar exactamente una vez: {label}")
    return content.replace(old, new, 1)


def _update_codex_adapter() -> None:
    """Evita diffs completos y resultados narrativos en el snapshot público."""

    content = _CODEX_PATH.read_text(encoding="utf-8")
    content = _replace_once(
        content,
        '''def _tool_summary(payload: dict[str, object]) -> str | None:\n    """Obtiene una descripción acotada de argumentos de una herramienta."""\n\n    raw_arguments = payload.get("arguments", payload.get("input"))\n''',
        '''def _tool_summary(payload: dict[str, object]) -> str | None:\n    """Obtiene una descripción acotada de argumentos de una herramienta."""\n\n    tool_name = _optional_text(payload.get("name"), 80)\n    if tool_name is not None and "patch" in tool_name.casefold():\n        return "Parche preparado"\n\n    raw_arguments = payload.get("arguments", payload.get("input"))\n''',
        "resumen seguro de apply_patch",
    )
    content = _replace_once(
        content,
        '''        if state.last_result is None and last_message is not None:\n            state.last_result = last_message\n''',
        '''        if state.last_result is None and is_meaningful_result(last_message):\n            state.last_result = last_message\n''',
        "resultado técnico de tarea completada",
    )
    _CODEX_PATH.write_text(content, encoding="utf-8")


def _update_viewer() -> None:
    """Oculta equivalencias y condensa la actividad histórica del visor."""

    content = _VIEWER_PATH.read_text(encoding="utf-8")
    content = _replace_once(
        content,
        '''    function renderActivity(items) {\n      if (!items?.length) return null;\n      const wrapper = document.createElement('div');\n      wrapper.className = 'activity';\n      const heading = document.createElement('h3');\n      heading.textContent = 'Actividad reciente';\n      const list = document.createElement('div');\n      list.className = 'activity-list';\n      items.slice(0, 8).forEach(item => {\n        const row = document.createElement('div');\n        row.className = 'activity-item';\n        const label = document.createElement('div');\n        label.className = 'activity-label';\n        label.textContent = item.label;\n        const summary = document.createElement('div');\n        summary.className = 'activity-summary';\n        summary.textContent = item.summary ?? statusLabels[item.status] ?? item.status;\n        const time = document.createElement('div');\n        time.className = 'activity-time';\n        time.textContent = formatDate(item.timestamp);\n        row.append(label, summary, time);\n        list.append(row);\n      });\n      wrapper.append(heading, list);\n      return wrapper;\n    }\n''',
        '''    function normalizeUiText(value) {\n      return typeof value === 'string'\n        ? value.replace(/\\s+/g, ' ').trim().toLocaleLowerCase('es-ES')\n        : '';\n    }\n\n    function equivalentText(left, right) {\n      const normalizedLeft = normalizeUiText(left);\n      const normalizedRight = normalizeUiText(right);\n      if (!normalizedLeft || !normalizedRight) return false;\n      if (normalizedLeft === normalizedRight) return true;\n      const shortest = Math.min(normalizedLeft.length, normalizedRight.length);\n      return shortest >= 30\n        && (normalizedLeft.startsWith(normalizedRight)\n          || normalizedRight.startsWith(normalizedLeft));\n    }\n\n    function visibleActivity(platform) {\n      const items = platform.recent_activity ?? [];\n      const seenItems = new Set();\n      const seenSummaries = new Set();\n      const hasApplyPatchResult = items.some(item =>\n        item.activity_type === 'tool_result' && /apply_patch/i.test(item.label)\n      );\n      return items.filter(item => {\n        if (platform.status_reason === 'usage_limit_exceeded'\n          && item.activity_type === 'limit') return false;\n        if (item.activity_type === 'task') return false;\n        if (item.activity_type === 'tool' && platform.status !== 'working') return false;\n        if (hasApplyPatchResult && item.activity_type === 'patch') return false;\n        if (equivalentText(item.summary, platform.task?.last_result)) return false;\n        if (equivalentText(item.summary, platform.task?.activity)) return false;\n        const summaryKey = normalizeUiText(item.summary);\n        const itemKey = `${normalizeUiText(item.label)}|${summaryKey}`;\n        if (seenItems.has(itemKey)) return false;\n        if (summaryKey && seenSummaries.has(summaryKey)) return false;\n        seenItems.add(itemKey);\n        if (summaryKey) seenSummaries.add(summaryKey);\n        return true;\n      });\n    }\n\n    function renderActivity(platform) {\n      const items = visibleActivity(platform);\n      if (!items.length) return null;\n      const wrapper = document.createElement('div');\n      wrapper.className = 'activity';\n      const heading = document.createElement('h3');\n      heading.textContent = 'Actividad reciente';\n      const list = document.createElement('div');\n      list.className = 'activity-list';\n      items.slice(0, 8).forEach(item => {\n        const row = document.createElement('div');\n        row.className = 'activity-item';\n        const label = document.createElement('div');\n        label.className = 'activity-label';\n        label.textContent = item.label;\n        const summary = document.createElement('div');\n        summary.className = 'activity-summary';\n        summary.textContent = item.summary ?? statusLabels[item.status] ?? item.status;\n        const time = document.createElement('div');\n        time.className = 'activity-time';\n        time.textContent = formatDate(item.timestamp);\n        row.append(label, summary, time);\n        list.append(row);\n      });\n      wrapper.append(heading, list);\n      return wrapper;\n    }\n''',
        "actividad reciente condensada",
    )
    content = _replace_once(
        content,
        '''    function latestResult(platform) {\n      if (platform.task?.last_result) {\n        return ['Resultado técnico', platform.task.last_result];\n      }\n      const result = platform.recent_activity?.find(item =>\n        ['completed', 'error'].includes(item.status) && item.activity_type !== 'limit'\n      );\n      if (!result) return ['No disponible', null];\n      return [result.label, result.summary ?? formatDate(result.timestamp)];\n    }\n''',
        '''    function latestResult(platform) {\n      if (platform.task?.last_result) {\n        return ['Resultado técnico', platform.task.last_result];\n      }\n      const result = platform.recent_activity?.find(item =>\n        item.activity_type === 'tool_result'\n        && ['completed', 'error'].includes(item.status)\n        && item.summary\n        && item.summary !== 'Código de salida 0'\n      );\n      if (!result) return null;\n      return [result.label, result.summary];\n    }\n''',
        "último resultado técnico",
    )
    content = _replace_once(
        content,
        '''      const message = document.createElement('p');\n      message.className = 'platform-message';\n      message.textContent = platform.status_message ?? 'Sin mensaje de estado adicional.';\n      headingGroup.append(title, message);\n''',
        '''      headingGroup.append(title);\n      if (platform.status_message\n        && platform.status_reason !== 'usage_limit_exceeded') {\n        const message = document.createElement('p');\n        message.className = 'platform-message';\n        message.textContent = platform.status_message;\n        headingGroup.append(message);\n      }\n''',
        "mensaje de estado no duplicado",
    )
    content = _replace_once(
        content,
        '''      const result = latestResult(platform);\n      const overview = document.createElement('div');\n      overview.className = 'overview';\n      overview.append(\n        section(\n          'Proyecto',\n          platform.project?.display_name,\n          platform.project?.cwd_alias ? `Ruta sanitizada: ${platform.project.cwd_alias}` : null\n        ),\n        section(\n          'Conversación',\n          platform.task?.conversation_name ?? platform.task?.display_name\n        ),\n        section(\n          'Objetivo',\n          platform.task?.objective ?? platform.task?.display_name\n        ),\n        section(\n          'Actividad actual',\n          platform.task?.activity ?? statusLabels[platform.status] ?? platform.status\n        ),\n        section(\n          'Último resultado',\n          result[0],\n          result[1]\n        ),\n        section(\n          'Pendiente',\n          platform.task?.pending\n        ),\n        section(\n          'Sesión',\n          platform.session?.originator ?? 'No disponible',\n          platform.session\n            ? `Inicio: ${formatDate(platform.session.started_at)} · Última actividad: ${formatDate(platform.session.last_activity_at)}`\n            : null\n        )\n      );\n      card.append(overview);\n''',
        '''      const result = latestResult(platform);\n      const overview = document.createElement('div');\n      overview.className = 'overview';\n      const overviewSections = [];\n      const project = platform.project;\n      const projectRoute = project?.cwd_alias\n        && !equivalentText(project.cwd_alias, project.display_name)\n        ? `Ruta sanitizada: ${project.cwd_alias}`\n        : null;\n      overviewSections.push(section('Proyecto', project?.display_name, projectRoute));\n\n      const task = platform.task;\n      const conversation = task?.conversation_name;\n      const objective = task?.objective;\n      if (conversation && !equivalentText(conversation, objective)) {\n        overviewSections.push(section('Conversación', conversation));\n      } else if (!conversation\n        && task?.display_name\n        && !equivalentText(task.display_name, objective)) {\n        overviewSections.push(section('Tarea', task.display_name));\n      }\n      if (objective) overviewSections.push(section('Objetivo', objective));\n\n      const currentActivity = task?.activity;\n      if (currentActivity\n        && platform.status_reason !== 'usage_limit_exceeded'\n        && !equivalentText(currentActivity, platform.status_message)) {\n        overviewSections.push(section('Actividad actual', currentActivity));\n      }\n      if (result) overviewSections.push(section('Último resultado', result[0], result[1]));\n      if (task?.pending) overviewSections.push(section('Pendiente', task.pending));\n      if (platform.session) {\n        overviewSections.push(section(\n          'Sesión',\n          platform.session.originator ?? 'No disponible',\n          `Inicio: ${formatDate(platform.session.started_at)} · Última actividad: ${formatDate(platform.session.last_activity_at)}`\n        ));\n      }\n      overview.append(...overviewSections);\n      card.append(overview);\n''',
        "resumen operativo condicional",
    )
    content = _replace_once(
        content,
        "      const activity = renderActivity(platform.recent_activity);\n",
        "      const activity = renderActivity(platform);\n",
        "renderizado de actividad normalizada",
    )
    _VIEWER_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    """Ejecuta la migración determinista sobre los dos archivos objetivo."""

    _update_codex_adapter()
    _update_viewer()


if __name__ == "__main__":
    main()
