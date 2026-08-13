"""Per-agent memory access pattern tracking."""

from __future__ import annotations

from datetime import datetime, timezone

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_access_patterns (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    entry_id TEXT NOT NULL,
    accessed_at TIMESTAMP NOT NULL DEFAULT NOW()
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_access_agent
ON memory_access_patterns(agent_id, accessed_at);
"""


class AccessPatternAnalyzer:
    def __init__(self, pool) -> None:
        self._pool = pool

    async def connect(self) -> None:
        await self._pool.execute(_CREATE_TABLE)
        await self._pool.execute(_CREATE_INDEX)

    async def record_access(
        self, agent_id: str, entry_id: str, timestamp: float | None = None
    ) -> None:
        ts = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc)
            if timestamp
            else datetime.now(timezone.utc)
        )
        await self._pool.execute(
            "INSERT INTO memory_access_patterns (agent_id, entry_id, accessed_at) VALUES ($1, $2, $3)",
            agent_id,
            entry_id,
            ts,
        )

    async def get_patterns(self, agent_id: str, window_s: int = 3600) -> list[dict]:
        rows = await self._pool.fetch(
            """SELECT entry_id, COUNT(*) as count, MAX(accessed_at) as last_accessed
               FROM memory_access_patterns
               WHERE agent_id = $1 AND accessed_at > NOW() - INTERVAL '1 second' * $2
               GROUP BY entry_id ORDER BY count DESC""",
            agent_id,
            window_s,
        )
        return [
            {
                "entry_id": r["entry_id"],
                "count": r["count"],
                "last_accessed": str(r["last_accessed"]),
            }
            for r in rows
        ]

    async def get_top_entries(self, agent_id: str, top_n: int = 10) -> list[str]:
        rows = await self._pool.fetch(
            """SELECT entry_id, COUNT(*) as count
               FROM memory_access_patterns WHERE agent_id = $1
               GROUP BY entry_id ORDER BY count DESC LIMIT $2""",
            agent_id,
            top_n,
        )
        return [r["entry_id"] for r in rows]
