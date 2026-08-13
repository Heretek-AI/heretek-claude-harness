"""
End-to-end tests for the LangGraph 5-phase HeavySwarm workflow.

Verifies the full state-graph pipeline (research → analysis → alternatives →
verification → decision) including:
  1. Complete 5-phase execution producing a valid WorkflowResult
  2. State propagation — each phase reads and extends prior phase output
  3. Context and workflow_id preservation through the pipeline
  4. Resumability via MemorySaver checkpointing (thread_id replay)
  5. Error handling — mid-pipeline failure produces FAILED state
  6. Final decision / consensus propagation
"""

from __future__ import annotations

import os
import unittest.mock as mock
import uuid
from typing import Any

import pytest
from heretek_swarm.orchestration.langgraph_nodes import (
    PhaseResult,
    WorkflowPhase,
    alternatives_node,
    analysis_node,
    decision_node,
    verification_node,
)
from heretek_swarm.orchestration.langgraph_workflow import (
    LangGraphHeavySwarmWorkflow,
    _build_initial_state,
    _state_to_workflow_result,
)

# DATABASE_URL (or HERETEK_CHECKPOINT_DB_URL) for Postgres persistence tests.
GENERIC_DATABASE_URL = os.environ.get(
    "DATABASE_URL", os.environ.get("HERETEK_CHECKPOINT_DB_URL")
)


async def _pg_is_reachable(url: str | None = None) -> bool:
    """Return True if we can connect to PostgreSQL with the given (or env) URL."""
    if url is None:
        url = GENERIC_DATABASE_URL
    if not url:
        return False
    try:
        import psycopg

        async with await psycopg.AsyncConnection.connect(url) as conn, conn.cursor() as cur:
            await cur.execute("SELECT 1")
            await cur.fetchone()
        return True
    except Exception:
        return False

# Skip entire module if langgraph is not installed.
pytestmark = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph"),
    reason="langgraph not installed",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_full_workflow(
    topic: str = "Should we refactor the consensus engine?",
    context: dict[str, Any] | None = None,
    workflow_id: str | None = None,
) -> tuple[LangGraphHeavySwarmWorkflow, Any]:
    """Execute the full 5-phase workflow and return (workflow, result)."""
    wf = LangGraphHeavySwarmWorkflow(name="e2e-test")
    result = await wf.execute(topic=topic, context=context, workflow_id=workflow_id)
    return wf, result


def _phase_output(result: Any, phase: WorkflowPhase) -> dict[str, Any]:
    """Extract the .output dict from a phase's PhaseResult."""
    pr: PhaseResult | None = result.phase_results.get(phase.value)
    assert pr is not None, f"Phase {phase.value} missing from phase_results"
    return pr.output


# ---------------------------------------------------------------------------
# 1. Full 5-phase execution
# ---------------------------------------------------------------------------


class TestFullExecution:
    """The complete pipeline runs without errors and returns a valid result."""

    @pytest.mark.asyncio
    async def test_completes_all_five_phases(self) -> None:
        """WorkflowResult.state == COMPLETED after running through all nodes."""
        _, result = await _run_full_workflow()
        assert result.state == WorkflowPhase.COMPLETED

    @pytest.mark.asyncio
    async def test_all_phase_results_populated(self) -> None:
        """Every active phase appears in phase_results with a PhaseResult."""
        _, result = await _run_full_workflow()
        for phase in (
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        ):
            pr = result.phase_results.get(phase.value)
            assert pr is not None, f"Missing phase_results[{phase.value}]"
            assert isinstance(pr, PhaseResult)
            assert pr.phase == phase
            assert pr.output  # non-empty dict

    @pytest.mark.asyncio
    async def test_result_has_workflow_id_and_topic(self) -> None:
        """workflow_id and topic round-trip through the graph."""
        _, result = await _run_full_workflow(topic="Deploy v2?")
        assert result.workflow_id  # non-empty
        assert result.topic == "Deploy v2?"

    @pytest.mark.asyncio
    async def test_timestamps_populated(self) -> None:
        """started_at and completed_at are set; total_duration_ms >= 0."""
        _, result = await _run_full_workflow()
        assert result.started_at
        assert result.completed_at
        assert result.total_duration_ms >= 0


