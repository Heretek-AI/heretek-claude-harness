"""
LangGraph-based HeavySwarm workflow engine.

M-arch PR #6 follow-up: replace the custom 1,363-LOC
``HeavySwarmWorkflow`` orchestrator with a LangGraph ``StateGraph``.

This module:
  * Defines ``LangGraphHeavySwarmWorkflow`` — a thin wrapper around
    LangGraph's ``StateGraph`` that provides the public contract.
  * Compiles a 5-node graph (research → analysis → alternatives →
    verification → decision) with ``MemorySaver`` for resumability.
  * Exposes ``execute(topic, context) -> WorkflowResult`` so callers
    can use it as a drop-in replacement for the legacy workflow.

Public contract is preserved:
  * ``WorkflowPhase`` enum (5 phases + COMPLETED + FAILED)
  * ``PhaseResult`` dataclass
  * ``WorkflowResult`` dataclass

Each phase is a real LangGraph node (defined in ``langgraph_nodes``)
registered directly on the ``StateGraph``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from itertools import pairwise
from typing import Any

import structlog

from heretek_swarm.orchestration.langgraph_nodes import (
    PHASE_NODES,
    WorkflowPhase,
    WorkflowResult,
    WorkflowState,
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

    # Fall back to phase_results['decision'] for final_decision if the
    # top-level field is unset. This matches the legacy pattern in
    # heavyswarm.py:334 where final_decision is read from
    # decision_result.output.get("consensus_result").
    final_decision = state.get("final_decision")
    if final_decision is None:
        decision_result = (state.get("phase_results") or {}).get(
            WorkflowPhase.DECISION.value
        )
        if decision_result is not None:
            decision_output = getattr(decision_result, "output", None) or {}
            final_decision = decision_output.get("consensus_result")

    return WorkflowResult(
        workflow_id=state.get("workflow_id", ""),
        topic=state.get("topic", ""),
        state=WorkflowPhase(state.get("current_phase", "completed")),
        phase_results=state.get("phase_results", {}),
        final_decision=final_decision,
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

    Supports two checkpointer backends:
    - ``MemorySaver`` (in-memory, default) for development/testing
    - ``AsyncPostgresSaver`` (PostgreSQL, opt-in) for production crash recovery

    The PostgreSQL checkpointer is activated by setting the
    ``HERETEK_CHECKPOINT_DB_URL`` environment variable.
    """

    def __init__(
        self,
        name: str | None = None,
    ) -> None:
        self.name = name or "LangGraphHeavySwarm"
        self._graph = self._compile_graph()  # Default with MemorySaver
        self._checkpointer = None
        self._initialized = False  # Will be set to True after initialize()

    def _compile_graph(self, checkpointer=None):  # pragma: no cover — exercised when langgraph is installed
        """Compile the StateGraph with real phase nodes.

        Uses the standalone node functions from ``langgraph_nodes``
        (``PHASE_NODES``) rather than the legacy bridge wrappers.

        Args:
            checkpointer: Checkpointer instance to use. If None, uses MemorySaver.

        Returns ``None`` if langgraph is not installed, so this
        module is importable even without the optional dep. Callers
        should check ``_graph is not None`` before invoking
        ``invoke()``.
        """
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            return None

        # Import MemorySaver as default if no checkpointer provided
        if checkpointer is None:
            try:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
            except ImportError:
                logger.warning("langgraph_not_installed")
                return None

        graph = StateGraph(WorkflowState)

        for phase in _PHASE_ORDER:
            graph.add_node(phase.value, PHASE_NODES[phase])

        graph.set_entry_point(WorkflowPhase.RESEARCH.value)
        # Wire linear phase transitions: research -> analysis -> ...
        for src, dst in pairwise(_PHASE_ORDER):
            graph.add_edge(src.value, dst.value)
        graph.add_edge(WorkflowPhase.DECISION.value, END)

        return graph.compile(checkpointer=checkpointer)

    async def initialize(self, checkpointer=None) -> None:
        """Initialize the workflow with optional PostgreSQL checkpointer.

        If ``HERETEK_CHECKPOINT_DB_URL`` is set, creates an
        ``AsyncPostgresSaver`` and recompiles the graph with it.
        Otherwise falls back to the default ``MemorySaver``.

        Args:
            checkpointer: Optional pre-configured checkpointer to use.
        """
        if self._initialized:
            return

        import os

        db_url = os.environ.get("HERETEK_CHECKPOINT_DB_URL")

        if checkpointer is not None:
            self._checkpointer = checkpointer
        elif db_url:
            try:
                from langgraph_checkpoint_postgres.aio import AsyncPostgresSaver
                from psycopg_pool import AsyncConnectionPool

                logger.info(
                    "langgraph_postgres_checkpointer_configuring",
                    db_url="***",  # Never log credentials
                )

                # Create connection pool for PostgreSQL
                pool = AsyncConnectionPool(conninfo=db_url, min_size=1, max_size=10)
                self._checkpointer = AsyncPostgresSaver(pool)

                # Setup the checkpointer (creates tables if needed)
                await self._checkpointer.setup()
                logger.info("langgraph_postgres_checkpointer_ready")

            except ImportError:
                logger.warning(
                    "langgraph_checkpoint_postgres_not_installed",
                    message="HERETEK_CHECKPOINT_DB_URL is set but langgraph-checkpoint-postgres is not installed. "
                    "Falling back to MemorySaver. Install with: uv pip install langgraph-checkpoint-postgres",
                )
                # Fall back to MemorySaver
                self._checkpointer = None
            except Exception as e:
                logger.exception(
                    "langgraph_postgres_checkpointer_failed",
                    error=str(e),
                    message="Failed to connect to PostgreSQL. Falling back to MemorySaver.",
                )
                # Fall back to MemorySaver
                self._checkpointer = None

        # Compile graph with the selected checkpointer (or re-use existing if MemorySaver)
        if self._checkpointer is not None or self._graph is None:
            self._graph = self._compile_graph(self._checkpointer)
        self._initialized = True

        checkpointer_type = type(self._checkpointer).__name__ if self._checkpointer else "MemorySaver"
        logger.info(
            "langgraph_workflow_initialized",
            checkpointer_type=checkpointer_type,
        )

    async def close(self) -> None:
        """Close the PostgreSQL checkpointer connection if one was created.

        Should be called when the workflow is no longer needed.
        """
        if self._checkpointer is not None:
            try:
                # Check if the checkpointer has a close method (AsyncPostgresSaver does)
                if hasattr(self._checkpointer, "conn") and hasattr(self._checkpointer.conn, "close"):
                    await self._checkpointer.conn.close()
                    logger.info("langgraph_postgres_checkpointer_closed")
                # If it's using a connection pool, close that
                elif hasattr(self._checkpointer, "pool") and hasattr(self._checkpointer.pool, "close"):
                    await self._checkpointer.pool.close()
                    logger.info("langgraph_postgres_checkpointer_pool_closed")
            except Exception as e:
                logger.exception(
                    "langgraph_postgres_checkpointer_close_failed",
                    error=str(e),
                )

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
        # Lazy initialization on first execute
        if not self._initialized:
            await self.initialize()

        if self._graph is None:  # pragma: no cover — only if langgraph import fails
            raise RuntimeError(
                "langgraph is not installed. Install with "
                "`uv pip install heretek-swarm[langgraph]` to use "
                "LangGraphHeavySwarmWorkflow."
            )

        initial = _build_initial_state(topic, context, workflow_id)
        thread_id = initial["workflow_id"]
        config = {"configurable": {"thread_id": thread_id}}

        checkpointer_type = type(self._checkpointer).__name__ if self._checkpointer else "MemorySaver"
        logger.info(
            "langgraph_workflow_starting",
            name=self.name,
            workflow_id=thread_id,
            topic=topic,
            checkpointer_type=checkpointer_type,
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
        import importlib.util

        if importlib.util.find_spec("langgraph") is None:
            return False
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


def build_legacy_workflow(**kwargs: Any) -> LangGraphHeavySwarmWorkflow:
    """Factory: return a ``LangGraphHeavySwarmWorkflow`` instance.

    Provided for API symmetry with ``build_langgraph_workflow()``.
    """
    return LangGraphHeavySwarmWorkflow(**kwargs)
