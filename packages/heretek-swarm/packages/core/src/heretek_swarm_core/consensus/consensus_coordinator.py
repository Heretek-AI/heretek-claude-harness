"""
Consensus Coordinator — bridges agent actors with MAKER voting.

Orchestrates the full consensus flow:
1. Select domain-relevant agents via DomainSelector
2. Start a MAKER consensus process
3. Collect votes from each agent via run_with_llm()
4. Parse decisions and confidence scores
5. Compute and return the ConsensusResult

Handles agent unavailability (skip + warn) and LLM failures
(abstain with zero confidence). Each agent receives a prompt
requesting a structured response with a decision and confidence.
"""

import asyncio
import json
import re
import uuid
from typing import Any

import structlog

from heretek_swarm_core.consensus.domain_selector import DomainSelector
from heretek_swarm_core.consensus.maker import ConsensusResult, MAKERConsensus

logger = structlog.get_logger("ConsensusCoordinator")

# Module-level constant for repeated log message
_JSON_PARSE_FALLBACK_MSG = "JSON parse fallback in consensus"


# Prompt template sent to each agent for voting
_VOTE_PROMPT = """You are participating in a multi-agent consensus process.

QUESTION: {question}

Respond with a JSON object containing:
- "decision": your answer (a short phrase or single word like "yes", "no", "approve", "reject", or a brief categorical answer)  # noqa: E501
- "confidence": a number between 0.0 and 1.0 indicating how confident you are
- "reasoning": one sentence explaining your decision

Respond ONLY with the JSON object, no other text.
Example: {{"decision": "yes", "confidence": 0.85, "reasoning": "The evidence supports this approach."}}"""


# Prompt template for subsequent rounds — includes prior round summary
_MULTI_ROUND_PROMPT = """You are participating in round {round_number} of a multi-agent consensus process.  # noqa: E501
The previous round did not reach clear consensus. Below is a summary of the prior round votes and key arguments.  # noqa: E501

QUESTION: {question}

PREVIOUS ROUND SUMMARY:
{round_summary}

ARGUMENTS FOR (supporting "approve"/"yes"):
{args_for}

ARGUMENTS AGAINST (supporting "reject"/"no"):
{args_against}

Please reconsider your position in light of the above arguments.
Respond with a JSON object containing:
- "decision": your updated answer (a short phrase or single word like "yes", "no", "approve", "reject", or a brief categorical answer)  # noqa: E501
- "confidence": a number between 0.0 and 1.0 indicating how confident you are
- "reasoning": one sentence explaining your updated decision

Respond ONLY with the JSON object, no other text.
Example: {{"decision": "yes", "confidence": 0.85, "reasoning": "The evidence supports this approach."}}"""

# Pattern for extracting JSON from potentially messy LLM output
_JSON_PATTERN = re.compile(r"\{[^}]+\}")


