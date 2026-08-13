"""
LangGraph node wrappers for the HeavySwarm 5-phase workflow.

M-arch PR #6 follow-up: replace the custom 1,363-LOC HeavySwarm
orchestrator with a LangGraph ``StateGraph``. This module
provides the 5 phase nodes (research, analysis, alternatives,
verification, decision) as standalone callables. They are wired
together by ``langgraph_workflow.py``.

Public contract (preserved from heavyswarm.py):
  * :class:`heretek_swarm.orchestration.heavyswarm.WorkflowPhase`
  * :class:`heretek_swarm.orchestration.heavyswarm.PhaseResult`
  * :class:`heretek_swarm.orchestration.heavyswarm.WorkflowResult`
  * :class:`heretek_swarm.orchestration.heavyswarm.HeavySwarmWorkflow`

The nodes accept and return a ``WorkflowState`` TypedDict that
matches the public dataclasses. HeavySwarmWorkflow's existing
instance methods (``_research_phase`` etc.) are wrapped by
``legacy_phase_node`` so the new graph can delegate to the
existing 1,363-LOC implementation without rewriting it.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, TypedDict

import structlog

from heretek_swarm.orchestration.heavyswarm import (
    HeavySwarmWorkflow,
    PhaseResult,
    WorkflowPhase,
    WorkflowResult,
)

# Public re-exports (M-arch contract: langgraph module must keep the
# existing public surface importable during the additive migration).
__all__ = [
    "PHASE_NODES",
    "WorkflowPhase",
    "WorkflowResult",
    "WorkflowState",
    "alternatives_node",
    "analysis_node",
    "build_phase_nodes",
    "decision_node",
    "legacy_phase_node",
    "research_node",
    "verification_node",
]

logger = structlog.get_logger("LangGraphNodes")


class WorkflowState(TypedDict, total=False):
    """LangGraph state schema for the HeavySwarm workflow.

    Mirrors the fields that the 5 phase nodes read and write.
    LangGraph passes this dict to each node and merges the result.
    """

    workflow_id: str
    topic: str
    context: dict[str, Any]
    current_phase: str
    phase_results: dict[str, PhaseResult]
    final_decision: Any  # ConsensusResult | None
    started_at: str
    completed_at: str
    error: str | None


def _phase_result_to_dict(result: PhaseResult) -> dict[str, Any]:
    """Convert a PhaseResult dataclass to a dict for state storage."""
    return asdict(result)


def research_node(state: WorkflowState) -> WorkflowState:
    """Node 1: Gather information and context for ``state['topic']``.

    This is a placeholder that captures the intent of the original
    ``_research_phase`` method. The real implementation is
    delegated to ``HeavySwarmWorkflow`` via ``legacy_phase_node``.
    """
    logger.info("research_node_entered", topic=state.get("topic"))
    return {"current_phase": WorkflowPhase.RESEARCH.value}


def analysis_node(state: WorkflowState) -> WorkflowState:
    """Node 2: Analyze the problem from multiple perspectives."""
    logger.info("analysis_node_entered", topic=state.get("topic"))
    return {"current_phase": WorkflowPhase.ANALYSIS.value}


def alternatives_node(state: WorkflowState) -> WorkflowState:
    """Node 3: Generate alternative solutions."""
    logger.info("alternatives_node_entered", topic=state.get("topic"))
    return {"current_phase": WorkflowPhase.ALTERNATIVES.value}


def verification_node(state: WorkflowState) -> WorkflowState:
    """Node 4: Verify and validate proposed solutions."""
    logger.info("verification_node_entered", topic=state.get("topic"))
    return {"current_phase": WorkflowPhase.VERIFICATION.value}


def decision_node(state: WorkflowState) -> WorkflowState:
    """Node 5: Final decision via MAKER consensus.

    Per PLAN.md §M-arch PR #6: the MAKER consensus becomes the
    Decision node. The real consensus computation is delegated
    to ``HeavySwarmWorkflow.consensus_engine`` via
    ``legacy_phase_node``.
    """
    logger.info("decision_node_entered", topic=state.get("topic"))
    return {"current_phase": WorkflowPhase.DECISION.value}


# Mapping from WorkflowPhase enum to the private method name on
# HeavySwarmWorkflow. Used by legacy_phase_node to dispatch.
_PHASE_METHODS: dict[WorkflowPhase, str] = {
    WorkflowPhase.RESEARCH: "_research_phase",
    WorkflowPhase.ANALYSIS: "_analysis_phase",
    WorkflowPhase.ALTERNATIVES: "_alternatives_phase",
    WorkflowPhase.VERIFICATION: "_verification_phase",
    WorkflowPhase.DECISION: "_decision_phase",
}

# Each non-first phase receives the previous phase's ``PhaseResult.output``
# as an extra positional arg (see ``HeavySwarmWorkflow.execute``). The
# bridge reads this from ``state.phase_results`` so the StateGraph can
# drive phases independently.
_PREVIOUS_PHASE: dict[WorkflowPhase, WorkflowPhase] = {
    WorkflowPhase.ANALYSIS: WorkflowPhase.RESEARCH,
    WorkflowPhase.ALTERNATIVES: WorkflowPhase.ANALYSIS,
    WorkflowPhase.VERIFICATION: WorkflowPhase.ALTERNATIVES,
    WorkflowPhase.DECISION: WorkflowPhase.VERIFICATION,
}


def legacy_phase_node(phase: WorkflowPhase, workflow: HeavySwarmWorkflow | None = None):
    """Build a LangGraph node that delegates to ``HeavySwarmWorkflow``.

    Args:
        phase: The workflow phase this node represents.
        workflow: Optional pre-configured ``HeavySwarmWorkflow`` instance.
            If ``None``, the node returns a state-update-only stub
            (useful for dry-runs and tests where no real workflow
            is wired up).

    Returns:
        A LangGraph-compatible async callable that takes
        ``WorkflowState`` and returns the updated state after
        running the corresponding legacy phase method.

    This is the bridge that lets the new StateGraph reuse the
    existing 1,363-LOC HeavySwarmWorkflow implementation without
    requiring a from-scratch rewrite. When a real workflow is
    provided, this node delegates to it.
    """
    phase_method = _PHASE_METHODS.get(phase)
    phase_attr = phase_method or f"_{phase.value}_phase"

    async def node(state: WorkflowState) -> WorkflowState:
        if workflow is None:
            logger.info(
                "legacy_phase_node_stub",
                phase=phase.value,
                topic=state.get("topic"),
            )
            return {"current_phase": phase.value}

        method = getattr(workflow, phase_attr, None)
        if method is None:
            logger.warning(
                "legacy_phase_method_missing",
                phase=phase.value,
                phase_attr=phase_attr,
            )
            return {"current_phase": phase.value}

        topic = state.get("topic", "")
        context = state.get("context", {})
        workflow_id = state.get("workflow_id", "")

        # Build the call to match HeavySwarmWorkflow._execute_phase's
        # real signature: (workflow_id, phase, phase_func, *args).
        # Phases 2-5 receive the previous phase's output as an extra
        # positional arg (see _PREVIOUS_PHASE above).
        call_args: list[Any] = [workflow_id, phase, method, topic, context]
        prev_phase = _PREVIOUS_PHASE.get(phase)
        if prev_phase is not None:
            prev_result = (state.get("phase_results") or {}).get(
                prev_phase.value
            )
            if prev_result is not None:
                call_args.append(prev_result.output)

        try:
            phase_result = await workflow._execute_phase(*call_args)
        except Exception as e:
            logger.exception(
                "legacy_phase_node_failed",
                phase=phase.value,
                error=str(e),
            )
            return {
                "current_phase": phase.value,
                "error": f"{phase.value}: {e}",
            }

        existing_results = dict(state.get("phase_results") or {})
        existing_results[phase.value] = phase_result
        out: dict[str, Any] = {
            "current_phase": phase.value,
            "phase_results": existing_results,
        }
        if phase == WorkflowPhase.DECISION and phase_result.output:
            decision = phase_result.output.get("decision") or phase_result.output.get(
                "consensus"
            )
            if decision is not None:
                out["final_decision"] = decision
        return out

    return node


# Map from phase to its node function (used by langgraph_workflow.py
# to wire the StateGraph).
PHASE_NODES = {
    WorkflowPhase.RESEARCH: research_node,
    WorkflowPhase.ANALYSIS: analysis_node,
    WorkflowPhase.ALTERNATIVES: alternatives_node,
    WorkflowPhase.VERIFICATION: verification_node,
    WorkflowPhase.DECISION: decision_node,
}


def build_phase_nodes(
    workflow: HeavySwarmWorkflow,
) -> dict[WorkflowPhase, Any]:
    """Build a {phase -> LangGraph node} mapping bound to a workflow instance.

    Each returned node delegates to ``workflow._execute_phase`` via
    ``legacy_phase_node``. This is what ``langgraph_workflow.py`` uses
    to wire the StateGraph so the graph actually runs the legacy
    phase logic (rather than the no-op stubs in ``PHASE_NODES``).
    """
    return {
        phase: legacy_phase_node(phase, workflow)
        for phase in (
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        )
    }
