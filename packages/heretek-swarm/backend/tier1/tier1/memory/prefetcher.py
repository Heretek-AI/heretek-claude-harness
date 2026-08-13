"""Intelligent memory prefetcher — preloads likely-needed entries into Redis."""

from __future__ import annotations

import structlog

from tier1.memory.access_patterns import AccessPatternAnalyzer
from tier1.memory.redis_cache import RedisMemoryCache

log = structlog.get_logger(__name__)


class IntelligentPrefetcher:
    def __init__(
        self,
        patterns: AccessPatternAnalyzer,
        cache: RedisMemoryCache,
        backend,  # MemoryBackend
    ) -> None:
        self.patterns = patterns
        self.cache = cache
        self.backend = backend

    async def get_candidates(self, agent_id: str) -> list[str]:
        return await self.patterns.get_top_entries(agent_id, top_n=10)

    async def prefetch(self, agent_id: str, context: dict | None = None) -> int:
        """Preload likely-needed entries into Redis. Returns count prefetched."""
        try:
            candidates = await self.get_candidates(agent_id)
            count = 0
            for entry_id in candidates:
                existing = await self.cache.get(entry_id)
                if existing is not None:
                    continue
                entries = await self.backend.postgres.get_history(entry_id)
                if entries:
                    await self.cache.set(entry_id, entries[0], ttl=3600)
                    count += 1
            return count
        except Exception as exc:  # noqa: BLE001
            log.warning("prefetch_failed", agent_id=agent_id, error=str(exc))
            return 0
