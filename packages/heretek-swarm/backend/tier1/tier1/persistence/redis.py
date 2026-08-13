"""Redis hot-cache for active deliberations.

Keys:
    tier1:state:{id}  ->  JSON-encoded DeliberationState
TTL: settings.redis_ttl_s (default 3600s)
"""

from __future__ import annotations

import json
from typing import cast

import redis.asyncio as aioredis

from tier1.deliberation.state import DeliberationState


class RedisCache:
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

    def _key(self, deliberation_id: str) -> str:
        return f"tier1:state:{deliberation_id}"

    async def put_state(self, state: DeliberationState) -> None:
        assert self.client is not None
        key = self._key(state["deliberation_id"])
        payload = json.dumps(state, default=lambda o: o.model_dump())
        await self.client.set(key, payload, ex=self.ttl_s)

    async def get_state(self, deliberation_id: str) -> DeliberationState | None:
        assert self.client is not None
        raw = await self.client.get(self._key(deliberation_id))
        if raw is None:
            return None
        return cast(DeliberationState, json.loads(raw))

    async def drop_state(self, deliberation_id: str) -> None:
        assert self.client is not None
        await self.client.delete(self._key(deliberation_id))
