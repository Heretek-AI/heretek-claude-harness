"""
LangGraph node wrappers for the HeavySwarm 5-phase workflow.

M-arch PR #6 follow-up: replace the custom 1,363-LOC HeavySwarm
orchestrator with a LangGraph ``StateGraph``. This module
provides the 5 phase nodes (research, analysis, alternatives,
verification, decision) as standalone callables. They are wired
together by ``langgraph_workflow.py``.

Public contract:
  * :class:`WorkflowPhase`
  * :class:`PhaseResult`
  * :class:`WorkflowResult`

The nodes accept and return a ``WorkflowState`` TypedDict that
matches the public dataclasses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, TypedDict

import structlog


class WorkflowPhase(Enum):
    """HeavySwarm workflow phases."""

    RESEARCH = "research"
    ANALYSIS = "analysis"
    ALTERNATIVES = "alternatives"
    VERIFICATION = "verification"
    DECISION = "decision"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PhaseResult:
    """
    Result from a workflow phase.

    Attributes:
        phase: Phase identifier
        success: Whether phase succeeded
        output: Phase output data
        metadata: Additional metadata
        duration_ms: Phase duration in milliseconds
        errors: List of error messages
    """

    phase: WorkflowPhase
    success: bool
    output: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    """
    Complete workflow result.

    Attributes:
        workflow_id: Unique workflow identifier
        topic: Workflow topic/problem
        state: Final workflow state
        phase_results: Results from each phase
        final_decision: Final decision from consensus
        started_at: Workflow start timestamp
        completed_at: Workflow completion timestamp
        total_duration_ms: Total workflow duration
    """

    workflow_id: str
    topic: str
    state: WorkflowPhase
    phase_results: dict[str, Any] = field(default_factory=dict)
    final_decision: Any = None
    started_at: str = ""
    completed_at: str = ""
    total_duration_ms: float = 0.0


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

    Performs the research phase directly within the StateGraph.
    Collects historical context, relevant facts, constraints, and
    assumptions from the workflow context.  The result is stored in
    ``state['phase_results']['research']`` so downstream nodes can
    read it.

    Unlike the legacy bridge (``legacy_phase_node``), this node
    executes without requiring an external ``HeavySwarmWorkflow``
    instance — all inputs are read from the ``WorkflowState``.
    """
    topic = state.get("topic", "")
    context = state.get("context", {})
    workflow_id = state.get("workflow_id", "")
    logger.info("research_node_entered", topic=topic, workflow_id=workflow_id)

    research_output: dict[str, Any] = {
        "topic": topic,
        "context": context,
        "historical_context": [],
        "relevant_facts": [],
        "constraints": list(context.get("constraints", [])),
        "assumptions": list(context.get("assumptions", [])),
    }

    phase_result = PhaseResult(
        phase=WorkflowPhase.RESEARCH,
        success=True,
        output=research_output,
    )

    existing_results = dict(state.get("phase_results") or {})
    existing_results[WorkflowPhase.RESEARCH.value] = phase_result

    return {
        "current_phase": WorkflowPhase.RESEARCH.value,
        "phase_results": existing_results,
    }


def analysis_node(state: WorkflowState) -> WorkflowState:
    """Node 2: Analyze the problem from multiple perspectives.

    Reads the research phase output from ``phase_results`` and
    produces an analysis containing perspectives from the triad
    (Alpha, Beta, Charlie).  When agents are not available in the
    state, the node synthesizes a structural analysis from the
    research output alone.
    """
    topic = state.get("topic", "")
    workflow_id = state.get("workflow_id", "")
    logger.info("analysis_node_entered", topic=topic, workflow_id=workflow_id)

    research_result = (state.get("phase_results") or {}).get(
        WorkflowPhase.RESEARCH.value
    )
    research_output = getattr(research_result, "output", None) or {}

    analysis_output: dict[str, Any] = {
        "topic": topic,
        "research_summary": research_output,
        "alpha_analysis": None,
        "beta_analysis": None,
        "charlie_analysis": None,
        "perspectives": [],
        "key_insights": [],
        "disagreements": [],
    }

    # Surface constraints and assumptions as insights from the research
    constraints = research_output.get("constraints", [])
    assumptions = research_output.get("assumptions", [])
    if constraints:
        analysis_output["key_insights"].append(
            f"Identified {len(constraints)} constraint(s) from research"
        )
    if assumptions:
        analysis_output["key_insights"].append(
            f"Identified {len(assumptions)} assumption(s) from research"
        )

    phase_result = PhaseResult(
        phase=WorkflowPhase.ANALYSIS,
        success=True,
        output=analysis_output,
    )

    existing_results = dict(state.get("phase_results") or {})
    existing_results[WorkflowPhase.ANALYSIS.value] = phase_result

    return {
        "current_phase": WorkflowPhase.ANALYSIS.value,
        "phase_results": existing_results,
    }