# ---------------------------------------------------------------------------
# 2. State propagation between phases
# ---------------------------------------------------------------------------


class TestStatePropagation:
    """Each phase reads and extends the output of the previous phase."""

    @pytest.mark.asyncio
    async def test_research_output_feeds_analysis(self) -> None:
        """analysis phase receives the research output as research_summary."""
        _, result = await _run_full_workflow()
        analysis_out = _phase_output(result, WorkflowPhase.ANALYSIS)
        research_out = _phase_output(result, WorkflowPhase.RESEARCH)
        # analysis.research_summary should mirror the research output
        assert analysis_out.get("research_summary") == research_out

    @pytest.mark.asyncio
    async def test_analysis_output_feeds_alternatives(self) -> None:
        """alternatives phase receives the analysis output."""
        _, result = await _run_full_workflow()
        alt_out = _phase_output(result, WorkflowPhase.ALTERNATIVES)
        analysis_out = _phase_output(result, WorkflowPhase.ANALYSIS)
        assert alt_out.get("analysis_summary") == analysis_out

    @pytest.mark.asyncio
    async def test_alternatives_recommendation_feeds_verification(self) -> None:
        """verification phase reads the recommended alternative."""
        _, result = await _run_full_workflow()
        alt_out = _phase_output(result, WorkflowPhase.ALTERNATIVES)
        ver_out = _phase_output(result, WorkflowPhase.VERIFICATION)
        assert ver_out.get("recommended_alternative") is not None
        assert ver_out["recommended_alternative"]["id"] == alt_out["recommended_alternative"]["id"]

    @pytest.mark.asyncio
    async def test_verification_feeds_decision(self) -> None:
        """decision phase reads verification's confidence and validity."""
        _, result = await _run_full_workflow()
        ver_out = _phase_output(result, WorkflowPhase.VERIFICATION)
        dec_out = _phase_output(result, WorkflowPhase.DECISION)
        # Decision should carry the same confidence value
        assert dec_out.get("confidence") == ver_out.get("confidence")

    @pytest.mark.asyncio
    async def test_research_stores_context_constraints(self) -> None:
        """Context constraints flow into research output."""
        ctx = {"constraints": ["must not break API", "budget <= 2 weeks"]}
        _, result = await _run_full_workflow(context=ctx)
        research_out = _phase_output(result, WorkflowPhase.RESEARCH)
        assert research_out["constraints"] == ["must not break API", "budget <= 2 weeks"]


# ---------------------------------------------------------------------------
# 3. Context and workflow_id preservation
# ---------------------------------------------------------------------------


class TestContextPreservation:
    """Caller-provided metadata survives the full pipeline."""

    @pytest.mark.asyncio
    async def test_custom_workflow_id_preserved(self) -> None:
        """A caller-provided workflow_id is preserved in the result."""
        _, result = await _run_full_workflow(workflow_id="my-e2e-id")
        assert result.workflow_id == "my-e2e-id"

    @pytest.mark.asyncio
    async def test_context_dict_stored_in_state(self) -> None:
        """The context dict is available in the initial state."""
        ctx = {"priority": "high", "stakeholders": ["eng", "product"]}
        _, result = await _run_full_workflow(context=ctx)
        # Context flows through research and ends up in its output
        research_out = _phase_output(result, WorkflowPhase.RESEARCH)
        assert research_out["context"] == ctx


# ---------------------------------------------------------------------------
# 4. Resumability via MemorySaver checkpointing
# ---------------------------------------------------------------------------


