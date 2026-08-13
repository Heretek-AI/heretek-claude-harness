"""
Tests for S06 autonomous API endpoints: tasks, goals, events, propose-goal.

Covers:
- push_task_snapshot function (buffer append + trim, concurrent safety)
- push_goal_snapshot function (buffer append + trim, concurrent safety)
- GET /api/autonomous/tasks pagination and empty state
- GET /api/autonomous/goals pagination and empty state
- GET /api/autonomous/events combined timeline
- POST /api/autonomous/propose-goal creation
"""

from __future__ import annotations

import asyncio
import math
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from heretek_swarm.api.autonomous import (
    MAX_ANALYSIS_RECORDS,
    MAX_GOALS,
    MAX_TASKS,
    _analysis_records,
    _goals_buffer,
    _tasks_buffer,
    push_goal_snapshot,
    push_task_snapshot,
    router,
)

# Module-level import checks
IMPORT_TASKS = callable(push_task_snapshot) and isinstance(_tasks_buffer, list)
IMPORT_GOALS = callable(push_goal_snapshot) and isinstance(_goals_buffer, list)


# ---------------------------------------------------------------------------
# Shared fixtures & helpers
# ---------------------------------------------------------------------------


def make_task(task_id: str, status: str = "pending") -> dict:
    """Helper to build a sample Chronos task snapshot dict."""
    return {
        "task_id": task_id,
        "title": f"Task {task_id}",
        "status": status,
        "priority": "medium",
        "created_at": "2026-06-03T12:00:00+00:00",
        "scheduled_at": "2026-06-03T13:00:00+00:00",
        "assigned_to": "chronos",
        "description": f"Description for {task_id}",
        "tags": ["test", "automation"],
    }


def make_goal(goal_id: str, status: str = "proposed") -> dict:
    """Helper to build a sample goal pipeline snapshot dict."""
    return {
        "goal_id": goal_id,
        "title": f"Goal {goal_id}",
        "description": f"Description for {goal_id}",
        "status": status,
        "priority": "high" if "high" in goal_id else "medium",
        "created_at": "2026-06-03T12:00:00+00:00",
        "updated_at": "2026-06-03T12:30:00+00:00",
        "votes_for": 5,
        "votes_against": 1,
        "outcome": None if status in ("proposed", "voting") else status,
        "proposed_by": "metis",
    }


def make_analysis_record(
    record_id: str,
    trigger_type: str = "goal_completed",
    mediation_dispatched: bool = False,
    metis_count: int = 1,
    empath_count: int = 1,
    chronos_count: int = 1,
) -> dict:
    """Helper to build a sample analysis record with configurable sub-events.

    This matches the structure consumed by GET /api/autonomous/events.
    """
    return {
        "id": record_id,
        "collected_at": "2026-06-03T12:00:00+00:00",
        "trigger_type": trigger_type,
        "metis_analyses": (
            [{"analysis": "test", "confidence": 0.9}] * metis_count
        ),
        "empath_responses": (
            [{"sentiment": "neutral", "stress": 0.2}] * empath_count
        ),
        "chronos_actions": (
            [{"action": "log", "status": "ok"}] * chronos_count
        ),
        "mediation_dispatched": mediation_dispatched,
    }


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset all in-memory buffers before each test."""
    _analysis_records.clear()
    _tasks_buffer.clear()
    _goals_buffer.clear()


# ---------------------------------------------------------------------------
# Helper for TestClient app fixture (shared across endpoint test classes)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Build a minimal FastAPI app with the autonomous router,
    overriding the auth dependency to a no-op."""
    _app = FastAPI()
    _app.include_router(router)
    from heretek_swarm.gateway.auth import verify_auth

    _app.dependency_overrides[verify_auth] = lambda: None
    return _app


@pytest.fixture(scope="module")
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ===================================================================
# push_task_snapshot tests
# ===================================================================


