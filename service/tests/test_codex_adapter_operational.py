"""Pruebas de telemetría operativa del adaptador real de Codex."""

import asyncio
import json
import shutil
from pathlib import Path

from agent_control_hub.adapters.codex import CodexAdapter
from agent_control_hub.models import AgentState

_FIXTURES = Path(__file__).parent / "fixtures" / "codex"


def _line(timestamp: str, record_type: str, payload: dict[str, object]) -> str:
    """Construye una línea JSONL mínima y determinista."""

    return json.dumps({"timestamp": timestamp, "type": record_type, "payload": payload})


def _token_count(timestamp: str, total: int, last_input: int = 800) -> str:
    """Construye consumo acumulado, última petición y cuota semanal."""

    return _line(
        timestamp,
        "event_msg",
        {
            "type": "token_count",
            "info": {
                "total_token_usage": {
                    "input_tokens": total - 100,
                    "cached_input_tokens": total - 200,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 100,
                    "reasoning_output_tokens": 10,
                    "total_tokens": total,
                },
                "last_token_usage": {
                    "input_tokens": last_input,
                    "cached_input_tokens": 700,
                    "cache_write_input_tokens": 0,
                    "output_tokens": 100,
                    "reasoning_output_tokens": 10,
                    "total_tokens": last_input + 100,
                },
                "model_context_window": 1_000,
            },
            "rate_limits": {
                "limit_id": "codex",
                "primary": {
                    "used_percent": 77.0,
                    "window_minutes": 10_080,
                    "resets_at": 1_785_322_523,
                },
                "secondary": None,
                "plan_type": "plus",
            },
        },
    )


def _copy_fixture(name: str, destination: Path) -> None:
    """Copia un JSONL pequeño para que cada prueba pueda modificarlo."""

    shutil.copyfile(_FIXTURES / name, destination)


def test_codex_adapter_extracts_session_project_task_and_usage(tmp_path: Path) -> None:
    """Expone telemetría útil y conserva token_usage para compatibilidad."""

    session = tmp_path / "rollout-operational.jsonl"
    _copy_fixture("operational.jsonl", session)

    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())

    assert snapshot.status == AgentState.WORKING
    assert snapshot.status_reason == "task_active"
    assert snapshot.session is not None
    assert snapshot.session.session_id == "session-123"
    assert snapshot.project is not None
    assert snapshot.project.display_name == "Agent Control Hub"
    assert snapshot.task is not None
    assert "[ruta]" in (snapshot.task.display_name or "")
    assert "[email]" in (snapshot.task.display_name or "")
    assert snapshot.usage is not None
    assert snapshot.usage.thread_total is snapshot.token_usage
    assert snapshot.usage.last_request is not None
    assert snapshot.usage.context_used_percent_estimated == 80.0
    assert snapshot.active_agents == 0
    serialized = snapshot.model_dump_json()
    assert r"C:\dev" not in serialized
    assert "sabas@example.com" not in serialized


def test_usage_limit_exceeded_produces_waiting_state(tmp_path: Path) -> None:
    """Evita representar como idle una tarea bloqueada por cuota."""

    session = tmp_path / "rollout-limit.jsonl"
    _copy_fixture("usage_limit.jsonl", session)

    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())

    assert snapshot.status == AgentState.WAITING
    assert snapshot.status_reason == "usage_limit_exceeded"
    assert snapshot.task is not None
    assert snapshot.task.status == AgentState.WAITING
    assert snapshot.recent_activity[0].activity_type == "limit"


def test_codex_adapter_reads_only_appended_bytes_and_resets_after_truncation(
    tmp_path: Path,
) -> None:
    """Mantiene cursores incrementales y reconstruye un archivo truncado."""

    session = tmp_path / "rollout-incremental.jsonl"
    session.write_text(
        _line(
            "2026-07-23T20:00:00Z",
            "session_meta",
            {
                "session_id": "first-session",
                "timestamp": "2026-07-23T20:00:00Z",
                "cwd": r"C:\dev\first-project",
            },
        )
        + "\n"
        + _token_count("2026-07-23T20:00:10Z", 1_000)
        + "\n",
        encoding="utf-8",
    )
    adapter = CodexAdapter(sessions_dir=tmp_path)

    first = asyncio.run(adapter.collect())
    first_offset = adapter._file_cache[session].offset
    with session.open("a", encoding="utf-8") as handle:
        handle.write(_token_count("2026-07-23T20:01:00Z", 2_000) + "\n")
    second = asyncio.run(adapter.collect())
    second_offset = adapter._file_cache[session].offset

    assert first.token_usage is not None
    assert first.token_usage.total_tokens == 1_000
    assert second.token_usage is not None
    assert second.token_usage.total_tokens == 2_000
    assert second_offset > first_offset

    session.write_text(
        _line(
            "2026-07-23T20:02:00Z",
            "session_meta",
            {
                "session_id": "replacement-session",
                "timestamp": "2026-07-23T20:02:00Z",
                "cwd": r"C:\dev\replacement",
            },
        )
        + "\n",
        encoding="utf-8",
    )
    third = asyncio.run(adapter.collect())

    assert third.session is not None
    assert third.session.session_id == "replacement-session"
    assert third.project is not None
    assert third.project.display_name == "replacement"
    assert third.token_usage is None


def test_platform_remains_compatible_without_new_optional_fields(tmp_path: Path) -> None:
    """Mantiene los campos anteriores aunque no existan eventos enriquecidos."""

    session = tmp_path / "rollout-legacy.jsonl"
    session.write_text(
        _token_count("2026-07-23T20:00:00Z", 4_000) + "\n",
        encoding="utf-8",
    )

    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())
    payload = snapshot.model_dump()

    assert payload["platform_id"] == "codex"
    assert payload["token_usage"] is not None
    assert payload["session"] is None
    assert payload["project"] is None
    assert payload["active_agents"] == 0
