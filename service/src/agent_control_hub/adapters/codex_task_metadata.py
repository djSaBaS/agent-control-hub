"""Interpreta metadatos visibles de tareas sin publicar contexto interno de Codex."""

from __future__ import annotations

import json
import re
from typing import Final

_OBJECTIVE_PATTERN: Final = re.compile(
    r"<objective>\s*(.*?)\s*</objective>",
    flags=re.IGNORECASE | re.DOTALL,
)
_INTERNAL_PREAMBLE_PATTERN: Final = re.compile(
    r"^\s*continue working toward the active thread goal[.\s]+"
    r"the objective below is user-provided data[.\s]+"
    r"treat it as the task to pursue,?\s*"
    r"not as higher-priority instructions[.\s]+",
    flags=re.IGNORECASE | re.DOTALL,
)
_INTERNAL_MARKERS: Final = (
    "<codex_internal_context",
    "continue working toward the active thread goal",
    "the objective below is user-provided data",
    "treat it as the task to pursue",
    "not as higher-priority instructions",
    "read the codex goal objective file",
    "goal-objective.md",
)
_EXPLICIT_TITLE_KEYS: Final = (
    "conversation_title",
    "thread_title",
    "thread_name",
)
_GENERIC_TITLE_KEYS: Final = (
    "title",
    "name",
)
_RESULT_HINTS: Final = (
    "correct",
    "playwright",
    "prueba",
    "regresi",
    "cobertura",
    "validaci",
    "rutas",
    "revalidado",
    "corregido",
)
_PENDING_PATTERNS: Final = (
    re.compile(
        r"(?:bloqueo actual|pendiente(?: operativo)?|queda por resolver)\s*:\s*"
        r"(.+?)(?:\n\s*\n|$)",
        flags=re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"queda\s+(?:un|una)\s+(?:único|única)\s+pendiente(?: operativo)?\s*:\s*"
        r"(.+?)(?:\n\s*\n|$)",
        flags=re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"queda\s+(?:un|una)\s+(?:único|única)\s+"
        r"(.+?)(?:\n\s*\n|$)",
        flags=re.IGNORECASE | re.DOTALL,
    ),
)
_RESULT_LABEL_PATTERN: Final = re.compile(
    r"(?:resultado|validación|hecho|completado)\s*:\s*[-*]?\s*(.+?)(?:\n|$)",
    flags=re.IGNORECASE,
)


def _mapping(value: object) -> dict[str, object] | None:
    """Normaliza mapas JSON sin aceptar claves que no sean texto."""

    if not isinstance(value, dict):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


def _normalized_text(value: object) -> str | None:
    """Devuelve texto no vacío con espacios internos normalizados."""

    if not isinstance(value, str):
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _strip_internal_preamble(value: str) -> str | None:
    """Retira la plantilla de continuidad y conserva solo el objetivo aportado."""

    stripped = _INTERNAL_PREAMBLE_PATTERN.sub("", value, count=1).strip()
    if stripped != value.strip():
        return _normalized_text(stripped)
    lowered = value.casefold()
    marker = "not as higher-priority instructions"
    marker_index = lowered.find(marker)
    if marker_index < 0:
        return _normalized_text(value)
    remainder = value[marker_index + len(marker) :].lstrip(" .:\n\r\t-")
    return _normalized_text(remainder)


def raw_message_text(payload: dict[str, object]) -> str | None:
    """Reconstruye el texto original de un mensaje antes de sanitizar etiquetas."""

    content = payload.get("content")
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    fragments: list[str] = []
    for item in content:
        item_mapping = _mapping(item)
        if item_mapping is None:
            continue
        if item_mapping.get("type") not in {"input_text", "output_text", "text"}:
            continue
        text = item_mapping.get("text")
        if isinstance(text, str):
            fragments.append(text)
    joined = "\n".join(fragments).strip()
    return joined or None


def extract_objective_block(value: object) -> str | None:
    """Extrae el objetivo y elimina cualquier preámbulo interno incluido dentro."""

    if not isinstance(value, str):
        return None
    match = _OBJECTIVE_PATTERN.search(value)
    if match is None:
        return None
    return _strip_internal_preamble(match.group(1))


