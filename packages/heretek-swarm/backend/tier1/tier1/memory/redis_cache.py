"""Redis ephemeral cache for memory entries."""

from __future__ import annotations

import json

import redis.asyncio as aioredis

from tier1.memory import MemoryEntry, MemoryType


class RedisMemoryCache:
    def __init__(self, url: str, ttl_s: int) -> None:
        self.url = url
        self.ttl_s = ttl_s
        self.client: aioredis.Redis | None = None

    async def connect(self) -> None:
        self.client = aioredis.from_url(self.url, decode_responses=True)
        await self.client.ping()

    async def close(self) -> None:
        if self.client is not None:
            await self.client.aclose()
            self.client = None

    def _key(self, entry_id: str) -> str:
        return f"tier1:memory:{entry_id}"

    async def get(self, entry_id: str) -> MemoryEntry | None:
        assert self.client is not None
        raw = await self.client.get(self._key(entry_id))
        if raw is None:
            return None
        data = json.loads(raw)
        return MemoryEntry(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            source=data.get("source", ""),
            deliberation_id=data.get("deliberation_id"),
            agent=data.get("agent", ""),
            created_at=data.get("created_at", ""),
            ttl_seconds=data.get("ttl_seconds"),
        )

    async def set(self, entry_id: str, entry: MemoryEntry, ttl: int | None = None) -> None:
        assert self.client is not None
        payload = json.dumps(
            {
                "id": entry.id,
                "content": entry.content,
                "memory_type": entry.memory_type.value,
                "embedding": entry.embedding,
                "metadata": entry.metadata,
                "source": entry.source,
                "deliberation_id": entry.deliberation_id,
                "agent": entry.agent,
                "created_at": entry.created_at,
                "ttl_seconds": entry.ttl_seconds,
            }
        )
        await self.client.set(self._key(entry_id), payload, ex=ttl or self.ttl_s)

    async def delete(self, entry_id: str) -> None:
        assert self.client is not None
        await self.client.delete(self._key(entry_id))
