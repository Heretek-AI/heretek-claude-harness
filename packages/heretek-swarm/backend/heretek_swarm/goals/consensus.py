"""
GoalConsensus — goal-specific consensus voting with 60% threshold.

Wraps :class:`ConsensusCoordinator` to apply the D024 threshold
(≥60% approval excluding abstain votes) to goal proposals.

Close splits (50–60% approval) trigger a second refinement round with  # noqa: RUF002
argument exchange. After 2 rounds, Steward + Arbiter serve as tie-breakers.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.goals.models import Goal, Vote

if TYPE_CHECKING:
    from heretek_swarm_core.consensus.consensus_coordinator import ConsensusCoordinator

logger = structlog.get_logger("GoalConsensus")

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_GOAL_VOTE_PROMPT = """You are participating in a vote on a proposed strategic goal for the Heretek autonomous swarm.  # noqa: E501

GOAL TITLE: {title}

GOAL DESCRIPTION:
{description}

SUCCESS CRITERIA:
{success_criteria}

Vote on whether this goal should be accepted. Consider:
- Is it achievable within a small number of implementation cycles?
- Does it advance the swarm's autonomy or capability?
- Are the success criteria measurable and realistic?

Respond with a JSON object containing:
- "decision": one of "approve", "reject", or "abstain"
- "confidence": a number between 0.0 and 1.0
- "reasoning": one sentence explaining your decision

Respond ONLY with the JSON object, no other text.
Example: {{"decision": "approve", "confidence": 0.8, "reasoning": "This goal is well-scoped and addresses a real gap."}}"""


_REFINEMENT_PROMPT = """You are participating in round 2 of a goal consensus vote. The first round was too close to call (approval within 50-60%).  # noqa: E501

GOAL TITLE: {title}

GOAL DESCRIPTION:
{description}

SUCCESS CRITERIA:
{success_criteria}

ROUND 1 ARGUMENTS FOR (approve):
{args_for}

ROUND 1 ARGUMENTS AGAINST (reject):
{args_against}

Please reconsider your position in light of the above arguments.
Respond with a JSON object containing:
- "decision": one of "approve", "reject", or "abstain"
- "confidence": a number between 0.0 and 1.0
- "reasoning": one sentence explaining your updated decision

Respond ONLY with the JSON object, no other text.
Example: {{"decision": "approve", "confidence": 0.85, "reasoning": "The counterarguments are weak; the goal remains sound."}}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Decision keywords that count as "approve"
_APPROVE_KEYWORDS = frozenset({"approve", "yes", "support", "agree", "accept"})

# Decision keywords that count as "reject"
_REJECT_KEYWORDS = frozenset({"reject", "no", "oppose", "disagree", "decline"})


def _normalise_decision(decision: str) -> str:
    """Map a free-form agent decision string to ``approve``, ``reject``, or ``abstain``."""
    lower = decision.strip().lower()
    if lower in _APPROVE_KEYWORDS:
        return "approve"
    if lower in _REJECT_KEYWORDS:
        return "reject"
    return "abstain"


def _build_goal_vote_prompt(goal: Goal) -> str:
    """Build the round-1 vote prompt from a Goal."""
    criteria_lines = "\n".join(f"- {c}" for c in goal.success_criteria)
    return _GOAL_VOTE_PROMPT.format(
        title=goal.title,
        description=goal.description,
        success_criteria=criteria_lines or "(none)",
    )