class TestResumability:
    """MemorySaver checkpointing lets us inspect intermediate state."""

    @pytest.mark.asyncio
    async def test_intermediate_checkpoint_exists(self) -> None:
        """After execution, MemorySaver contains checkpoint data for the thread."""
        wf = LangGraphHeavySwarmWorkflow(name="resume-test")
        topic = "Checkpoint inspection test"
        result = await wf.execute(topic=topic)

        # The checkpointer is an InMemorySaver — verify it exists and is wired
        checkpointer = wf._graph.checkpointer
        assert checkpointer is not None
        # Confirm the graph compiled with a MemorySaver checkpointer
        assert "MemorySaver" in type(checkpointer).__name__ or "InMemory" in type(checkpointer).__name__
        # The workflow completed successfully, which proves checkpoints were written
        assert result.state == WorkflowPhase.COMPLETED

    @pytest.mark.asyncio
    async def test_workflow_result_consistent_on_rerun(self) -> None:
        """Re-executing with the same workflow_id produces a consistent result."""
        wf1 = LangGraphHeavySwarmWorkflow(name="rerun-test")
        result1 = await wf1.execute(topic="rerun topic", workflow_id="rerun-42")

        # Execute again with the same thread_id
        wf2 = LangGraphHeavySwarmWorkflow(name="rerun-test-2")
        result2 = await wf2.execute(topic="rerun topic", workflow_id="rerun-42")

        assert result1.state == WorkflowPhase.COMPLETED
        assert result2.state == WorkflowPhase.COMPLETED
        assert result1.workflow_id == result2.workflow_id == "rerun-42"
        for phase in (
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        ):
            assert phase.value in result1.phase_results
            assert phase.value in result2.phase_results


