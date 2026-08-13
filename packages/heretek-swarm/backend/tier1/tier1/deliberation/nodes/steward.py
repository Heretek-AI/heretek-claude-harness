"""Steward node — tally, finalize, or feedback-loop.

The Steward is deterministic. It does not call an LLM. It runs after
all three agents have produced verdicts in a round.
"""

from __future__ import annotations

from functools import partial
from typing import Awaitable, Callable

from tier1.config import Settings
from tier1.deliberation.nodes.consensus import build_final_verdict
from tier1.observability.metrics import record_consensus_outcome
from tier1.deliberation.state import (
    DeliberationEvent,
    DeliberationState,
    next_seq,
    now_ts,
)

EventSink = Callable[[DeliberationEvent], Awaitable[None]]


async def steward_node(
    state: DeliberationState,
    settings: Settings,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
) -> DeliberationState:
    """Tally verdicts. Either finalize or emit feedback and continue."""
    events = list(state.get("events", []))

    # Guard: all three verdicts must be present.
    if not (
        state.get("alpha_verdict") and state.get("beta_verdict") and state.get("charlie_verdict")
    ):
        return state

    final = build_final_verdict(
        state,
        charlie_veto_confidence=settings.charlie_veto_confidence,
        unanimous_floor=settings.unanimous_confidence_floor,
        max_rounds=settings.max_rounds,
    )

    record_consensus_outcome(final.decision)

    new_state: DeliberationState = {**state, "events": events}

    # Decide: finalize or feedback
    if final.decision in ("approved", "rejected", "no-consensus"):
        new_state["final_verdict"] = final
        # Finalize. Per spec §4: approved/rejected are both definitive
        # verdicts (consensus_reached); only no-consensus is a failure.
        kind = (
            "consensus_reached"
            if final.decision in ("approved", "rejected")
            else "consensus_failed"
        )
        events.append(
            DeliberationEvent(
                seq=next_seq(events),
                ts=now_ts(),
                kind=kind,
                payload={"decision": final.decision, "summary": final.summary},
            )
        )
        if sink is not None:
            await sink(events[-1])
        events.append(
            DeliberationEvent(
                seq=next_seq(events),
                ts=now_ts(),
                kind="completed",
                payload=final.model_dump(),
            )
        )
        if sink is not None:
            await sink(events[-1])
        new_state["events"] = events
        new_state["status"] = "completed"
        return new_state

    # Feedback loop: build concrete feedback for the next round.
    feedback_text = _build_feedback(state, final)
    new_round = state.get("round", 0) + 1

    events.append(
        DeliberationEvent(
            seq=next_seq(events),
            ts=now_ts(),
            kind="steward_feedback",
            payload={"round": new_round, "feedback_text": feedback_text},
        )
    )
    if sink is not None:
        await sink(events[-1])

    # Reset verdicts for the next round, accumulate feedback, increment round.
    feedback = list(state.get("feedback", []))
    feedback.append(feedback_text)

    new_state["events"] = events
    new_state["feedback"] = feedback
    new_state["round"] = new_round
    new_state["alpha_verdict"] = None
    new_state["beta_verdict"] = None
    new_state["charlie_verdict"] = None
    return new_state


def _build_feedback(state: DeliberationState, final) -> str:
    """Construct concrete feedback for the next round."""
    lines = [
        f"Round {state.get('round', 0)} produced decision={final.decision}. "
        "Address the following in your next round:",
    ]
    for name in ("alpha", "beta", "charlie"):
        v = state[f"{name}_verdict"]  # type: ignore[literal-required]
        if v and v.concerns:
            lines.append(f"- {name}'s concerns: {'; '.join(v.concerns)}")
    if not any(
        state[f"{name}_verdict"] and state[f"{name}_verdict"].concerns  # type: ignore[literal-required]
        for name in ("alpha", "beta", "charlie")
    ):
        lines.append("- No specific concerns raised; re-examine the problem with deeper rigor.")
    return "\n".join(lines)


def make_steward_node(
    settings: Settings,
    sink: EventSink | None = None,
    memory: "MemoryBackend | None" = None,
):
    if sink is None and memory is None:
        return partial(steward_node, settings=settings)
    if memory is None:
        return partial(steward_node, settings=settings, sink=sink)
    if sink is None:
        return partial(steward_node, settings=settings, memory=memory)
    return partial(steward_node, settings=settings, sink=sink, memory=memory)