class TestPushTaskSnapshot:
    """Tests for the push_task_snapshot function."""

    @pytest.mark.asyncio
    async def test_import_ok(self) -> None:
        assert IMPORT_TASKS

    @pytest.mark.asyncio
    async def test_append_snapshot(self) -> None:
        """A single task snapshot is appended."""
        snapshot = make_task("t-001")
        await push_task_snapshot(snapshot)
        assert len(_tasks_buffer) == 1
        assert _tasks_buffer[0]["task_id"] == "t-001"

    @pytest.mark.asyncio
    async def test_multiple_ordered(self) -> None:
        """Snapshots are stored in insertion order."""
        for i in range(5):
            await push_task_snapshot(make_task(f"t-{i:03d}"))
        assert len(_tasks_buffer) == 5
        assert _tasks_buffer[0]["task_id"] == "t-000"
        assert _tasks_buffer[-1]["task_id"] == "t-004"

    @pytest.mark.asyncio
    async def test_trim_to_max(self) -> None:
        """Buffer is trimmed to MAX_TASKS when full."""
        for i in range(MAX_TASKS + 50):
            await push_task_snapshot(make_task(f"t-{i:05d}"))
        assert len(_tasks_buffer) == MAX_TASKS
        assert _tasks_buffer[0]["task_id"] == f"t-{50:05d}"
        assert _tasks_buffer[-1]["task_id"] == f"t-{MAX_TASKS + 49:05d}"

    @pytest.mark.asyncio
    async def test_concurrent_safe(self) -> None:
        """Multiple concurrent pushes do not corrupt the buffer."""

        async def push(i: int) -> None:
            await push_task_snapshot(make_task(f"t-{i:04d}"))

        await asyncio.gather(*[push(i) for i in range(100)])
        assert len(_tasks_buffer) == 100
        ids = {r["task_id"] for r in _tasks_buffer}
        assert len(ids) == 100


# ===================================================================
# push_goal_snapshot tests
# ===================================================================


class TestPushGoalSnapshot:
    """Tests for the push_goal_snapshot function."""

    @pytest.mark.asyncio
    async def test_import_ok(self) -> None:
        assert IMPORT_GOALS

    @pytest.mark.asyncio
    async def test_append_snapshot(self) -> None:
        """A single goal snapshot is appended."""
        snapshot = make_goal("g-001")
        await push_goal_snapshot(snapshot)
        assert len(_goals_buffer) == 1
        assert _goals_buffer[0]["goal_id"] == "g-001"

    @pytest.mark.asyncio
    async def test_multiple_ordered(self) -> None:
        """Snapshots are stored in insertion order."""
        for i in range(5):
            await push_goal_snapshot(make_goal(f"g-{i:03d}"))
        assert len(_goals_buffer) == 5
        assert _goals_buffer[0]["goal_id"] == "g-000"
        assert _goals_buffer[-1]["goal_id"] == "g-004"

    @pytest.mark.asyncio
    async def test_trim_to_max(self) -> None:
        """Buffer is trimmed to MAX_GOALS when full."""
        for i in range(MAX_GOALS + 30):
            await push_goal_snapshot(make_goal(f"g-{i:05d}"))
        assert len(_goals_buffer) == MAX_GOALS
        assert _goals_buffer[0]["goal_id"] == f"g-{30:05d}"
        assert _goals_buffer[-1]["goal_id"] == f"g-{MAX_GOALS + 29:05d}"

    @pytest.mark.asyncio
    async def test_concurrent_safe(self) -> None:
        """Multiple concurrent pushes do not corrupt the buffer."""

        async def push(i: int) -> None:
            await push_goal_snapshot(make_goal(f"g-{i:04d}"))

        await asyncio.gather(*[push(i) for i in range(100)])
        assert len(_goals_buffer) == 100
        ids = {r["goal_id"] for r in _goals_buffer}
        assert len(ids) == 100


# ===================================================================
# GET /api/autonomous/tasks endpoint tests
# ===================================================================


