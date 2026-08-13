"""Memory system — unified facade over Qdrant, Redis, and PostgreSQL."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import AsyncIterator


class MemoryType(str, Enum):
    episodic = "episodic"
    semantic = "semantic"
    procedural = "procedural"


@dataclass
class MemoryEntry:
    content: str
    memory_type: MemoryType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)
    source: str = ""
    deliberation_id: str | None = None
    agent: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: int | None = None


class MemoryBackend:
    """Unified memory facade over Qdrant, Redis, and PostgreSQL."""

    def __init__(
        self,
        qdrant: "QdrantStore",
        redis: "RedisMemoryCache",
        postgres: "PostgresMemoryStore",
        mem0: "Mem0Backend | None" = None,
        cognee: "CogneePipeline | None" = None,
    ) -> None:
        self.qdrant = qdrant
        self.redis = redis
        self.postgres = postgres
        self.mem0 = mem0
        self.cognee = cognee

    async def store(self, entry: MemoryEntry) -> str:
        """Store entry to all tiers. Returns entry.id."""
        # Qdrant (vector) — best effort
        try:
            await self.qdrant.store(entry)
        except Exception:  # noqa: BLE001
            pass

        # Redis (ephemeral) — best effort
        ttl = entry.ttl_seconds or 3600
        try:
            await self.redis.set(entry.id, entry, ttl)
        except Exception:  # noqa: BLE001
            pass

        # Postgres (lineage) — critical
        await self.postgres.store(entry)

        # Mem0 (semantic) — best effort
        if self.mem0:
            try:
                await self.mem0.add(entry.content, user_id=entry.agent, metadata=entry.metadata)
            except Exception:  # noqa: BLE001
                pass

        # Cognee (knowledge graph) — best effort
        if self.cognee is not None:
            try:
                await self.cognee.add(entry.content, metadata=entry.metadata)
            except Exception:  # noqa: BLE001
                pass

        return entry.id

    async def search(self, query: str, *, top_k: int = 5) -> list[MemoryEntry]:
        """Semantic search via Qdrant."""
        return await self.qdrant.search(query, top_k=top_k)

    async def get_history(self, deliberation_id: str) -> list[MemoryEntry]:
        """Decision history from Postgres."""
        return await self.postgres.get_history(deliberation_id)

    async def get_session(self, key: str) -> MemoryEntry | None:
        """Ephemeral session lookup from Redis."""
        return await self.redis.get(key)
