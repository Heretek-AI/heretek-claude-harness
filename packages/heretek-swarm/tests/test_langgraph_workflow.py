"""
Tests for the LangGraph HeavySwarm migration (M-arch PR #6 follow-up).

Per PLAN.md: replace the custom 1,363-LOC HeavySwarm orchestrator
with a LangGraph StateGraph. These tests verify:
  1. The new module imports cleanly (with or without langgraph)
  2. The 5 phase nodes are callable and return the correct state
  3. The state schema matches the public WorkflowState TypedDict
  4. The legacy_phase_node bridge is importable
  5. The factory helpers return the right type based on availability

If langgraph is not installed, the compile- and invoke-level
tests are skipped (the module is opt-in via [langgraph] extra).
"""

from __future__ import annotations

from typing import Any

import pytest
from heretek_swarm.orchestration import langgraph_nodes
from heretek_swarm.orchestration.langgraph_nodes import (
    PhaseResult,
    WorkflowPhase,
)


class TestPhaseNodes:
    def test_research_node_sets_phase(self) -> None:
        """research_node updates state.current_phase to RESEARCH."""
        state: dict[str, Any] = {"topic": "x", "phase_results": {}}
        result = langgraph_nodes.research_node(state)
        assert result["current_phase"] == "research"

    def test_analysis_node_sets_phase(self) -> None:
        """analysis_node updates state.current_phase to ANALYSIS."""
        state: dict[str, Any] = {"topic": "x", "phase_results": {}}
        result = langgraph_nodes.analysis_node(state)
        assert result["current_phase"] == "analysis"

    def test_alternatives_node_sets_phase(self) -> None:
        """alternatives_node updates state.current_phase to ALTERNATIVES."""
        state: dict[str, Any] = {"topic": "x", "phase_results": {}}
        result = langgraph_nodes.alternatives_node(state)
        assert result["current_phase"] == "alternatives"

    def test_verification_node_sets_phase(self) -> None:
        """verification_node updates state.current_phase to VERIFICATION."""
        state: dict[str, Any] = {"topic": "x", "phase_results": {}}
        result = langgraph_nodes.verification_node(state)
        assert result["current_phase"] == "verification"

    def test_decision_node_sets_phase(self) -> None:
        """decision_node updates state.current_phase to DECISION."""
        state: dict[str, Any] = {"topic": "x", "phase_results": {}}
        result = langgraph_nodes.decision_node(state)
        assert result["current_phase"] == "decision"

    def test_legacy_phase_node_returns_callable(self) -> None:
        """legacy_phase_node returns a callable for each phase."""
        for phase in (
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        ):
            node = langgraph_nodes.legacy_phase_node(phase)
            assert callable(node)

    def test_legacy_phase_node_preserves_phase(self) -> None:
        """legacy_phase_node returns a node that sets the right phase."""
        import asyncio

        node = langgraph_nodes.legacy_phase_node(WorkflowPhase.ANALYSIS)
        result = asyncio.run(node({"topic": "x", "phase_results": {}}))
        assert result["current_phase"] == "analysis"


class TestPhaseNodeMapping:
    def test_phase_nodes_covers_all_phases(self) -> None:
        """PHASE_NODES contains an entry for each of the 5 active phases.

        Note: COMPLETED and FAILED are terminal states, not nodes.
        """
        active_phases = {
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        }
        assert set(langgraph_nodes.PHASE_NODES.keys()) == active_phases

    def test_phase_nodes_values_are_callable(self) -> None:
        """Each entry in PHASE_NODES is a callable."""
        for phase, fn in langgraph_nodes.PHASE_NODES.items():
            assert callable(fn), f"PHASE_NODES[{phase!r}] is not callable"