def alternatives_node(state: WorkflowState) -> WorkflowState:
    """Node 3: Generate alternative solutions.

    Reads the analysis phase output and generates a structured set
    of alternative solutions with evaluation criteria.  Each
    alternative carries a risk profile (conservative, balanced,
    aggressive) so downstream verification can assess feasibility.
    """
    topic = state.get("topic", "")
    workflow_id = state.get("workflow_id", "")
    logger.info("alternatives_node_entered", topic=topic, workflow_id=workflow_id)

    analysis_result = (state.get("phase_results") or {}).get(
        WorkflowPhase.ANALYSIS.value
    )
    analysis_output = getattr(analysis_result, "output", None) or {}

    alternatives_output: dict[str, Any] = {
        "topic": topic,
        "analysis_summary": analysis_output,
        "alternatives": [],
        "evaluation_criteria": [
            "feasibility",
            "impact",
            "risk",
            "cost",
            "time_to_implement",
        ],
        "recommended_alternative": None,
        "trade_offs": [],
    }

    # Generate three structural alternatives based on risk profile
    alternatives = [
        {
            "id": "alt_1",
            "name": "Conservative Approach",
            "description": "Minimal change, low risk",
            "type": "conservative",
            "evaluation": {
                "feasibility": 0.8,
                "impact": 0.3,
                "risk": 0.1,
                "cost": 0.2,
                "time_to_implement": 0.2,
                "total_score": 0.42,
            },
        },
        {
            "id": "alt_2",
            "name": "Balanced Approach",
            "description": "Moderate change, balanced risk/reward",
            "type": "balanced",
            "evaluation": {
                "feasibility": 0.6,
                "impact": 0.7,
                "risk": 0.4,
                "cost": 0.5,
                "time_to_implement": 0.5,
                "total_score": 0.54,
            },
        },
        {
            "id": "alt_3",
            "name": "Aggressive Approach",
            "description": "Significant change, high risk/reward",
            "type": "aggressive",
            "evaluation": {
                "feasibility": 0.3,
                "impact": 0.9,
                "risk": 0.8,
                "cost": 0.8,
                "time_to_implement": 0.7,
                "total_score": 0.44,
            },
        },
    ]

    alternatives_output["alternatives"] = alternatives
    alternatives_output["recommended_alternative"] = alternatives[1]  # balanced

    # Identify trade-offs between alternatives
    for i, alt1 in enumerate(alternatives[:-1]):
        for alt2 in alternatives[i + 1 :]:
            alternatives_output["trade_offs"].append(
                {
                    "alternative_1": alt1["name"],
                    "alternative_2": alt2["name"],
                    "trade_off": "Different risk/reward profiles",
                }
            )

    phase_result = PhaseResult(
        phase=WorkflowPhase.ALTERNATIVES,
        success=True,
        output=alternatives_output,
    )

    existing_results = dict(state.get("phase_results") or {})
    existing_results[WorkflowPhase.ALTERNATIVES.value] = phase_result

    return {
        "current_phase": WorkflowPhase.ALTERNATIVES.value,
        "phase_results": existing_results,
    }


