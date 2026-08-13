"""
Deliberation Orchestrator — extracts triad deliberation, MAKER consensus,
and routed-task dispatch logic from AutonomousSwarm.

These methods coordinate multi-agent interactions but do not manage
actor lifecycle or the main processing loop.
"""

import asyncio
from typing import Any

import structlog

from heretek_swarm.consensus.consensus_coordinator import ConsensusCoordinator
from heretek_swarm.consensus.domain_selector import DomainSelector
from heretek_swarm.consensus.maker import MAKERConsensus

logger = structlog.get_logger(__name__)


class DeliberationOrchestrator:
    """Orchestrates triad deliberation, MAKER consensus, and routed-task dispatch.

    Takes supervisor and consensus engine references — these are shared
    with AutonomousSwarm and mutated during ``initialize()``, so the
    orchestrator always sees the latest state.
    """

    def __init__(
        self,
        supervisor: Any,
        consensus: MAKERConsensus | None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self._supervisor = supervisor
        self._consensus = consensus
        self._config = config or {}

    async def run_deliberation(
        self,
        prompt: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Run a triad deliberation: route a prompt through Steward → Alpha → Beta → Charlie.
        """
        logger.info("run_deliberation_started", prompt=prompt, timeout=timeout)

        supervisor_actors = self._supervisor.actors if self._supervisor else {}
        steward = supervisor_actors.get("steward")
        if steward is None:
            raise RuntimeError(
                "Steward agent not found in supervisor.actors — "
                "cannot coordinate triad. Ensure spawn_all_actors() completed successfully."
            )

        try:
            delib_id = await self._initiate_triad(steward, prompt)
            await self._poll_triad_completion(supervisor_actors, delib_id, timeout)
        except TimeoutError:
            logger.warning("deliberation_timeout", prompt=prompt)
        except Exception as exc:
            logger.error("deliberation_failed", prompt=prompt, error=str(exc))

        results = self._collect_triad_results(supervisor_actors)
        logger.info(
            "run_deliberation_complete",
            alpha_count=len(results.get("alpha", {}).get("analyses", [])),
            beta_count=len(results.get("beta", {}).get("analyses", [])),
            charlie_count=len(results.get("charlie", {}).get("challenges", [])),
        )

        await self._handoff_to_coder(supervisor_actors, steward, results, prompt, timeout)
        return results

    async def _initiate_triad(self, steward: Any, prompt: str) -> str:
        """Initiate triad deliberation and return the deliberation ID."""
        deliberation_record = await steward.coordinate_triad(
            topic=prompt, triad_members=["alpha", "beta", "charlie"],
        )
        delib_id: str = (
            deliberation_record
            if isinstance(deliberation_record, str)
            else deliberation_record.get("session_id", "")
        )
        logger.info("deliberation_initiated", deliberation_id=delib_id)
        return delib_id

    async def _poll_triad_completion(
        self, actors: dict[str, Any], delib_id: str, timeout: int
    ) -> None:
        """Poll at 0.5s intervals until all triad agents complete or timeout."""
        elapsed = 0.0
        interval = 0.5
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval

            alpha = actors.get("alpha")
            beta = actors.get("beta")
            charlie = actors.get("charlie")

            alpha_done = bool(alpha and len(getattr(alpha, "analysis_history", [])) > 0)
            beta_done = bool(beta and delib_id and delib_id in getattr(beta, "_analyses", {}))
            charlie_done = bool(charlie and delib_id and delib_id in getattr(charlie, "_challenges", {}))

            logger.info(
                "deliberation_polling", elapsed=round(elapsed, 1),
                alpha_done=alpha_done, beta_done=beta_done, charlie_done=charlie_done,
            )

            if alpha_done and beta_done and charlie_done:
                logger.info("deliberation_all_agents_complete", elapsed=round(elapsed, 1))
                break

    @staticmethod
    def _collect_triad_results(actors: dict[str, Any]) -> dict[str, Any]:
        """Read results from per-agent state attributes."""
        results: dict[str, Any] = {}
        for agent_id in ["alpha", "beta", "charlie"]:
            agent = actors.get(agent_id)
            if agent is None:
                results[agent_id] = {"error": f"Agent {agent_id} not found"}
                continue
            if agent_id == "alpha":
                history = getattr(agent, "analysis_history", [])
                results[agent_id] = {"analyses": history[-3:] if history else []}
            elif agent_id == "beta":
                analyses = getattr(agent, "_analyses", {})
                results[agent_id] = {"analyses": list(analyses.values())[-3:] if analyses else []}
            elif agent_id == "charlie":
                challenges = getattr(agent, "_challenges", {})
                results[agent_id] = {"challenges": list(challenges.values())[-3:] if challenges else []}
        return results

    async def _handoff_to_coder(
        self, actors: dict[str, Any], steward: Any,
        results: dict[str, Any], prompt: str, timeout: int,
    ) -> None:
        """Best-effort specialist handoff to Coder agent."""
        coder = actors.get("coder")
        if coder is None:
            logger.info("specialist_handoff_failed", reason="Coder agent not in supervisor.actors")
            return

        try:
            requirements = self._extract_requirements(results)
            task_data: dict[str, Any] = {
                "description": prompt,
                "requirements": requirements if requirements else ["Implement as described"],
                "language": "python", "include_tests": True, "include_docs": True,
            }

            logger.info("specialist_handoff_initiated", target_agent="coder",
                        task_type="implement_task", prompt_preview=prompt[:200])

            pre_counter: int = getattr(coder, "_task_counter", 0)
            message_id = await steward.route_to_agent(
                agent_name="coder", task_type="implement_task", task_data=task_data,
            )

            if not message_id:
                logger.warning("specialist_handoff_failed", reason="route_to_agent returned empty")
                return

            specialist_output = await self._poll_coder_completion(
                actors, pre_counter, timeout
            )
            if specialist_output:
                results["specialist_output"] = specialist_output
                logger.info("specialist_handoff_complete", target_agent="coder",
                            has_code=bool(specialist_output.get("code")))
            else:
                logger.warning("specialist_handoff_failed", reason="Coder task timed out")

        except Exception as exc:
            logger.warning("specialist_handoff_failed", reason=str(exc))

    @staticmethod
    def _extract_requirements(results: dict[str, Any]) -> list[str]:
        """Extract requirements from triad results."""
        requirements: list[str] = []
        for entry in results.get("alpha", {}).get("analyses", [])[-2:]:
            if isinstance(entry, dict):
                for key in ("decision", "analysis", "summary"):
                    if key in entry:
                        requirements.append(f"Alpha {key}: {entry[key]}")
                        break
        for entry in results.get("beta", {}).get("analyses", [])[-2:]:
            if isinstance(entry, dict):
                for key in ("analysis", "validation", "decision"):
                    if key in entry:
                        requirements.append(f"Beta {key}: {entry[key]}")
                        break
        for entry in results.get("charlie", {}).get("challenges", [])[-2:]:
            if isinstance(entry, dict):
                if "challenges" in entry:
                    requirements.append(f"Charlie flags: {entry['challenges']}")
                elif "challenge" in entry:
                    requirements.append(f"Charlie: {entry['challenge']}")
        return requirements

    async def _poll_coder_completion(
        self, actors: dict[str, Any], pre_counter: int, timeout: int
    ) -> dict[str, Any] | None:
        """Poll Coder for task completion, return specialist output or None."""
        coder_timeout = min(max(timeout / 2, 5), 60)
        coder_elapsed = 0.0
        interval = 0.5

        while coder_elapsed < coder_timeout:
            await asyncio.sleep(interval)
            coder_elapsed += interval
            coder = actors.get("coder")
            if coder is None:
                break
            post_counter = getattr(coder, "_task_counter", 0)
            if isinstance(post_counter, int) and post_counter > pre_counter:
                return self._collect_coder_output(coder)
        return None

    @staticmethod
    def _collect_coder_output(coder: Any) -> dict[str, Any]:
        """Collect output from Coder's _tasks and _code_snippets."""
        tasks: dict = getattr(coder, "_tasks", {})
        snippets: dict = getattr(coder, "_code_snippets", {})

        if tasks:
            last_key = max(tasks)
            last_task = tasks[last_key]
            return {
                "task_id": getattr(last_task, "id", last_key),
                "status": getattr(last_task, "status", "unknown"),
                "code": getattr(last_task, "generated_code", ""),
                "tests": getattr(last_task, "tests", None),
                "documentation": getattr(last_task, "documentation", None),
            }

        if snippets:
            last_key = max(snippets)
            last_snippet = snippets[last_key]
            return {
                "code": getattr(last_snippet, "code", ""),
                "language": str(getattr(last_snippet, "language", "")),
                "purpose": getattr(last_snippet, "purpose", ""),
            }

        return {}

    async def run_consensus(
        self,
        question: str,
        timeout: float = 120,
        max_rounds: int = 3,
    ) -> dict[str, Any]:
        """
        Run a MAKER consensus process with domain-based agent selection.

        Uses DomainSelector to find question-relevant agents, then orchestrates
        MAKER ahead-by-k voting via ConsensusCoordinator. Each selected agent
        produces a structured vote (decision + confidence) through its LLM.

        Args:
            question: The question to reach consensus on.
            timeout: Overall timeout in seconds (default 120).
            max_rounds: Reserved for future multi-round deliberation.

        Returns:
            Structured dict with keys:
            - decision: Winning decision string
            - confidence: Overall confidence score (0.0-1.0)
            - votes: List of per-agent vote dicts
            - red_flags: List of red flag messages
            - reasoning: Aggregated reasoning from votes
            - consensus_id: Unique process identifier

            Returns an error dict if consensus cannot be initiated
            (e.g. no supervisor, no consensus engine).
        """
        logger.info(
            "run_consensus_started",
            question=question[:200],
            timeout=timeout,
            max_rounds=max_rounds,
        )

        # Guard: supervisor must be available
        if self._supervisor is None:
            logger.error("run_consensus_no_supervisor")
            return {
                "decision": "error",
                "confidence": 0.0,
                "votes": [],
                "red_flags": ["Supervisor not initialized"],
                "reasoning": "Cannot run consensus without actor supervisor",
            }

        # Guard: consensus engine must be available
        if self._consensus is None:
            logger.error("run_consensus_no_consensus_engine")
            return {
                "decision": "error",
                "confidence": 0.0,
                "votes": [],
                "red_flags": ["Consensus engine not initialized"],
                "reasoning": "Cannot run consensus without MAKER consensus engine",
            }

        # Build domain selector from character files
        domain_selector = DomainSelector()

        # Build coordinator with real actors
        coordinator = ConsensusCoordinator(
            maker=self._consensus,
            domain_selector=domain_selector,
            actors=self._supervisor.actors,
        )

        # Run consensus
        result = await coordinator.run_consensus(
            question=question,
            timeout=timeout,
            max_rounds=max_rounds,
        )

        if result is None:
            logger.warning("run_consensus_no_result", question=question[:200])
            return {
                "decision": "no_consensus",
                "confidence": 0.0,
                "votes": [],
                "red_flags": ["No consensus reached"],
                "reasoning": "MAKER could not reach a decisive consensus",
            }

        # Build structured response
        vote_dicts = [
            {
                "agent_id": v.agent_id,
                "decision": v.decision,
                "confidence": v.confidence,
                "metadata": v.metadata,
            }
            for v in result.votes
        ]

        # Aggregate reasoning from non-abstain votes
        reasoning_parts = []
        for v in result.votes:
            if v.decision != "abstain" and v.metadata.get("reasoning"):
                reasoning_parts.append(f"{v.agent_id}: {v.metadata['reasoning']}")

        response = {
            "decision": result.decision,
            "confidence": result.confidence,
            "votes": vote_dicts,
            "red_flags": result.red_flags,
            "reasoning": "; ".join(reasoning_parts) if reasoning_parts else "No reasoning captured",
            "consensus_id": result.metadata.get("consensus_id", "unknown"),
            "round_history": result.metadata.get("round_history", []),
            "total_rounds": result.metadata.get("total_rounds", 1),
        }

        logger.info(
            "run_consensus_complete",
            decision=response["decision"],
            confidence=response["confidence"],
            vote_count=len(vote_dicts),
            red_flag_count=len(response["red_flags"]),
        )

        return response

    async def run_routed_task(
        self,
        agent_name: str,
        task_type: str,
        task_data: dict[str, Any],
        timeout: int = 30,
    ) -> dict[str, Any]:
        """
        Route a task to a specific agent using Steward's ``route_to_agent()``
        and log the event to Historian.

        This is a one-shot dispatch path for the CLI ``--target-agent``
        flag — it sends a structured task to a single agent (cast-style
        delivery) rather than orchestrating a triad deliberation.

        Args:
            agent_name: Target agent ID (e.g. ``"coder"``).
            task_type: Machine-readable task label (e.g. ``"code_analysis"``).
            task_data: Arbitrary payload dict for the receiving agent.
            timeout: Maximum wall-clock seconds to sleep for async mailbox
                     processing (capped at 30). The agent's internal handler
                     deadline should be shorter; this sleep is a best-effort
                     wait for the mailbox to be consumed.

        Returns:
            A dict with dispatch status, target agent, task type, and the
            message ID from Steward's send_to_actor on success::

                {"status": "dispatched", "target_agent": "coder",
                 "task_type": "code_analysis", "message_id": "abc123"}

            On dispatch failure: ``{"status": "failed",
            "error": "route_to_agent returned empty"}``

        Raises:
            RuntimeError: If Steward agent is not in the actor registry.
        """
        logger.info(
            "run_routed_task_started",
            agent_name=agent_name,
            task_type=task_type,
            timeout=timeout,
        )

        supervisor_actors = self._supervisor.actors if self._supervisor else {}
        steward = supervisor_actors.get("steward")
        if steward is None:
            raise RuntimeError(
                "Steward agent not found in supervisor.actors — "
                "cannot route task. Ensure spawn_all_actors() "
                "completed successfully."
            )

        message_id = await steward.route_to_agent(
            agent_name=agent_name,
            task_type=task_type,
            task_data=task_data,
        )

        if not message_id:
            logger.warning(
                "run_routed_task_dispatch_failed",
                agent_name=agent_name,
                task_type=task_type,
            )
            return {
                "status": "failed",
                "error": "route_to_agent returned empty",
            }

        logger.info(
            "run_routed_task_dispatched",
            agent_name=agent_name,
            task_type=task_type,
            message_id=message_id,
        )

        # Poll at 0.5 s intervals for the target agent to process the
        # routed task.  For Coder we watch _task_counter increment; for
        # other agents we check a generic state attribute.  Timeout at
        # the configured limit; return partial/empty results on timeout.
        target_agent = supervisor_actors.get(agent_name)
        pre_counter: int | None = None
        if target_agent is not None:
            pre_counter = getattr(target_agent, "_task_counter", None)
            if isinstance(pre_counter, int):
                # Initial counter — task is complete when it increases.
                pass
            else:
                # Fallback: track _last_analysis / _last_challenge presence.
                pass

        elapsed = 0.0
        interval = 0.5
        while elapsed < timeout:
            await asyncio.sleep(interval)
            elapsed += interval

            target = supervisor_actors.get(agent_name)
            done = False
            if target is not None:
                counter = getattr(target, "_task_counter", None)
                if isinstance(counter, int) and pre_counter is not None:
                    done = counter > pre_counter
                elif agent_name in ("alpha", "beta", "charlie"):
                    # Triad agents: check their standard output attrs.
                    if agent_name == "alpha":
                        done = len(getattr(target, "analysis_history", [])) > 0
                    elif agent_name == "beta":
                        done = len(getattr(target, "_analyses", {})) > 0
                    elif agent_name == "charlie":
                        done = len(getattr(target, "_challenges", {})) > 0

            logger.info(
                "routed_task_polling",
                agent_name=agent_name,
                elapsed=round(elapsed, 1),
                done=done,
            )

            if done:
                logger.info(
                    "routed_task_complete",
                    agent_name=agent_name,
                    elapsed=round(elapsed, 1),
                )
                break

        # Log the routed event to Historian. Gracefully handle missing
        # historian (log warning, still return dispatch status). This
        # follows the same None-guard pattern as _process_scheduled_tasks().
        historian = supervisor_actors.get("historian")
        if historian is not None:
            await historian.log_event(
                "routed_task",
                "main_loop",
                {
                    "target_agent": agent_name,
                    "task_type": task_type,
                    "message_id": message_id,
                },
            )
        else:
            logger.warning(
                "run_routed_task_historian_skipped",
                agent_name=agent_name,
                task_type=task_type,
            )

        return {
            "status": "dispatched",
            "target_agent": agent_name,
            "task_type": task_type,
            "message_id": message_id,
        }
