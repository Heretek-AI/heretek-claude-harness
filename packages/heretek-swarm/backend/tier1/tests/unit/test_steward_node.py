"""Unit tests for tier1.deliberation.nodes.steward.

Targets branches the existing test_steward.py leaves uncovered:
  - make_steward_node all four kwarg combinations
  - _build_feedback with no concerns raised by any agent
  - steward_node with sink=None at finalize (covers the if-None skips)
  - final_verdict missing on the consensus-failed path
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tier1.config import Settings
from tier1.deliberation.nodes.steward import (
    _build_feedback,
    make_steward_node,
    steward_node,
)
from tier1.deliberation.state import AgentVerdict, initial_state


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


# ---------- make_steward_node all branches ----------


def test_make_steward_node_no_args_uses_defaults():
    """Both sink and memory None -> partial without those kwargs."""
    settings = _settings()
    node = make_steward_node(settings)
    assert callable(node)
    # invoke it with just state; sink/memory default to None
    assert node.func is steward_node  # partial target


def test_make_steward_node_with_sink_only():
    settings = _settings()
    sink = MagicMock()
    node = make_steward_node(settings, sink=sink)
    assert node.keywords["sink"] is sink
    assert "memory" not in node.keywords


def test_make_steward_node_with_memory_only():
    settings = _settings()
    memory = MagicMock()
    node = make_steward_node(settings, memory=memory)
    assert node.keywords["memory"] is memory
    assert "sink" not in node.keywords


def test_make_steward_node_with_both():
    settings = _settings()
    sink = MagicMock()
    memory = MagicMock()
    node = make_steward_node(settings, sink=sink, memory=memory)
    assert node.keywords["sink"] is sink
    assert node.keywords["memory"] is memory


# ---------- _build_feedback branches ----------


def test_build_feedback_with_no_concerns_raises():
    """When no agent has concerns, fallback text appears."""
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = AgentVerdict(
        agent="alpha", position="approve", confidence=0.9, concerns=[], reasoning="a"
    )
    state["beta_verdict"] = AgentVerdict(
        agent="beta", position="approve", confidence=0.9, concerns=[], reasoning="b"
    )
    state["charlie_verdict"] = AgentVerdict(
        agent="charlie", position="approve", confidence=0.9, concerns=[], reasoning="c"
    )
    final = MagicMock()
    final.decision = "challenge"
    fb = _build_feedback(state, final)
    assert "No specific concerns raised" in fb
    assert "Round 0" in fb


def test_build_feedback_includes_round_number():
    state = _state_with_votes()
    state["round"] = 2
    final = MagicMock()
    final.decision = "challenge"
    fb = _build_feedback(state, final)
    assert "Round 2" in fb


def test_build_feedback_lists_each_agent_with_concerns():
    state = _state_with_votes()
    final = MagicMock()
    final.decision = "challenge"
    fb = _build_feedback(state, final)
    assert "alpha's concerns" in fb
    assert "beta's concerns" in fb
    assert "charlie's concerns" in fb


# ---------- steward_node sink=None branches ----------


async def test_steward_finalize_with_sink_none_does_not_await():
    """When sink is None, the finalize branch skips both sink awaits."""
    state = _state_with_votes()
    result = await steward_node(state, _settings(), sink=None)
    assert result["final_verdict"].decision == "approved"
    assert result["status"] == "completed"
    # New events emitted by steward: consensus_reached + completed
    new_kinds = [e.kind for e in result["events"] if e.kind in ("consensus_reached", "completed")]
    assert "consensus_reached" in new_kinds
    assert "completed" in new_kinds


async def test_steward_feedback_with_sink_none_does_not_await():
    """When sink is None on the feedback path, the sink await is skipped."""
    state = _state_with_votes(alpha_pos="approve", beta_pos="reject", charlie_pos="challenge")
    state["round"] = 1
    result = await steward_node(state, _settings(), sink=None)
    # Single feedback event appended.
    feedback_events = [e for e in result["events"] if e.kind == "steward_feedback"]
    assert len(feedback_events) == 1


async def test_steward_missing_all_verdicts_returns_state_unchanged():
    """All three verdicts None -> no-op (line 35-38)."""
    state = initial_state(deliberation_id="abc", problem="x")
    events_before = list(state["events"])
    result = await steward_node(state, _settings())
    assert result["final_verdict"] is None
    assert result["status"] == "running"
    # Steward must not have appended any new events on the no-op path.
    new_events = [e for e in result["events"] if e not in events_before]
    assert new_events == []


async def test_steward_one_verdict_missing_returns_unchanged():
    """Only two verdicts present -> guard fires."""
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = AgentVerdict(
        agent="alpha", position="approve", confidence=0.9, concerns=[], reasoning=""
    )
    state["beta_verdict"] = AgentVerdict(
        agent="beta", position="approve", confidence=0.9, concerns=[], reasoning=""
    )
    result = await steward_node(state, _settings())
    assert result["final_verdict"] is None


async def test_steward_feedback_round_increments_and_resets_verdicts():
    """After feedback loop, verdicts reset to None for the next round."""
    state = _state_with_votes(alpha_pos="approve", beta_pos="reject", charlie_pos="challenge")
    state["round"] = 1
    result = await steward_node(state, _settings())
    assert result["round"] == 2
    assert result["alpha_verdict"] is None
    assert result["beta_verdict"] is None
    assert result["charlie_verdict"] is None
    assert len(result["feedback"]) == 1
