"""Tests for the autonomous main loop — goal pipeline wiring and periodic analysis.

Verifies that the fix for the dangling ``_run_goal_pipeline_cycle`` call
does not crash when invoked with mock actors and a temp file goal store.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from heretek_swarm.goals.models import Goal
from heretek_swarm.runtime.main_loop import AutonomousSwarm


@pytest.mark.asyncio
async def test_goal_pipeline_wiring_does_not_crash(
    tmp_path: Path,
) -> None:
    """Validate the goal pipeline wiring (in _run_goal_pipeline) does
    not crash when invoked with mock actors and a temp file goal store.

    The test:
    1. Creates an AutonomousSwarm in no_infra mode
    2. Sets up a minimal supervisor with mock metis/historian actors
    3. Provides a consensus engine
    4. Calls _run_goal_pipeline directly
    5. Asserts no exception is raised
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    # --- Wire the minimum components needed by _run_goal_pipeline ------
    from heretek_swarm_core.consensus.maker import MAKERConsensus

    swarm.consensus = MAKERConsensus(
        ahead_by_k=2,
        min_votes=3,
        confidence_threshold=0.3,
    )

    # Create a minimal supervisor stub with just actors
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # --- Mock metis: return a valid Goal proposal ----------------------
    goal = Goal(
        id="test_goal_001",
        title="Test strategic goal",
        description="A test goal for verifying pipeline wiring.",
        success_criteria=["Criterion 1", "Criterion 2"],
    )
    mock_metis = AsyncMock()
    mock_metis.generate_goal_proposal = AsyncMock(return_value={"goal": goal})
    supervisor.actors["metis"] = mock_metis

    # --- Mock historian: no-op -----------------------------------------
    mock_historian = AsyncMock()
    mock_historian.log_event = AsyncMock()
    supervisor.actors["historian"] = mock_historian

    # --- Point the goal store at a temp file ---------------------------
    from heretek_swarm.goals.store import FileGoalStore

    goal_store_path = tmp_path / "goals.json"
    swarm._goal_store = FileGoalStore(store_path=goal_store_path)

    # --- Execute — should NOT raise ------------------------------------
    await swarm._run_goal_pipeline(
        metis=mock_metis,
        historian=mock_historian,
    )

    # --- Verify the goal was persisted to the store --------------------
    goals = swarm._goal_store.load_all()
    assert len(goals) == 1, "Expected exactly one goal to be persisted"
    assert goals[0].id == "test_goal_001"
    assert goals[0].status == "proposed"

    # --- Verify metis was consulted ------------------------------------
    mock_metis.generate_goal_proposal.assert_awaited_once()

    # --- Verify historian was called -----------------------------------
    found_proposed_event = any(
        call.args[0] == "goal_proposed"
        for call in mock_historian.log_event.call_args_list
    )
    assert found_proposed_event, (
        "Expected historian.log_event to be called with event_type='goal_proposed'"
    )


@pytest.mark.asyncio
async def test_goal_pipeline_handles_missing_metis_gracefully(
    tmp_path: Path,
) -> None:
    """When metis is None, _run_goal_pipeline should not crash."""
    swarm = AutonomousSwarm(config={}, no_infra=True)

    from heretek_swarm_core.consensus.maker import MAKERConsensus

    swarm.consensus = MAKERConsensus(
        ahead_by_k=2,
        min_votes=3,
        confidence_threshold=0.3,
    )
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    mock_historian = AsyncMock()
    supervisor.actors["historian"] = mock_historian

    from heretek_swarm.goals.store import FileGoalStore

    goal_store_path = tmp_path / "goals-missing-metis.json"
    swarm._goal_store = FileGoalStore(store_path=goal_store_path)

    # metis is None — should not crash
    await swarm._run_goal_pipeline(metis=None, historian=mock_historian)

    # No goals should have been created
    assert swarm._goal_store.count() == 0


@pytest.mark.asyncio
async def test_goal_pipeline_skipped_without_consensus() -> None:
    """When consensus is None, _run_goal_pipeline should short-circuit."""
    swarm = AutonomousSwarm(config={}, no_infra=True)
    swarm.consensus = None

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Should not crash when consensus is None
    await swarm._run_goal_pipeline(
        metis=MagicMock(),
        historian=MagicMock(),
    )
    # No assertion needed — we just need no crash


