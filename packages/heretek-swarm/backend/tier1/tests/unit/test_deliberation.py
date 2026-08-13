"""Tests for Tribunal.run() and Tribunal.stream()."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.config import Settings
from tier1.deliberation.graph import Tribunal
from tier1.deliberation.state import (
    DeliberationEvent,
    initial_state,
)


def _settings() -> Settings:
    return Settings(
        minimax_api_key="",
        anthropic_api_key="",
        openai_api_key="",
    )


def _verdict_json(position: str = "approve", confidence: float = 0.8) -> str:
    return (
        '{"position":"' + position + '",'
        '"confidence":' + str(confidence) + ","
        '"reasoning":"ok","concerns":[]}'
    )


def _make_capturing_garage() -> MagicMock:
    """Build a ModelGarage stub that yields one valid verdict token per agent."""
    garage = MagicMock()

    async def fake_stream(prompt, *, agent):
        yield MagicMock(
            token=_verdict_json(),
            agent=agent,
            seq=0,
        )

    garage.stream_chat = fake_stream
    return garage


# -------------------------------------------------------------------
# Tribunal.run()
# -------------------------------------------------------------------


async def test_tribunal_run_returns_final_state():
    settings = _settings()
    garage = _make_capturing_garage()
    state = initial_state(deliberation_id="did-run", problem="test problem")
    tribunal = Tribunal(settings, garage)
    result = await tribunal.run(state)
    assert result["status"] == "completed"
    assert result.get("final_verdict") is not None


async def test_tribunal_run_records_metrics():
    settings = _settings()
    garage = _make_capturing_garage()
    state = initial_state(deliberation_id="did-metrics", problem="x")
    tribunal = Tribunal(settings, garage)

    with (
        patch("tier1.deliberation.graph.record_deliberation_latency") as mock_latency,
        patch("tier1.deliberation.graph.record_deliberation_rounds") as mock_rounds,
    ):
        await tribunal.run(state)

    mock_latency.assert_called_once()
    latency_arg = mock_latency.call_args.args[0]
    assert isinstance(latency_arg, float)
    assert latency_arg > 0.0
    mock_rounds.assert_called_once()
    rounds_arg = mock_rounds.call_args.args[0]
    assert rounds_arg >= 1


# -------------------------------------------------------------------
# Tribunal.stream()
# -------------------------------------------------------------------


async def test_tribunal_stream_yields_events_in_order():
    settings = _settings()
    garage = _make_capturing_garage()
    state = initial_state(deliberation_id="did-stream", problem="stream test")
    # Pre-seed the state with one prior event so the stream has something
    # to forward before the graph emits its own.
    state["events"] = [
        DeliberationEvent(
            seq=0,
            ts=0.0,
            kind="started",
            payload={"problem": "stream test"},
        )
    ]
    tribunal = Tribunal(settings, garage)

    kinds: list[str] = []
    async for event in tribunal.stream(state):
        kinds.append(event.kind)
        if event.kind == "completed":
            break

    # At least: one started, one token, the three verdict events, and completed.
    assert "started" in kinds
    assert "token" in kinds
    assert "alpha_verdict" in kinds
    assert "beta_verdict" in kinds
    assert "charlie_verdict" in kinds
    assert "completed" in kinds

    # The started event comes before any tokens, completed last.
    assert kinds.index("started") < kinds.index("token")
    assert kinds.index("completed") == len(kinds) - 1


async def test_tribunal_stream_drains_after_run_completes():
    """The stream terminates with a None sentinel after the run task finishes."""
    settings = _settings()
    garage = _make_capturing_garage()
    state = initial_state(deliberation_id="did-drain", problem="drain test")
    tribunal = Tribunal(settings, garage)

    # Drive the stream and confirm it terminates (does not hang).
    collected: list[DeliberationEvent] = []
    async for event in tribunal.stream(state):
        collected.append(event)
    # We collected some events and the generator exited.
    assert len(collected) > 0
    # The last event in the stream is the "completed" event.
    assert collected[-1].kind == "completed"