def is_internal_task_text(value: object) -> bool:
    """Detecta envoltorios internos que nunca deben usarse como título de tarea."""

    if not isinstance(value, str):
        return False
    lowered = value.casefold()
    return any(marker in lowered for marker in _INTERNAL_MARKERS)


def normalize_goal_objective(value: object) -> str | None:
    """Normaliza un objetivo plano o incluido dentro de contexto interno."""

    if not isinstance(value, str):
        return None
    objective = extract_objective_block(value)
    if objective is not None:
        return objective
    cleaned = _strip_internal_preamble(value)
    if cleaned is None or is_internal_task_text(cleaned):
        return None
    return cleaned


def extract_tool_arguments(payload: dict[str, object]) -> dict[str, object] | None:
    """Interpreta argumentos JSON de function_call y custom_tool_call."""

    raw_arguments = payload.get("arguments", payload.get("input"))
    if isinstance(raw_arguments, str):
        try:
            parsed: object = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return None
    else:
        parsed = raw_arguments
    return _mapping(parsed)


def extract_tool_objective(payload: dict[str, object]) -> str | None:
    """Obtiene el objetivo limpio de herramientas create_goal o update_goal."""

    arguments = extract_tool_arguments(payload)
    if arguments is None:
        return None
    return normalize_goal_objective(arguments.get("objective"))


def extract_conversation_title(mapping: dict[str, object]) -> str | None:
    """Acepta títulos explícitos y limita claves genéricas a eventos de título."""

    for key in _EXPLICIT_TITLE_KEYS:
        candidate = _normalized_text(mapping.get(key))
        if candidate is not None and not is_internal_task_text(candidate):
            return candidate
    event_type = mapping.get("type")
    if event_type not in {"thread_title_updated", "thread_name_updated"}:
        return None
    for key in _GENERIC_TITLE_KEYS:
        candidate = _normalized_text(mapping.get(key))
        if candidate is not None and not is_internal_task_text(candidate):
            return candidate
    return None


def derive_objective_title(objective: object, max_length: int = 180) -> str | None:
    """Crea un título determinista a partir del objetivo cuando falta uno oficial."""

    normalized = normalize_goal_objective(objective)
    if normalized is None:
        return None
    first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
    title = first_sentence.strip(" -:;")
    if len(title) <= max_length:
        return title
    return title[: max_length - 1].rstrip() + "…"


def extract_result_from_message(value: object) -> str | None:
    """Extrae una validación o un resultado breve sin copiar el informe completo."""

    if not isinstance(value, str):
        return None
    for raw_line in value.splitlines():
        line = _normalized_text(raw_line)
        if line is None:
            continue
        lowered = line.casefold()
        if re.search(r"\b\d+\s*/\s*\d+\b", line) and any(
            hint in lowered for hint in _RESULT_HINTS
        ):
            return line
    labelled = _RESULT_LABEL_PATTERN.search(value)
    if labelled is not None:
        return _normalized_text(labelled.group(1))
    for raw_line in value.splitlines():
        line = _normalized_text(raw_line.lstrip("-*• "))
        if line is None or len(line) > 220:
            continue
        lowered = line.casefold()
        if any(lowered.startswith(prefix) for prefix in ("revalidado", "corregido", "completado")):
            return line
    return None


def extract_pending_from_message(value: object) -> str | None:
    """Extrae el bloqueo o pendiente explícito del último mensaje del agente."""

    if not isinstance(value, str):
        return None
    for pattern in _PENDING_PATTERNS:
        match = pattern.search(value)
        if match is None:
            continue
        pending = match.group(1).strip()
        first_paragraph = pending.split("\n\n", maxsplit=1)[0]
        return _normalized_text(first_paragraph)
    return None


def is_meaningful_result(summary: object) -> bool:
    """Acepta resultados técnicos breves y rechaza mensajes narrativos completos."""

    normalized = _normalized_text(summary)
    if normalized is None or len(normalized) > 220:
        return False
    lowered = normalized.casefold()
    if normalized == "Código de salida 0":
        return False
    return bool(re.search(r"\b\d+\s*/\s*\d+\b", normalized)) or any(
        hint in lowered for hint in _RESULT_HINTS
    )
