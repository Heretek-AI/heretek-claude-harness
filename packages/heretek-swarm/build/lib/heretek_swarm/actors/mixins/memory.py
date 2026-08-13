"""
MemoryMixin - Memory access tracking and tier management.

Provides methods for tracking memory access patterns,
determining memory tiers, and prefetching relevant memories.
"""

import structlog

from heretek_swarm.memory.access_patterns import AccessPatternAnalyzer, AccessTier

logger = structlog.get_logger("MemoryMixin")


class MemoryMixin:
    """
    Mixin providing memory optimization methods.

    Requires the host actor to have:
        - access_analyzer: AccessPatternAnalyzer | None

    Methods:
        _track_memory_access: Record a memory access event
        _get_memory_tier: Get tier classification for an item
        _prefetch_relevant: Prefetch items an agent likely needs
    """

    access_analyzer: AccessPatternAnalyzer | None = None

    def _track_memory_access(
        self,
        item_id: str,
        item_type: str,
        access_type: str = "read",
    ) -> None:
        """
        Track a memory access pattern.

        Args:
            item_id: Unique identifier for the item
            item_type: Type of item (e.g., "code", "decision")
            access_type: Type of access ("read" or "write")
        """
        if not self.access_analyzer:
            raise TypeError("_track_memory_access requires access_analyzer")

        memory_id = f"{item_type}_{item_id}"
        self.access_analyzer.record_access(
            memory_id=memory_id,
            access_type=access_type,
            agent_id=self.agent_id,
        )

    def _get_memory_tier(self, item_id: str, item_type: str) -> AccessTier:
        """
        Get memory tier classification for an item.

        Args:
            item_id: Unique identifier for the item
            item_type: Type of item

        Returns:
            AccessTier classification (HOT, WARM, COLD)
        """
        if not self.access_analyzer:
            raise TypeError("_get_memory_tier requires access_analyzer")

        memory_id = f"{item_type}_{item_id}"
        profile = self.access_analyzer.get_profile(memory_id)
        return profile.tier if profile else AccessTier.COLD

    async def _prefetch_relevant(
        self,
        agent_id: str,
        item_type: str,
    ) -> list[str]:
        """
        Prefetch items an agent is likely to need.

        Args:
            agent_id: The agent to prefetch for
            item_type: Type of items to prefetch

        Returns:
            List of item IDs predicted to be relevant
        """
        if not self.access_analyzer:
            raise TypeError("_prefetch_relevant requires access_analyzer")

        try:
            predicted_memories = self.access_analyzer.predict_agent_access(agent_id)
            return [
                mem.replace(f"{item_type}_", "")
                for mem in predicted_memories
                if mem.startswith(f"{item_type}_")
            ]
        except Exception as e:
            logger.warning(
                "failed_to_prefetch",
                agent_id=agent_id,
                error=str(e),
            )
            return []