class TestTasksEndpoint:
    """Tests for the GET /api/autonomous/tasks endpoint."""

    def test_empty_list(self, client: TestClient) -> None:
        """Returns empty list with 0 total when no tasks exist."""
        resp = client.get("/api/autonomous/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["limit"] == 20
        assert data["pages"] == 1

    def test_single_page(self, client: TestClient) -> None:
        """Returns snapshots sorted newest-first."""

        async def seed() -> None:
            for i in range(3):
                await push_task_snapshot(make_task(f"t-{i:03d}"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # Most recent first (t-002 first)
        assert data["items"][0]["task_id"] == "t-002"
        assert data["items"][2]["task_id"] == "t-000"

    def test_pagination(self, client: TestClient) -> None:
        """Pagination parameters work correctly."""

        async def seed() -> None:
            for i in range(25):
                await push_task_snapshot(make_task(f"t-{i:03d}"))

        asyncio.run(seed())

        # Page 1 (limit 10) -> items 0-9 = t-024 down to t-015
        resp = client.get("/api/autonomous/tasks?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["pages"] == 3
        assert data["items"][0]["task_id"] == "t-024"

        # Page 3 (limit 10) -> items 20-24 = t-004 down to t-000
        resp = client.get("/api/autonomous/tasks?page=3&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["items"][-1]["task_id"] == "t-000"

    def test_limit_validation(self, client: TestClient) -> None:
        """Limit above 100 is rejected."""
        resp = client.get("/api/autonomous/tasks?limit=200")
        assert resp.status_code == 422

    def test_page_zero_rejected(self, client: TestClient) -> None:
        """Page 0 is rejected (ge=1)."""
        resp = client.get("/api/autonomous/tasks?page=0")
        assert resp.status_code == 422

    def test_response_shape(self, client: TestClient) -> None:
        """Response items have the expected fields."""

        async def seed() -> None:
            await push_task_snapshot(make_task("t-shape"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/tasks")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "task_id" in item
        assert "title" in item
        assert "status" in item
        assert "priority" in item
        assert "created_at" in item
        assert "assigned_to" in item
        assert "tags" in item


# ===================================================================
# GET /api/autonomous/goals endpoint tests
# ===================================================================


class TestGoalsEndpoint:
    """Tests for the GET /api/autonomous/goals endpoint."""

    def test_empty_list(self, client: TestClient) -> None:
        """Returns empty list with 0 total when no goals exist."""
        resp = client.get("/api/autonomous/goals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["limit"] == 20
        assert data["pages"] == 1

    def test_single_page(self, client: TestClient) -> None:
        """Returns snapshots sorted newest-first."""

        async def seed() -> None:
            for i in range(3):
                await push_goal_snapshot(make_goal(f"g-{i:03d}"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/goals")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # Most recent first (g-002 first)
        assert data["items"][0]["goal_id"] == "g-002"
        assert data["items"][2]["goal_id"] == "g-000"

    def test_pagination(self, client: TestClient) -> None:
        """Pagination parameters work correctly."""

        async def seed() -> None:
            for i in range(25):
                await push_goal_snapshot(make_goal(f"g-{i:03d}"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/goals?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["pages"] == 3
        assert data["items"][0]["goal_id"] == "g-024"

        resp = client.get("/api/autonomous/goals?page=3&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["items"][-1]["goal_id"] == "g-000"

    def test_limit_validation(self, client: TestClient) -> None:
        """Limit above 100 is rejected."""
        resp = client.get("/api/autonomous/goals?limit=200")
        assert resp.status_code == 422

    def test_response_shape(self, client: TestClient) -> None:
        """Response items have the expected fields."""

        async def seed() -> None:
            await push_goal_snapshot(make_goal("g-shape", "accepted"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/goals")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "goal_id" in item
        assert "title" in item
        assert "status" in item
        assert item["status"] == "accepted"
        assert "priority" in item
        assert "votes_for" in item
        assert "outcome" in item


# ===================================================================
# GET /api/autonomous/events endpoint tests
# ===================================================================


class TestEventsEndpoint:
    """Tests for the GET /api/autonomous/events endpoint."""

    def test_empty_list(self, client: TestClient) -> None:
        """Returns empty list with 0 total when no analysis records exist."""
        resp = client.get("/api/autonomous/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["pages"] == 1

    def test_single_record_produces_multiple_events(self, client: TestClient) -> None:
        """One analysis record with sub-events generates multiple timeline events."""

        async def seed() -> None:
            from heretek_swarm.api.autonomous import push_analysis_record

            await push_analysis_record(
                make_analysis_record(
                    "r-events",
                    mediation_dispatched=True,
                    metis_count=2,
                    empath_count=1,
                    chronos_count=2,
                )
            )

        asyncio.run(seed())

        resp = client.get("/api/autonomous/events")
        assert resp.status_code == 200
        data = resp.json()
        # Expected events: 1 analysis + 2 metis + 1 empath + 2 chronos + 1 mediation = 7
        assert data["total"] == 7
        assert len(data["items"]) == 7

        # Verify event types present
        event_types = {e["event_type"] for e in data["items"]}
        assert "analysis_completed" in event_types
        assert "metis_analysis" in event_types
        assert "empath_response" in event_types
        assert "chronos_action" in event_types
        assert "mediation_dispatched" in event_types

        # Verify sources present
        sources = {e["source"] for e in data["items"]}
        assert "autonomous_loop" in sources
        assert "metis" in sources
        assert "empath" in sources
        assert "chronos" in sources
        assert "mediator" in sources

    def test_no_mediation_no_mediation_event(self, client: TestClient) -> None:
        """Record without mediation_dispatched does not produce mediation event."""

        async def seed() -> None:
            from heretek_swarm.api.autonomous import push_analysis_record

            await push_analysis_record(
                make_analysis_record("r-nomed", mediation_dispatched=False)
            )

        asyncio.run(seed())

        resp = client.get("/api/autonomous/events")
        assert resp.status_code == 200
        data = resp.json()
        # 1 analysis + 1 metis + 1 empath + 1 chronos = 4
        assert data["total"] == 4
        event_types = {e["event_type"] for e in data["items"]}
        assert "mediation_dispatched" not in event_types

    def test_multiple_records_ordered_newest_first(self, client: TestClient) -> None:
        """Events from multiple records come in reverse chronological order."""

        async def seed() -> None:
            from heretek_swarm.api.autonomous import push_analysis_record

            # Record 1 (older in buffer order)
            rec1 = make_analysis_record("r-001", trigger_type="goal_completed")
            rec1["collected_at"] = "2026-06-03T10:00:00+00:00"
            await push_analysis_record(rec1)

            # Record 2 (newer)
            rec2 = make_analysis_record("r-002", trigger_type="anomaly_detected")
            rec2["collected_at"] = "2026-06-03T12:00:00+00:00"
            await push_analysis_record(rec2)

        asyncio.run(seed())

        resp = client.get("/api/autonomous/events")
        assert resp.status_code == 200
        data = resp.json()
        # r-002 events come first (most recent first)
        first_event = data["items"][0]
        assert first_event["id"].startswith("r-002")
        assert data["items"][4]["id"].startswith("r-001")

    def test_pagination(self, client: TestClient) -> None:
        """Events pagination works correctly."""

        async def seed() -> None:
            from heretek_swarm.api.autonomous import push_analysis_record

            for i in range(5):
                rec = make_analysis_record(
                    f"r-{i:03d}",
                    metis_count=3,
                    empath_count=1,
                    chronos_count=1,
                    mediation_dispatched=(i % 2 == 0),
                )
                rec["collected_at"] = f"2026-06-03T{10+i:02d}:00:00+00:00"
                await push_analysis_record(rec)

        asyncio.run(seed())
        # Each of 5 records: 1 analysis + 3 metis + 1 empath + 1 chronos + (1 mediation if even)
        # r-000: 7 events, r-001: 6 events, r-002: 7 events, r-003: 6 events, r-004: 7 events
        # Total = 7+6+7+6+7 = 33 events

        # Page 1, limit 10
        resp = client.get("/api/autonomous/events?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 33
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["pages"] == 4

        # Page 4, limit 10 -> last 3 items
        resp = client.get("/api/autonomous/events?page=4&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3

    def test_event_response_shape(self, client: TestClient) -> None:
        """Each event has the expected fields."""

        async def seed() -> None:
            from heretek_swarm.api.autonomous import push_analysis_record

            await push_analysis_record(make_analysis_record("r-shape"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/events")
        assert resp.status_code == 200
        item = resp.json()["items"][0]
        assert "id" in item
        assert "event_type" in item
        assert "collected_at" in item
        assert "source" in item
        assert "summary" in item
        assert "payload" in item


# ===================================================================
# POST /api/autonomous/propose-goal endpoint tests
# ===================================================================


class TestProposeGoalEndpoint:
    """Tests for the POST /api/autonomous/propose-goal endpoint."""

    def test_propose_goal_default_priority(self, client: TestClient) -> None:
        """Proposing a goal with no priority defaults to 'medium'."""
        resp = client.post(
            "/api/autonomous/propose-goal",
            json={
                "title": "Test Goal",
                "description": "A test goal proposal",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "proposed"
        assert "goal_id" in data
        assert "Test Goal" in data["message"]

        # Verify it appears in the goals buffer
        resp2 = client.get("/api/autonomous/goals")
        goals = resp2.json()
        assert goals["total"] == 1
        assert goals["items"][0]["title"] == "Test Goal"
        assert goals["items"][0]["priority"] == "medium"

    def test_propose_goal_custom_priority(self, client: TestClient) -> None:
        """Proposing a goal with explicit priority works."""
        resp = client.post(
            "/api/autonomous/propose-goal",
            json={
                "title": "High Priority Goal",
                "description": "Critical improvement",
                "priority": "high",
                "tags": ["critical", "performance"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "proposed"

        resp2 = client.get("/api/autonomous/goals")
        goal = resp2.json()["items"][0]
        assert goal["priority"] == "high"
        assert goal["title"] == "High Priority Goal"

    def test_propose_goal_validation_error(self, client: TestClient) -> None:
        """Missing required fields returns 422."""
        resp = client.post(
            "/api/autonomous/propose-goal",
            json={"title": "Missing description"},
        )
        assert resp.status_code == 422

    def test_propose_goal_empty_title(self, client: TestClient) -> None:
        """Empty title should still be accepted as a string."""
        resp = client.post(
            "/api/autonomous/propose-goal",
            json={"title": "", "description": "some desc"},
        )
        assert resp.status_code == 201

    def test_propose_goal_creates_goal_in_buffer(self, client: TestClient) -> None:
        """Multiple proposals all appear in the goals buffer."""
        for i in range(3):
            resp = client.post(
                "/api/autonomous/propose-goal",
                json={
                    "title": f"Goal {i}",
                    "description": f"Description {i}",
                },
            )
            assert resp.status_code == 201

        resp = client.get("/api/autonomous/goals")
        data = resp.json()
        assert data["total"] == 3
        titles = {item["title"] for item in data["items"]}
        assert "Goal 0" in titles
        assert "Goal 1" in titles
        assert "Goal 2" in titles


# ===================================================================
# Cross-endpoint integration tests
# ===================================================================


class TestCrossEndpointIntegration:
    """Tests that multiple endpoints work correctly together."""

    def test_tasks_and_goals_independent_buffers(self, client: TestClient) -> None:
        """Tasks and goals buffers are independent."""

        async def seed() -> None:
            for i in range(3):
                await push_task_snapshot(make_task(f"t-{i:03d}"))
            for i in range(5):
                await push_goal_snapshot(make_goal(f"g-{i:03d}"))

        asyncio.run(seed())

        resp_tasks = client.get("/api/autonomous/tasks")
        resp_goals = client.get("/api/autonomous/goals")

        assert resp_tasks.json()["total"] == 3
        assert resp_goals.json()["total"] == 5

    def test_status_untouched_by_new_buffers(self, client: TestClient) -> None:
        """The existing /status endpoint is not affected by new buffers."""

        async def seed() -> None:
            from heretek_swarm.api.autonomous import push_analysis_record

            for i in range(4):
                await push_analysis_record(
                    make_analysis_record(f"r-{i:03d}")
                )
            for i in range(3):
                await push_task_snapshot(make_task(f"t-{i:03d}"))
            for i in range(2):
                await push_goal_snapshot(make_goal(f"g-{i:03d}"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/status")
        data = resp.json()
        # Status only tracks analysis records, not tasks or goals
        assert data["total_analyses"] == 4
        assert "connected" in data
        assert "agent_count" in data
