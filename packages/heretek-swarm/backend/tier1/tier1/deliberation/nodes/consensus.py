"""Consensus rule — pure function.

The Tribunan's decision is computed from the three agent verdicts. The
function `apply` returns a FinalDecision enum; `build_final_verdict`
wraps it in a FinalVerdict object along with a summary.

Rule (verbatim from spec §4):
    if all 3 approve AND min(confidence_alpha, confidence_beta,
       confidence_charlie) >= unanimous_floor  -> approved
    if 2-of-3 approve AND charlie position != "challenge" -> approved
    if 2-of-3 reject -> rejected
    if charlie "challenge" with confidence > charlie_veto_confidence -> needs-revision
    if round >= max_rounds -> no-consensus
    else -> feedback loop (handled by Steward node, not here)
"""

from __future__ import annotations

from tier1.deliberation.state import (
    AgentName,
    AgentVerdict,
    DeliberationState,
    FinalDecision,
    FinalVerdict,
)


def apply(
    votes: dict[AgentName, AgentVerdict],
    *,
    charlie_veto_confidence: float = 0.7,
    unanimous_floor: float = 0.7,
) -> FinalDecision:
    """Decide based on the three agent verdicts only.

    The Steward handles the round limit separately because it needs
    state context; this function only considers the votes.
    """
    a = votes["alpha"]
    b = votes["beta"]
    c = votes["charlie"]

    approves = sum(1 for v in (a, b, c) if v.position == "approve")
    rejects = sum(1 for v in (a, b, c) if v.position == "reject")

    # Charlie's high-confidence challenge is a hard veto.
    if c.position == "challenge" and c.confidence > charlie_veto_confidence:
        return "needs-revision"

    # Unanimous high-confidence approval.
    if approves == 3 and min(a.confidence, b.confidence, c.confidence) >= unanimous_floor:
        return "approved"

    # 2-of-3 approve, with Charlie's challenge not at veto strength.
    # (High-confidence challenge already returned needs-revision above.)
    if approves >= 2 and not (c.position == "challenge" and c.confidence > charlie_veto_confidence):
        return "approved"

    # 2-of-3 reject.
    if rejects >= 2:
        return "rejected"

    # Otherwise, fall through to feedback loop in the Steward.
    return "needs-revision"


def build_final_verdict(
    state: DeliberationState,
    *,
    charlie_veto_confidence: float = 0.7,
    unanimous_floor: float = 0.7,
    max_rounds: int = 3,
) -> FinalVerdict:
    """Build a FinalVerdict from the current state's agent verdicts."""
    votes: dict[AgentName, AgentVerdict] = {
        "alpha": state["alpha_verdict"],  # type: ignore[typeddict-item]
        "beta": state["beta_verdict"],  # type: ignore[typeddict-item]
        "charlie": state["charlie_verdict"],  # type: ignore[typeddict-item]
    }
    decision = apply(
        votes,
        charlie_veto_confidence=charlie_veto_confidence,
        unanimous_floor=unanimous_floor,
    )
    # `max_rounds` is the number of rounds allowed total. After the final
    # round (0-indexed: round == max_rounds - 1), unresolved verdicts
    # collapse to no-consensus.
    if state.get("round", 0) + 1 >= max_rounds and decision == "needs-revision":
        decision = "no-consensus"
    summary = _summarize(votes, decision)
    return FinalVerdict(
        decision=decision, summary=summary, votes=votes, rounds=state.get("round", 0)
    )


def _summarize(votes: dict[AgentName, AgentVerdict], decision: FinalDecision) -> str:
    lines = [f"Decision: {decision}", ""]
    for name in ("alpha", "beta", "charlie"):
        v = votes[name]
        lines.append(f"{name}: position={v.position} confidence={v.confidence:.2f}")
        if v.concerns:
            lines.append(f"  concerns: {'; '.join(v.concerns)}")
    return "\n".join(lines)