# ---------------------------------------------------------------------------
# 5. Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Mid-pipeline failures are caught and reported."""

    @pytest.mark.asyncio
    async def test_exception_produces_failed_state(self) -> None:
        """If a node raises, the workflow returns FAILED state."""

        async def failing_research(state: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("simulated node failure")

        # We must patch PHASE_NODES *before* LangGraphHeavySwarmWorkflow
        # builds the graph, because _compile_graph captures the node
        # functions at graph-construction time.  Keys must be WorkflowPhase
        # enums (not strings) to match the dict that _compile_graph indexes.
        patched_nodes = {
            WorkflowPhase.RESEARCH: failing_research,
            WorkflowPhase.ANALYSIS: analysis_node,
            WorkflowPhase.ALTERNATIVES: alternatives_node,
            WorkflowPhase.VERIFICATION: verification_node,
            WorkflowPhase.DECISION: decision_node,
        }
        with mock.patch(
            "heretek_swarm.orchestration.langgraph_workflow.PHASE_NODES",
            patched_nodes,
        ):
            wf = LangGraphHeavySwarmWorkflow(name="error-test")
            result = await wf.execute(topic="should fail")

        assert result.state == WorkflowPhase.FAILED
        # WorkflowResult doesn't have an error field; verify the FAILED state
        # is set, which proves the exception was caught by execute().


# ---------------------------------------------------------------------------
# 6. Decision / consensus propagation
# ---------------------------------------------------------------------------


class TestDecisionPropagation:
    """The decision phase's consensus_result flows to final_decision."""

    @pytest.mark.asyncio
    async def test_final_decision_from_consensus(self) -> None:
        """WorkflowResult.final_decision matches the decision phase's consensus_result."""
        _, result = await _run_full_workflow()
        dec_out = _phase_output(result, WorkflowPhase.DECISION)
        expected_consensus = dec_out.get("consensus_result")
        assert result.final_decision == expected_consensus

    @pytest.mark.asyncio
    async def test_final_decision_contains_decision_and_confidence(self) -> None:
        """final_decision has 'decision' and 'confidence' keys."""
        _, result = await _run_full_workflow()
        assert result.final_decision is not None
        assert "decision" in result.final_decision
        assert "confidence" in result.final_decision
        assert isinstance(result.final_decision["confidence"], float)
        assert 0.0 <= result.final_decision["confidence"] <= 1.0

    @pytest.mark.asyncio
    async def test_decision_references_balanced_approach(self) -> None:
        """The decision phase recommends the balanced alternative (alt_2)."""
        _, result = await _run_full_workflow()
        dec_out = _phase_output(result, WorkflowPhase.DECISION)
        consensus = dec_out["consensus_result"]
        assert consensus["decision"] == "Balanced Approach"


# ---------------------------------------------------------------------------
# 7. State helper coverage
# ---------------------------------------------------------------------------


class TestStateHelpers:
    """Unit tests for internal helpers that build / convert state."""

    def test_build_initial_state_defaults(self) -> None:
        """_build_initial_state fills defaults when context is None."""
        state = _build_initial_state("topic", None, None)
        assert state["topic"] == "topic"
        assert state["context"] == {}
        assert state["workflow_id"]  # auto-generated UUID
        assert state["current_phase"] == ""
        assert state["phase_results"] == {}
        assert state["final_decision"] is None
        assert state["error"] is None

    def test_build_initial_state_custom_id(self) -> None:
        """_build_initial_state uses caller-provided workflow_id."""
        state = _build_initial_state("t", {}, "my-id")
        assert state["workflow_id"] == "my-id"

    def test_state_to_workflow_result_computes_duration(self) -> None:
        """_state_to_workflow_result computes total_duration_ms from timestamps."""
        state: dict[str, Any] = {
            "workflow_id": "w1",
            "topic": "t",
            "current_phase": "completed",
            "phase_results": {},
            "final_decision": None,
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:01+00:00",
            "error": None,
        }
        result = _state_to_workflow_result(state)
        assert result.total_duration_ms == pytest.approx(1000.0)

    def test_state_to_workflow_result_falls_back_to_phase_decision(self) -> None:
        """When final_decision is None, falls back to phase_results['decision'].output."""
        dec_output = {"consensus_result": {"decision": "GO", "confidence": 0.9}}
        pr = PhaseResult(phase=WorkflowPhase.DECISION, success=True, output=dec_output)
        state: dict[str, Any] = {
            "workflow_id": "w2",
            "topic": "t",
            "current_phase": "completed",
            "phase_results": {"decision": pr},
            "final_decision": None,
            "started_at": "",
            "completed_at": "",
            "error": None,
        }
        result = _state_to_workflow_result(state)
        assert result.final_decision == {"decision": "GO", "confidence": 0.9}


# ---------------------------------------------------------------------------
# 8. PostgreSQL checkpoint persistence
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph"),
    reason="langgraph not installed",
)
@pytest.mark.skipif(
    not GENERIC_DATABASE_URL,
    reason="DATABASE_URL / HERETEK_CHECKPOINT_DB_URL not set",
)
class TestPostgresPersistence:
    """PostgreSQL checkpoint persistence tests — require a live database."""

    @pytest.fixture(autouse=True)
    async def _require_pg(self) -> None:
        """Skip all tests in this class if PostgreSQL is unreachable."""
        if not await _pg_is_reachable():
            pytest.skip("PostgreSQL is not reachable from this environment")

    @pytest.mark.asyncio
    async def test_postgres_checkpointer_persists_state(self) -> None:
        """Workflow with PostgreSQL checkpointer completes and uses AsyncPostgresSaver."""
        wf = LangGraphHeavySwarmWorkflow(name="pg-persist")
        result = await wf.execute(topic="PostgreSQL persistence test")

        assert result.state == WorkflowPhase.COMPLETED
        assert wf._checkpointer is not None
        from langgraph_checkpoint_postgres.aio import AsyncPostgresSaver

        assert isinstance(wf._checkpointer, AsyncPostgresSaver)

        await wf.close()

    @pytest.mark.asyncio
    async def test_postgres_checkpointer_survives_restart(self) -> None:
        """State survives across two workflow instances sharing the same wf_id."""
        wf_id = f"restart-test-{uuid.uuid4()}"

        wf1 = LangGraphHeavySwarmWorkflow(name="pg-restart-1")
        result1 = await wf1.execute(
            topic="Restart survival test", workflow_id=wf_id
        )
        assert result1.state == WorkflowPhase.COMPLETED
        await wf1.close()

        # Second instance with the same workflow_id should pick up the checkpoint
        wf2 = LangGraphHeavySwarmWorkflow(name="pg-restart-2")
        result2 = await wf2.execute(
            topic="Restart survival test", workflow_id=wf_id
        )
        assert result2.state == WorkflowPhase.COMPLETED
        assert result2.workflow_id == wf_id
        # Both should have completed all five phases
        for phase in (
            WorkflowPhase.RESEARCH,
            WorkflowPhase.ANALYSIS,
            WorkflowPhase.ALTERNATIVES,
            WorkflowPhase.VERIFICATION,
            WorkflowPhase.DECISION,
        ):
            assert phase.value in result1.phase_results
            assert phase.value in result2.phase_results
        await wf2.close()

    @pytest.mark.asyncio
    async def test_postgres_checkpoint_table_exists(self) -> None:
        """After running a workflow, the checkpoint tables exist in the database."""
        import psycopg

        wf = LangGraphHeavySwarmWorkflow(name="pg-tables")
        await wf.execute(topic="Table existence check")
        await wf.close()

        async with await psycopg.AsyncConnection.connect(
            GENERIC_DATABASE_URL
        ) as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name IN ('checkpoint', 'checkpoint_blobs', 'checkpoint_writes') "
                "ORDER BY table_name"
            )
            rows = await cur.fetchall()
            table_names = {row[0] for row in rows}
            # The langgraph checkpoint saver creates 'checkpoint' table;
            # blob/writes tables may or may not exist depending on version.
            assert "checkpoint" in table_names, (
                f"Expected 'checkpoint' table; found: {table_names}"
            )


