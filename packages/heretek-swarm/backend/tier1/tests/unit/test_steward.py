"""Tests for Steward node — finalize and feedback paths."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.deliberation.nodes.steward import steward_node
from tier1.deliberation.state import AgentVerdict, DeliberationEvent, initial_state


def _settings(max_rounds=3) -> Settings:
    return Settings(minimax_api_key="sk-test", max_rounds=max_rounds)


def _state_with_votes(alpha_pos="approve", beta_pos="approve", charlie_pos="approve"):
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = AgentVerdict(
        agent="alpha", position=alpha_pos, confidence=0.9, concerns=["a-c"], reasoning="a-r"
    )
    state["beta_verdict"] = AgentVerdict(
        agent="beta", position=beta_pos, confidence=0.85, concerns=["b-c"], reasoning="b-r"
    )
    state["charlie_verdict"] = AgentVerdict(
        agent="charlie", position=charlie_pos, confidence=0.8, concerns=["c-c"], reasoning="c-r"
    )
    return state


async def test_steward_finalizes_unanimous_approval():
    state = _state_with_votes()
    result = await steward_node(state, _settings())
    assert result["final_verdict"] is not None
    assert result["final_verdict"].decision == "approved"
    assert result["status"] == "completed"
    kinds = [e.kind for e in result["events"]]
    assert "completed" in kinds
    assert "consensus_reached" in kinds


async def test_steward_finalizes_rejection():
    state = _state_with_votes(alpha_pos="reject", beta_pos="reject", charlie_pos="reject")
    result = await steward_node(state, _settings())
    assert result["final_verdict"].decision == "rejected"


async def test_steward_rejection_emits_consensus_reached():
    """Per spec §4: rejected is a definitive answer -> consensus_reached."""
    state = _state_with_votes(alpha_pos="reject", beta_pos="reject", charlie_pos="reject")
    result = await steward_node(state, _settings())
    kinds = [e.kind for e in result["events"]]
    assert "consensus_reached" in kinds
    assert "consensus_failed" not in kinds


async def test_steward_no_consensus_emits_consensus_failed():
    """Per spec §4: no-consensus -> consensus_failed (distinct from rejection)."""
    state = _state_with_votes(alpha_pos="approve", beta_pos="reject", charlie_pos="challenge")
    state["round"] = 3  # at max_rounds
    result = await steward_node(state, _settings(max_rounds=3))
    assert result["final_verdict"].decision == "no-consensus"
    kinds = [e.kind for e in result["events"]]
    assert "consensus_failed" in kinds
    assert "consensus_reached" not in kinds


async def test_steward_emits_feedback_on_no_consensus():
    state = _state_with_votes(alpha_pos="approve", beta_pos="reject", charlie_pos="challenge")
    state["round"] = 1
    result = await steward_node(state, _settings())
    assert result["final_verdict"] is None
    assert result["status"] == "running"
    assert result["round"] == 2  # incremented
    assert result["alpha_verdict"] is None  # reset for next round
    assert result["beta_verdict"] is None
    assert result["charlie_verdict"] is None
    feedback_events = [e for e in result["events"] if e.kind == "steward_feedback"]
    assert len(feedback_events) == 1
    assert feedback_events[0].payload["round"] == 2
    assert "alpha's concerns" in feedback_events[0].payload["feedback_text"].lower()


async def test_steward_no_consensus_at_max_rounds():
    state = _state_with_votes(alpha_pos="approve", beta_pos="reject", charlie_pos="challenge")
    state["round"] = 3
    result = await steward_node(state, _settings(max_rounds=3))
    assert result["final_verdict"] is not None
    assert result["final_verdict"].decision == "no-consensus"
    assert result["status"] == "completed"


async def test_steward_with_missing_verdicts_no_ops():
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = None
    result = await steward_node(state, _settings())
    # Should be a no-op when verdicts aren't all present.
    assert result["final_verdict"] is None
    assert result["status"] == "running"


async def test_steward_sink_receives_events():
    state = _state_with_votes()
    received: list[DeliberationEvent] = []

    async def sink(e):
        received.append(e)

    await steward_node(state, _settings(), sink=sink)
    assert any(e.kind == "consensus_reached" for e in received)
    assert any(e.kind == "completed" for e in received)


async def test_steward_feedback_accumulates():
    state = _state_with_votes(alpha_pos="approve", beta_pos="reject", charlie_pos="challenge")
    state["round"] = 1
    state["feedback"] = ["prior feedback text"]
    result = await steward_node(state, _settings())
    assert len(result["feedback"]) == 2
    assert result["feedback"][0] == "prior feedback text"