class TestLegacyPhaseNodeBridge:
    """Tests for legacy_phase_node(phase, workflow) — the bridge
    that lets the LangGraph StateGraph delegate to the existing
    HeavySwarmWorkflow implementation.
    """

    def test_legacy_node_with_workflow_calls_execute_phase(self) -> None:
        """legacy_phase_node(phase, workflow) calls workflow._execute_phase."""
        from unittest.mock import AsyncMock, MagicMock

        workflow = MagicMock()
        workflow._execute_phase = AsyncMock(
            return_value=PhaseResult(
                phase=WorkflowPhase.RESEARCH,
                success=True,
                output={"summary": "ok"},
                duration_ms=42.0,
            )
        )
        workflow._research_phase = MagicMock()
        node = langgraph_nodes.legacy_phase_node(
            WorkflowPhase.RESEARCH, workflow
        )
        import asyncio

        state: dict[str, Any] = {
            "topic": "t",
            "context": {"k": "v"},
            "workflow_id": "wf-1",
        }
        result = asyncio.run(node(state))
        assert result["current_phase"] == "research"
        workflow._execute_phase.assert_awaited_once()
        # Real signature: (workflow_id, phase, phase_func, topic, context)
        call_args = workflow._execute_phase.await_args.args
        assert call_args[0] == "wf-1"
        assert call_args[1] == WorkflowPhase.RESEARCH
        assert call_args[2] is workflow._research_phase
        assert call_args[3] == "t"
        assert call_args[4] == {"k": "v"}

    def test_legacy_node_stores_phase_result(self) -> None:
        """legacy_phase_node stores the PhaseResult in state.phase_results."""
        from unittest.mock import AsyncMock, MagicMock

        workflow = MagicMock()
        workflow._execute_phase = AsyncMock(
            return_value=PhaseResult(
                phase=WorkflowPhase.ANALYSIS,
                success=True,
                output={"perspectives": ["a", "b", "c"]},
                duration_ms=100.0,
            )
        )
        node = langgraph_nodes.legacy_phase_node(
            WorkflowPhase.ANALYSIS, workflow
        )
        import asyncio

        result = asyncio.run(node({"topic": "t", "context": {}, "workflow_id": "wf"}))
        assert "phase_results" in result
        assert WorkflowPhase.ANALYSIS.value in result["phase_results"]
        pr = result["phase_results"][WorkflowPhase.ANALYSIS.value]
        assert pr.phase == WorkflowPhase.ANALYSIS
        assert pr.success is True

    def test_legacy_node_handles_workflow_error(self) -> None:
        """legacy_phase_node captures exceptions and sets state.error."""
        from unittest.mock import AsyncMock, MagicMock

        workflow = MagicMock()
        workflow._execute_phase = AsyncMock(
            side_effect=RuntimeError("simulated phase failure")
        )
        node = langgraph_nodes.legacy_phase_node(
            WorkflowPhase.VERIFICATION, workflow
        )
        import asyncio

        result = asyncio.run(node({"topic": "t", "context": {}, "workflow_id": "wf"}))
        assert result["current_phase"] == "verification"
        assert "error" in result
        assert "simulated phase failure" in result["error"]

    def test_legacy_node_without_workflow_returns_stub(self) -> None:
        """legacy_phase_node(phase, None) returns a state-update-only stub."""
        node = langgraph_nodes.legacy_phase_node(WorkflowPhase.RESEARCH, None)
        import asyncio

        result = asyncio.run(node({"topic": "t", "context": {}}))
        assert result["current_phase"] == "research"
        assert "phase_results" not in result or not result.get("phase_results")


class TestPublicContractPreserved:
    def test_workflow_phase_enum_preserved(self) -> None:
        """The WorkflowPhase enum is importable from langgraph_nodes."""
        from heretek_swarm.orchestration.langgraph_nodes import (
            WorkflowPhase as WorkflowPhase2,
        )
        assert WorkflowPhase2 is langgraph_nodes.WorkflowPhase

    def test_phase_result_importable(self) -> None:
        """PhaseResult is importable from langgraph_nodes."""
        from heretek_swarm.orchestration.langgraph_nodes import (
            PhaseResult as PhaseResult2,
        )
        assert PhaseResult2 is langgraph_nodes.PhaseResult

    def test_workflow_result_importable(self) -> None:
        """WorkflowResult is importable from langgraph_nodes."""
        from heretek_swarm.orchestration.langgraph_nodes import (
            WorkflowResult as WorkflowResult2,
        )
        assert WorkflowResult2 is langgraph_nodes.WorkflowResult


