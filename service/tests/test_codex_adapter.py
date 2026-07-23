"""Pruebas del adaptador de telemetría real de OpenAI Codex."""

import asyncio
import json
from pathlib import Path

from agent_control_hub.adapters.codex import CodexAdapter
from agent_control_hub.models import AgentState, PlatformSnapshot


def _record(
    timestamp: str,
    total_tokens: int,
    primary: dict[str, object] | None,
    secondary: dict[str, object] | None,
) -> str:
    """Crea un evento token_count con la estructura real observada en Codex."""

    return json.dumps(
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {
                        "input_tokens": total_tokens - 100,
                        "cached_input_tokens": total_tokens - 200,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 100,
                        "reasoning_output_tokens": 10,
                        "total_tokens": total_tokens,
                    },
                    "last_token_usage": {
                        "input_tokens": 100,
                        "cached_input_tokens": 80,
                        "cache_write_input_tokens": 0,
                        "output_tokens": 10,
                        "reasoning_output_tokens": 1,
                        "total_tokens": 110,
                    },
                    "model_context_window": 258400,
                },
                "rate_limits": {
                    "limit_id": "codex" if primary else "premium",
                    "primary": primary,
                    "secondary": secondary,
                    "credits": None,
                    "plan_type": "plus" if primary else None,
                },
            },
        }
    )


def _session_meta(timestamp: str, session_id: str, cwd: str) -> str:
    """Crea los metadatos mínimos de una sesión real."""

    return json.dumps(
        {
            "timestamp": timestamp,
            "type": "session_meta",
            "payload": {
                "session_id": session_id,
                "timestamp": timestamp,
                "cwd": cwd,
                "originator": "Codex Desktop",
                "source": "vscode",
                "cli_version": "0.142.3",
                "model_provider": "openai",
            },
        }
    )


def _event(timestamp: str, event_type: str) -> str:
    """Crea un evento de estado sencillo."""

    return json.dumps(
        {
            "timestamp": timestamp,
            "type": "event_msg",
            "payload": {"type": event_type},
        }
    )


def test_codex_adapter_uses_latest_usage_and_last_real_windows(tmp_path: Path) -> None:
    """Separa el último consumo de los últimos límites completos."""

    session = tmp_path / "2026" / "07" / "06" / "rollout-test.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
                _session_meta(
                    "2026-07-06T08:00:00Z",
                    "session-test",
                    r"C:\dev\Agent Control Hub",
                ),
                _record(
                    "2026-07-06T08:23:31Z",
                    17_805_907,
                    {
                        "used_percent": 74.0,
                        "window_minutes": 300,
                        "resets_at": 1_783_339_171,
                    },
                    {
                        "used_percent": 63.0,
                        "window_minutes": 10_080,
                        "resets_at": 1_783_409_063,
                    },
                ),
                _record("2026-07-20T11:29:12Z", 17_805_907, None, None),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())

    assert snapshot.status == AgentState.IDLE
    assert snapshot.tokens_today is None
    assert snapshot.token_usage is not None
    assert snapshot.token_usage.total_tokens == 17_805_907
    assert snapshot.token_usage.scope == "thread_total"
    assert snapshot.token_usage.source_reference == "2026/07/06/rollout-test.jsonl"
    assert snapshot.usage_breakdown is not None
    assert snapshot.usage_breakdown.last_request is not None
    assert snapshot.usage_breakdown.last_request.total_tokens == 110
    assert snapshot.rate_limits is not None
    assert snapshot.rate_limits.primary is not None
    assert snapshot.rate_limits.primary.used_percent == 74.0
    assert snapshot.rate_limits.secondary is not None
    assert snapshot.rate_limits.secondary.used_percent == 63.0
    assert snapshot.rolling_remaining_pct == 26
    assert snapshot.weekly_remaining_pct == 37
    assert snapshot.project is not None
    assert snapshot.project.display_name == "Agent Control Hub"
    assert str(tmp_path) not in snapshot.model_dump_json()


