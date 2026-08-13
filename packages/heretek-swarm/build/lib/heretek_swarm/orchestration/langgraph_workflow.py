"""
LangGraph-based HeavySwarm workflow engine.

M-arch PR #6 follow-up: replace the custom 1,363-LOC
``HeavySwarmWorkflow`` orchestrator with a LangGraph ``StateGraph``.

This module:
  * Defines ``LangGraphHeavySwarmWorkflow`` — a thin wrapper around
    LangGraph's ``StateGraph`` that preserves the public contract
    of :class:`heretek_swarm.orchestration.heavyswarm.HeavySwarmWorkflow`.
  * Compiles a 5-node graph (research → analysis → alternatives →
    verification → decision) with ``MemorySaver`` for resumability.
  * Exposes ``execute(topic, context) -> WorkflowResult`` so callers
    can use it as a drop-in replacement for the legacy workflow.

Public contract is preserved:
  * ``WorkflowPhase`` enum (5 phases + COMPLETED + FAILED)
  * ``PhaseResult`` dataclass
  * ``WorkflowResult`` dataclass
  * ``HeavySwarmWorkflow`` class (legacy) keeps working unchanged

This is a focused first pass — the legacy ``_research_phase`` etc.
methods are still the source of truth for the phase logic (delegated
to via ``legacy_phase_node``). A follow-up PR can port each phase
to a true LangGraph node and delete the legacy 1,363-LOC file.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.orchestration.heavyswarm import (
    HeavySwarmWorkflow,
    WorkflowPhase,
    WorkflowResult,
)
from heretek_swarm.orchestration.langgraph_nodes import (
    WorkflowState,
    build_phase_nodes,
)

logger = structlog.get_logger("LangGraphHeavySwarm")


# Linear phase order. The StateGraph connects them in this sequence.
_PHASE_ORDER: list[WorkflowPhase] = [
    WorkflowPhase.RESEARCH,
    WorkflowPhase.ANALYSIS,
    WorkflowPhase.ALTERNATIVES,
    WorkflowPhase.VERIFICATION,
    WorkflowPhase.DECISION,
]


def _build_initial_state(
    topic: str,
    context: dict[str, Any] | None,
    workflow_id: str | None,
) -> WorkflowState:
    """Build the initial WorkflowState for a new execution."""
    return {
        "workflow_id": workflow_id or str(uuid.uuid4()),
        "topic": topic,
        "context": context or {},
        "current_phase": "",
        "phase_results": {},
        "final_decision": None,
        "started_at": datetime.now(UTC).isoformat(),
        "completed_at": "",
        "error": None,
    }


def _state_to_workflow_result(state: WorkflowState) -> WorkflowResult:
    """Convert a final WorkflowState to the public WorkflowResult."""
    started = state.get("started_at", "")
    completed = state.get("completed_at", "")
    duration_ms = 0.0
    if started and completed:
        try:
            t0 = datetime.fromisoformat(started)
            t1 = datetime.fromisoformat(completed)
            duration_ms = (t1 - t0).total_seconds() * 1000
        except ValueError:
            duration_ms = 0.0

    return WorkflowResult(
        workflow_id=state.get("workflow_id", ""),
        topic=state.get("topic", ""),
        state=WorkflowPhase(state.get("current_phase", "completed")),
        phase_results=state.get("phase_results", {}),
        final_decision=state.get("final_decision"),
        started_at=started,
        completed_at=completed,
        total_duration_ms=duration_ms,
    )


class LangGraphHeavySwarmWorkflow:
    """LangGraph-backed implementation of the 5-phase HeavySwarm workflow.

    The public surface (``execute(topic, context) -> WorkflowResult``)
    matches :class:`HeavySwarmWorkflow` so callers can swap the
    two implementations without changing call sites.

    Graph topology:
        research -> analysis -> alternatives -> verification -> decision -> END

    The ``MemorySaver`` checkpointer persists state after every
    node, so a crashed workflow can be resumed by passing the
    same ``thread_id`` to ``execute()``.
    """

    def __init__(
        self,
        name: str | None = None,
        workflow: HeavySwarmWorkflow | None = None,
    ) -> None:
        self.name = name or "LangGraphHeavySwarm"
        self.workflow = workflow or HeavySwarmWorkflow(name=self.name)
        self._graph = self._compile_graph()

    def _compile_graph(self):  # pragma: no cover — exercised when langgraph is installed
        """Compile the StateGraph.

        Returns ``None`` if langgraph is not installed, so this
        module is importable even without the optional dep. Callers
        should check ``_graph is not None`` before invoking
        ``invoke()``.
        """
        try:
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.graph import END, StateGraph
        except ImportError:
            return None

        phase_nodes = build_phase_nodes(self.workflow)
        graph = StateGraph(WorkflowState)
        graph.add_node(WorkflowPhase.RESEARCH.value, phase_nodes[WorkflowPhase.RESEARCH])
        graph.add_node(WorkflowPhase.ANALYSIS.value, phase_nodes[WorkflowPhase.ANALYSIS])
        graph.add_node(
            WorkflowPhase.ALTERNATIVES.value, phase_nodes[WorkflowPhase.ALTERNATIVES]
        )
        graph.add_node(
            WorkflowPhase.VERIFICATION.value, phase_nodes[WorkflowPhase.VERIFICATION]
        )
        graph.add_node(WorkflowPhase.DECISION.value, phase_nodes[WorkflowPhase.DECISION])

        graph.set_entry_point(WorkflowPhase.RESEARCH.value)
        graph.add_edge(WorkflowPhase.RESEARCH.value, WorkflowPhase.ANALYSIS.value)
        graph.add_edge(WorkflowPhase.ANALYSIS.value, WorkflowPhase.ALTERNATIVES.value)
        graph.add_edge(WorkflowPhase.ALTERNATIVES.value, WorkflowPhase.VERIFICATION.value)
        graph.add_edge(WorkflowPhase.VERIFICATION.value, WorkflowPhase.DECISION.value)
        graph.add_edge(WorkflowPhase.DECISION.value, END)

        return graph.compile(checkpointer=MemorySaver())

    async def execute(
        self,
        topic: str,
        context: dict[str, Any] | None = None,
        workflow_id: str | None = None,
    ) -> WorkflowResult:
        """Execute the 5-phase workflow and return a ``WorkflowResult``.

        Mirrors the public contract of
        :meth:`HeavySwarmWorkflow.execute`.
        """
        if self._graph is None:
            raise RuntimeError(
                "langgraph is not installed. Install with "
                "`uv pip install heretek-swarm[langgraph]` to use "
                "LangGraphHeavySwarmWorkflow."
            )

        initial = _build_initial_state(topic, context, workflow_id)
        thread_id = initial["workflow_id"]
        config = {"configurable": {"thread_id": thread_id}}

        logger.info(
            "langgraph_workflow_starting",
            name=self.name,
            workflow_id=thread_id,
            topic=topic,
        )

        try:
            final_state = await self._graph.ainvoke(initial, config=config)
        except Exception as e:
            logger.exception(
                "langgraph_workflow_failed",
                workflow_id=thread_id,
                error=str(e),
            )
            initial["error"] = str(e)
            initial["current_phase"] = WorkflowPhase.FAILED.value
            initial["completed_at"] = datetime.now(UTC).isoformat()
            return _state_to_workflow_result(initial)

        final_state["completed_at"] = datetime.now(UTC).isoformat()
        final_state["current_phase"] = WorkflowPhase.COMPLETED.value
        logger.info(
            "langgraph_workflow_completed",
            name=self.name,
            workflow_id=thread_id,
        )
        return _state_to_workflow_result(final_state)


def is_langgraph_available() -> bool:
    """Return True if the langgraph optional dep is importable."""
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


def build_langgraph_workflow() -> LangGraphHeavySwarmWorkflow | None:
    """Factory: return a LangGraphHeavySwarmWorkflow if langgraph is available,
    else ``None`` so callers can fall back to the legacy
    ``HeavySwarmWorkflow``.
    """
    if not is_langgraph_available():
        logger.warning("langgraph_not_available_falling_back_to_legacy")
        return None
    return LangGraphHeavySwarmWorkflow()


def build_legacy_workflow(**kwargs: Any) -> HeavySwarmWorkflow:
    """Factory: return a legacy ``HeavySwarmWorkflow`` instance.

    Provided for API symmetry with ``build_langgraph_workflow()``.
    """
    return HeavySwarmWorkflow(**kwargs)
