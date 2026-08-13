"""
Deliberation API — the ``/api/prompt`` swarm-deliberation endpoint.

Extracted from ``api/main.py`` as part of Phase 2.7 of PLAN.md
(§1.4 god-class extraction — ``api/main.py`` is 1,448 LOC and
should become "wiring + health + 1 deliberation route" once
extractions land). The prompt endpoint is the only one that
inlines a full deliberation pipeline (gathering positions,
running a round, broadcasting WebSocket events, computing a
synthesis); moving it into its own module shrinks main.py by
~315 LOC and gives the deliberation pipeline a focused test
surface.

Backwards compatibility: ``app.include_router(deliberation.router)``
preserves the existing ``POST /api/prompt`` URL exactly. No
client-visible change.
"""

from __future__ import annotations

import os
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger("api.deliberation")

router = APIRouter(tags=["deliberation"])


class PromptRequest(BaseModel):
    """Request model for the prompt endpoint."""

    prompt: str


class PromptResponse(BaseModel):
    """Response model for swarm deliberation output."""

    deliberation_id: str
    topic: str
    opinions: list[dict[str, Any]]
    votes: dict[str, int]
    synthesis: str
    consensus_score: float
    rounds: int
    participants: list[str]
    dissent_notes: list[str]
    llm_available: bool


