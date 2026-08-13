"""Tests for state.py models and factories."""

import pytest
from pydantic import ValidationError

from tier1.deliberation.state import (
    AgentName,
    AgentVerdict,
    DeliberationEvent,
    DeliberationState,
    FinalDecision,
    FinalVerdict,
    VerdictPosition,
    initial_state,
    new_deliberation_id,
    next_seq,
    now_ts,
)
from tier1.events.channels import subject_for


def test_agent_verdict_confidence_bounds():
    with pytest.raises(ValidationError):
        AgentVerdict(agent="alpha", position="approve", confidence=1.5, reasoning="x")
    with pytest.raises(ValidationError):
        AgentVerdict(agent="alpha", position="approve", confidence=-0.1, reasoning="x")
    v = AgentVerdict(agent="alpha", position="approve", confidence=0.7, reasoning="ok")
    assert v.confidence == 0.7


def test_agent_verdict_rejects_unknown_position():
    with pytest.raises(ValidationError):
        AgentVerdict(agent="alpha", position="approveish", confidence=0.5, reasoning="x")


def test_agent_verdict_rejects_extra_fields():
    with pytest.raises(ValidationError):
        AgentVerdict(agent="alpha", position="approve", confidence=0.5, reasoning="x", sneaky=True)


def test_final_verdict_decision_literal():
    fv = FinalVerdict(
        decision="approved",
        summary="ok",
        votes={
            "alpha": AgentVerdict(agent="alpha", position="approve", confidence=0.9, reasoning="ok")
        },
        rounds=1,
    )
    assert fv.decision == "approved"


def test_event_seq_must_be_non_negative():
    with pytest.raises(ValidationError):
        DeliberationEvent(seq=-1, ts=0.0, kind="started", payload={})


def test_initial_state_round_zero_no_verdicts():
    state = initial_state(deliberation_id="abc", problem="test problem")
    assert state["round"] == 0
    assert state["alpha_verdict"] is None
    assert state["beta_verdict"] is None
    assert state["charlie_verdict"] is None
    assert state["final_verdict"] is None
    assert state["status"] == "running"
    assert len(state["events"]) == 1
    assert state["events"][0].kind == "started"
    assert state["max_rounds"] == 3


def test_initial_state_default_user_id():
    state = initial_state(deliberation_id="abc", problem="x")
    assert state["user_id"] == "default"


def test_initial_state_emits_started_event():
    state = initial_state(deliberation_id="abc", problem="hello")
    e = state["events"][0]
    assert e.kind == "started"
    assert e.payload == {"problem": "hello"}


def test_new_deliberation_id_returns_uuid_string():
    a = new_deliberation_id()
    b = new_deliberation_id()
    assert isinstance(a, str)
    assert a != b


def test_next_seq_monotonic():
    state = initial_state(deliberation_id="abc", problem="x")
    assert next_seq(state["events"]) == 1
    state["events"].append(DeliberationEvent(seq=1, ts=0.0, kind="alpha_thinking", payload={}))
    assert next_seq(state["events"]) == 2


def test_subject_for():
    assert subject_for("xyz") == "tier1.deliberation.xyz.events"


def test_now_ts_returns_float():
    t = now_ts()
    assert isinstance(t, float)
    assert t > 0


def test_state_keys_present_in_typed_dict():
    state: DeliberationState = initial_state(deliberation_id="x", problem="p")
    required = {
        "deliberation_id",
        "problem",
        "user_id",
        "round",
        "max_rounds",
        "alpha_verdict",
        "beta_verdict",
        "charlie_verdict",
        "feedback",
        "events",
        "final_verdict",
        "status",
    }
    assert required.issubset(state.keys())
