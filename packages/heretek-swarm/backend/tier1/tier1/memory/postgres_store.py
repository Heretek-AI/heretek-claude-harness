"""PostgreSQL persistent store for memory entries and decision lineage."""

from __future__ import annotations

import json

from tier1.memory import MemoryEntry, MemoryType

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    source TEXT DEFAULT '',
    deliberation_id TEXT,
    agent TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_memory_deliberation
ON memory_entries(deliberation_id);
"""


class PostgresMemoryStore:
    def __init__(self, pool) -> None:
        self._pool = pool

    async def connect(self) -> None:
        """Create tables if they don't exist."""
        await self._pool.execute(_CREATE_TABLE)
        await self._pool.execute(_CREATE_INDEX)

    async def store(self, entry: MemoryEntry) -> None:
        await self._pool.execute(
            """INSERT INTO memory_entries (id, content, memory_type, source, deliberation_id, agent, created_at, metadata)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
               ON CONFLICT (id) DO UPDATE SET content = $2, metadata = $8::jsonb""",
            entry.id,
            entry.content,
            entry.memory_type.value,
            entry.source,
            entry.deliberation_id,
            entry.agent,
            entry.created_at,
            json.dumps(entry.metadata),
        )

    async def get_history(self, deliberation_id: str) -> list[MemoryEntry]:
        rows = await self._pool.fetch(
            "SELECT * FROM memory_entries WHERE deliberation_id = $1 ORDER BY created_at",
            deliberation_id,
        )
        return [
            MemoryEntry(
                id=row["id"],
                content=row["content"],
                memory_type=MemoryType(row["memory_type"]),
                source=row["source"],
                deliberation_id=row["deliberation_id"],
                agent=row["agent"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            )
            for row in rows
        ]

    async def delete(self, entry_id: str) -> None:
        await self._pool.execute("DELETE FROM memory_entries WHERE id = $1", entry_id)
