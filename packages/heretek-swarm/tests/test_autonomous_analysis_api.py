"""
Tests for autonomous analysis persistence and API endpoints.

Covers:
- push_analysis_record function (buffer append + trim)
- GET /api/autonomous/analyses pagination
- GET /api/autonomous/analyses/{id} lookup
- GET /api/autonomous/status total_analyses count
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from heretek_swarm.api.autonomous import (
    MAX_ANALYSIS_RECORDS,
    _analysis_records,
    push_analysis_record,
    router,
)

# Module-level import check (primary imports above already validate this)
IMPORT_OK = callable(push_analysis_record) and isinstance(_analysis_records, list)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset the in-memory analysis buffer before each test."""
    _analysis_records.clear()


def make_record(record_id: str, trigger_type: str = "goal_completed") -> dict:
    """Helper to build a sample analysis record dict."""
    return {
        "id": record_id,
        "collected_at": "2026-06-03T12:00:00+00:00",
        "trigger_type": trigger_type,
        "metis_analyses": [{"analysis": "test", "confidence": 0.9}],
        "empath_responses": [{"sentiment": "neutral", "stress": 0.2}],
        "chronos_actions": [{"action": "log", "status": "ok"}],
        "mediation_dispatched": False,
    }


class TestPushAnalysisRecord:
    """Tests for the push_analysis_record function."""

    @pytest.mark.asyncio
    async def test_append_record(self) -> None:
        """A single record is appended to the buffer."""
        record = make_record("r-001")
        await push_analysis_record(record)
        assert len(_analysis_records) == 1
        assert _analysis_records[0]["id"] == "r-001"

    @pytest.mark.asyncio
    async def test_multiple_records_ordered(self) -> None:
        """Records are stored in insertion order."""
        for i in range(5):
            await push_analysis_record(make_record(f"r-{i:03d}"))
        assert len(_analysis_records) == 5
        assert _analysis_records[0]["id"] == "r-000"
        assert _analysis_records[-1]["id"] == "r-004"

    @pytest.mark.asyncio
    async def test_trim_to_max(self) -> None:
        """Buffer is trimmed to MAX_ANALYSIS_RECORDS when full."""
        # Fill just under the cap
        for i in range(MAX_ANALYSIS_RECORDS + 50):
            await push_analysis_record(make_record(f"r-{i:05d}"))
        assert len(_analysis_records) == MAX_ANALYSIS_RECORDS
        # Only the last MAX_ANALYSIS_RECORDS survive (oldest dropped)
        assert _analysis_records[0]["id"] == f"r-{50:05d}"
        assert _analysis_records[-1]["id"] == f"r-{MAX_ANALYSIS_RECORDS + 49:05d}"

    @pytest.mark.asyncio
    async def test_concurrent_safe(self) -> None:
        """Multiple concurrent pushes do not corrupt the buffer."""

        async def push(i: int) -> None:
            await push_analysis_record(make_record(f"r-{i:04d}"))

        await asyncio.gather(*[push(i) for i in range(100)])
        assert len(_analysis_records) == 100
        ids = {r["id"] for r in _analysis_records}
        assert len(ids) == 100


class TestAnalysisEndpointApp:
    """Tests for the analysis API endpoints using TestClient.

    The router uses Depends(verify_auth) at the router level,
    so we override the dependency to permit unauthenticated access
    during tests.
    """

    @pytest.fixture
    def app(self) -> FastAPI:
        """Build a minimal FastAPI app with the autonomous router,
        overriding the auth dependency to a no-op."""
        _app = FastAPI()
        _app.include_router(router)
        # Override the auth dependency so tests work without credentials
        from heretek_swarm.gateway.auth import verify_auth

        _app.dependency_overrides[verify_auth] = lambda: None
        return _app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    def test_import(self) -> None:
        """Verify the module can import push_analysis_record and _analysis_records."""
        assert IMPORT_OK or callable(push_analysis_record)
        assert isinstance(_analysis_records, list)

    def test_empty_list(self, client: TestClient) -> None:
        """GET /api/autonomous/analyses returns empty list with 0 total."""
        resp = client.get("/api/autonomous/analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["limit"] == 20
        assert data["pages"] == 1

    def test_single_page(self, client: TestClient) -> None:
        """GET /api/autonomous/analyses returns records sorted newest-first."""

        async def seed() -> None:
            for i in range(3):
                await push_analysis_record(
                    make_record(f"r-{i:03d}", "goal_completed")
                )

        asyncio.run(seed())

        resp = client.get("/api/autonomous/analyses")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        # Most recent first (r-002 first)
        assert data["items"][0]["id"] == "r-002"
        assert data["items"][2]["id"] == "r-000"

    def test_pagination(self, client: TestClient) -> None:
        """Pagination parameters work correctly."""

        async def seed() -> None:
            for i in range(25):
                await push_analysis_record(make_record(f"r-{i:03d}"))

        asyncio.run(seed())

        # Page 1 (limit 10) -> items 0-9 = r-024 down to r-015
        resp = client.get("/api/autonomous/analyses?page=1&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["page"] == 1
        assert data["pages"] == 3
        assert data["items"][0]["id"] == "r-024"

        # Page 3 (limit 10) -> items 20-24 = r-004 down to r-000
        resp = client.get("/api/autonomous/analyses?page=3&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 5
        assert data["items"][-1]["id"] == "r-000"

    def test_limit_validation(self, client: TestClient) -> None:
        """Limit above 100 is rejected."""
        resp = client.get("/api/autonomous/analyses?limit=200")
        assert resp.status_code == 422

    def test_page_zero_rejected(self, client: TestClient) -> None:
        """Page 0 is rejected (ge=1)."""
        resp = client.get("/api/autonomous/analyses?page=0")
        assert resp.status_code == 422

    def test_get_by_id_found(self, client: TestClient) -> None:
        """GET /api/autonomous/analyses/{id} returns the record."""

        async def seed() -> None:
            await push_analysis_record(
                make_record("r-found", "goal_completed")
            )
            await push_analysis_record(
                make_record("r-other", "goal_completed")
            )

        asyncio.run(seed())

        resp = client.get("/api/autonomous/analyses/r-found")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "r-found"
        assert data["trigger_type"] == "goal_completed"
        assert len(data["metis_analyses"]) == 1

    def test_get_by_id_not_found(self, client: TestClient) -> None:
        """GET /api/autonomous/analyses/{id} returns 404 for unknown ID."""
        resp = client.get("/api/autonomous/analyses/r-nonexistent")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Analysis not found"

    def test_status_includes_total_analyses(self, client: TestClient) -> None:
        """GET /api/autonomous/status includes total_analyses field."""

        async def seed() -> None:
            for i in range(7):
                await push_analysis_record(make_record(f"r-{i:03d}"))

        asyncio.run(seed())

        resp = client.get("/api/autonomous/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_analyses" in data
        assert data["total_analyses"] == 7

    def test_record_limit(self, client: TestClient) -> None:
        """Pushing over MAX_ANALYSIS_RECORDS keeps the buffer
        at the cap. The status endpoint reports the correct (capped)
        count.
        """

        async def seed() -> None:
            for i in range(MAX_ANALYSIS_RECORDS + 50):
                await push_analysis_record(
                    make_record(f"r-{i:06d}")
                )

        asyncio.run(seed())

        # Verify via status
        resp = client.get("/api/autonomous/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_analyses"] == MAX_ANALYSIS_RECORDS

        # Verify via analyses list (top of list)
        resp = client.get("/api/autonomous/analyses?limit=50")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == MAX_ANALYSIS_RECORDS