class ConsensusCoordinator:
    """
    Bridges agent actors with MAKER consensus voting.

    Coordinates the end-to-end consensus flow by:
    - Using DomainSelector to find relevant agents for a question
    - Sending each agent the question via run_with_llm()
    - Parsing structured decision+confidence responses
    - Feedings votes into MAKERConsensus for aggregation

    Args:
        maker: MAKERConsensus instance for vote aggregation
        domain_selector: DomainSelector for agent selection
        actors: Dict mapping agent_id -> AgentActor instances
    """

    def __init__(
        self,
        maker: MAKERConsensus,
        domain_selector: DomainSelector,
        actors: dict[str, Any],
    ) -> None:
        self.maker = maker
        self.domain_selector = domain_selector
        self.actors = actors

    async def run_consensus(
        self,
        question: str,
        timeout: float = 120,
        max_rounds: int = 3,
    ) -> ConsensusResult | None:
        """
        Run a full consensus process on *question* with multi-round deliberation.

        Steps:
        1. Select domain-relevant agents via DomainSelector
        2. Start a MAKER consensus process
        3. Collect votes from each agent concurrently (with timeout)
        4. Parse each agent's response for decision + confidence
        5. Compute consensus via MAKER ahead-by-k voting
        6. If no consensus reached and max_rounds > 1, re-prompt agents with
           a summary of previous round arguments and re-collect votes

        Args:
            question: The question to reach consensus on
            timeout: Overall timeout in seconds (default 120)
            max_rounds: Maximum number of deliberation rounds (default 3)

        Returns:
            ConsensusResult on success, None on failure/timeout
        """
        consensus_id = str(uuid.uuid4())[:8]
        per_round_timeout = max(timeout / max_rounds, 10.0)

        logger.info(
            "consensus_started",
            consensus_id=consensus_id,
            question=question[:200],
            timeout=timeout,
            max_rounds=max_rounds,
        )

        # 1. Select agents
        selected_ids = self.domain_selector.score_agents(question)
        logger.info(
            "domain_selection_complete",
            consensus_id=consensus_id,
            selected_agents=selected_ids,
            agent_count=len(selected_ids),
        )

        round_history: list[dict[str, Any]] = []

        for round_num in range(1, max_rounds + 1):
            # 2. Start MAKER process for this round
            round_consensus_id = f"{consensus_id}-r{round_num}"
            self.maker.start_consensus(round_consensus_id)

            logger.info(
                "consensus_round_started",
                consensus_id=consensus_id,
                round_number=round_num,
                round_consensus_id=round_consensus_id,
            )

            # 3. Build the prompt for this round
            if round_num == 1:
                prompt = _VOTE_PROMPT.format(question=question)
            else:
                # Build argument exchange summary from prior round
                prior_result = round_history[-1].get("result")
                round_summary, args_for, args_against = self._build_argument_exchange(prior_result)
                prompt = _MULTI_ROUND_PROMPT.format(
                    round_number=round_num,
                    question=question,
                    round_summary=round_summary,
                    args_for=args_for,
                    args_against=args_against,
                )

                logger.info(
                    "consensus_round_argument_exchange",
                    consensus_id=consensus_id,
                    round_number=round_num,
                    args_for_count=args_for.count("\n"),
                    args_against_count=args_against.count("\n"),
                )

            # 4. Collect votes concurrently with timeout
            try:
                await asyncio.wait_for(
                    self._collect_all_votes(round_consensus_id, question, selected_ids, prompt),
                    timeout=per_round_timeout,
                )
            except TimeoutError:
                logger.warning(
                    "consensus_round_timeout",
                    consensus_id=consensus_id,
                    round_number=round_num,
                    timeout=per_round_timeout,
                )
                # Still try to compute with whatever votes we have
            except Exception as exc:
                logger.error(
                    "consensus_round_failed",
                    consensus_id=consensus_id,
                    round_number=round_num,
                    reason=str(exc),
                )

            # 5. Compute consensus
            result = self.maker.compute_consensus(round_consensus_id)

            round_record: dict[str, Any] = {
                "round_number": round_num,
                "consensus_id": round_consensus_id,
                "vote_count": len(self.maker.active_processes.get(round_consensus_id, [])),
                "result": result,
            }

            if result:
                round_record["consensus_score"] = result.confidence
                round_record["decision"] = result.decision
            else:
                round_record["consensus_score"] = 0.0
                round_record["decision"] = None

            round_history.append(round_record)

            logger.info(
                "consensus_round_completed",
                consensus_id=consensus_id,
                round_number=round_num,
                consensus_reached=result is not None,
                decision=round_record["decision"],
                consensus_score=round_record["consensus_score"],
                vote_count=round_record["vote_count"],
            )

            if result:
                # Consensus reached — enrich with round history and return
                result.metadata["round_history"] = [
                    {
                        "round_number": r["round_number"],
                        "consensus_score": r["consensus_score"],
                        "decision": r["decision"],
                        "vote_count": r["vote_count"],
                    }
                    for r in round_history
                ]
                result.metadata["total_rounds"] = round_num

                logger.info(
                    "consensus_completed",
                    consensus_id=consensus_id,
                    decision=result.decision,
                    confidence=result.confidence,
                    vote_count=len(result.votes),
                    red_flag_count=len(result.red_flags),
                    total_rounds=round_num,
                )

                # Cleanup all round MAKER states
                for r in round_history:
                    self.maker.cleanup_process(r["consensus_id"])

                return result

            # Cleanup this round's MAKER state before next round
            self.maker.cleanup_process(round_consensus_id)

        # All rounds exhausted without consensus
        logger.warning(
            "consensus_exhausted_rounds",
            consensus_id=consensus_id,
            total_rounds=max_rounds,
        )

        # Return the best result from the last round (may be None)
        last_result = round_history[-1]["result"]
        if last_result:
            last_result.metadata["round_history"] = [
                {
                    "round_number": r["round_number"],
                    "consensus_score": r["consensus_score"],
                    "decision": r["decision"],
                    "vote_count": r["vote_count"],
                }
                for r in round_history
            ]
            last_result.metadata["total_rounds"] = max_rounds

        return last_result

    def _build_argument_exchange(
        self,
        prior_result: ConsensusResult | None,
    ) -> tuple[str, str, str]:
        """
        Build an argument exchange summary from a prior round's result.

        Args:
            prior_result: The ConsensusResult from the previous round, or None.

        Returns:
            Tuple of (round_summary, args_for, args_against) strings.
        """
        if prior_result is None:
            return (
                "No clear votes were recorded in the previous round.",
                "- (none recorded)",
                "- (none recorded)",
            )

        # Summary of votes
        vote_lines: list[str] = []
        for vote in prior_result.votes:
            vote_lines.append(
                f"  {vote.agent_id}: {vote.decision} (confidence: {vote.confidence:.2f})"
            )
        round_summary = f"{len(prior_result.votes)} agents voted:\n" + "\n".join(vote_lines)

        # Arguments for/against
        args_for_lines: list[str] = []
        args_against_lines: list[str] = []
        for vote in prior_result.votes:
            reasoning = vote.metadata.get("reasoning", "")
            if not reasoning:
                continue
            line = f'- {vote.agent_id}: "{reasoning}"'
            if vote.decision in ("yes", "approve", "support", "agree"):
                args_for_lines.append(line)
            elif vote.decision in ("no", "reject", "oppose", "disagree"):
                args_against_lines.append(line)

        args_for = "\n".join(args_for_lines) if args_for_lines else "- (none)"
        args_against = "\n".join(args_against_lines) if args_against_lines else "- (none)"

        return round_summary, args_for, args_against

    async def _collect_all_votes(
        self,
        consensus_id: str,
        question: str,
        agent_ids: list[str],
        prompt: str | None = None,
    ) -> None:
        """Collect votes from all selected agents concurrently.

        Args:
            consensus_id: MAKER consensus process ID for this round
            question: Original question (unused if prompt is provided)
            agent_ids: List of agent IDs to collect votes from
            prompt: Optional override prompt (used for multi-round deliberation)
        """
        if prompt is None:
            prompt = _VOTE_PROMPT.format(question=question)

        tasks = [
            self._collect_single_vote(consensus_id, agent_id, prompt) for agent_id in agent_ids
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _collect_single_vote(
        self,
        consensus_id: str,
        agent_id: str,
        prompt: str,
    ) -> None:
        """
        Collect a vote from a single agent.

        Handles:
        - Agent not found in registry (skip + warn)
        - LLM failure (record as abstain with zero confidence)
        - Response parsing failure (record as abstain with zero confidence)
        """
        actor = self.actors.get(agent_id)

        if actor is None:
            logger.warning(
                "agent_vote_collected",
                consensus_id=consensus_id,
                agent_id=agent_id,
                status="unavailable",
                decision="abstain",
                confidence=0.0,
            )
            self.maker.add_vote(
                consensus_id=consensus_id,
                agent_id=agent_id,
                decision="abstain",
                confidence=0.0,
                metadata={"status": "agent_unavailable"},
            )
            return

        try:
            # Call the agent's LLM via run_with_llm
            raw_response = await actor.run_with_llm(prompt, timeout=30)
            decision, confidence = self._parse_response(raw_response)
            reasoning = self._extract_reasoning(raw_response)

            logger.info(
                "agent_vote_collected",
                consensus_id=consensus_id,
                agent_id=agent_id,
                status="success",
                decision=decision,
                confidence=confidence,
            )
            self.maker.add_vote(
                consensus_id=consensus_id,
                agent_id=agent_id,
                decision=decision,
                confidence=confidence,
                metadata={"reasoning": reasoning} if reasoning else None,
            )

        except Exception as exc:
            logger.warning(
                "agent_vote_collected",
                consensus_id=consensus_id,
                agent_id=agent_id,
                status="llm_failure",
                decision="abstain",
                confidence=0.0,
                error=str(exc)[:200],
            )
            self.maker.add_vote(
                consensus_id=consensus_id,
                agent_id=agent_id,
                decision="abstain",
                confidence=0.0,
                metadata={"status": "llm_failure", "error": str(exc)[:200]},
            )

    @staticmethod
    def _parse_response(raw: str) -> tuple[str, float]:
        """
        Parse an agent's LLM response into (decision, confidence).

        Attempts:
        1. JSON parse of the full response
        2. Regex extraction of a JSON object substring
        3. Fallback: first meaningful word as decision, 0.5 confidence

        Args:
            raw: Raw LLM response string

        Returns:
            Tuple of (decision, confidence)
        """
        if not raw or not raw.strip():
            return "abstain", 0.0

        text = raw.strip()

        # Try 1: Direct JSON parse
        try:
            data = json.loads(text)
            return _extract_decision_confidence(data)
        except (json.JSONDecodeError, ValueError):
            logger.warning(_JSON_PARSE_FALLBACK_MSG, exc_info=True)

        # Try 2: Regex extract JSON substring
        match = _JSON_PATTERN.search(text)
        if match:
            try:
                data = json.loads(match.group())
                return _extract_decision_confidence(data)
            except (json.JSONDecodeError, ValueError):
                logger.warning(_JSON_PARSE_FALLBACK_MSG, exc_info=True)

        # Try 3: Look for common decision patterns in free text
        lower = text.lower()
        words = [re.sub(r"[^a-z]", "", w) for w in lower.split()]
        for keyword in ("yes", "no", "approve", "reject", "support", "oppose"):
            if keyword in words:
                return keyword, 0.5

        # Fallback: first meaningful word
        for word in words:
            if word and len(word) <= 20:
                return word, 0.3

        return "abstain", 0.0

    @staticmethod
    def _extract_reasoning(raw: str) -> str:
        """
        Extract reasoning from an agent's LLM response.

        Args:
            raw: Raw LLM response string

        Returns:
            The reasoning string, or empty string if not found
        """
        if not raw or not raw.strip():
            return ""

        text = raw.strip()

        # Try direct JSON parse
        try:
            data = json.loads(text)
            return str(data.get("reasoning", ""))
        except (json.JSONDecodeError, ValueError):
            logger.warning(_JSON_PARSE_FALLBACK_MSG, exc_info=True)

        # Try regex JSON extraction
        match = _JSON_PATTERN.search(text)
        if match:
            try:
                data = json.loads(match.group())
                return str(data.get("reasoning", ""))
            except (json.JSONDecodeError, ValueError):
                logger.warning(_JSON_PARSE_FALLBACK_MSG, exc_info=True)

        return ""


def _extract_decision_confidence(data: dict) -> tuple[str, float]:
    """Extract decision and confidence from a parsed JSON dict."""
    decision = str(data.get("decision", "abstain")).strip().lower()
    try:
        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
    except (TypeError, ValueError):
        confidence = 0.5

    if not decision:
        decision = "abstain"

    return decision, confidence