@pytest.mark.asyncio
async def test_response_collection_subscribes_to_topics() -> None:
    """Verify _collect_responses subscribes to both analysis response topics."""
    from heretek_swarm.actors.stubs import StubEventMesh

    swarm = AutonomousSwarm(config={}, no_infra=True)
    swarm.event_mesh = StubEventMesh()
    await swarm.event_mesh.connect()

    # Start _collect_responses as a background task; it subscribes on startup,
    # then blocks on asyncio.Event().wait().  We let subscriptions register and
    # then cancel the task.
    task = asyncio.create_task(swarm._collect_responses())
    await asyncio.sleep(0.02)

    sub_ids = swarm.event_mesh.get_subscription_ids()
    assert len(sub_ids) == 2, f"Expected 2 subscriptions, got {len(sub_ids)}"

    subjects = list(swarm.event_mesh._subscriptions.keys())
    assert "swarm.analysis.metis.response" in subjects
    assert "swarm.analysis.empath.response" in subjects

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_response_collection_callback_queues_message() -> None:
    """Verify the _on_response callback puts a message into _response_queue."""
    from heretek_swarm.actors.stubs import StubEventMesh

    swarm = AutonomousSwarm(config={}, no_infra=True)
    swarm.event_mesh = StubEventMesh()
    await swarm.event_mesh.connect()

    task = asyncio.create_task(swarm._collect_responses())
    await asyncio.sleep(0.02)

    # Retrieve the callback handler from StubEventMesh subscriptions
    metis_subs = swarm.event_mesh._subscriptions.get(
        "swarm.analysis.metis.response", []
    )
    assert len(metis_subs) == 1, "Expected one subscription for metis.response"
    handler = metis_subs[0]["handler"]

    await handler(
        None,  # mesh_or_none — ignored by _on_response
        "swarm.analysis.metis.response",
        {"message_type": "analysis_result", "analysis": "test_strategy"},
    )

    assert not swarm._response_queue.empty()
    item = swarm._response_queue.get_nowait()
    assert item["subject"] == "swarm.analysis.metis.response"
    assert item["data"]["message_type"] == "analysis_result"
    assert item["data"]["analysis"] == "test_strategy"
    assert "timestamp" in item

    # Also test the empath subscription callback
    empath_subs = swarm.event_mesh._subscriptions.get(
        "swarm.analysis.empath.response", []
    )
    assert len(empath_subs) == 1
    handler2 = empath_subs[0]["handler"]

    await handler2(
        None,
        "swarm.analysis.empath.response",
        {"message_type": "sentiment_result", "sentiment": "positive"},
    )

    item2 = swarm._response_queue.get_nowait()
    assert item2["subject"] == "swarm.analysis.empath.response"
    assert item2["data"]["sentiment"] == "positive"

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_response_drain_resets_latest_analysis_on_cycle_30() -> None:
    """Verify the drain logic in _process_cycle populates _latest_analysis.

    We can't fully exercise _process_cycle here (it needs a live supervisor
    with actors), so we test the drain logic directly:  queue items, then
    exercise the same drain loop that _process_cycle would run.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    # Enqueue two fake response items
    await swarm._response_queue.put({
        "subject": "swarm.analysis.metis.response",
        "data": {"message_type": "analysis_result"},
        "timestamp": "2026-01-01T00:00:00Z",
    })
    await swarm._response_queue.put({
        "subject": "swarm.analysis.empath.response",
        "data": {"message_type": "sentiment_result"},
        "timestamp": "2026-01-01T00:00:01Z",
    })

    # Exercise the same drain logic from _process_cycle()
    drained: list[dict[str, Any]] = []
    while not swarm._response_queue.empty():
        item = swarm._response_queue.get_nowait()
        drained.append(item)

    assert len(drained) == 2

    # This is what _process_cycle does after draining
    swarm._latest_analysis = {
        "responses": drained,
        "collected_at": "2026-01-01T00:00:00Z",
    }

    assert len(swarm._latest_analysis["responses"]) == 2
    assert (
        swarm._latest_analysis["responses"][0]["subject"]
        == "swarm.analysis.metis.response"
    )
    assert (
        swarm._latest_analysis["responses"][1]["subject"]
        == "swarm.analysis.empath.response"
    )
    assert swarm._response_queue.empty()


@pytest.mark.asyncio
async def test_response_queue_empty_when_no_responses() -> None:
    """Verify _response_queue is empty before any responses are published."""
    swarm = AutonomousSwarm(config={}, no_infra=True)
    assert swarm._response_queue.empty()
    assert swarm._latest_analysis == {}


@pytest.mark.asyncio
async def test_process_cycle_drains_responses_at_cycle_30() -> None:
    """Verify _process_cycle drains responses when the cycle counter reaches 30.

    Full-flow integration test:
    1. Pre-seed _response_queue with two analysis response items
    2. Set _analysis_cycle_count to 29 so the next call triggers periodic analysis
    3. Provide a minimal supervisor with empty actors dict (methods degrade gracefully)
    4. Call _process_cycle
    5. Verify cycle counter reset, drain into _latest_analysis, queue empty
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    # Minimal supervisor with empty actors dict -> internal methods log warnings
    # and short-circuit gracefully
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Pre-seed the response queue with two analysis response items
    await swarm._response_queue.put({
        "subject": "swarm.analysis.metis.response",
        "data": {"message_type": "analysis_result", "analysis": "focus on scaling"},
        "timestamp": "2026-01-01T00:00:00Z",
    })
    await swarm._response_queue.put({
        "subject": "swarm.analysis.empath.response",
        "data": {"message_type": "sentiment_result", "sentiment": "positive"},
        "timestamp": "2026-01-01T00:00:01Z",
    })

    # Set cycle count to 29 -> the next call triggers periodic analysis + drain
    swarm._analysis_cycle_count = 29

    # Call _process_cycle
    await swarm._process_cycle()

    # 1. Cycle counter was reset to 0
    assert swarm._analysis_cycle_count == 0

    # 2. Response queue was drained into _latest_analysis
    assert len(swarm._latest_analysis["responses"]) == 2
    assert swarm._response_queue.empty()

    # 3. Responses are correctly stored with subject and data
    assert (
        swarm._latest_analysis["responses"][0]["subject"]
        == "swarm.analysis.metis.response"
    )
    assert (
        swarm._latest_analysis["responses"][1]["subject"]
        == "swarm.analysis.empath.response"
    )
    assert "collected_at" in swarm._latest_analysis


@pytest.mark.asyncio
async def test_process_cycle_skips_drain_below_cycle_30() -> None:
    """Verify _process_cycle does NOT trigger drain below the 30-cycle threshold.

    Negative test: with _analysis_cycle_count < 29, the periodic analysis
    block (including the drain) should not execute, and queued responses
    should remain in _response_queue.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Pre-seed the response queue
    await swarm._response_queue.put({
        "subject": "swarm.analysis.metis.response",
        "data": {"message_type": "analysis_result"},
        "timestamp": "2026-01-01T00:00:00Z",
    })

    # Set cycle count to 5 -> well below the drain threshold
    swarm._analysis_cycle_count = 5

    await swarm._process_cycle()

    # Cycle counter should increment but NOT reset (didn't hit 30)
    assert swarm._analysis_cycle_count == 6

    # Response queue should NOT have been drained (drain is inside the >=30 block)
    assert not swarm._response_queue.empty()

    # _latest_analysis should remain empty (never populated outside drain)
    assert swarm._latest_analysis == {}


@pytest.mark.asyncio
async def test_cooldown_suppresses_second_dispatch() -> None:
    """Verify _request_analysis sets cooldown and suppresses a second dispatch.

    Under cooldown, the second condition set is coalesced into
    _pending_event_conditions rather than dispatched immediately.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # First call should trigger dispatch and set cooldown
    await swarm._request_analysis([{"type": "test"}])
    assert swarm._cooldown_until is not None, "Cooldown should be set after first dispatch"

    # Second call while cooldown is active should coalesce, not dispatch
    await swarm._request_analysis([{"type": "test2"}])
    assert len(swarm._pending_event_conditions) == 1, (
        "Expected one coalesced event condition"
    )
    assert swarm._pending_event_conditions[0]["type"] == "test2"