def _build_refinement_prompt(goal: Goal, args_for: str, args_against: str) -> str:
    """Build the round-2 refinement prompt."""
    criteria_lines = "\n".join(f"- {c}" for c in goal.success_criteria)
    return _REFINEMENT_PROMPT.format(
        title=goal.title,
        description=goal.description,
        success_criteria=criteria_lines or "(none)",
        args_for=args_for or "(none)",
        args_against=args_against or "(none)",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class GoalConsensus:
    """Applies D024 goal voting (≥60% threshold) on top of MAKER consensus.

    Args:
        coordinator: A :class:`ConsensusCoordinator` for collecting agent votes.
        steward_agent_id: Agent ID of the Steward (tie-breaker).
        arbiter_agent_id: Agent ID of the Arbiter (tie-breaker).
    """

    def __init__(
        self,
        coordinator: ConsensusCoordinator,
        steward_agent_id: str = "steward",
        arbiter_agent_id: str = "arbiter",
    ) -> None:
        self.coordinator = coordinator
        self.steward_agent_id = steward_agent_id
        self.arbiter_agent_id = arbiter_agent_id

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run_goal_consensus(
        self,
        goal: Goal,
        actors: dict[str, Any],
        timeout: float = 120,
    ) -> tuple[bool, list[Vote], int]:
        """Run goal-specific consensus voting with 60% threshold.

        Flow:
        1. Round 1 — prompt all agents to vote approve/reject/abstain.
        2. Apply the 60% rule excluding abstentions.
        3. Close splits (≥50% but <60%) trigger a refinement round.
        4. After 2 rounds without resolution, Steward + Arbiter
           serve as tie-breakers (their votes are final).

        Args:
            goal: The Goal to vote on.
            actors: Dict mapping agent_id → AgentActor instances.
            timeout: Overall timeout in seconds.

        Returns:
            Tuple of ``(accepted: bool, votes: list[Vote], rounds: int)``.
        """
        per_round_timeout = max(timeout / 2, 30.0)

        # --- Round 1 -------------------------------------------------------
        prompt = _build_goal_vote_prompt(goal)

        logger.info(
            "goal_consensus_round_started",
            goal_id=goal.id,
            round_number=1,
            goal_title=goal.title[:100],
        )

        r1_votes = await self._collect_goal_votes(goal, actors, prompt, per_round_timeout)

        approved, close = self._evaluate_threshold(r1_votes)

        logger.info(
            "goal_consensus_round_completed",
            goal_id=goal.id,
            round_number=1,
            vote_count=len(r1_votes),
            approval=self._approval_ratio(r1_votes),
            approved=approved,
            close_split=close,
        )

        if approved:
            return True, r1_votes, 1

        if not close:
            # Clear rejection or complete split — rejected
            return False, r1_votes, 1

        # --- Round 2: refinement -------------------------------------------
        args_for, args_against = self._extract_arguments(r1_votes)
        r2_prompt = _build_refinement_prompt(goal, args_for, args_against)

        logger.info(
            "goal_consensus_round_started",
            goal_id=goal.id,
            round_number=2,
            goal_title=goal.title[:100],
            reason="close_split_refinement",
        )

        r2_votes = await self._collect_goal_votes(goal, actors, r2_prompt, per_round_timeout)

        approved, _ = self._evaluate_threshold(r2_votes)

        logger.info(
            "goal_consensus_round_completed",
            goal_id=goal.id,
            round_number=2,
            vote_count=len(r2_votes),
            approval=self._approval_ratio(r2_votes),
            approved=approved,
        )

        if approved:
            return True, r2_votes, 2

        # --- Tie-break via Steward + Arbiter -------------------------------
        return await self._tie_break(goal, actors, r2_votes, per_round_timeout)

    # ------------------------------------------------------------------
    # Vote collection
    # ------------------------------------------------------------------

    async def _collect_goal_votes(
        self,
        goal: Goal,
        actors: dict[str, Any],
        prompt: str,
        timeout: float,
    ) -> list[Vote]:
        """Collect votes from all available agents.

        Uses the coordinator to run a single-round MAKER consensus,
        then converts the raw MAKER votes into goal-domain ``Vote``
        objects with normalised decisions.
        """
        try:
            result = await asyncio.wait_for(
                self.coordinator.run_consensus(
                    question=prompt,
                    timeout=timeout,
                    max_rounds=1,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            logger.warning(
                "goal_vote_collection_timeout",
                goal_id=goal.id,
                timeout=timeout,
            )
            result = None
        except Exception as exc:
            logger.error(
                "goal_vote_collection_failed",
                goal_id=goal.id,
                error=str(exc)[:200],
            )
            result = None

        if result is None or not result.votes:
            return []

        votes: list[Vote] = []
        for mv in result.votes:
            normalised = _normalise_decision(mv.decision)
            votes.append(
                Vote(
                    agent_id=mv.agent_id,
                    decision=normalised,  # type: ignore[arg-type]
                    confidence=mv.confidence,
                    rationale=mv.metadata.get("reasoning", ""),
                )
            )
        return votes

    # ------------------------------------------------------------------
    # Threshold evaluation
    # ------------------------------------------------------------------

    @staticmethod
    def _approval_ratio(votes: list[Vote]) -> float:
        """Compute approve / (approve + reject), ignoring abstains.

        Returns 0.0 when there are no approve or reject votes.
        """
        approve_count = sum(1 for v in votes if v.decision == "approve")
        reject_count = sum(1 for v in votes if v.decision == "reject")
        total = approve_count + reject_count
        if total == 0:
            return 0.0
        return approve_count / total

    def _evaluate_threshold(self, votes: list[Vote]) -> tuple[bool, bool]:
        """Evaluate votes against the 60% threshold.

        Returns:
            ``(accepted, close_split)`` where *close_split* means
            approval is ≥50% but <60% — triggering a refinement round.
        """
        if not votes:
            return False, False

        ratio = self._approval_ratio(votes)
        approve_count = sum(1 for v in votes if v.decision == "approve")
        reject_count = sum(1 for v in votes if v.decision == "reject")

        if approve_count + reject_count == 0:
            # All abstained — reject
            return False, False

        if ratio >= 0.6:
            return True, False

        # Close split: within 10 percentage points of 60%
        if ratio >= 0.5:
            return False, True

        return False, False

    # ------------------------------------------------------------------
    # Argument extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_arguments(votes: list[Vote]) -> tuple[str, str]:
        """Extract for/against arguments from round-1 votes."""
        args_for: list[str] = []
        args_against: list[str] = []

        for v in votes:
            if not v.rationale:
                continue
            line = f'- {v.agent_id}: "{v.rationale}"'
            if v.decision == "approve":
                args_for.append(line)
            elif v.decision == "reject":
                args_against.append(line)

        return (
            "\n".join(args_for) if args_for else "(none)",
            "\n".join(args_against) if args_against else "(none)",
        )

    # ------------------------------------------------------------------

    # ------------------------------------------------------------------

    async def _tie_break(
        self,
        goal: Goal,
        actors: dict[str, Any],
        prior_votes: list[Vote],
        timeout: float,
    ) -> tuple[bool, list[Vote], int]:
        """Steward + Arbiter serve as tie-breakers after 2 rounds.

        If Steward or Arbiter voted in prior rounds, their round-2
        decisions are final.  Otherwise they are prompted directly.
        """
        logger.info(
            "goal_consensus_tie_break",
            goal_id=goal.id,
            steward_id=self.steward_agent_id,
            arbiter_id=self.arbiter_agent_id,
        )

        # Check if Steward/Arbiter already voted in prior rounds
        steward_vote = next((v for v in prior_votes if v.agent_id == self.steward_agent_id), None)
        arbiter_vote = next((v for v in prior_votes if v.agent_id == self.arbiter_agent_id), None)

        tie_votes: list[Vote] = []
        for agent_id, existing in [
            (self.steward_agent_id, steward_vote),
            (self.arbiter_agent_id, arbiter_vote),
        ]:
            if existing is not None:
                tie_votes.append(existing)
                continue

            actor = actors.get(agent_id)
            if actor is None:
                logger.warning(
                    "tie_breaker_unavailable",
                    goal_id=goal.id,
                    agent_id=agent_id,
                )
                continue

            try:
                prompt = (
                    f"As a tie-breaker after 2 rounds of goal consensus, "
                    f"cast your final vote on: {goal.title}\n\n"
                    f"{goal.description}\n\n"
                    f'Respond: {{"decision": "approve"|"reject", "confidence": 0.0-1.0, "reasoning": "..."}}'
                )
                raw = await asyncio.wait_for(
                    actor.run_with_llm(prompt, timeout=30),
                    timeout=min(timeout, 30),
                )
                import json
                import re

                decision = "abstain"
                confidence = 0.5
                reasoning = ""
                try:
                    data = json.loads(raw)
                    decision = _normalise_decision(str(data.get("decision", "")))
                    confidence = float(data.get("confidence", 0.5))
                    reasoning = str(data.get("reasoning", ""))
                except (json.JSONDecodeError, ValueError):
                    m = re.search(r"\{[^}]+\}", raw)
                    if m:
                        try:
                            data = json.loads(m.group())
                            decision = _normalise_decision(str(data.get("decision", "")))
                            confidence = float(data.get("confidence", 0.5))
                            reasoning = str(data.get("reasoning", ""))
                        except (json.JSONDecodeError, ValueError):
                            logger.debug("Goal consensus JSON parse fallback", exc_info=True)

                tie_votes.append(
                    Vote(
                        agent_id=agent_id,
                        decision=decision,  # type: ignore[arg-type]
                        confidence=confidence,
                        rationale=reasoning,
                    )
                )
            except Exception as exc:
                logger.warning(
                    "tie_breaker_failed",
                    goal_id=goal.id,
                    agent_id=agent_id,
                    error=str(exc)[:200],
                )

        # Combine prior votes with tie-breaker votes
        all_votes = list(prior_votes)
        for tv in tie_votes:
            # Replace if already present
            for i, pv in enumerate(all_votes):
                if pv.agent_id == tv.agent_id:
                    all_votes[i] = tv
                    break
            else:
                all_votes.append(tv)

        approved, _ = self._evaluate_threshold(all_votes)
        if approved:
            return True, all_votes, 3
        return False, all_votes, 3
