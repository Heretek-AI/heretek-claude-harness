"""Unit tests for tier1.persistence.postgres.

All asyncpg interactions are mocked; no real DB is contacted.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tier1.deliberation.state import (
    AgentVerdict,
    DeliberationEvent,
    DeliberationState,
    FinalVerdict,
)
from tier1.persistence.postgres import (
    PostgresPool,
    _set_json_codecs,
    _state_to_jsonable,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    return conn


def _make_pool(conn: AsyncMock | None = None) -> MagicMock:
    pool = MagicMock()
    pool.close = AsyncMock(return_value=None)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    pool.acquire = MagicMock(return_value=cm)
    return pool


def _make_state(
    *,
    deliberation_id: str = "d1",
    problem: str = "p",
    user_id: str = "u",
    status: str = "running",
    round_: int = 0,
    max_rounds: int = 3,
    final_verdict: FinalVerdict | None = None,
    events: list | None = None,
    feedback: list[str] | None = None,
    alpha: AgentVerdict | None = None,
    beta: AgentVerdict | None = None,
    charlie: AgentVerdict | None = None,
) -> DeliberationState:
    return DeliberationState(
        deliberation_id=deliberation_id,
        problem=problem,
        user_id=user_id,
        round=round_,
        max_rounds=max_rounds,
        alpha_verdict=alpha,
        beta_verdict=beta,
        charlie_verdict=charlie,
        feedback=feedback if feedback is not None else [],
        events=events if events is not None else [],
        final_verdict=final_verdict,
        status=status,
        failure_reason=None,
    )


# ---------------------------------------------------------------------------
# _set_json_codecs
# ---------------------------------------------------------------------------


async def test_set_json_codecs_decodes_jsonb() -> None:
    conn = _make_conn()
    await _set_json_codecs(conn)
    conn.set_type_codec.assert_awaited_once()
    args, kwargs = conn.set_type_codec.call_args
    assert args[0] == "jsonb"
    assert kwargs.get("schema") == "pg_catalog"
    assert callable(kwargs.get("encoder"))
    assert callable(kwargs.get("decoder"))


# ---------------------------------------------------------------------------
# connect / close
# ---------------------------------------------------------------------------


async def test_connect_creates_pool_and_tables() -> None:
    conn = _make_conn()
    pool = _make_pool(conn)
    with patch("tier1.persistence.postgres.asyncpg.create_pool", new=AsyncMock(return_value=pool)):
        p = PostgresPool(dsn="postgres://x")
        await p.connect()

    # Both CREATE TABLE statements issued
    execute_calls = conn.execute.await_args_list
    sql_concat = " ".join(c.args[0] for c in execute_calls)
    assert "CREATE TABLE IF NOT EXISTS deliberations" in sql_concat
    assert "CREATE TABLE IF NOT EXISTS deliberation_events" in sql_concat


async def test_close_closes_pool_when_set() -> None:
    pool = _make_pool(_make_conn())
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool
    await p.close()
    pool.close.assert_awaited_once()
    assert p.pool is None


async def test_close_noop_when_pool_none() -> None:
    p = PostgresPool(dsn="postgres://x")
    p.pool = None
    # Should not raise
    await p.close()
    await p.close()
    assert p.pool is None


# ---------------------------------------------------------------------------
# save_deliberation
# ---------------------------------------------------------------------------


async def test_save_deliberation_inserts_with_all_fields() -> None:
    conn = _make_conn()
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    state = _make_state()
    await p.save_deliberation(state)

    assert conn.execute.await_count == 1
    call = conn.execute.await_args
    sql = call.args[0]
    args = call.args[1:]
    assert "INSERT INTO deliberations" in sql
    assert "ON CONFLICT (id) DO UPDATE" in sql
    assert len(args) == 8


async def test_save_deliberation_upsert_on_conflict() -> None:
    conn = _make_conn()
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool
    await p.save_deliberation(_make_state())
    sql = conn.execute.await_args.args[0]
    assert "ON CONFLICT (id) DO UPDATE" in sql


async def test_save_deliberation_serializes_final_verdict() -> None:
    conn = _make_conn()
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    final = FinalVerdict(
        decision="approved",
        summary="ok",
        votes={
            "alpha": AgentVerdict(
                agent="alpha",
                position="approve",
                confidence=0.9,
                reasoning="r",
            )
        },
        rounds=1,
    )
    state = _make_state(final_verdict=final)
    await p.save_deliberation(state)

    args = conn.execute.await_args.args
    final_json = args[8]  # 8th positional arg, 1-indexed $8
    assert final_json is not None
    assert final_json["decision"] == "approved"
    assert final_json["summary"] == "ok"
    assert "alpha" in final_json["votes"]


# ---------------------------------------------------------------------------
# load_deliberation
# ---------------------------------------------------------------------------


async def test_load_deliberation_returns_none_when_no_row() -> None:
    conn = _make_conn()
    conn.fetchrow = AsyncMock(return_value=None)
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    result = await p.load_deliberation("missing")
    assert result is None
    conn.fetchrow.assert_awaited_once()


async def test_load_deliberation_returns_state_from_jsonb() -> None:
    state_dict = {"deliberation_id": "d1", "status": "running"}
    row = {"state_json": state_dict}
    conn = _make_conn()
    conn.fetchrow = AsyncMock(return_value=row)
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    result = await p.load_deliberation("d1")
    assert result == state_dict


# ---------------------------------------------------------------------------
# list_deliberations
# ---------------------------------------------------------------------------


async def test_list_deliberations_builds_summaries() -> None:
    rows = [
        {"id": "a", "problem": "p1", "status": "running", "created_at": 100.0},
        {"id": "b", "problem": "p2", "status": "done", "created_at": 50.0},
    ]
    conn = _make_conn()
    conn.fetch = AsyncMock(return_value=rows)
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    out = await p.list_deliberations(limit=10)
    assert len(out) == 2
    assert out[0].id == "a"
    assert out[1].id == "b"
    assert out[0].status == "running"


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------


async def test_append_event_inserts_event() -> None:
    conn = _make_conn()
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    ev = DeliberationEvent(seq=1, ts=2.0, kind="started", payload={"k": "v"})
    await p.append_event("d1", ev)

    call = conn.execute.await_args
    sql = call.args[0]
    args = call.args[1:]
    assert "INSERT INTO deliberation_events" in sql
    assert len(args) == 5
    assert args[0] == "d1"
    assert args[1] == 1
    assert args[2] == 2.0
    assert args[3] == "started"
    assert args[4] == {"k": "v"}


async def test_append_event_uses_on_conflict_do_nothing() -> None:
    conn = _make_conn()
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool
    ev = DeliberationEvent(seq=0, ts=0.0, kind="started", payload={})
    await p.append_event("d1", ev)
    sql = conn.execute.await_args.args[0]
    assert "ON CONFLICT DO NOTHING" in sql


async def test_get_events_returns_events_in_seq_order() -> None:
    rows = [
        {"seq": 0, "ts": 1.0, "kind": "started", "payload": {}},
        {"seq": 1, "ts": 2.0, "kind": "started", "payload": {"x": 1}},
    ]
    conn = _make_conn()
    conn.fetch = AsyncMock(return_value=rows)
    pool = _make_pool(conn)
    p = PostgresPool(dsn="postgres://x")
    p.pool = pool

    out = await p.get_events("d1")
    assert len(out) == 2
    assert isinstance(out[0], DeliberationEvent)
    assert out[0].seq == 0
    assert out[1].seq == 1


# ---------------------------------------------------------------------------
# assertion guards
# ---------------------------------------------------------------------------


async def test_all_methods_assert_pool_set() -> None:
    p = PostgresPool(dsn="postgres://x")
    state = _make_state()
    ev = DeliberationEvent(seq=0, ts=0.0, kind="started", payload={})
    with pytest.raises(AssertionError, match="PostgresPool"):
        await p.save_deliberation(state)
    with pytest.raises(AssertionError):
        await p.load_deliberation("d1")
    with pytest.raises(AssertionError):
        await p.list_deliberations(5)
    with pytest.raises(AssertionError):
        await p.append_event("d1", ev)
    with pytest.raises(AssertionError):
        await p.get_events("d1")


# ---------------------------------------------------------------------------
# _state_to_jsonable
# ---------------------------------------------------------------------------


def test_state_to_jsonable_handles_pydantic_via_model_dump() -> None:
    av = AgentVerdict(agent="alpha", position="approve", confidence=0.5, reasoning="r")
    state = _make_state(alpha=av)
    out = _state_to_jsonable(state)
    assert out["alpha_verdict"] == av.model_dump()
    assert out["deliberation_id"] == "d1"


def test_state_to_jsonable_handles_list_with_models() -> None:
    av1 = AgentVerdict(agent="alpha", position="approve", confidence=0.1, reasoning="r")
    av2 = AgentVerdict(agent="beta", position="reject", confidence=0.2, reasoning="r")
    # feedback is list[str] in DeliberationState, but test the list-w-models branch
    # by triggering it via _state_to_jsonable on an ad-hoc dict via state mutation
    state = _make_state(feedback=["a", "b"])
    out = _state_to_jsonable(state)
    assert out["feedback"] == ["a", "b"]
    # Now hit the actual list-models code path with a synthesized call shape:
    out2 = _state_to_jsonable({"items": [av1, av2]})  # type: ignore[arg-type]
    assert out2["items"][0]["agent"] == "alpha"
    assert out2["items"][1]["agent"] == "beta"


def test_state_to_jsonable_handles_dict_with_models() -> None:
    av = AgentVerdict(agent="alpha", position="approve", confidence=0.5, reasoning="r")
    state = _make_state()
    # State already triggers dict branch only if value is dict-of-models.
    state["extra"] = {"k1": av}  # type: ignore[typeddict-unknown-key]
    out = _state_to_jsonable(state)
    assert out["extra"]["k1"]["agent"] == "alpha"
