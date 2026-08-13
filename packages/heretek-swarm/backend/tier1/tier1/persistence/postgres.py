"""Postgres pool + deliberations table.

Schema (created on connect if missing):

    CREATE TABLE deliberations (
        id              TEXT PRIMARY KEY,
        problem         TEXT NOT NULL,
        user_id         TEXT NOT NULL,
        status          TEXT NOT NULL,
        round           INT  NOT NULL DEFAULT 0,
        max_rounds      INT  NOT NULL,
        state_json      JSONB NOT NULL,
        final_verdict   JSONB,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    CREATE TABLE deliberation_events (
        deliberation_id TEXT NOT NULL REFERENCES deliberations(id) ON DELETE CASCADE,
        seq             INT  NOT NULL,
        ts              DOUBLE PRECISION NOT NULL,
        kind            TEXT NOT NULL,
        payload         JSONB NOT NULL,
        PRIMARY KEY (deliberation_id, seq)
    );
"""

from __future__ import annotations

import json

import asyncpg

from tier1.api.schemas import DeliberationSummary
from tier1.deliberation.state import DeliberationEvent, DeliberationState


async def _set_json_codecs(conn: asyncpg.Connection) -> None:
    """Decode JSONB columns to dicts/lists automatically."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


class PostgresPool:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.dsn, min_size=1, max_size=10, init=_set_json_codecs
        )
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deliberations (
                    id TEXT PRIMARY KEY,
                    problem TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    "round" INT NOT NULL DEFAULT 0,
                    max_rounds INT NOT NULL,
                    state_json JSONB NOT NULL,
                    final_verdict JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deliberation_events (
                    deliberation_id TEXT NOT NULL REFERENCES deliberations(id) ON DELETE CASCADE,
                    seq INT NOT NULL,
                    ts DOUBLE PRECISION NOT NULL,
                    kind TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    PRIMARY KEY (deliberation_id, seq)
                )
                """
            )

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    async def save_deliberation(self, state: DeliberationState) -> None:
        assert self.pool is not None, "PostgresPool.connect() must be called first"
        state_json = _state_to_jsonable(state)
        final = state.get("final_verdict")
        final_json = final.model_dump() if final is not None else None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deliberations
                    (id, problem, user_id, status, "round", max_rounds, state_json, final_verdict, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    "round" = EXCLUDED."round",
                    state_json = EXCLUDED.state_json,
                    final_verdict = EXCLUDED.final_verdict,
                    updated_at = NOW()
                """,
                state["deliberation_id"],
                state["problem"],
                state["user_id"],
                state.get("status", "running"),
                state.get("round", 0),
                state.get("max_rounds", 3),
                state_json,
                final_json,
            )

    async def load_deliberation(self, deliberation_id: str) -> DeliberationState | None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT state_json FROM deliberations WHERE id = $1", deliberation_id
            )
        if row is None:
            return None
        data = row["state_json"]
        return _state_from_jsonable(data)

    async def list_deliberations(self, limit: int) -> list[DeliberationSummary]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, problem, status, EXTRACT(EPOCH FROM created_at) AS created_at
                FROM deliberations
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [
            DeliberationSummary(
                id=r["id"], problem=r["problem"], status=r["status"], created_at=r["created_at"]
            )
            for r in rows
        ]

    async def append_event(self, deliberation_id: str, event: DeliberationEvent) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO deliberation_events (deliberation_id, seq, ts, kind, payload)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT DO NOTHING
                """,
                deliberation_id,
                event.seq,
                event.ts,
                event.kind,
                event.payload,
            )

    async def get_events(self, deliberation_id: str) -> list[DeliberationEvent]:
        assert self.pool is not None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT seq, ts, kind, payload
                FROM deliberation_events
                WHERE deliberation_id = $1
                ORDER BY seq ASC
                """,
                deliberation_id,
            )
        return [
            DeliberationEvent(seq=r["seq"], ts=r["ts"], kind=r["kind"], payload=r["payload"])
            for r in rows
        ]


def _state_to_jsonable(state: DeliberationState) -> dict:
    """Convert a DeliberationState (with Pydantic models inside) to a JSON-safe dict."""
    out: dict = {}
    for k, v in state.items():
        if hasattr(v, "model_dump"):
            out[k] = v.model_dump()
        elif isinstance(v, list):
            out[k] = [x.model_dump() if hasattr(x, "model_dump") else x for x in v]
        elif isinstance(v, dict):
            out[k] = {
                kk: vv.model_dump() if hasattr(vv, "model_dump") else vv for kk, vv in v.items()
            }
        else:
            out[k] = v
    return out


def _state_from_jsonable(data: dict) -> DeliberationState:
    """Rehydrate a DeliberationState from its JSON form.

    Note: verdict fields are kept as raw dicts here; callers that need
    AgentVerdict objects should construct them at the use site.
    """
    out: DeliberationState = {}
    for k, v in data.items():
        out[k] = v
    return out
