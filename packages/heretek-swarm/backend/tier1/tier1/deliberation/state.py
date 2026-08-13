"""Deliberation state — Pydantic models + TypedDict.

These models are the single source of truth for everything that flows
through the system. Later tasks import these exact types; do not rename
fields without updating all callers.
"""

from __future__ import annotations

import time
import uuid
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Literals — locked here; import from this module elsewhere.
# ---------------------------------------------------------------------------

AgentName = Literal["steward", "alpha", "beta", "charlie"]
VerdictPosition = Literal["approve", "reject", "challenge", "abstain"]
FinalDecision = Literal["approved", "rejected", "needs-revision", "no-consensus"]
EventKind = Literal[
    "started",
    "alpha_thinking",
    "alpha_verdict",
    "beta_thinking",
    "beta_verdict",
    "charlie_thinking",
    "charlie_verdict",
    "steward_feedback",
    "user_interjection",
    "token",
    "consensus_reached",
    "consensus_failed",
    "completed",
]
DeliberationStatus = Literal["running", "completed", "failed"]


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AgentVerdict(BaseModel):
    """One agent's output for a single round."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    position: VerdictPosition
    confidence: float = Field(ge=0.0, le=1.0)
    concerns: list[str] = Field(default_factory=list)
    reasoning: str


class FinalVerdict(BaseModel):
    """The Tribunan's decision at the end of a deliberation."""

    model_config = ConfigDict(extra="forbid")

    decision: FinalDecision
    summary: str
    votes: dict[AgentName, AgentVerdict]
    rounds: int


class DeliberationEvent(BaseModel):
    """One immutable event in the deliberation timeline."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0)
    ts: float
    kind: EventKind
    payload: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# TypedDict — runtime shape used by LangGraph state.
# ---------------------------------------------------------------------------


class DeliberationState(TypedDict, total=False):
    deliberation_id: str
    problem: str
    user_id: str
    round: int
    max_rounds: int
    alpha_verdict: AgentVerdict | None
    beta_verdict: AgentVerdict | None
    charlie_verdict: AgentVerdict | None
    feedback: list[str]
    events: list[DeliberationEvent]
    final_verdict: FinalVerdict | None
    status: DeliberationStatus
    failure_reason: str | None


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def new_deliberation_id() -> str:
    """UUID4 string identifier for a new deliberation."""
    return str(uuid.uuid4())


def now_ts() -> float:
    """Wall-clock timestamp in seconds (float)."""
    return time.time()


def initial_state(
    *,
    deliberation_id: str,
    problem: str,
    user_id: str = "default",
    max_rounds: int = 3,
) -> DeliberationState:
    """Build the starting state for a fresh deliberation."""
    return DeliberationState(
        deliberation_id=deliberation_id,
        problem=problem,
        user_id=user_id,
        round=0,
        max_rounds=max_rounds,
        alpha_verdict=None,
        beta_verdict=None,
        charlie_verdict=None,
        feedback=[],
        events=[
            DeliberationEvent(
                seq=0,
                ts=now_ts(),
                kind="started",
                payload={"problem": problem},
            )
        ],
        final_verdict=None,
        status="running",
        failure_reason=None,
    )


def next_seq(events: list[DeliberationEvent]) -> int:
    """Monotonic sequence number for the next event."""
    return len(events)
