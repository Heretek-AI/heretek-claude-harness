"""Integration tests for PostgresPool. Requires a live Postgres at $TIER1_TEST_PG_DSN.

If TIER1_TEST_PG_DSN is not set, tests are skipped.
"""

from __future__ import annotations

import os
import uuid

import pytest

from tier1.deliberation.state import (
    DeliberationEvent,
    initial_state,
    new_deliberation_id,
)
from tier1.persistence.postgres import PostgresPool


DSN = os.environ.get("TIER1_TEST_PG_DSN", "")


@pytest.fixture
async def pg():
    if not DSN:
        pytest.skip("set TIER1_TEST_PG_DSN to enable Postgres integration tests")
    pool = PostgresPool(DSN)
    await pool.connect()
    yield pool
    async with pool.pool.acquire() as conn:  # type: ignore[union-attr]
        await conn.execute("DELETE FROM deliberation_events")
        await conn.execute("DELETE FROM deliberations")
    await pool.close()


async def test_save_and_load(pg: PostgresPool):
    state = initial_state(deliberation_id=new_deliberation_id(), problem="hi")
    await pg.save_deliberation(state)
    loaded = await pg.load_deliberation(state["deliberation_id"])
    assert loaded is not None
    assert loaded["problem"] == "hi"


async def test_save_updates_existing(pg: PostgresPool):
    state = initial_state(deliberation_id=new_deliberation_id(), problem="hi")
    await pg.save_deliberation(state)
    state["round"] = 1
    await pg.save_deliberation(state)
    loaded = await pg.load_deliberation(state["deliberation_id"])
    assert loaded["round"] == 1


async def test_list_deliberations(pg: PostgresPool):
    for _ in range(3):
        await pg.save_deliberation(
            initial_state(deliberation_id=new_deliberation_id(), problem="x")
        )
    summaries = await pg.list_deliberations(10)
    assert len(summaries) == 3


async def test_append_and_get_events(pg: PostgresPool):
    did = new_deliberation_id()
    state = initial_state(deliberation_id=did, problem="x")
    await pg.save_deliberation(state)
    e1 = DeliberationEvent(seq=1, ts=1.0, kind="alpha_thinking", payload={})
    e2 = DeliberationEvent(seq=2, ts=2.0, kind="alpha_verdict", payload={"position": "approve"})
    await pg.append_event(did, e1)
    await pg.append_event(did, e2)
    events = await pg.get_events(did)
    assert [e.seq for e in events] == [1, 2]
    assert events[0].kind == "alpha_thinking"