@router.post("/api/prompt", response_model=PromptResponse)
async def prompt_endpoint(
    request: PromptRequest,
    authenticated: str = Depends(verify_auth),
):
    """
    Submit a prompt for swarm deliberation.

    Accepts a user prompt and orchestrates a deliberation across
    available swarm agents. Each agent submits a position and
    reasoning; the engine aggregates these into a synthesis.

    When no LLM provider is configured, agents contribute
    archetype-based responses derived from their agent type and
    role.

    Returns structured JSON containing agent opinions, votes,
    and synthesis.
    """
    # Imported here (not at module top) to avoid a circular import
    # with main.py: this module is included by main.py; the
    # deliberation_engine lives in api.consensus which itself
    # imports from heretek_swarm_core.consensus.*.
    from heretek_swarm.api.consensus import deliberation_engine
    from heretek_swarm.api.main import manager, supervisor
    from heretek_swarm_core.consensus.deliberation import Position

    logger.info("prompt_received", prompt=request.prompt[:200])

    # Determine active participants from the supervisor
    participants: list[str] = []
    if supervisor is not None and supervisor.actors:
        max_participants = int(
            os.environ.get("HERETEK_MAX_DELIBERATION_PARTICIPANTS", "5")
        )
        participants = list(supervisor.actors.keys())[:max_participants]
        logger.info(
            "prompt_participants", count=len(participants), agents=participants
        )

    # If no supervisor actors exist, return empty — client should
    # spawn agents first.
    if not participants:
        raise HTTPException(
            status_code=503,
            detail=(
                "No agents available in supervisor registry. "
                "Deploy agents before starting deliberation."
            ),
        )

    # Check whether we have a working LLM provider
    llm_available = bool(
        os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    )

    # Start the deliberation
    deliberation_id = deliberation_engine.start_deliberation(
        topic=request.prompt,
        participants=participants,
    )

    # Broadcast deliberation_started to dashboard WebSocket clients
    with suppress(Exception):
        await manager.broadcast_dashboard(
            {
                "type": "deliberation_started",
                "deliberation_id": deliberation_id,
                "topic": request.prompt[:200],
                "participant_count": len(participants),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    # Gather positions from each participant via submit_argument
    opinions: list[dict[str, Any]] = []
    votes: dict[str, int] = {"for": 0, "against": 0, "neutral": 0}

    for agent_id in participants:
        # Attempt real LLM-driven position when available
        reasoning: str | None = None
        if supervisor is not None and agent_id in supervisor.actors:
            actor = supervisor.actors[agent_id]
            try:
                run_fn = getattr(actor, "run_with_llm", None)
                if callable(run_fn) and llm_available:
                    reasoning = await run_fn(
                        f"As {agent_id}, give your position on: {request.prompt}\n"
                        f"Respond with a single paragraph of reasoning.",
                        timeout=15,
                    )
            except Exception:
                logger.warning(
                    "agent_llm_call_failed", agent_id=agent_id, exc_info=True
                )

        # Fallback: archetype-based synthetic position
        if not reasoning:
            reasoning = _archetype_response(agent_id, request.prompt)

        # Determine position from reasoning
        position_str = _classify_position(reasoning)
        position = Position(position_str)
        confidence = 0.6  # Default

        deliberation_engine.submit_argument(
            deliberation_id=deliberation_id,
            agent_id=agent_id,
            position=position,
            reasoning=reasoning,
            evidence_refs=[],
            confidence=confidence,
        )

        votes[position_str] += 1
        opinions.append(
            {
                "agent_id": agent_id,
                "position": position_str,
                "confidence": confidence,
                "reasoning": reasoning,
            }
        )

        # Broadcast agent position to dashboard WebSocket clients
        with suppress(Exception):
            await manager.broadcast_dashboard(
                {
                    "type": "agent_position_submitted",
                    "deliberation_id": deliberation_id,
                    "agent_id": agent_id,
                    "position": position_str,
                    "confidence": confidence,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    # Run a deliberation round to synthesize
    consensus_score = 0.0
    round_count = 0
    synthesis = ""
    try:
        round_result = deliberation_engine.run_deliberation_round(
            deliberation_id=deliberation_id,
        )
        if round_result:
            consensus_score = round_result.consensus_score
            round_count = deliberation_engine.current_rounds.get(
                deliberation_id, 0
            )
            synthesis = _build_synthesis(round_result, votes, len(participants))
    except Exception:
        logger.warning("deliberation_round_failed", exc_info=True)
        synthesis = _synthesize_fallback(opinions)
        consensus_score = 0.5
        round_count = 1

        with suppress(Exception):
            await manager.broadcast_dashboard(
                {
                    "type": "deliberation_round_failed",
                    "deliberation_id": deliberation_id,
                    "error": "deliberation_round_engine_failed",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

    # Collect dissent notes
    dissent_notes: list[str] = []
    try:
        dissent = deliberation_engine.dissent_records.get(deliberation_id, [])
        for d in dissent:
            if hasattr(d, "note") and d.note:
                dissent_notes.append(d.note)
            elif isinstance(d, dict) and d.get("note"):
                dissent_notes.append(d["note"])
    except Exception:
        # Dissent notes are display-only — skip inconsistent records
        # silently.
        logger.debug("Malformed dissent note skipped", exc_info=True)

    # Broadcast deliberation_completed to dashboard WebSocket clients
    with suppress(Exception):
        await manager.broadcast_dashboard(
            {
                "type": "deliberation_completed",
                "deliberation_id": deliberation_id,
                "consensus_score": round(consensus_score, 3),
                "votes": votes,
                "participant_count": len(participants),
                "rounds": max(round_count, 1),
                "llm_available": llm_available,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    logger.info(
        "prompt_completed",
        deliberation_id=deliberation_id,
        participants=len(participants),
        votes=votes,
        consensus_score=consensus_score,
    )

    return PromptResponse(
        deliberation_id=deliberation_id,
        topic=request.prompt,
        opinions=opinions,
        votes=votes,
        synthesis=synthesis,
        consensus_score=round(consensus_score, 3),
        rounds=max(round_count, 1),
        participants=participants,
        dissent_notes=dissent_notes,
        llm_available=llm_available,
    )


def _archetype_response(agent_id: str, prompt: str) -> str:
    """Generate an archetype-based synthetic response when LLM is unavailable."""
    archetypes: dict[str, str] = {
        "analyst": (
            f"Analyzing '{prompt}': This proposal warrants systematic "
            "examination. Key factors include feasibility, resource "
            "allocation, and alignment with swarm objectives. Recommend "
            "proceeding with structured evaluation."
        ),
        "critic": (
            f"Regarding '{prompt}': Critical assessment identifies "
            "potential risks. We must verify assumptions, test edge "
            "cases, and ensure robustness before committing. Caution "
            "is warranted."
        ),
        "synthesizer": (
            f"On '{prompt}': Integrating multiple perspectives reveals "
            "convergence points. The swarm's collective intelligence "
            "suggests a balanced approach that incorporates both "
            "innovation and prudence."
        ),
        "explorer": (
            f"Exploring '{prompt}': Novel directions emerge from this "
            "prompt. We could expand into adjacent problem spaces, "
            "consider unconventional solutions, and probe the "
            "boundaries of our current understanding."
        ),
        "validator": (
            f"Validating '{prompt}': Cross-referencing against "
            "established patterns confirms internal consistency. The "
            "proposition aligns with swarm principles and operational "
            "constraints."
        ),
        "steward": (
            f"Stewarding '{prompt}': The swarm's governance framework "
            "guides us. I recommend structured deliberation with "
            "clear success criteria. We should proceed methodically "
            "while maintaining operational integrity."
        ),
        "alpha": (
            f"Alpha perspective on '{prompt}': As primary agent, I "
            "support moving forward with this direction. The proposal "
            "aligns with our core objectives and warrants full swarm "
            "engagement."
        ),
        "beta": (
            f"Beta analysis of '{prompt}': While the direction is "
            "sound, I suggest refining the approach with additional "
            "safeguards. We should validate assumptions before full "
            "commitment."
        ),
        "charlie": (
            f"Charlie's take on '{prompt}': I concur with the general "
            "direction but note potential edge cases. Recommend "
            "modifying scope to account for boundary conditions."
        ),
        "historian": (
            f"Historical context on '{prompt}': Based on prior "
            "deliberation patterns, this type of proposal typically "
            "benefits from iterative refinement. I recommend at "
            "least two rounds of structured review."
        ),
    }

    agent_lower = agent_id.lower()
    for key, response in archetypes.items():
        if key in agent_lower:
            return response

    return (
        f"Considering '{prompt}': As agent {agent_id}, I evaluate "
        "this prompt within the swarm's collective framework. The "
        "proposal merits deliberation and structured analysis before "
        "reaching consensus."
    )


def _classify_position(reasoning: str) -> str:
    """Classify an agent's reasoning into a deliberation position."""
    reasoning_lower = reasoning.lower()
    if any(
        w in reasoning_lower
        for w in (
            "support",
            "recommend",
            "agree",
            "proceed",
            "promising",
            "should",
            "forward",
            "engage",
        )
    ):
        return "for"
    if any(
        w in reasoning_lower
        for w in (
            "oppose",
            "reject",
            "disagree",
            "danger",
            "unsafe",
            "against",
        )
    ):
        return "against"
    return "neutral"


def _build_synthesis(
    round_result: Any,
    votes: dict[str, int],
    participant_count: int,
) -> str:
    """Build a human-readable synthesis from a deliberation round result."""
    outcome = getattr(round_result, "outcome", None)
    outcome_str = outcome.value if outcome else "unknown"
    score = getattr(round_result, "consensus_score", 0.0)
    changes = getattr(round_result, "position_changes", 0)

    parts: list[str] = [
        f"Deliberation outcome: {outcome_str}",
        f"Consensus score: {score:.2f}",
        f"Vote distribution: {votes.get('for', 0)} for, "
        f"{votes.get('against', 0)} against, "
        f"{votes.get('neutral', 0)} neutral",
        f"Position changes during round: {changes}",
    ]

    arguments = getattr(round_result, "arguments", [])
    if arguments:
        previews: list[str] = []
        for arg in arguments[:3]:
            agent = getattr(arg, "agent_id", "unknown")
            pos = getattr(getattr(arg, "position", None), "value", "?")
            reason = getattr(arg, "reasoning", "")
            truncated = reason[:120] + "..." if len(reason) > 120 else reason
            previews.append(f"[{agent} / {pos}] {truncated}")
        parts.append("Argument previews:\n" + "\n".join(previews))

    return "\n\n".join(parts)


def _synthesize_fallback(opinions: list[dict[str, Any]]) -> str:
    """Build a fallback synthesis from agent opinions."""
    support_count = sum(1 for o in opinions if o["position"] == "for")
    total = len(opinions) or 1
    if support_count > total / 2:
        return (
            f"Consensus emerges: {support_count}/{total} agents favor the "
            "proposal. The swarm inclines toward acceptance with minor "
            "reservations noted."
        )
    return (
        f"Deliberation inconclusive: {support_count}/{total} agents favor. "
        "Further rounds may be needed to resolve divergent positions."
    )


__all__ = [
    "PromptRequest",
    "PromptResponse",
    "router",
    "prompt_endpoint",
]
