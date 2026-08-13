"""MemoryAccessMixin for agent memory operations."""

import asyncio
from typing import Any


class MemoryAccessMixin:
    """Mixin for memory access and tracking.

    Extracted from 16 actor files to remove ~544 lines of duplication.
    """

    async def _track_memory_access(
        self, memory_id: str, access_type: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """Track memory access for observability."""
        access_record = {
            "memory_id": memory_id,
            "access_type": access_type,
            "agent_id": getattr(self, "agent_id", "unknown"),
            "timestamp": asyncio.get_event_loop().time(),
            "metadata": metadata or {},
        }
        try:
            if hasattr(self, "_memory_access_logger"):
                await self._memory_access_logger.log(access_record)
        except Exception:
            self.logger.debug("Memory access tracking failed: {e}")

    async def _get_memory_tier(self, memory_type: str = "episodic") -> str:
        """Get memory tier for specified memory type."""
        tier_mapping = {
            "working": "tier-1",
            "episodic": "tier-2",
            "semantic": "tier-3",
        }
        return tier_mapping.get(memory_type, "tier-2")

    async def _fetch_from_memory(
        self, query: str, memory_type: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Fetch memories matching query."""
        try:
            if hasattr(self, "_memory_system"):
                memories = await self._memory_system.search(
                    query=query, memory_type=memory_type, limit=limit
                )
                for memory in memories:
                    await self._track_memory_access(memory_id=memory.get("id"), access_type="read")
                return memories
        except Exception:
            self.logger.warning("Memory fetch failed: {e}")
        return []

    async def _store_to_memory(
        self, content: str, memory_type: str = "episodic", metadata: dict[str, Any] | None = None
    ) -> str | None:
        """Store content to memory."""
        try:
            if hasattr(self, "_memory_system"):
                memory_id = await self._memory_system.store(
                    content=content, memory_type=memory_type, metadata=metadata or {}
                )
                await self._track_memory_access(memory_id=memory_id, access_type="write")
                return memory_id
        except Exception:
            self.logger.warning("Memory store failed: {e}")
        return None