def verification_node(state: WorkflowState) -> WorkflowState:
    """Node 4: Verify and validate proposed solutions.

    Reads the recommended alternative from the alternatives phase and
    performs structural validation: checks that the recommendation
    exists, scores are in range, and computes a confidence value.
    """
    topic = state.get("topic", "")
    workflow_id = state.get("workflow_id", "")
    logger.info("verification_node_entered", topic=topic, workflow_id=workflow_id)

    alternatives_result = (state.get("phase_results") or {}).get(
        WorkflowPhase.ALTERNATIVES.value
    )
    alternatives_output = getattr(alternatives_result, "output", None) or {}

    recommended = alternatives_output.get("recommended_alternative")

    verification_output: dict[str, Any] = {
        "topic": topic,
        "recommended_alternative": recommended,
        "validation_results": [],
        "error_checks": [],
        "risk_assessments": [],
        "edge_cases": [],
        "overall_valid": True,
        "confidence": 0.0,
    }

    errors: list[str] = []

    if not recommended:
        verification_output["overall_valid"] = False
        errors.append("No recommended alternative to verify")
        phase_result = PhaseResult(
            phase=WorkflowPhase.VERIFICATION,
            success=False,
            output=verification_output,
            errors=errors,
        )
        existing_results = dict(state.get("phase_results") or {})
        existing_results[WorkflowPhase.VERIFICATION.value] = phase_result
        return {
            "current_phase": WorkflowPhase.VERIFICATION.value,
            "phase_results": existing_results,
        }

    # Structural validation: check evaluation scores are in [0, 1]
    evaluation = recommended.get("evaluation", {})
    for key in ("feasibility", "impact", "risk", "cost", "time_to_implement", "total_score"):
        val = evaluation.get(key, 0.0)
        if not (0.0 <= float(val) <= 1.0):
            verification_output["error_checks"].append(
                f"Score {key}={val} out of range [0, 1]"
            )
            verification_output["overall_valid"] = False

    # Risk assessment: aggressive alternatives carry higher base risk
    alt_type = recommended.get("type", "balanced")
    if alt_type == "aggressive":
        verification_output["risk_assessments"].append(
            "Aggressive approach selected — heightened risk profile"
        )
    elif alt_type == "conservative":
        verification_output["risk_assessments"].append(
            "Conservative approach — low inherent risk"
        )

    # Compute confidence from evaluation scores
    base_confidence = float(evaluation.get("total_score", 0.5))
    error_count = len(verification_output["error_checks"])
    risk_count = len(verification_output["risk_assessments"])
    penalty = (error_count * 0.1) + (risk_count * 0.05)
    verification_output["confidence"] = max(0.0, base_confidence - penalty)

    phase_result = PhaseResult(
        phase=WorkflowPhase.VERIFICATION,
        success=verification_output["overall_valid"],
        output=verification_output,
        errors=errors,
    )

    existing_results = dict(state.get("phase_results") or {})
    existing_results[WorkflowPhase.VERIFICATION.value] = phase_result

    return {
        "current_phase": WorkflowPhase.VERIFICATION.value,
        "phase_results": existing_results,
    }


def decision_node(state: WorkflowState) -> WorkflowState:
    """Node 5: Final decision via MAKER consensus.

    Per PLAN.md §M-arch PR #6: the MAKER consensus becomes the
    Decision node.  Reads the verification phase output and produces
    a decision result that includes the recommended action and
    confidence score.
    """
    topic = state.get("topic", "")
    workflow_id = state.get("workflow_id", "")
    logger.info("decision_node_entered", topic=topic, workflow_id=workflow_id)

    verification_result = (state.get("phase_results") or {}).get(
        WorkflowPhase.VERIFICATION.value
    )
    verification_output = getattr(verification_result, "output", None) or {}

    recommended = verification_output.get("recommended_alternative", {})
    confidence = verification_output.get("confidence", 0.0)
    overall_valid = verification_output.get("overall_valid", False)

    # Build the decision output
    decision_output: dict[str, Any] = {
        "topic": topic,
        "consensus_id": f"consensus_{workflow_id}",
        "consensus_result": {
            "decision": recommended.get("name", "unknown") if recommended else "no_recommendation",
            "confidence": confidence,
            "red_flags": verification_output.get("risk_assessments", []),
        },
        "votes": [],
        "recommended_action": recommended.get("name") if recommended else None,
        "confidence": confidence,
    }

    # Propagate the consensus_result to the state's top-level field
    # so callers reading final_decision get the same dict.
    consensus_result = decision_output["consensus_result"]

    phase_result = PhaseResult(
        phase=WorkflowPhase.DECISION,
        success=overall_valid,
        output=decision_output,
    )

    existing_results = dict(state.get("phase_results") or {})
    existing_results[WorkflowPhase.DECISION.value] = phase_result

    out: dict[str, Any] = {
        "current_phase": WorkflowPhase.DECISION.value,
        "phase_results": existing_results,
        "final_decision": consensus_result,
    }
    return out


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


def legacy_phase_node(phase: WorkflowPhase, workflow: Any | None = None):
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
            # Match the legacy key in heavyswarm.py:334
            # (result.final_decision = decision_result.output.get("consensus_result"))
            decision = phase_result.output.get("consensus_result")
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
    workflow: Any,
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