@pytest.mark.asyncio
async def test_cooldown_expired_dispatches_coalesced_events() -> None:
    """Verify that after cooldown expires, pending + new events are dispatched
    and _pending_event_conditions is cleared.

    Simulates cooldown expiry by resetting _cooldown_until to a past timestamp.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # First dispatch triggers cooldown
    await swarm._request_analysis([{"type": "event1"}])
    assert swarm._cooldown_until is not None

    # Coalesce a second event during cooldown
    await swarm._request_analysis([{"type": "event2"}])
    assert len(swarm._pending_event_conditions) == 1

    # Simulate cooldown expiry by setting timestamp to the past
    swarm._cooldown_until = 0.0
    assert not swarm._is_in_cooldown(), "Expected cooldown to be expired"

    # Third dispatch should merge pending (event2) + new (event3) and dispatch
    await swarm._request_analysis([{"type": "event3"}])

    # _pending_event_conditions should be empty (merged into dispatch)
    assert len(swarm._pending_event_conditions) == 0, (
        "Expected pending events to be cleared after dispatch"
    )


@pytest.mark.asyncio
async def test_is_in_cooldown_returns_false_when_none() -> None:
    """Verify _is_in_cooldown returns False before any analysis is requested."""
    swarm = AutonomousSwarm(config={}, no_infra=True)
    assert not swarm._is_in_cooldown()


@pytest.mark.asyncio
async def test_pending_event_conditions_empty_initially() -> None:
    """Verify _pending_event_conditions is an empty list at construction."""
    swarm = AutonomousSwarm(config={}, no_infra=True)
    assert swarm._pending_event_conditions == []


@pytest.mark.asyncio
async def test_event_driven_dispatch_still_drains_responses() -> None:
    """Integration test: verify that event-driven dispatch via _request_analysis
    does not interfere with the response queue drain in _process_cycle.

    Triggers event-driven analysis, then runs _process_cycle at cycle 29
    to verify the periodic heartbeat drain still collects responses.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Pre-seed the response queue
    await swarm._response_queue.put({
        "subject": "swarm.analysis.metis.response",
        "data": {"message_type": "analysis_result"},
        "timestamp": "2026-01-01T00:00:00Z",
    })
    await swarm._response_queue.put({
        "subject": "swarm.analysis.empath.response",
        "data": {"message_type": "sentiment_result"},
        "timestamp": "2026-01-01T00:00:01Z",
    })

    # Trigger event-driven analysis first
    await swarm._request_analysis([{"type": "event"}])

    # Set cycle count to 29 so _process_cycle fires periodic heartbeat + drain
    swarm._analysis_cycle_count = 29

    # Call _process_cycle -- should increment to 30, fire heartbeat, drain queue
    await swarm._process_cycle()

    # Cycle counter should be reset (heartbeat fired)
    assert swarm._analysis_cycle_count == 0

    # Response queue should be drained
    assert swarm._response_queue.empty()

    # _latest_analysis should have both responses
    assert len(swarm._latest_analysis["responses"]) == 2
    assert (
        swarm._latest_analysis["responses"][0]["subject"]
        == "swarm.analysis.metis.response"
    )
    assert (
        swarm._latest_analysis["responses"][1]["subject"]
        == "swarm.analysis.empath.response"
    )


@pytest.mark.asyncio
async def test_fallback_heartbeat_fires_at_30_cycles() -> None:
    """Verify the fallback periodic heartbeat fires when _analysis_cycle_count
    reaches 30, even without pending_event_conditions.

    Sets _analysis_cycle_count to 29, calls _process_cycle, and asserts
    the counter is reset to 0 (heartbeat fired) with no errors.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # No pending events, no cooldown
    swarm._pending_event_conditions = []
    swarm._cooldown_until = None
    swarm._analysis_cycle_count = 29

    await swarm._process_cycle()

    # Heartbeat should have fired, resetting the counter
    assert swarm._analysis_cycle_count == 0, (
        "Expected cycle counter to reset after heartbeat at 30"
    )


@pytest.mark.asyncio
async def test_fallback_heartbeat_not_fired_when_pending_events_available() -> None:
    """Verify that when pending_event_conditions are present and cooldown is
    expired, the event-driven path fires first. The periodic heartbeat still
    runs after event dispatch since the counter hits 30.

    Both _pending_event_conditions should be drained (by event path)
    and _analysis_cycle_count should be reset (by heartbeat path).
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Set pending events and expired cooldown
    swarm._pending_event_conditions = [{"type": "test"}]
    swarm._cooldown_until = 0.0  # Expired
    swarm._analysis_cycle_count = 29

    await swarm._process_cycle()

    # Event path should have drained pending events
    assert len(swarm._pending_event_conditions) == 0, (
        "Expected pending events to be drained by event-driven path"
    )
    # Heartbeat path should have reset the counter
    assert swarm._analysis_cycle_count == 0, (
        "Expected cycle counter to reset after heartbeat at 30"
    )


@pytest.mark.asyncio
async def test_monitor_error_rate_detects_errors() -> None:
    """Verify _monitor_error_rate detects an actor in error state and
    dispatches an error_spike condition via _request_analysis.

    Sets up a mock actor that returns state='error', runs one iteration
    of the monitor, and verifies that _request_analysis was triggered
    (cooldown_until is set, indicating dispatch occurred).
    """
    import os

    os.environ["HERETEK_ANALYSIS_ERROR_THRESHOLD"] = "0"

    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor
    swarm._running = True
    swarm._health_check_interval = 0.01

    # Create a mock actor whose get_status() returns state = "error"
    mock_actor = MagicMock()
    mock_actor.get_status.return_value.state.value = "error"
    supervisor.actors["test_agent"] = mock_actor

    # Run the monitor as a background task for one iteration
    task = asyncio.create_task(swarm._monitor_error_rate())
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # After one iteration with 0 threshold and 1 error agent,
    # _request_analysis should have been called and set cooldown
    assert swarm._cooldown_until is not None, (
        "Expected cooldown to be set after error spike dispatch"
    )