def test_codex_adapter_extracts_sanitized_telemetry_and_limit_state(tmp_path: Path) -> None:
    """Publica proyecto, tarea y actividad sin filtrar datos sensibles."""

    fixture = Path(__file__).parent / "fixtures" / "codex_session_telemetry.jsonl"
    session = tmp_path / "2026" / "07" / "23" / "rollout-telemetry.jsonl"
    session.parent.mkdir(parents=True)
    session.write_bytes(fixture.read_bytes())

    snapshot = asyncio.run(CodexAdapter(sessions_dir=tmp_path).collect())
    serialized = snapshot.model_dump_json()

    assert snapshot.status == AgentState.WAITING
    assert snapshot.status_reason == "usage_limit_exceeded"
    assert snapshot.active_agents == 0
    assert snapshot.agents == []
    assert snapshot.session is not None
    assert snapshot.session.session_id == "session-demo"
    assert snapshot.session.originator == "Codex Desktop"
    assert snapshot.project is not None
    assert snapshot.project.display_name == "Agent Control Hub"
    assert snapshot.task is not None
    assert snapshot.task.status == AgentState.WAITING
    assert snapshot.task.display_name is not None
    assert "[correo]" in snapshot.task.display_name
    assert snapshot.usage_breakdown is not None
    assert snapshot.usage_breakdown.thread_total is not None
    assert snapshot.usage_breakdown.thread_total.total_tokens == 1_010_000
    assert snapshot.usage_breakdown.last_request is not None
    assert snapshot.usage_breakdown.last_request.total_tokens == 129_600
    assert snapshot.usage_breakdown.context_used_pct_estimated == 50.0
    assert snapshot.recent_activity[0].activity_type == "limit"
    assert any(item.summary == "Correcto · 14/14" for item in snapshot.recent_activity)
    assert "user@example.com" not in serialized
    assert "sk-proj-12345678901234567890" not in serialized
    assert r"C:\dev\secreto" not in serialized


def test_codex_adapter_reads_only_appended_bytes_and_detects_truncation(
    tmp_path: Path,
) -> None:
    """Mantiene el offset incremental y reconstruye una sesión truncada."""

    session = tmp_path / "rollout-cache.jsonl"
    session.write_text(
        "\n".join(
            [
                _session_meta("2026-07-23T08:00:00Z", "first", r"C:\dev\First"),
                _record("2026-07-23T08:01:00Z", 1_000, None, None),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    adapter = CodexAdapter(sessions_dir=tmp_path)

    first = asyncio.run(adapter.collect())
    first_offset = adapter._file_cache[session].offset
    with session.open("a", encoding="utf-8") as handle:
        handle.write(_event("2026-07-23T08:05:00Z", "task_started") + "\n")
    second = asyncio.run(adapter.collect())
    second_offset = adapter._file_cache[session].offset

    assert first.token_usage is not None
    assert first.token_usage.total_tokens == 1_000
    assert first_offset < second_offset == session.stat().st_size
    assert second.status == AgentState.WORKING

    session.write_text(
        "\n".join(
            [
                _session_meta("2026-07-23T09:00:00Z", "second", r"C:\dev\Second"),
                _event("2026-07-23T09:01:00Z", "task_complete"),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    third = asyncio.run(adapter.collect())

    assert third.session is not None
    assert third.session.session_id == "second"
    assert third.project is not None
    assert third.project.display_name == "Second"
    assert third.status == AgentState.COMPLETED
    assert third.token_usage is None


def test_platform_snapshot_accepts_legacy_payload_without_new_fields() -> None:
    """Mantiene compatibles los mensajes del protocolo 1.0 anteriores."""

    snapshot = PlatformSnapshot.model_validate(
        {
            "platform_id": "codex",
            "display_name": "Codex",
            "status": "idle",
            "active_agents": 0,
            "agents": [],
        }
    )

    assert snapshot.session is None
    assert snapshot.project is None
    assert snapshot.task is None
    assert snapshot.usage_breakdown is None
    assert snapshot.recent_activity == []


def test_codex_adapter_is_offline_without_cli_or_sessions(tmp_path: Path) -> None:
    """No inventa métricas cuando Codex no está disponible."""

    snapshot = asyncio.run(
        CodexAdapter(
            sessions_dir=tmp_path,
            executable="agent-control-hub-codex-command-that-does-not-exist",
        ).collect()
    )

    assert snapshot.status == AgentState.OFFLINE
    assert snapshot.status_reason == "source_unavailable"
    assert snapshot.token_usage is None
    assert snapshot.usage_breakdown is None
    assert snapshot.rate_limits is None
