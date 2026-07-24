"""Pruebas del adaptador de consumo real de OpenAI Codex."""

import asyncio
import json
from pathlib import Path

from agent_control_hub.adapters.codex import CodexAdapter
from agent_control_hub.models import AgentState


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
                    "last_token_usage": {"total_tokens": 100},
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


def test_codex_adapter_uses_latest_usage_and_last_real_windows(tmp_path: Path) -> None:
    """Separa el último consumo de los últimos límites completos."""

    session = tmp_path / "2026" / "07" / "06" / "rollout-test.jsonl"
    session.parent.mkdir(parents=True)
    session.write_text(
        "\n".join(
            [
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
    assert snapshot.token_usage.scope == "session_total"
    assert snapshot.token_usage.source_reference == "2026/07/06/rollout-test.jsonl"
    assert snapshot.rate_limits is not None
    assert snapshot.rate_limits.primary is not None
    assert snapshot.rate_limits.primary.used_percent == 74.0
    assert snapshot.rate_limits.secondary is not None
    assert snapshot.rate_limits.secondary.used_percent == 63.0
    assert snapshot.rolling_remaining_pct == 26
    assert snapshot.weekly_remaining_pct == 37
    assert str(tmp_path) not in snapshot.model_dump_json()


def test_codex_adapter_refreshes_cache_when_session_grows(tmp_path: Path) -> None:
    """Relee únicamente un archivo que cambia y conserva los datos nuevos."""

    session = tmp_path / "rollout-cache.jsonl"
    session.write_text(
        _record("2026-07-23T08:00:00Z", 1_000, None, None) + "\n",
        encoding="utf-8",
    )
    adapter = CodexAdapter(sessions_dir=tmp_path)

    first = asyncio.run(adapter.collect())
    with session.open("a", encoding="utf-8") as handle:
        handle.write(_record("2026-07-23T08:05:00Z", 2_000, None, None) + "\n")
    second = asyncio.run(adapter.collect())

    assert first.token_usage is not None
    assert first.token_usage.total_tokens == 1_000
    assert second.token_usage is not None
    assert second.token_usage.total_tokens == 2_000


def test_codex_adapter_is_offline_without_cli_or_sessions(tmp_path: Path) -> None:
    """No inventa métricas cuando Codex no está disponible."""

    snapshot = asyncio.run(
        CodexAdapter(
            sessions_dir=tmp_path,
            executable="agent-control-hub-codex-command-that-does-not-exist",
        ).collect()
    )

    assert snapshot.status == AgentState.OFFLINE
    assert snapshot.token_usage is None
    assert snapshot.rate_limits is None