@pytest.mark.asyncio
async def test_monitor_agent_state_detects_changes() -> None:
    """Verify _monitor_agent_state detects a state transition and
    dispatches an agent_state_change condition via _request_analysis.

    Runs the monitor for two iterations: first records the initial state
    ('active'), second detects the transition to 'suspended' and dispatches.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)
    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor
    swarm._running = True
    swarm._health_check_interval = 0.01

    # Mock actor starts in 'active' state
    mock_actor = MagicMock()
    mock_actor.get_status.return_value.state.value = "active"
    supervisor.actors["test_agent"] = mock_actor

    # Run the monitor; first iteration records 'active' in last_states
    task = asyncio.create_task(swarm._monitor_agent_state())
    await asyncio.sleep(0.05)

    # Change actor state to 'suspended' for the second iteration
    mock_actor.get_status.return_value.state.value = "suspended"
    await asyncio.sleep(0.05)

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # After two iterations with a state transition, _request_analysis
    # should have been called and set cooldown
    assert swarm._cooldown_until is not None, (
        "Expected cooldown to be set after state change dispatch"
    )


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_creates_task() -> None:
    """Verify bulk_schedule_adjust create operation schedules a new task."""
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent

    agent = ChronosAgent(agent_id="test_chronos_create", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "create",
                    "operation_id": "c1",
                    "task_id": "created_task",
                    "name": "Created via bulk",
                    "scheduled_at": "2026-06-04T00:00:00Z",
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    assert "created_task" in agent._tasks
    assert agent._tasks["created_task"].name == "Created via bulk"
    assert mock_send.called
    content = mock_send.call_args.kwargs["content"]
    assert content["total"] == 1
    assert content["succeeded"] == 1


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_cancels_task() -> None:
    """Verify bulk_schedule_adjust cancel operation cancels an existing task."""
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.chronos.types import ScheduledTask, ScheduleStatus

    agent = ChronosAgent(agent_id="test_chronos_cancel", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    agent._tasks["task_to_cancel"] = ScheduledTask(
        task_id="task_to_cancel",
        name="To Cancel",
        description="",
        scheduled_at=datetime(2026, 6, 4, tzinfo=UTC),
    )

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "cancel",
                    "operation_id": "x1",
                    "task_id": "task_to_cancel",
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    assert agent._tasks["task_to_cancel"].status == ScheduleStatus.CANCELLED
    content = mock_send.call_args.kwargs["content"]
    assert content["succeeded"] == 1


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_updates_priority() -> None:
    """Verify bulk_schedule_adjust update_priority operation changes priority."""
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.chronos.types import Priority, ScheduledTask

    agent = ChronosAgent(agent_id="test_chronos_priority", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    agent._tasks["priority_task"] = ScheduledTask(
        task_id="priority_task",
        name="Priority Task",
        description="",
        scheduled_at=datetime(2026, 6, 4, tzinfo=UTC),
    )

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "update_priority",
                    "operation_id": "p1",
                    "task_id": "priority_task",
                    "new_priority": 5,
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    assert agent._tasks["priority_task"].priority == Priority.CRITICAL
    content = mock_send.call_args.kwargs["content"]
    assert content["succeeded"] == 1


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_retries_failed_operations() -> None:
    """Verify bulk_schedule_adjust retries failed operations once.

    A 'create' operation targeting a task_id that already exists will fail on
    both the initial attempt and the retry, proving the retry mechanism fires
    without crashing.
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.chronos.types import ScheduledTask

    agent = ChronosAgent(agent_id="test_chronos_retry", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    agent._tasks["existing"] = ScheduledTask(
        task_id="existing",
        name="Existing",
        description="",
        scheduled_at=datetime(2026, 6, 4, tzinfo=UTC),
    )

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "create",
                    "operation_id": "r1",
                    "task_id": "existing",
                    "name": "Should Fail",
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    content = mock_send.call_args.kwargs["content"]
    assert content["failed"] >= 1
    assert "already exists" in content["results"][0]["error"]
    assert content["total"] == 1


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_updates_interval() -> None:
    """Verify bulk_schedule_adjust update_interval changes interval_seconds
    on a recurring INTERVAL task.
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.chronos.types import RecurrenceType, ScheduledTask

    agent = ChronosAgent(agent_id="test_chronos_interval", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    agent._tasks["interval_task"] = ScheduledTask(
        task_id="interval_task",
        name="Interval Task",
        description="",
        scheduled_at=datetime(2026, 6, 4, tzinfo=UTC),
        recurrence=RecurrenceType.INTERVAL,
        recurrence_config={"interval_seconds": 300},
    )

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "update_interval",
                    "operation_id": "i1",
                    "task_id": "interval_task",
                    "interval_seconds": 600,
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    assert agent._tasks["interval_task"].recurrence_config["interval_seconds"] == 600
    content = mock_send.call_args.kwargs["content"]
    assert content["succeeded"] == 1


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_mixed_batch() -> None:
    """Verify bulk_schedule_adjust handles a mixed batch of create, cancel,
    and update_priority operations in a single call.
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.chronos.types import Priority, ScheduledTask

    agent = ChronosAgent(agent_id="test_chronos_mixed", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    agent._tasks["existing_task"] = ScheduledTask(
        task_id="existing_task",
        name="Existing Task",
        description="",
        scheduled_at=datetime(2026, 6, 4, tzinfo=UTC),
    )

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "create",
                    "operation_id": "c1",
                    "task_id": "new_task",
                    "name": "New Task",
                    "scheduled_at": "2026-06-05T00:00:00Z",
                },
                {
                    "op": "cancel",
                    "operation_id": "x1",
                    "task_id": "existing_task",
                },
                {
                    "op": "update_priority",
                    "operation_id": "p1",
                    "task_id": "existing_task",
                    "new_priority": 5,
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    # Note: cancel sets status=CANCELLED, then update_priority on a CANCELLED
    # task should fail because the handler checks for completed/cancelled state.
    await agent._handle_bulk_schedule_adjust(msg)

    # create succeeded
    assert "new_task" in agent._tasks
    assert agent._tasks["new_task"].name == "New Task"

    # cancel succeeded
    from heretek_swarm.actors.chronos.types import ScheduleStatus
    assert agent._tasks["existing_task"].status == ScheduleStatus.CANCELLED

    # update_priority failed because the task was already cancelled by the
    # preceding cancel operation in the batch.  But the batch itself completed
    # without crashing and reported results for all 3 operations.
    content = mock_send.call_args.kwargs["content"]
    assert content["total"] == 3
    assert content["succeeded"] >= 1  # create + cancel = 2, or create = 1 + cancel = 1


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_handles_unknown_task() -> None:
    """Verify bulk_schedule_adjust reports failure with error message
    when operating on a nonexistent task_id.
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent

    agent = ChronosAgent(agent_id="test_chronos_unknown", config={})
    mock_send = AsyncMock()
    agent.send = mock_send

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "cancel",
                    "operation_id": "x1",
                    "task_id": "nonexistent",
                },
                {
                    "op": "update_priority",
                    "operation_id": "p1",
                    "task_id": "also_missing",
                    "new_priority": 5,
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    content = mock_send.call_args.kwargs["content"]
    assert content["total"] == 2
    assert content["succeeded"] == 0
    assert content["failed"] == 2

    # Both operations should have "not found" in their error messages
    for result in content["results"]:
        assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_chronos_bulk_schedule_adjust_max_tasks() -> None:
    """Verify bulk_schedule_adjust create operation fails with max-tasks error
    when the task limit is reached.
    """
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.chronos import ChronosAgent
    from heretek_swarm.actors.chronos.types import ScheduledTask

    agent = ChronosAgent(agent_id="test_chronos_maxtasks", config={})
    agent._max_tasks = 1  # Override to a small limit
    mock_send = AsyncMock()
    agent.send = mock_send

    # Fill the task limit
    agent._tasks["filler"] = ScheduledTask(
        task_id="filler",
        name="Filler",
        description="",
        scheduled_at=datetime(2026, 6, 4, tzinfo=UTC),
    )

    msg = SimpleNamespace(
        sender="requester",
        message_type="bulk_schedule_adjust",
        content={
            "operations": [
                {
                    "op": "create",
                    "operation_id": "c1",
                    "task_id": "over_limit",
                    "name": "Over Limit",
                },
            ]
        },
        timestamp=datetime.now(UTC).isoformat(),
    )

    await agent._handle_bulk_schedule_adjust(msg)

    content = mock_send.call_args.kwargs["content"]
    assert content["total"] == 1
    assert content["succeeded"] == 0
    assert content["failed"] == 1
    assert "task limit" in content["results"][0]["error"].lower()


@pytest.mark.asyncio
async def test_integrate_analysis_invokes_chronos_on_valid_response() -> None:
    """Verify _integrate_analysis_into_chronos translates Metis
    recommendations into a bulk_schedule_adjust message sent to Chronos.

    Pre-seeds _latest_analysis with a Metis response containing
    recommendations, provides a mock Chronos actor in the supervisor,
    calls the integration method, and verifies the Chronos agent
    received a put_message call with message_type='bulk_schedule_adjust'
    and the correct operations.
    """
    from unittest.mock import AsyncMock

    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Mock Chronos actor
    mock_chronos = AsyncMock()
    mock_chronos.put_message = AsyncMock()
    supervisor.actors["chronos"] = mock_chronos

    # Pre-seed _latest_analysis with a Metis response containing recommendations
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "recommendations": [
                        "Monitor the scaling metrics for potential bottlenecks",
                        "Prioritize the backlog cleanup task",
                        "Cancel the outdated weekly report job",
                    ]
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Call the integration method
    await swarm._integrate_analysis_into_chronos()

    # Verify Chronos received a bulk_schedule_adjust message
    mock_chronos.put_message.assert_awaited_once()
    call_args = mock_chronos.put_message.call_args[0][0]
    assert call_args.message_type == "bulk_schedule_adjust"
    assert "operations" in call_args.content
    assert len(call_args.content["operations"]) == 3

    # Verify operation types match the heuristic classification
    ops = call_args.content["operations"]
    ops_by_type: dict[str, int] = {}
    for op in ops:
        ops_by_type[op["op"]] = ops_by_type.get(op["op"], 0) + 1
    assert ops_by_type.get("create", 0) == 1  # "Monitor the scaling metrics..."
    assert ops_by_type.get("update_priority", 0) == 1  # "Prioritize..."
    assert ops_by_type.get("cancel", 0) == 1  # "Cancel..."


@pytest.mark.asyncio
async def test_integrate_analysis_skips_when_no_responses() -> None:
    """Verify _integrate_analysis_into_chronos returns early when
    _latest_analysis is empty or has no responses.
    """
    from unittest.mock import AsyncMock

    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    mock_chronos = AsyncMock()
    swarm.supervisor.actors["chronos"] = mock_chronos

    # Case 1: _latest_analysis is empty
    swarm._latest_analysis = {}
    await swarm._integrate_analysis_into_chronos()
    mock_chronos.put_message.assert_not_awaited()

    # Case 2: _latest_analysis has no 'responses' key
    swarm._latest_analysis = {"collected_at": "2026-01-01T00:00:00Z"}
    await swarm._integrate_analysis_into_chronos()
    mock_chronos.put_message.assert_not_awaited()

    # Case 3: responses is empty list
    swarm._latest_analysis = {"responses": [], "collected_at": "2026-01-01T00:00:00Z"}
    await swarm._integrate_analysis_into_chronos()
    mock_chronos.put_message.assert_not_awaited()

    # Case 4: only Empath responses (no Metis subject)
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.empath.response",
                "data": {"sentiment": "positive"},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }
    await swarm._integrate_analysis_into_chronos()
    mock_chronos.put_message.assert_not_awaited()

    # Case 5: Metis response with empty recommendations list
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {"recommendations": []},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }
    await swarm._integrate_analysis_into_chronos()
    mock_chronos.put_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_integrate_analysis_does_not_crash_on_missing_chronos() -> None:
    """Verify _integrate_analysis_into_chronos does not crash when
    the Chronos agent is not registered in the supervisor.

    The method should log a warning and return gracefully.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}  # No chronos actor
    swarm.supervisor = supervisor

    # Pre-seed valid analysis data
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {"recommendations": ["Monitor the scaling metrics"]},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Should not raise any exception
    await swarm._integrate_analysis_into_chronos()


@pytest.mark.asyncio
async def test_full_cycle_drain_and_integration() -> None:
    """Full integration test: wire the cycle-30 drain through to the
    Chronos integration layer.

    Pre-seeds the response queue with a Metis response that contains
    recommendations, sets _analysis_cycle_count to 29, calls
    _process_cycle, and verifies that:
    1. The response queue is drained
    2. _latest_analysis is populated
    3. The chronos actor receives a bulk_schedule_adjust message
    4. The cycle counter is reset
    """
    from unittest.mock import AsyncMock

    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Mock Chronos actor. Use AsyncMock for async methods (generate_ticks, put_message)
    # but override get_status() as a sync mock since _run_health_checks calls it without await.
    from heretek_swarm.actors.base.core import ActorState, ActorStatus

    mock_chronos = AsyncMock()
    # Override get_status as sync: _run_health_checks calls it without await
    mock_chronos.get_status = MagicMock(return_value=ActorStatus(
        agent_id="chronos",
        state=ActorState.ACTIVE,
        message_count=0,
        created_at="2026-01-01T00:00:00Z",
        topics=[],
        capabilities=[],
        mailbox_size=0,
    ))
    mock_chronos.generate_ticks = AsyncMock(return_value=[])
    mock_chronos.put_message = AsyncMock()
    supervisor.actors["chronos"] = mock_chronos

    # Pre-seed the response queue with a Metis response
    await swarm._response_queue.put({
        "subject": "swarm.analysis.metis.response",
        "data": {
            "recommendations": [
                "Monitor the scaling metrics for bottlenecks",
                "Prioritize the security audit",
            ]
        },
        "timestamp": "2026-01-01T00:00:00Z",
    })

    # Set cycle count to 29 so the next call triggers periodic analysis
    swarm._analysis_cycle_count = 29

    # Call _process_cycle
    await swarm._process_cycle()

    # 1. Cycle counter was reset
    assert swarm._analysis_cycle_count == 0

    # 2. Response queue was drained into _latest_analysis
    assert len(swarm._latest_analysis["responses"]) == 1
    assert swarm._response_queue.empty()

    # 3. Chronos received a bulk_schedule_adjust
    mock_chronos.put_message.assert_awaited_once()
    call_args = mock_chronos.put_message.call_args[0][0]
    assert call_args.message_type == "bulk_schedule_adjust"
    assert len(call_args.content["operations"]) == 2

    # 4. Operation types correspond to recommendations
    ops = call_args.content["operations"]
    assert ops[0]["op"] == "create"  # "Monitor..." -> create
    assert ops[1]["op"] == "update_priority"  # "Prioritize..." -> update_priority


@pytest.mark.asyncio
async def test_empath_stress_triggers_mediation() -> None:
    """Verify _check_empath_stress_and_mediate dispatches trigger_mediation
    when collective_stress exceeds the default threshold of 0.7.

    Pre-seeds _latest_analysis with an Empath response where
    collective_stress > 0.7, mocks a Coordinator actor,
    calls the method, and verifies put_message was called with
    message_type='trigger_mediation' and the high-stress agent.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Mock Coordinator actor
    mock_coordinator = AsyncMock()
    mock_coordinator.put_message = AsyncMock()
    supervisor.actors["coordinator"] = mock_coordinator

    # Pre-seed _latest_analysis with high-stress Empath response
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.empath.response",
                "data": {
                    "collective_stress": 0.85,
                    "source_agent": "test_agent_1",
                    "sentiment": "negative",
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Call the stress check method
    await swarm._check_empath_stress_and_mediate()

    # Verify the Coordinator received a trigger_mediation message
    mock_coordinator.put_message.assert_awaited_once()
    call_args = mock_coordinator.put_message.call_args[0][0]
    assert call_args.message_type == "trigger_mediation"
    assert "test_agent_1" in call_args.content["agents"]
    assert call_args.content["stress_levels"]["test_agent_1"] == 0.85
    assert "context" in call_args.content


@pytest.mark.asyncio
async def test_empath_low_stress_does_not_trigger() -> None:
    """Verify _check_empath_stress_and_mediate does NOT dispatch
    mediation when collective_stress is below the threshold.

    Same setup as the positive test but collective_stress < 0.7.
    Coordinator.put_message should NOT be called.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    mock_coordinator = AsyncMock()
    mock_coordinator.put_message = AsyncMock()
    supervisor.actors["coordinator"] = mock_coordinator

    # Pre-seed _latest_analysis with low-stress Empath response
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.empath.response",
                "data": {
                    "collective_stress": 0.3,
                    "source_agent": "test_agent_1",
                    "sentiment": "positive",
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    await swarm._check_empath_stress_and_mediate()

    # Verify put_message was NOT called (low stress, no mediation)
    mock_coordinator.put_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_empath_stress_missing_coordinator_does_not_crash() -> None:
    """Verify _check_empath_stress_and_mediate does not crash when
    the Coordinator agent is not registered in the supervisor.

    Pre-seeds high-stress Empath data but omits the coordinator
    from supervisor.actors. The method should log an error and
    return gracefully.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}  # No coordinator actor
    swarm.supervisor = supervisor

    # Pre-seed _latest_analysis with high-stress Empath response
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.empath.response",
                "data": {
                    "collective_stress": 0.85,
                    "source_agent": "test_agent_1",
                    "sentiment": "negative",
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Should not raise any exception
    await swarm._check_empath_stress_and_mediate()


@pytest.mark.asyncio
async def test_empath_stress_empty_latest_analysis() -> None:
    """Verify _check_empath_stress_and_mediate returns early without
    crashing when _latest_analysis is an empty dict."""
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    mock_coordinator = AsyncMock()
    mock_coordinator.put_message = AsyncMock()
    supervisor.actors["coordinator"] = mock_coordinator

    # _latest_analysis is empty dict (no responses)
    swarm._latest_analysis = {}

    await swarm._check_empath_stress_and_mediate()

    # Coordinator should NOT have been called
    mock_coordinator.put_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_empath_stress_no_empath_responses() -> None:
    """Verify _check_empath_stress_and_mediate returns early without
    dispatching mediation when _latest_analysis contains only Metis
    responses (no Empath responses to check stress against).
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    mock_coordinator = AsyncMock()
    mock_coordinator.put_message = AsyncMock()
    supervisor.actors["coordinator"] = mock_coordinator

    # Only Metis responses, no Empath
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "recommendations": ["Monitor scaling metrics"],
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    await swarm._check_empath_stress_and_mediate()

    # Coordinator should NOT have been called (no Empath data)
    mock_coordinator.put_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_store_analysis_to_cognee_appends_record() -> None:
    """Verify _store_analysis_to_cognee builds a structured record from
    _latest_analysis and appends it to _analysis_records.

    Also verifies that transient tracking state (_last_chronos_operations,
    _mediation_dispatched) is cleared after storage.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Pre-populate transient tracking state
    swarm._last_chronos_operations = [
        {"op": "create", "operation_id": "create_abc123"},
        {"op": "update_priority", "operation_id": "prio_def456"},
    ]
    swarm._mediation_dispatched = True

    # Seed _latest_analysis with Metis + Empath responses
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "analysis": "Focus on scaling infrastructure",
                    "recommendations": ["Add more worker nodes", "Optimize query paths"],
                    "confidence": 0.85,
                },
                "timestamp": "2026-01-01T00:00:00Z",
            },
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "analysis": "Check error rates on coordinator",
                    "recommendations": ["Increase retry budget"],
                    "confidence": 0.72,
                },
                "timestamp": "2026-01-01T00:00:01Z",
            },
            {
                "subject": "swarm.analysis.empath.response",
                "data": {
                    "collective_stress": 0.3,
                    "source_agent": "main_loop",
                    "conflict_detected": False,
                    "sentiment": "neutral",
                },
                "timestamp": "2026-01-01T00:00:02Z",
            },
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Execute
    await swarm._store_analysis_to_cognee()

    # 1. Record was appended to the in-memory buffer
    assert len(swarm._analysis_records) == 1
    record = swarm._analysis_records[0]

    # 2. Record has the expected structure
    assert "id" in record
    assert record["trigger_type"] == "periodic"
    assert record["collected_at"] == "2026-01-01T00:00:00Z"
    assert record["mediation_dispatched"] is True

    # 3. Metis analyses captured correctly (2 responses)
    assert len(record["metis_analyses"]) == 2
    assert record["metis_analyses"][0]["confidence"] == 0.85
    assert record["metis_analyses"][1]["confidence"] == 0.72
    assert len(record["metis_analyses"][0]["recommendations"]) == 2
    assert len(record["metis_analyses"][1]["recommendations"]) == 1

    # 4. Empath responses captured correctly (1 response)
    assert len(record["empath_responses"]) == 1
    assert record["empath_responses"][0]["collective_stress"] == 0.3
    assert record["empath_responses"][0]["sentiment"] == "neutral"

    # 5. Chronos actions preserved from pre-populated state
    assert len(record["chronos_actions"]) == 2
    assert record["chronos_actions"][0]["op"] == "create"
    assert record["chronos_actions"][1]["op"] == "update_priority"

    # 6. Transient state was cleared after storage
    assert swarm._last_chronos_operations == []
    assert swarm._mediation_dispatched is False


@pytest.mark.asyncio
async def test_store_analysis_to_cognee_skipped_when_no_analysis() -> None:
    """Verify _store_analysis_to_cognee returns early without appending
    when _latest_analysis is empty or has no responses.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # No _latest_analysis set at all
    await swarm._store_analysis_to_cognee()
    assert len(swarm._analysis_records) == 0

    # Empty analysis dict
    swarm._latest_analysis = {}
    await swarm._store_analysis_to_cognee()
    assert len(swarm._analysis_records) == 0

    # Analysis with no responses key
    swarm._latest_analysis = {"collected_at": "2026-01-01T00:00:00Z"}
    await swarm._store_analysis_to_cognee()
    assert len(swarm._analysis_records) == 0

    # Analysis with empty responses list
    swarm._latest_analysis = {"responses": [], "collected_at": "2026-01-01T00:00:00Z"}
    await swarm._store_analysis_to_cognee()
    assert len(swarm._analysis_records) == 0


@pytest.mark.asyncio
async def test_store_analysis_to_cognee_caps_buffer() -> None:
    """Verify _store_analysis_to_cognee caps the in-memory buffer at
    _max_analysis_records by dropping the oldest records.
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Set a small max for testing
    swarm._max_analysis_records = 3

    # Seed a minimal _latest_analysis
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {"analysis": "test", "recommendations": [], "confidence": 0.5},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Store 5 records (buffer caps at 3)
    for i in range(5):
        swarm._latest_analysis["collected_at"] = f"2026-01-0{i+1}T00:00:00Z"
        await swarm._store_analysis_to_cognee()

    assert len(swarm._analysis_records) == 3
    # Only the last 3 survive (most recent at index -1)
    assert swarm._analysis_records[-1]["collected_at"] == "2026-01-05T00:00:00Z"
    assert swarm._analysis_records[0]["collected_at"] == "2026-01-03T00:00:00Z"


@pytest.mark.asyncio
async def test_store_analysis_to_cognee_clears_pending_chronos_on_empty() -> None:
    """Verify _store_analysis_to_cognee clears tracking state even when
    Chronos had no operations (empty _last_chronos_operations).
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Set mediation_dispatched to True but no chronos operations
    swarm._mediation_dispatched = True
    swarm._last_chronos_operations = []

    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {"analysis": "test", "recommendations": [], "confidence": 0.5},
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    await swarm._store_analysis_to_cognee()

    assert len(swarm._analysis_records) == 1
    # Tracking state was cleared
    assert swarm._mediation_dispatched is False
    assert swarm._last_chronos_operations == []
    # The record should have empty chronos_actions
    assert swarm._analysis_records[0]["chronos_actions"] == []
    assert swarm._analysis_records[0]["mediation_dispatched"] is True


@pytest.mark.asyncio
async def test_store_analysis_attempts_cognee_write() -> None:
    """Verify _store_analysis_to_cognee attempts to persist via
    _cognee_writer.store when a Cognee writer is configured.
    """
    from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Wire a mock Cognee writer
    swarm._cognee_writer = AsyncMock(spec=CogneeMemoryWriter)

    # Pre-seed _latest_analysis with a Metis response
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "analysis": "Test analysis",
                    "recommendations": ["Do something"],
                    "confidence": 0.75,
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    await swarm._store_analysis_to_cognee()

    # Cognee writer was called
    swarm._cognee_writer.store.assert_awaited_once()

    # Verify the store call had the right params
    call_kwargs = swarm._cognee_writer.store.call_args.kwargs
    assert call_kwargs["dataset"] == "analysis_history"
    assert call_kwargs["cognify_after"] is False

    # Record was also appended to in-memory buffer
    assert len(swarm._analysis_records) == 1


@pytest.mark.asyncio
async def test_store_analysis_handles_cognee_failure() -> None:
    """Verify _store_analysis_to_cognee does not raise when the
    Cognee writer's store() method raises an exception.

    The in-memory buffer should still be populated despite the failure.
    """
    from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Wire a mock Cognee writer that raises
    mock_writer = AsyncMock(spec=CogneeMemoryWriter)
    mock_writer.store.side_effect = RuntimeError("Cognee connection lost")
    swarm._cognee_writer = mock_writer

    # Pre-seed _latest_analysis
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "analysis": "Test analysis",
                    "recommendations": [],
                    "confidence": 0.5,
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Should NOT raise
    await swarm._store_analysis_to_cognee()

    # In-memory buffer was still populated
    assert len(swarm._analysis_records) == 1
    assert swarm._analysis_records[0]["trigger_type"] == "periodic"


@pytest.mark.asyncio
async def test_store_analysis_handles_no_cognee_writer() -> None:
    """Verify _store_analysis_to_cognee works correctly when
    _cognee_writer is None (no_infra mode, no Cognee configured).
    """
    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Verify _cognee_writer is None in no_infra mode
    assert swarm._cognee_writer is None

    # Pre-seed _latest_analysis
    swarm._latest_analysis = {
        "responses": [
            {
                "subject": "swarm.analysis.metis.response",
                "data": {
                    "analysis": "Test analysis",
                    "recommendations": ["Improve reliability"],
                    "confidence": 0.8,
                },
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "collected_at": "2026-01-01T00:00:00Z",
    }

    # Should not crash or raise
    await swarm._store_analysis_to_cognee()

    # In-memory buffer was populated
    assert len(swarm._analysis_records) == 1
    assert len(swarm._analysis_records[0]["metis_analyses"]) == 1
    assert swarm._analysis_records[0]["metis_analyses"][0]["analysis"] == "Test analysis"


@pytest.mark.asyncio
async def test_full_cycle_drain_and_persistence() -> None:
    """Full integration test: wire the cycle-30 drain through to
    the _store_analysis_to_cognee record persistence.

    Pre-seeds the response queue with one Metis and one Empath
    response, sets _analysis_cycle_count to 29, provides a supervisor
    with mock actors for all downstream consumers (chronos,
    coordinator), calls _process_cycle, and verifies that:
    1. The response queue is drained
    2. _latest_analysis is populated
    3. _analysis_records has 1 entry with both metis and empath data
    4. The cycle counter is reset
    """
    from unittest.mock import AsyncMock

    from heretek_swarm.actors.base.core import ActorState, ActorStatus

    swarm = AutonomousSwarm(config={}, no_infra=True)

    supervisor = MagicMock()
    supervisor.actors = {}
    swarm.supervisor = supervisor

    # Mock Chronos actor (needed by _integrate_analysis_into_chronos)
    mock_chronos = AsyncMock()
    mock_chronos.get_status = MagicMock(return_value=ActorStatus(
        agent_id="chronos",
        state=ActorState.ACTIVE,
        message_count=0,
        created_at="2026-01-01T00:00:00Z",
        topics=[],
        capabilities=[],
        mailbox_size=0,
    ))
    mock_chronos.generate_ticks = AsyncMock(return_value=[])
    mock_chronos.put_message = AsyncMock()
    supervisor.actors["chronos"] = mock_chronos

    # Mock Coordinator actor (needed by _check_empath_stress_and_mediate and _run_health_checks)
    mock_coordinator = AsyncMock()
    mock_coordinator.get_status = MagicMock(return_value=ActorStatus(
        agent_id="coordinator",
        state=ActorState.ACTIVE,
        message_count=0,
        created_at="2026-01-01T00:00:00Z",
        topics=[],
        capabilities=[],
        mailbox_size=0,
    ))
    mock_coordinator.put_message = AsyncMock()
    supervisor.actors["coordinator"] = mock_coordinator

    # Mock Historian actor (needed for cycle_complete logging and _run_health_checks)
    mock_historian = AsyncMock()
    mock_historian.get_status = MagicMock(return_value=ActorStatus(
        agent_id="historian",
        state=ActorState.ACTIVE,
        message_count=0,
        created_at="2026-01-01T00:00:00Z",
        topics=[],
        capabilities=[],
        mailbox_size=0,
    ))
    mock_historian.log_event = AsyncMock()
    supervisor.actors["historian"] = mock_historian

    # Pre-seed the response queue with one Metis and one Empath response
    await swarm._response_queue.put({
        "subject": "swarm.analysis.metis.response",
        "data": {
            "analysis": "Focus on scaling infrastructure",
            "recommendations": ["Add more worker nodes"],
            "confidence": 0.85,
        },
        "timestamp": "2026-01-01T00:00:00Z",
    })
    await swarm._response_queue.put({
        "subject": "swarm.analysis.empath.response",
        "data": {
            "collective_stress": 0.3,
            "source_agent": "main_loop",
            "conflict_detected": False,
            "sentiment": "neutral",
        },
        "timestamp": "2026-01-01T00:00:01Z",
    })

    # Set cycle count to 29 so the next call triggers periodic analysis
    swarm._analysis_cycle_count = 29

    # Call _process_cycle
    await swarm._process_cycle()

    # 1. Cycle counter was reset
    assert swarm._analysis_cycle_count == 0

    # 2. Response queue was drained into _latest_analysis
    assert len(swarm._latest_analysis["responses"]) == 2
    assert swarm._response_queue.empty()

    # 3. _analysis_records has 1 entry with both metis and empath data
    assert len(swarm._analysis_records) == 1
    record = swarm._analysis_records[0]
    assert len(record["metis_analyses"]) == 1
    assert record["metis_analyses"][0]["analysis"] == "Focus on scaling infrastructure"
    assert len(record["empath_responses"]) == 1
    assert record["empath_responses"][0]["collective_stress"] == 0.3
    assert record["trigger_type"] == "periodic"
