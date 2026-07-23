"""Utilidades de validación y sanitización para eventos locales de Codex."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_WINDOWS_PATH_PATTERN = re.compile(r"(?<!\w)[A-Za-z]:\\(?:[^\s\"']+\\)*[^\s\"']*")
_UNIX_PATH_PATTERN = re.compile(r"(?<![\w:])/(?:[^\s/]+/)+[^\s\"']*")
_SECRET_PATTERN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{12,}|gh[oprsu]_[A-Za-z0-9]{12,}|Bearer\s+\S+)",
    re.IGNORECASE,
)
_EXIT_CODE_PATTERN = re.compile(r"Exit code:\s*(-?\d+)", re.IGNORECASE)
_WALL_TIME_PATTERN = re.compile(r"Wall time:\s*([0-9.]+)\s*(?:seconds?|s)", re.IGNORECASE)
_RATIO_KEYS = (("ok", "total"), ("playwrightExactCovered", "discoveredTotal"))


def as_object_dict(value: object) -> dict[str, object] | None:
    """Convierte diccionarios JSON en mapas con claves de texto."""

    if not isinstance(value, dict):
        return None
    return {key: item for key, item in value.items() if isinstance(key, str)}


def parse_timestamp(value: object) -> datetime | None:
    """Interpreta fechas ISO 8601 o marcas de tiempo Unix de Codex."""

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
        if seconds > 10_000_000_000:
            seconds /= 1000
        try:
            return datetime.fromtimestamp(seconds, UTC)
        except (OSError, OverflowError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def integer(mapping: dict[str, object], key: str, default: int = 0) -> int:
    """Obtiene un entero no negativo sin aceptar booleanos."""

    value = mapping.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return default


def number(mapping: dict[str, object], key: str) -> float | None:
    """Obtiene un número decimal sin aceptar booleanos."""

    value = mapping.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def string_value(mapping: dict[str, object], key: str, limit: int) -> str | None:
    """Obtiene texto limitado de un mapa JSON."""

    value = mapping.get(key)
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    return cleaned[:limit]


def source_reference(path: Path, sessions_dir: Path) -> str:
    """Genera una referencia relativa que no expone el perfil local."""

    try:
        return path.relative_to(sessions_dir).as_posix()
    except ValueError:
        return path.name


def sanitize_text(value: str, limit: int = 240) -> str:
    """Elimina credenciales, correos y rutas absolutas antes de publicar texto."""

    cleaned = value.replace("\x00", " ")
    cleaned = _SECRET_PATTERN.sub("[secreto]", cleaned)
    cleaned = _EMAIL_PATTERN.sub("[correo]", cleaned)
    cleaned = _WINDOWS_PATH_PATTERN.sub("[ruta]", cleaned)
    cleaned = _UNIX_PATH_PATTERN.sub("[ruta]", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit].rstrip()


def project_alias(cwd: str) -> str | None:
    """Obtiene únicamente el nombre público de una carpeta de proyecto."""

    candidate = PureWindowsPath(cwd).name if "\\" in cwd else PurePosixPath(cwd).name
    cleaned = sanitize_text(candidate, 160)
    return cleaned or None


def task_candidate(value: str) -> str | None:
    """Reduce un mensaje a un título de tarea útil y descarta contexto técnico."""

    stripped = value.strip()
    lowered = stripped.lower()
    if not stripped or stripped.startswith("<"):
        return None
    if "goal objective file" in lowered or "permissions instructions" in lowered:
        return None
    sanitized = sanitize_text(stripped, 160)
    if not sanitized or (sanitized.startswith("[") and sanitized.endswith("]")):
        return None
    sentence = re.split(r"(?<=[.!?])\s+", sanitized, maxsplit=1)[0]
    return sentence[:160].rstrip()


def extract_message_text(payload: dict[str, object]) -> str | None:
    """Extrae texto de mensajes estructurados sin conservar el objeto completo."""

    direct = payload.get("message") or payload.get("text")
    if isinstance(direct, str):
        return direct
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        content_item = as_object_dict(item)
        if content_item is None:
            continue
        text = content_item.get("text")
        if isinstance(text, str):
            parts.append(text)
    return " ".join(parts) if parts else None


def classify_tool(name: str, arguments: object) -> tuple[str, str]:
    """Clasifica una herramienta sin publicar sus argumentos originales."""

    searchable = name.lower()
    if isinstance(arguments, str):
        searchable += " " + arguments.lower()[:4000]
    if "patch" in searchable or "apply_patch" in searchable:
        return "patch", "Aplicando cambios"
    if "playwright" in searchable or "browser" in searchable:
        return "test", "Validando interfaz"
    if any(token in searchable for token in ("pytest", " test", "tests\\", "tests/")):
        return "test", "Ejecutando pruebas"
    if any(token in searchable for token in ("ruff", "mypy", "pyright", "lint")):
        return "quality", "Validando calidad"
    if "git" in searchable:
        return "git", "Consultando Git"
    if any(token in searchable for token in ("read", "fetch", "search", "find")):
        return "analysis", "Analizando archivos"
    if any(token in searchable for token in ("shell", "exec", "command")):
        return "command", "Ejecutando comando"
    return "tool", "Ejecutando herramienta"


def call_identifier(payload: dict[str, object]) -> str | None:
    """Obtiene el identificador estable que enlaza llamada y resultado."""

    for key in ("call_id", "id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value[:160]
    return None


def output_result(output: str) -> tuple[bool, str, float | None]:
    """Resume un resultado de herramienta sin publicar su salida completa."""

    exit_match = _EXIT_CODE_PATTERN.search(output)
    exit_code = int(exit_match.group(1)) if exit_match else 0
    duration_match = _WALL_TIME_PATTERN.search(output)
    duration = float(duration_match.group(1)) if duration_match else None
    succeeded = exit_code == 0
    summary = "Correcto" if succeeded else f"Error de ejecución ({exit_code})"
    for completed_key, total_key in _RATIO_KEYS:
        completed_match = re.search(rf'"{completed_key}"\s*:\s*(\d+)', output)
        total_match = re.search(rf'"{total_key}"\s*:\s*(\d+)', output)
        if completed_match and total_match:
            completed = int(completed_match.group(1))
            total = int(total_match.group(1))
            summary = f"{summary} · {completed}/{total}"
            break
    return succeeded, summary, duration
