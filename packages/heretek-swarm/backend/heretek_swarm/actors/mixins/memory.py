"""
MemoryMixin - Memory access tracking and tier management.

Provides methods for tracking memory access patterns,
determining memory tiers, and prefetching relevant memories.

Follow-up to Phase 1.1 of PLAN.md: the mixin used to hard-code
``self.access_analyzer: AccessPatternAnalyzer | None = None``
and raise ``TypeError`` when missing. New code can instead
use the canonical :class:`heretek_swarm.memory.MemoryStore`
Protocol via :func:`heretek_swarm.memory.get_default_store`;
the legacy ``self.access_analyzer`` path still works for
backwards compatibility.
"""

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm_core.memory.access_patterns import (
        AccessPatternAnalyzer,
        AccessTier,
    )
    from heretek_swarm_core.memory.store import MemoryStore

# Lazy imports at runtime to avoid the circular-import chain:
# actors.mixins -> heretek_swarm_core.memory -> heretek_swarm_core.__init__
#   -> heretek_swarm.actors.supervisor -> actors.mixins (partial).
# Functions below import on demand.

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

    # Use string annotations to avoid needing runtime imports of the
    # analyzer / store types — those are resolved lazily inside the
    # methods below to dodge the heretek_swarm_core import cycle.
    access_analyzer: "AccessPatternAnalyzer | None" = None
    # Optional canonical MemoryStore (Phase 1.1 of PLAN.md). When
    # ``access_analyzer`` is None, ``_get_memory_store`` falls back
    # to :func:`get_default_store`, which returns the cognee /
    # mem0 / null adapter the swarm was configured with. New
    # actors should set this attribute (or rely on the default
    # resolver) instead of wiring an analyzer explicitly.
    memory_store: "MemoryStore | None" = None

    def _get_memory_store(self) -> "MemoryStore":
        """Return the canonical memory store for this actor.

        Prefers ``self.memory_store`` if explicitly set; falls
        back to ``get_default_store()``; if neither is usable,
        returns the in-memory null store so the actor stays
        bootable in dev.
        """
        if self.memory_store is not None:
            return self.memory_store
        from heretek_swarm_core.memory.store import get_default_store

        return get_default_store()

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

        Phase 1.1 follow-up: when the legacy ``access_analyzer``
        is not wired, this is a no-op (the canonical ``MemoryStore``
        is the primary write path now). New code should write
        directly to the store via ``_get_memory_store()`` and
        reserve access-pattern tracking for the AccessPatternAnalyzer
        only when the host actor opted in explicitly.
        """
        if not self.access_analyzer:
            return

        memory_id = f"{item_type}_{item_id}"
        self.access_analyzer.record_access(
            memory_id=memory_id,
            access_type=access_type,
            agent_id=self.agent_id,
        )

    def _get_memory_tier(self, item_id: str, item_type: str) -> "AccessTier":
        """
        Get memory tier classification for an item.

        Args:
            item_id: Unique identifier for the item
            item_type: Type of item

        Returns:
            AccessTier classification (HOT, WARM, COLD)
        """
        from heretek_swarm_core.memory.access_patterns import AccessTier

        # Phase 1.1 follow-up: if access_analyzer is not wired,
        # fall back to the canonical MemoryStore's read; if
        # even that is unavailable, return COLD as the safe default
        # so the actor stays bootable.
        memory_id = f"{item_type}_{item_id}"
        if self.access_analyzer is not None:
            profile = self.access_analyzer.get_profile(memory_id)
            return profile.tier if profile else AccessTier.COLD
        try:
            import asyncio

            store = self._get_memory_store()
            entry = (
                asyncio.get_event_loop().run_until_complete(store.read(memory_id))
                if asyncio.get_event_loop().is_running() is False
                else None
            )
            if entry is not None and entry.metadata.get("tier"):
                return AccessTier(entry.metadata["tier"])
        except Exception:
            pass
        return AccessTier.COLD

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

        Phase 1.1 follow-up: when the legacy ``access_analyzer``
        is not wired, this returns an empty list. The canonical
        :class:`MemoryStore` exposes ``search()`` for relevance;
        callers that need prefetch semantics should call
        ``_get_memory_store().search()`` directly with a
        per-agent query. The legacy analyzer is reserved for
        host actors that opted in explicitly.
        """
        if not self.access_analyzer:
            return []

        try:
            predicted_memories = self.access_analyzer.predict_agent_access(agent_id)
            return [mem.replace(f"{item_type}_", "") for mem in predicted_memories if mem.startswith(f"{item_type}_")]
        except Exception as e:
            logger.warning(
                "failed_to_prefetch",
                agent_id=agent_id,
                error=str(e),
            )
            return []
