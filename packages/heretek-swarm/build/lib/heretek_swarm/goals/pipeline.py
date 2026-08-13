"""
Goal pipeline — bridges the goal store, proposer, and consensus layers
so the autonomous main loop can propose and vote on strategic goals.

Public entry points:
- ``run_goal_cycle(store, metis, coordinator, actors, historian)``
  Called from _trigger_periodic_analysis() every 30 cycles. Implements:
  1. If any goal has status='proposed', run consensus on it.
  2. If no proposed goals, generate a new proposal via Metis + persist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.goals.consensus import GoalConsensus

if TYPE_CHECKING:
    from heretek_swarm.goals.models import Goal
    from heretek_swarm.goals.store import FileGoalStore

logger = structlog.get_logger("GoalPipeline")


async def _log_historian(historian: Any, event_type: str, data: dict[str, Any]) -> None:
    """Log an event to the Historian actor if available."""
    if historian is None:
        return
    try:
        await historian.log_event(event_type, "goal_pipeline", data)
    except Exception as exc:
        logger.warning(
            "historian_log_failed",
            event_type=event_type,
            error=str(exc)[:200],
        )


async def run_goal_cycle(
    store: FileGoalStore,
    metis: Any,
    coordinator: Any,
    actors: dict[str, Any],
    historian: Any,
) -> Goal | None:
    """Run one goal pipeline cycle.

    Flow:
    1. Find the first goal with status='proposed'. If found, run consensus.
    2. If no proposed goals, generate a new proposal via Metis.

    Returns the affected Goal on success, or None if skipped.
    """
    # --- Check for proposed goals needing votes -------------------------------
    all_goals = store.load_all()
    proposed = [g for g in all_goals if g.status == "proposed"]

    if proposed:
        goal = proposed[0]
        logger.info("goal_consensus_triggered", goal_id=goal.id, goal_title=goal.title[:100])

        # Run consensus
        consensus = GoalConsensus(coordinator=coordinator)
        try:
            accepted, votes, rounds = await consensus.run_goal_consensus(
                goal=goal,
                actors=actors,
                timeout=120,
            )
        except Exception as exc:
            logger.error(
                "goal_consensus_failed",
                goal_id=goal.id,
                error=str(exc)[:200],
            )
            await _log_historian(
                historian,
                "goal_consensus_error",
                {"goal_id": goal.id, "error": str(exc)[:200]},
            )
            # Don't crash — just skip this cycle
            return None

        # Persist each vote
        for vote in votes:
            store.add_vote(goal.id, vote)
        goal = store.load(goal.id)  # refresh after votes

        if accepted:
            store.update_status(goal.id, "accepted")
            updated = store.load(goal.id)
            await _log_historian(
                historian,
                "goal_accepted",
                {
                    "goal_id": goal.id,
                    "title": goal.title,
                    "vote_count": len(votes),
                    "rounds": rounds,
                },
            )
            logger.info("goal_accepted", goal_id=goal.id, rounds=rounds)
            return updated
        store.update_status(goal.id, "rejected")
        updated = store.load(goal.id)
        await _log_historian(
            historian,
            "goal_rejected",
            {
                "goal_id": goal.id,
                "title": goal.title,
                "vote_count": len(votes),
                "rounds": rounds,
            },
        )
        logger.info("goal_rejected", goal_id=goal.id, rounds=rounds)
        return updated

    # --- No proposed goals — generate a new proposal --------------------------
    if metis is None:
        logger.warning("goal_cycle_skipped_no_metis")
        return None

    try:
        result = await metis.generate_goal_proposal()
    except Exception as exc:
        logger.error(
            "goal_proposal_generation_failed",
            error=str(exc)[:200],
        )
        await _log_historian(
            historian,
            "goal_proposal_error",
            {"error": str(exc)[:200]},
        )
        return None

    goal = result.get("goal")
    if goal is None:
        logger.warning("goal_proposal_returned_none")
        return None

    store.save(goal)
    await _log_historian(
        historian,
        "goal_proposed",
        {
            "goal_id": goal.id,
            "title": goal.title,
            "description_preview": goal.description[:200],
        },
    )
    logger.info(
        "goal_proposed",
        goal_id=goal.id,
        title=goal.title[:100],
    )
    return goal
