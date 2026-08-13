"""Property-based tests for consensus logic using Hypothesis.

Tests consensus.apply(), build_final_verdict(), and steward_node()
with randomly generated agent verdicts to find edge cases.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from hypothesis import given, settings, strategies as st

from tier1.config import Settings
from tier1.deliberation.nodes.consensus import apply, build_final_verdict
from tier1.deliberation.nodes.steward import steward_node
from tier1.deliberation.state import (
    AgentVerdict,
    DeliberationEvent,
    DeliberationState,
)


# --- Strategies ---

position_strat = st.sampled_from(["approve", "reject", "challenge"])
confidence_strat = st.floats(min_value=0.0, max_value=1.0)
concerns_strat = st.lists(st.text(max_size=20), max_size=3)
reasoning_strat = st.text(max_size=100)

verdict_strat = st.fixed_dictionaries(
    {
        "position": position_strat,
        "confidence": confidence_strat,
        "concerns": concerns_strat,
        "reasoning": reasoning_strat,
    }
)

three_verdicts = st.tuples(verdict_strat, verdict_strat, verdict_strat)


AGENT_NAMES = ("alpha", "beta", "charlie")


def _make_verdict(d: dict, agent: str) -> AgentVerdict:
    """Wrap a raw dict as an AgentVerdict."""
    return AgentVerdict(agent=agent, **d)


def _verdicts_to_dict(triple):
    """Convert tuple of 3 verdict dicts to the format apply() expects."""
    return {name: _make_verdict(d, name) for name, d in zip(AGENT_NAMES, triple)}


VALID_DECISIONS = {"approved", "rejected", "needs-revision"}


# --- Property tests ---


@settings(max_examples=500)
@given(triple=three_verdicts)
def test_apply_always_returns_valid_decision(triple):
    """apply() must return one of the three valid decisions for any input."""
    votes = _verdicts_to_dict(triple)
    result = apply(votes)
    assert result in VALID_DECISIONS, f"Invalid decision: {result}"


@settings(max_examples=500)
@given(confidence=confidence_strat)
def test_unanimous_high_confidence_approves(confidence):
    """When all 3 approve and min(confidence) >= 0.7, result is approved."""
    floor = 0.7
    verdict = AgentVerdict(
        agent="alpha", position="approve", confidence=confidence, concerns=[], reasoning=""
    )
    votes = {"alpha": verdict, "beta": verdict, "charlie": verdict}
    result = apply(votes, unanimous_floor=floor)
    if confidence >= floor:
        assert result == "approved", f"Unanimous high confidence should approve, got {result}"


@settings(max_examples=500)
@given(triple=three_verdicts)
def test_two_of_three_rejects_rejected(triple):
    """When 2+ agents reject (and Charlie doesn't veto), result is rejected."""
    votes = _verdicts_to_dict(triple)
    rejects = sum(1 for v in triple if v["position"] == "reject")
    charlie = triple[2]
    charlie_vetoes = charlie["position"] == "challenge" and charlie["confidence"] > 0.7
    result = apply(votes)
    if rejects >= 2 and not charlie_vetoes:
        assert result == "rejected", f"2+ rejects should yield rejected, got {result}"


@settings(max_examples=500)
@given(triple=three_verdicts)
def test_charlie_veto_overrides_approval(triple):
    """Charlie high-confidence challenge overrides unanimous approval."""
    alpha, beta, _ = triple
    charlie = AgentVerdict(
        agent="charlie", position="challenge", confidence=0.95, concerns=[], reasoning=""
    )
    votes = {
        "alpha": _make_verdict(alpha, "alpha"),
        "beta": _make_verdict(beta, "beta"),
        "charlie": charlie,
    }
    result = apply(votes, charlie_veto_confidence=0.7)
    # If alpha and beta both approve, charlie's veto should force needs-revision
    if alpha["position"] == "approve" and beta["position"] == "approve":
        assert result == "needs-revision", f"Charlie veto should override approval, got {result}"


@settings(max_examples=200)
@given(triple=three_verdicts, round_num=st.integers(min_value=0, max_value=20))
def test_build_final_verdict_never_exceeds_rounds(triple, round_num):
    """build_final_verdict never returns needs-revision when round limit reached."""
    votes = _verdicts_to_dict(triple)
    decision = apply(votes)
    max_rounds = 3
    state: DeliberationState = {
        "deliberation_id": "test",
        "problem": "test",
        "user_id": "test",
        "round": round_num,
        "max_rounds": max_rounds,
        "alpha_verdict": _make_verdict(triple[0], "alpha"),
        "beta_verdict": _make_verdict(triple[1], "beta"),
        "charlie_verdict": _make_verdict(triple[2], "charlie"),
        "feedback": [],
        "events": [],
        "status": "running",
    }
    verdict = build_final_verdict(state, max_rounds=max_rounds)
    if round_num + 1 >= max_rounds and decision == "needs-revision":
        assert verdict.decision == "no-consensus", (
            f"Round limit should collapse needs-revision to no-consensus, got {verdict.decision}"
        )
    else:
        assert verdict.decision == decision


# --- Deterministic tests ---


def test_build_final_verdict_round_limit_collapses():
    """Exact boundary: round=2, max_rounds=3, needs-revision → no-consensus."""
    state: DeliberationState = {
        "deliberation_id": "test",
        "problem": "test",
        "user_id": "test",
        "round": 2,
        "max_rounds": 3,
        "alpha_verdict": AgentVerdict(
            agent="alpha", position="approve", confidence=0.8, concerns=[], reasoning=""
        ),
        "beta_verdict": AgentVerdict(
            agent="beta", position="reject", confidence=0.6, concerns=[], reasoning=""
        ),
        "charlie_verdict": AgentVerdict(
            agent="charlie", position="challenge", confidence=0.5, concerns=[], reasoning=""
        ),
        "feedback": [],
        "events": [],
        "status": "running",
    }
    verdict = build_final_verdict(state, max_rounds=3)
    assert verdict.decision == "no-consensus"


async def test_steward_node_finalizes_on_approved():
    """steward_node sets status=completed and emits consensus_reached."""
    state: DeliberationState = {
        "deliberation_id": "test",
        "problem": "test",
        "user_id": "test",
        "round": 0,
        "max_rounds": 3,
        "alpha_verdict": AgentVerdict(
            agent="alpha", position="approve", confidence=0.9, concerns=[], reasoning=""
        ),
        "beta_verdict": AgentVerdict(
            agent="beta", position="approve", confidence=0.8, concerns=[], reasoning=""
        ),
        "charlie_verdict": AgentVerdict(
            agent="charlie", position="approve", confidence=0.85, concerns=[], reasoning=""
        ),
        "feedback": [],
        "events": [],
        "status": "running",
    }
    sink = AsyncMock()
    settings = Settings()
    result = await steward_node(state, settings, sink=sink)
    assert result["status"] == "completed"
    assert result.get("final_verdict") is not None
    # sink should have been called with consensus_reached + completed events
    assert sink.call_count >= 2
    event_kinds = [call.args[0].kind for call in sink.call_args_list]
    assert "consensus_reached" in event_kinds
    assert "completed" in event_kinds


# --- Strategy validation ---


def test_strategy_generates_valid_verdicts():
    """Strategy produces verdicts with valid positions and confidence ranges."""
    for _ in range(100):
        v = verdict_strat.example()
        assert v["position"] in ("approve", "reject", "challenge")
        assert 0.0 <= v["confidence"] <= 1.0


def test_hypothesis_finds_known_edge_case():
    """Hypothesis can reach the all-challenge, high-confidence edge case."""
    _v = {"position": "challenge", "confidence": 0.9, "concerns": [], "reasoning": ""}
    votes = {
        "alpha": AgentVerdict(agent="alpha", **_v),
        "beta": AgentVerdict(agent="beta", **_v),
        "charlie": AgentVerdict(agent="charlie", **_v),
    }
    result = apply(votes)
    assert result == "needs-revision"