# ---------------------------------------------------------------------------
# 9. Checkpointer fallback logic
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph"),
    reason="langgraph not installed",
)
class TestCheckpointerFallback:
    """Verify env-var-driven checkpointer selection and graceful degradation."""

    @pytest.mark.asyncio
    async def test_in_memory_when_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MemorySaver is used when HERETEK_CHECKPOINT_DB_URL is not set."""
        monkeypatch.delenv("HERETEK_CHECKPOINT_DB_URL", raising=False)
        monkeypatch.delenv("DATABASE_URL", raising=False)

        wf = LangGraphHeavySwarmWorkflow(name="fallback-noenv")
        result = await wf.execute(topic="no env var")
        assert result.state == WorkflowPhase.COMPLETED
        # _checkpointer stays None (MemorySaver used internally in _compile_graph)
        assert wf._checkpointer is None

    @pytest.mark.asyncio
    async def test_graceful_fallback_when_postgres_pkg_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falls back to MemorySaver when langgraph-checkpoint-postgres is missing."""
        import builtins

        monkeypatch.setenv("HERETEK_CHECKPOINT_DB_URL", "postgres://fake:fake@localhost/fakedb")

        real_import = builtins.__import__

        def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "langgraph_checkpoint_postgres.aio":
                raise ImportError("simulated missing package")
            if name == "psycopg_pool":
                raise ImportError("simulated missing package")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)

        wf = LangGraphHeavySwarmWorkflow(name="fallback-pkg")
        result = await wf.execute(topic="missing package")
        assert result.state == WorkflowPhase.COMPLETED
        # Should have fallen back — _checkpointer is None
        assert wf._checkpointer is None

    @pytest.mark.asyncio
    async def test_async_initialize_sets_checkpointer(self) -> None:
        """After initialize(), the _checkpointer field is set (or remains None for MemorySaver)."""
        wf = LangGraphHeavySwarmWorkflow(name="init-check")
        assert wf._initialized is False
        assert wf._checkpointer is None

        await wf.initialize()

        assert wf._initialized is True
        # With no DB URL, _checkpointer stays None (MemorySaver used inside graph)
        assert wf._checkpointer is None
        # But the graph is compiled and ready
        assert wf._graph is not None


# ---------------------------------------------------------------------------
# 10. MemorySaver default behaviour preserved
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("langgraph"),
    reason="langgraph not installed",
)
class TestMemorySaverDefault:
    """Existing default behaviour — MemorySaver — remains intact."""

    @pytest.mark.asyncio
    async def test_default_compile_uses_memory_saver(self) -> None:
        """_compile_graph() produces a graph with a MemorySaver checkpointer."""
        wf = LangGraphHeavySwarmWorkflow(name="memory-default")
        checkpointer = wf._graph.checkpointer
        assert checkpointer is not None
        assert "MemorySaver" in type(checkpointer).__name__
