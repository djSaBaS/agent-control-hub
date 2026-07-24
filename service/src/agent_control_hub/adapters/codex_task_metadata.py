"""Interpreta metadatos visibles de tareas sin publicar contexto interno de Codex."""

from __future__ import annotations

import json
import re
from typing import Final

_OBJECTIVE_PATTERN: Final = re.compile(
    r"<objective>\s*(.*?)\s*</objective>",
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
_TITLE_KEYS: Final = (
    "conversation_title",
    "thread_title",
    "thread_name",
    "title",
    "name",
)
_RESULT_HINTS: Final = (
    "correct",
    "complet",
    "playwright",
    "prueba",
    "regresi",
    "cobertura",
    "validaci",
    "rutas",
)
_PENDING_LABEL_PATTERN: Final = re.compile(
    r"(?:bloqueo actual|pendiente(?: operativo)?|queda por resolver)\s*:\s*(.+?)(?:\n\s*\n|$)",
    flags=re.IGNORECASE | re.DOTALL,
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
    """Extrae exclusivamente el contenido encerrado en una etiqueta objective."""

    if not isinstance(value, str):
        return None
    match = _OBJECTIVE_PATTERN.search(value)
    if match is None:
        return None
    return _normalized_text(match.group(1))


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
    if is_internal_task_text(value):
        return None
    return _normalized_text(value)


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
    """Busca un título explícito sin inferirlo cuando la fuente no lo ofrece."""

    for key in _TITLE_KEYS:
        candidate = _normalized_text(mapping.get(key))
        if candidate is not None and not is_internal_task_text(candidate):
            return candidate
    return None


def derive_objective_title(objective: object, max_length: int = 180) -> str | None:
    """Crea un título determinista a partir del objetivo cuando falta uno oficial."""

    normalized = _normalized_text(objective)
    if normalized is None:
        return None
    first_sentence = re.split(r"(?<=[.!?])\s+", normalized, maxsplit=1)[0]
    title = first_sentence.strip(" -:;")
    if len(title) <= max_length:
        return title
    return title[: max_length - 1].rstrip() + "…"


def extract_result_from_message(value: object) -> str | None:
    """Extrae una línea de validación o resultado sin confundirla con el bloqueo."""

    if not isinstance(value, str):
        return None
    for raw_line in value.splitlines():
        line = _normalized_text(raw_line)
        if line is None:
            continue
        lowered = line.casefold()
        if re.search(r"\b\d+\s*/\s*\d+\b", line) and any(hint in lowered for hint in _RESULT_HINTS):
            return line
    return None


def extract_pending_from_message(value: object) -> str | None:
    """Extrae el bloqueo o pendiente explícito del último mensaje del agente."""

    if not isinstance(value, str):
        return None
    match = _PENDING_LABEL_PATTERN.search(value)
    if match is None:
        return None
    pending = match.group(1).strip()
    first_paragraph = pending.split("\n\n", maxsplit=1)[0]
    return _normalized_text(first_paragraph)


def is_meaningful_result(summary: object) -> bool:
    """Evita que resultados genéricos sustituyan una validación técnica útil."""

    normalized = _normalized_text(summary)
    if normalized is None:
        return False
    lowered = normalized.casefold()
    if normalized == "Código de salida 0":
        return False
    return bool(re.search(r"\b\d+\s*/\s*\d+\b", normalized)) or any(
        hint in lowered for hint in _RESULT_HINTS
    )
