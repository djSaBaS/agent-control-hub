"""Aplica la evolución compatible de conversación, objetivo, resultado y pendiente."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def _replace_once(path: Path, old: str, new: str) -> None:
    """Sustituye un bloque exacto y falla si el repositorio no coincide."""

    content = path.read_text(encoding="utf-8")
    occurrences = content.count(old)
    if occurrences != 1:
        raise RuntimeError(f"Se esperaba una coincidencia en {path}, encontradas: {occurrences}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def _update_models() -> None:
    """Añade campos opcionales sin retirar propiedades del protocolo 1.0."""

    path = _ROOT / "service" / "src" / "agent_control_hub" / "models.py"
    _replace_once(
        path,
        """    display_name: str | None = Field(default=None, max_length=180)\n    status: AgentState\n    activity: str | None = Field(default=None, max_length=180)\n    started_at: datetime | None = None\n    last_activity_at: datetime | None = None\n""",
        """    display_name: str | None = Field(default=None, max_length=180)\n    conversation_name: str | None = Field(default=None, max_length=120)\n    objective: str | None = Field(default=None, max_length=500)\n    status: AgentState\n    activity: str | None = Field(default=None, max_length=180)\n    last_result: str | None = Field(default=None, max_length=220)\n    pending: str | None = Field(default=None, max_length=220)\n    started_at: datetime | None = None\n    last_activity_at: datetime | None = None\n""",
    )


def _update_adapter() -> None:
    """Integra el parser especializado en el acumulador incremental existente."""

    path = _ROOT / "service" / "src" / "agent_control_hub" / "adapters" / "codex.py"
    _replace_once(
        path,
        """from agent_control_hub.adapters.base import PlatformAdapter\nfrom agent_control_hub.models import (\n""",
        """from agent_control_hub.adapters.base import PlatformAdapter\nfrom agent_control_hub.adapters.codex_task_metadata import (\n    derive_objective_title,\n    extract_conversation_title,\n    extract_objective_block,\n    extract_pending_from_message,\n    extract_result_from_message,\n    extract_tool_arguments,\n    extract_tool_objective,\n    is_internal_task_text,\n    is_meaningful_result,\n    normalize_goal_objective,\n    raw_message_text,\n)\nfrom agent_control_hub.models import (\n""",
    )
    _replace_once(
        path,
        """    latest_user_message: str | None = None\n    latest_goal: str | None = None\n    latest_agent_message: str | None = None\n""",
        """    latest_user_message: str | None = None\n    latest_goal: str | None = None\n    conversation_name: str | None = None\n    objective: str | None = None\n    latest_agent_message: str | None = None\n    last_result: str | None = None\n    pending: str | None = None\n""",
    )
    _replace_once(
        path,
        """    sanitized = re.sub(r\"<[^>]+>\", \" \", value)\n    sanitized = re.sub(r\"https?://\\S+\", \"[url]\", sanitized, flags=re.IGNORECASE)\n""",
        """    sanitized = re.sub(r\"<[^>]+>\", \" \", value)\n    sanitized = re.sub(r\"https?://\\S+\", \"[url]\", sanitized, flags=re.IGNORECASE)\n    sanitized = re.sub(\n        r\"(?i)\\b[A-Z]:\\\\[^\\r\\n<>|?*]+?\\.(?:php|txt|md|jsonl?|log|csv|xlsx?|docx?|pdf|py|js|ts|c|cpp|h)\\b\",\n        \"[ruta]\",\n        sanitized,\n    )\n""",
    )
    _replace_once(
        path,
        """    lowered = value.casefold()\n    return any(marker in lowered for marker in _TECHNICAL_OBJECTIVE_MARKERS)\n""",
        """    lowered = value.casefold()\n    return is_internal_task_text(value) or any(\n        marker in lowered for marker in _TECHNICAL_OBJECTIVE_MARKERS\n    )\n""",
    )
    _replace_once(
        path,
        """    state.cli_version = _optional_text(payload.get(\"cli_version\"), 40)\n    state.model_provider = _optional_text(payload.get(\"model_provider\"), 80)\n    if project is not None:\n""",
        """    state.cli_version = _optional_text(payload.get(\"cli_version\"), 40)\n    state.model_provider = _optional_text(payload.get(\"model_provider\"), 80)\n    conversation_name = _sanitize_text(extract_conversation_title(payload), 120)\n    if conversation_name is not None:\n        state.conversation_name = conversation_name\n    if project is not None:\n""",
    )
    _replace_once(
        path,
        """    error = _as_object_dict(payload.get(\"error\"))\n    last_message = _sanitize_text(payload.get(\"last_agent_message\"), 180)\n    if last_message is not None:\n        state.latest_agent_message = last_message\n""",
        """    error = _as_object_dict(payload.get(\"error\"))\n    raw_last_message = payload.get(\"last_agent_message\")\n    last_message = _sanitize_text(raw_last_message, 180)\n    objective = _sanitize_text(extract_objective_block(raw_last_message), 500)\n    result = _sanitize_text(extract_result_from_message(raw_last_message), 220)\n    pending = _sanitize_text(extract_pending_from_message(raw_last_message), 220)\n    if last_message is not None and not is_internal_task_text(raw_last_message):\n        state.latest_agent_message = last_message\n    if objective is not None:\n        state.objective = objective\n        state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)\n    if result is not None:\n        state.last_result = result\n    if pending is not None:\n        state.pending = pending\n""",
    )
    _replace_once(
        path,
        """    if error is None:\n        state.task_completed = True\n        state.error_message = None\n""",
        """    if error is None:\n        state.task_completed = True\n        state.error_message = None\n        if state.last_result is None and last_message is not None:\n            state.last_result = last_message\n""",
    )
    _replace_once(
        path,
        """    if event_type == \"thread_goal_updated\":\n        goal = _as_object_dict(payload.get(\"goal\"))\n        objective = _sanitize_text(goal.get(\"objective\"), 180) if goal is not None else None\n        if objective is not None and not _is_technical_objective(objective):\n            state.latest_goal = objective\n        return\n    if event_type == \"agent_message\":\n        message = _sanitize_text(payload.get(\"message\"), 180)\n        if message is not None:\n            state.latest_agent_message = message\n            _add_activity(\n                state,\n                \"message\",\n                \"Actualización de Codex\",\n                AgentState.WORKING,\n                timestamp,\n                message,\n            )\n        return\n""",
        """    if event_type == \"thread_goal_updated\":\n        goal = _as_object_dict(payload.get(\"goal\"))\n        raw_objective = goal.get(\"objective\") if goal is not None else None\n        objective = _sanitize_text(normalize_goal_objective(raw_objective), 500)\n        if objective is not None and not _is_technical_objective(objective):\n            state.objective = objective\n            state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)\n        return\n    if event_type in {\"thread_title_updated\", \"thread_name_updated\"}:\n        conversation_name = _sanitize_text(extract_conversation_title(payload), 120)\n        if conversation_name is not None:\n            state.conversation_name = conversation_name\n        return\n    if event_type == \"agent_message\":\n        raw_message = payload.get(\"message\")\n        message = _sanitize_text(raw_message, 180)\n        objective = _sanitize_text(extract_objective_block(raw_message), 500)\n        result = _sanitize_text(extract_result_from_message(raw_message), 220)\n        pending = _sanitize_text(extract_pending_from_message(raw_message), 220)\n        if objective is not None:\n            state.objective = objective\n            state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)\n        if result is not None:\n            state.last_result = result\n        if pending is not None:\n            state.pending = pending\n        if message is not None and not is_internal_task_text(raw_message):\n            state.latest_agent_message = message\n            _add_activity(\n                state,\n                \"message\",\n                \"Actualización de Codex\",\n                AgentState.WORKING,\n                timestamp,\n                message,\n            )\n        return\n""",
    )
    _replace_once(
        path,
        """    name = _optional_text(payload.get(\"name\"), 80) or \"herramienta\"\n    call_id = _optional_text(payload.get(\"call_id\", payload.get(\"id\")), 160)\n""",
        """    name = _optional_text(payload.get(\"name\"), 80) or \"herramienta\"\n    arguments = extract_tool_arguments(payload)\n    if arguments is not None:\n        conversation_name = _sanitize_text(extract_conversation_title(arguments), 120)\n        if conversation_name is not None:\n            state.conversation_name = conversation_name\n    if name.casefold() in {\"create_goal\", \"update_goal\"}:\n        objective = _sanitize_text(extract_tool_objective(payload), 500)\n        if objective is not None:\n            state.objective = objective\n            state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)\n    call_id = _optional_text(payload.get(\"call_id\", payload.get(\"id\")), 160)\n""",
    )
    _replace_once(
        path,
        """    summary = _output_summary(output)\n    if failed:\n        state.error_message = summary or \"Una herramienta devolvió un error.\"\n""",
        """    summary = _output_summary(output)\n    if not failed and is_meaningful_result(summary):\n        state.last_result = summary\n    if failed:\n        state.error_message = summary or \"Una herramienta devolvió un error.\"\n""",
    )
    _replace_once(
        path,
        """        role = payload.get(\"role\")\n        if role == \"user\":\n            message = _extract_message_text(payload)\n            if message is not None:\n                state.latest_user_message = message\n        return\n""",
        """        role = payload.get(\"role\")\n        if role == \"user\":\n            raw_message = raw_message_text(payload)\n            objective = _sanitize_text(extract_objective_block(raw_message), 500)\n            if objective is not None:\n                state.objective = objective\n                state.latest_goal = _sanitize_text(derive_objective_title(objective), 180)\n            if raw_message is not None and not is_internal_task_text(raw_message):\n                message = _sanitize_text(raw_message, 180)\n                if message is not None:\n                    state.latest_user_message = message\n        return\n""",
    )
    _replace_once(
        path,
        """    coverage = re.search(\n        r'\"playwrightExactCovered\"\\s*:\\s*(\\d+).*?\"discoveredTotal\"\\s*:\\s*(\\d+)',\n        output,\n        flags=re.DOTALL,\n    )\n    if coverage is not None:\n        covered, total = coverage.groups()\n        return f\"Cobertura Playwright: {covered}/{total}\"\n""",
        """    coverage = re.search(\n        r'\"playwrightExactCovered\"\\s*:\\s*(\\d+).*?\"discoveredTotal\"\\s*:\\s*(\\d+)',\n        output,\n        flags=re.DOTALL,\n    )\n    if coverage is not None:\n        covered, total = coverage.groups()\n        return f\"Cobertura Playwright: {covered}/{total}\"\n    reverse_coverage = re.search(\n        r'\"discoveredTotal\"\\s*:\\s*(\\d+).*?\"playwrightExactCovered\"\\s*:\\s*(\\d+)',\n        output,\n        flags=re.DOTALL,\n    )\n    if reverse_coverage is not None:\n        total, covered = reverse_coverage.groups()\n        return f\"Cobertura Playwright: {covered}/{total}\"\n""",
    )
    _replace_once(
        path,
        """    return state.latest_user_message or state.latest_goal or state.latest_agent_message\n""",
        """    if state.conversation_name is not None:\n        return state.conversation_name\n    if state.objective is not None:\n        return _sanitize_text(derive_objective_title(state.objective), 180)\n    return state.latest_user_message or state.latest_goal or state.latest_agent_message\n""",
    )
    _replace_once(
        path,
        """    return TaskInfo(\n        display_name=display_name,\n        status=status,\n        activity=activity,\n        started_at=state.task_started_at,\n        last_activity_at=state.task_last_activity_at,\n    )\n""",
        """    return TaskInfo(\n        display_name=display_name,\n        conversation_name=state.conversation_name,\n        objective=state.objective,\n        status=status,\n        activity=activity,\n        last_result=state.last_result,\n        pending=state.pending,\n        started_at=state.task_started_at,\n        last_activity_at=state.task_last_activity_at,\n    )\n""",
    )


def _update_viewer() -> None:
    """Separa visualmente conversación, objetivo, actividad, resultado y pendiente."""

    path = _ROOT / "tools" / "pc-viewer" / "index.html"
    _replace_once(
        path,
        """    function latestResult(platform) {\n      const result = platform.recent_activity?.find(item =>\n        ['completed', 'error', 'waiting'].includes(item.status)\n      );\n      if (!result) return ['No disponible', null];\n      return [result.label, result.summary ?? formatDate(result.timestamp)];\n    }\n""",
        """    function latestResult(platform) {\n      if (platform.task?.last_result) {\n        return ['Resultado técnico', platform.task.last_result];\n      }\n      const result = platform.recent_activity?.find(item =>\n        ['completed', 'error'].includes(item.status) && item.activity_type !== 'limit'\n      );\n      if (!result) return ['No disponible', null];\n      return [result.label, result.summary ?? formatDate(result.timestamp)];\n    }\n""",
    )
    _replace_once(
        path,
        """        section(\n          'Tarea',\n          platform.task?.display_name,\n          platform.task?.activity ?? null\n        ),\n        section(\n          'Último resultado',\n          result[0],\n          result[1]\n        ),\n        section(\n          'Sesión',\n""",
        """        section(\n          'Conversación',\n          platform.task?.conversation_name ?? platform.task?.display_name\n        ),\n        section(\n          'Objetivo',\n          platform.task?.objective ?? platform.task?.display_name\n        ),\n        section(\n          'Actividad actual',\n          platform.task?.activity ?? statusLabels[platform.status] ?? platform.status\n        ),\n        section(\n          'Último resultado',\n          result[0],\n          result[1]\n        ),\n        section(\n          'Pendiente',\n          platform.task?.pending\n        ),\n        section(\n          'Sesión',\n""",
    )
    _replace_once(
        path,
        """        if (stale.length) {\n          const ages = stale\n            .map(item => ageMinutes(item.rate_limits.updated_at))\n            .filter(value => value != null);\n          warning.textContent = `Las cuotas son reales, pero su última actualización tiene ${Math.max(...ages)} minutos. Una nueva actividad de Codex debería refrescarlas.`;\n          warning.className = 'notice visible';\n""",
        """        if (stale.length) {\n          const ages = stale\n            .map(item => ageMinutes(item.rate_limits.updated_at))\n            .filter(value => value != null);\n          const blocked = stale.find(item => item.status_reason === 'usage_limit_exceeded');\n          warning.textContent = blocked\n            ? `Cuota agotada. Último dato recibido hace ${Math.max(...ages)} minutos. Reinicio previsto: ${formatDate(blocked.next_reset_at)}.`\n            : `Las cuotas son reales, pero su última actualización tiene ${Math.max(...ages)} minutos.`;\n          warning.className = 'notice visible';\n""",
    )


def main() -> None:
    """Ejecuta todas las migraciones deterministas de esta fase."""

    _update_models()
    _update_adapter()
    _update_viewer()


if __name__ == "__main__":
    main()