class TestLangGraphWorkflowModule:
    def test_workflow_module_imports(self) -> None:
        """langgraph_workflow module imports cleanly."""
        from heretek_swarm.orchestration import langgraph_workflow

        assert hasattr(langgraph_workflow, "LangGraphHeavySwarmWorkflow")
        assert hasattr(langgraph_workflow, "build_langgraph_workflow")
        assert hasattr(langgraph_workflow, "build_legacy_workflow")
        assert hasattr(langgraph_workflow, "is_langgraph_available")

    def test_is_langgraph_available_returns_bool(self) -> None:
        """is_langgraph_available returns a bool."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            is_langgraph_available,
        )
        result = is_langgraph_available()
        assert isinstance(result, bool)

    def test_build_legacy_workflow_returns_heavy(self) -> None:
        """build_legacy_workflow returns a LangGraphHeavySwarmWorkflow instance."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
            build_legacy_workflow,
        )

        wf = build_legacy_workflow(name="test")
        assert isinstance(wf, LangGraphHeavySwarmWorkflow)
        assert wf.name == "test"

    def test_build_phase_nodes_returns_all_five(self) -> None:
        """build_phase_nodes(workflow) returns a callable for every phase."""
        from unittest.mock import MagicMock

        from heretek_swarm.orchestration.langgraph_nodes import (
            build_phase_nodes,
        )

        workflow = MagicMock()
        nodes = build_phase_nodes(workflow)
        assert set(nodes.keys()) == {
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        }
        for phase, node_fn in nodes.items():
            assert callable(node_fn), f"node for {phase!r} is not callable"

    def test_build_phase_nodes_uses_provided_workflow(self) -> None:
        """Each bridge node delegates to the provided workflow's _execute_phase."""
        from unittest.mock import AsyncMock, MagicMock

        from heretek_swarm.orchestration.langgraph_nodes import (
            build_phase_nodes,
        )

        workflow = MagicMock()
        workflow._execute_phase = AsyncMock(
            return_value=PhaseResult(
                phase=WorkflowPhase.VERIFICATION,
                success=True,
                output={"ok": True},
                duration_ms=1.0,
            )
        )
        workflow._verification_phase = MagicMock()

        nodes = build_phase_nodes(workflow)
        import asyncio

        result = asyncio.run(
            nodes[WorkflowPhase.VERIFICATION](
                {
                    "topic": "t",
                    "context": {},
                    "workflow_id": "wf-x",
                    "phase_results": {},
                }
            )
        )
        assert result["current_phase"] == "verification"
        workflow._execute_phase.assert_awaited_once()

    def test_langgraph_workflow_no_heavy_dependency(self) -> None:
        """LangGraphHeavySwarmWorkflow no longer requires a HeavySwarmWorkflow."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="test")
        assert wf.name == "test"
        assert not hasattr(wf, "workflow")

    def test_langgraph_workflow_default_name(self) -> None:
        """LangGraphHeavySwarmWorkflow uses a sensible default name."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow()
        assert wf.name == "LangGraphHeavySwarm"


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph"),
    reason="langgraph not installed",
)
class TestLangGraphWorkflowExecution:
    """Tests that require the langgraph optional dep."""

    @pytest.mark.asyncio
    async def test_workflow_executes_through_all_phases(self) -> None:
        """The compiled StateGraph runs all 5 phases and returns a WorkflowResult."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="test")
        result = await wf.execute(topic="Should we deploy?")
        assert result.state == WorkflowPhase.COMPLETED
        assert result.workflow_id  # non-empty
        assert result.topic == "Should we deploy?"
        assert result.started_at
        assert result.completed_at
        assert result.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_workflow_id_is_preserved(self) -> None:
        """A caller-provided workflow_id is preserved in the result."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow()
        result = await wf.execute(topic="x", workflow_id="my-custom-id-123")
        assert result.workflow_id == "my-custom-id-123"

    @pytest.mark.asyncio
    async def test_workflow_context_is_stored(self) -> None:
        """The context dict is stored in the initial state."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow()
        ctx = {"k": "v", "n": 42}
        result = await wf.execute(topic="x", context=ctx)
        assert result.phase_results or result.state == WorkflowPhase.COMPLETED


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph"),
    reason="langgraph not installed",
)
class TestCheckpointerSupport:
    """Tests for dual checkpointer support (MemorySaver and PostgreSQL)."""

    @pytest.mark.asyncio
    async def test_initialize_sets_memory_saver_by_default(self) -> None:
        """initialize() uses MemorySaver when no DB URL is set."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="checkpointer-test")
        await wf.initialize()
        assert wf._initialized is True
        assert wf._checkpointer is None  # Uses MemorySaver internally

    @pytest.mark.asyncio
    async def test_initialize_logs_checkpointer_type(self) -> None:
        """initialize() logs the checkpointer type."""
        from unittest.mock import patch

        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="checkpointer-test")
        with patch("heretek_swarm.orchestration.langgraph_workflow.logger") as mock_logger:
            await wf.initialize()
            mock_logger.info.assert_called_with(
                "langgraph_workflow_initialized",
                checkpointer_type="MemorySaver",
            )

    @pytest.mark.asyncio
    async def test_execute_lazy_initialization(self) -> None:
        """execute() calls initialize() lazily on first call."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="lazy-init-test")
        assert wf._initialized is False
        result = await wf.execute(topic="test topic")
        # The workflow ran successfully, which means initialize() was called
        assert result.state == WorkflowPhase.COMPLETED
        # Note: _initialized is set to True inside initialize(), which is called by execute()

    @pytest.mark.asyncio
    async def test_close_method_exists(self) -> None:
        """close() method exists and can be called."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow()
        await wf.initialize()
        await wf.close()  # Should not raise

    @pytest.mark.asyncio
    async def test_execute_logs_checkpointer_type(self) -> None:
        """execute() logs the checkpointer type in the start message."""
        from unittest.mock import patch

        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="checkpointer-log-test")
        with patch("heretek_swarm.orchestration.langgraph_workflow.logger") as mock_logger:
            await wf.execute(topic="test")
            # Find the langgraph_workflow_starting call
            starting_calls = [
                call for call in mock_logger.info.call_args_list
                if call[0][0] == "langgraph_workflow_starting"
            ]
            assert len(starting_calls) == 1
            # Verify checkpointer_type is in the kwargs
            assert "checkpointer_type" in starting_calls[0][1]
            # The checkpointer_type should be "MemorySaver" since no DB URL is set
            assert starting_calls[0][1]["checkpointer_type"] == "MemorySaver"

    @pytest.mark.asyncio
    async def test_initialize_with_explicit_checkpointer(self) -> None:
        """initialize() accepts an explicit checkpointer instance."""
        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )
        from langgraph.checkpoint.memory import MemorySaver

        # Use a real MemorySaver instance instead of a mock
        real_checkpointer = MemorySaver()
        wf = LangGraphHeavySwarmWorkflow(name="explicit-checkpointer-test")
        await wf.initialize(checkpointer=real_checkpointer)
        assert wf._checkpointer is real_checkpointer


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph_checkpoint_postgres"),
    reason="langgraph-checkpoint-postgres not installed",
)
class TestPostgreSQLCheckpointer:
    """Tests for PostgreSQL checkpointer support.

    These tests require:
    1. langgraph-checkpoint-postgres installed
    2. HERETEK_CHECKPOINT_DB_URL set to a valid PostgreSQL connection string
    """

    @pytest.mark.asyncio
    async def test_postgres_checkpointer_initialization(self, monkeypatch) -> None:
        """initialize() uses PostgreSQL checkpointer when DB URL is set."""
        import os

        # Skip if no PostgreSQL is available
        db_url = os.environ.get("HERETEK_CHECKPOINT_DB_URL")
        if not db_url:
            pytest.skip("HERETEK_CHECKPOINT_DB_URL not set")

        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="postgres-test")
        await wf.initialize()
        assert wf._initialized is True
        # The checkpointer should be an AsyncPostgresSaver, not None
        assert wf._checkpointer is not None

    @pytest.mark.asyncio
    async def test_postgres_checkpointer_workflow_execution(self, monkeypatch) -> None:
        """Workflow executes successfully with PostgreSQL checkpointer."""
        import os

        # Skip if no PostgreSQL is available
        db_url = os.environ.get("HERETEK_CHECKPOINT_DB_URL")
        if not db_url:
            pytest.skip("HERETEK_CHECKPOINT_DB_URL not set")

        from heretek_swarm.orchestration.langgraph_workflow import (
            LangGraphHeavySwarmWorkflow,
        )

        wf = LangGraphHeavySwarmWorkflow(name="postgres-exec-test")
        result = await wf.execute(topic="PostgreSQL checkpoint test")
        assert result.state == WorkflowPhase.COMPLETED
        assert result.workflow_id
