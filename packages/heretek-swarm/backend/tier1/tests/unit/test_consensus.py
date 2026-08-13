"""Tests for the consensus rule (pure function). 100% line coverage target."""

from __future__ import annotations

import pytest

from tier1.deliberation.nodes.consensus import apply, build_final_verdict
from tier1.deliberation.state import AgentVerdict, initial_state


def _v(agent, position, confidence, concerns=None, reasoning="r"):
    return AgentVerdict(
        agent=agent,
        position=position,
        confidence=confidence,
        concerns=concerns or [],
        reasoning=reasoning,
    )


def test_unanimous_high_confidence_approves():
    votes = {
        "alpha": _v("alpha", "approve", 0.9),
        "beta": _v("beta", "approve", 0.85),
        "charlie": _v("charlie", "approve", 0.8),
    }
    assert apply(votes) == "approved"


def test_unanimous_but_low_confidence_falls_through():
    votes = {
        "alpha": _v("alpha", "approve", 0.5),
        "beta": _v("beta", "approve", 0.5),
        "charlie": _v("charlie", "approve", 0.5),
    }
    # unanimous but confidence below floor -> not the gold path; falls through
    # to 2-of-3 rule and approves.
    assert apply(votes) == "approved"


def test_two_of_three_approve_with_charlie_neutral():
    votes = {
        "alpha": _v("alpha", "approve", 0.8),
        "beta": _v("beta", "approve", 0.8),
        "charlie": _v("charlie", "abstain", 0.5),
    }
    assert apply(votes) == "approved"


def test_two_of_three_approve_with_charlie_challenging_low_confidence():
    votes = {
        "alpha": _v("alpha", "approve", 0.8),
        "beta": _v("beta", "approve", 0.8),
        "charlie": _v("charlie", "challenge", 0.5),  # below veto threshold
    }
    assert apply(votes) == "approved"


def test_two_of_three_reject():
    votes = {
        "alpha": _v("alpha", "reject", 0.9),
        "beta": _v("beta", "reject", 0.9),
        "charlie": _v("charlie", "approve", 0.5),
    }
    assert apply(votes) == "rejected"


def test_charlie_high_confidence_challenge_vetoes_unanimous_approval():
    votes = {
        "alpha": _v("alpha", "approve", 0.95),
        "beta": _v("beta", "approve", 0.95),
        "charlie": _v("charlie", "challenge", 0.95),
    }
    # Charlie's high-confidence challenge wins over unanimous approval.
    assert apply(votes) == "needs-revision"


def test_split_decision_with_no_clear_majority():
    votes = {
        "alpha": _v("alpha", "approve", 0.7),
        "beta": _v("beta", "reject", 0.7),
        "charlie": _v("charlie", "challenge", 0.5),
    }
    assert apply(votes) == "needs-revision"


def test_three_rejects():
    votes = {
        "alpha": _v("alpha", "reject", 0.9),
        "beta": _v("beta", "reject", 0.9),
        "charlie": _v("charlie", "reject", 0.9),
    }
    assert apply(votes) == "rejected"


def test_veto_threshold_respected():
    votes = {
        "alpha": _v("alpha", "approve", 0.9),
        "beta": _v("beta", "approve", 0.9),
        "charlie": _v("charlie", "challenge", 0.71),
    }
    assert apply(votes, charlie_veto_confidence=0.7) == "needs-revision"
    assert apply(votes, charlie_veto_confidence=0.8) == "approved"


def test_unanimous_floor_respected():
    votes = {
        "alpha": _v("alpha", "approve", 0.71),
        "beta": _v("beta", "approve", 0.71),
        "charlie": _v("charlie", "approve", 0.71),
    }
    assert apply(votes, unanimous_floor=0.7) == "approved"
    assert apply(votes, unanimous_floor=0.8) == "approved"  # falls through to 2-of-3 which approves


def test_build_final_verdict_no_consensus_at_max_rounds():
    state = initial_state(deliberation_id="abc", problem="x")
    state["round"] = 3
    state["alpha_verdict"] = _v("alpha", "approve", 0.5)
    state["beta_verdict"] = _v("beta", "reject", 0.5)
    state["charlie_verdict"] = _v("charlie", "challenge", 0.5)
    fv = build_final_verdict(state, max_rounds=3)
    assert fv.decision == "no-consensus"
    assert fv.rounds == 3


def test_build_final_verdict_includes_all_votes():
    state = initial_state(deliberation_id="abc", problem="x")
    state["alpha_verdict"] = _v("alpha", "approve", 0.9, reasoning="alpha-r")
    state["beta_verdict"] = _v("beta", "approve", 0.9, reasoning="beta-r")
    state["charlie_verdict"] = _v("charlie", "approve", 0.9, reasoning="charlie-r")
    fv = build_final_verdict(state)
    assert fv.votes["alpha"].reasoning == "alpha-r"
    assert fv.votes["beta"].reasoning == "beta-r"
    assert fv.votes["charlie"].reasoning == "charlie-r"
