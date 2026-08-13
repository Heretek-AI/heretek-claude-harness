"""PatternConsumerMixin for collective learning patterns."""

import asyncio
from typing import Any


class PatternConsumerMixin:
    """Mixin for pattern emission and consumption.

    Extracted from 16 actor files to remove ~608 lines of duplication.
    """

    async def _emit_pattern(
        self, pattern_type: str, data: dict[str, Any], metadata: dict[str, Any] | None = None
    ) -> None:
        """Emit a pattern for collective learning.

        Args:
            pattern_type: Type of pattern
            data: Pattern data payload
            metadata: Optional metadata
        """
        pattern = {
            "type": pattern_type,
            "data": data,
            "metadata": metadata or {},
        }

        if hasattr(self, "agent_id"):
            pattern["metadata"]["agent_id"] = self.agent_id
        pattern["metadata"]["timestamp"] = asyncio.get_event_loop().time()

        try:
            if hasattr(self, "_pattern_publisher"):
                await self._pattern_publisher.publish(
                    channel="collective:patterns", message=pattern
                )
        except Exception:
            self.logger.warning("Failed to emit pattern: {e}")

    async def _consume_patterns(
        self, pattern_types: list[str] | None = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Consume patterns from collective learning.

        Args:
            pattern_types: Filter by pattern types
            limit: Maximum patterns to retrieve

        Returns:
            List of patterns matching criteria
        """
        try:
            if hasattr(self, "_pattern_subscriber"):
                patterns = await self._pattern_subscriber.fetch(
                    channel="collective:patterns", limit=limit
                )
                if pattern_types:
                    patterns = [p for p in patterns if p.get("type") in pattern_types]
                return patterns
        except Exception:
            self.logger.warning("Failed to consume patterns: {e}")
        return []

    async def _learn_from_pattern(self, pattern: dict[str, Any]) -> None:
        """Extract and apply learning from a pattern."""
        pattern_type = pattern.get("type")
        data = pattern.get("data", {})

        if pattern_type == "consensus_decision":
            await self._learn_from_consensus(data)
        elif pattern_type == "task_success":
            await self._learn_from_success(data)
        elif pattern_type == "task_failure":
            await self._learn_from_failure(data)

    async def _learn_from_consensus(self, data: dict[str, Any]) -> None:
        """Learn from consensus decision pattern."""
        if hasattr(self, "_learning_system"):
            await self._learning_system.update_from_consensus(data)

    async def _learn_from_success(self, data: dict[str, Any]) -> None:
        """Learn from task success pattern."""
        if hasattr(self, "_learning_system"):
            await self._learning_system.update_from_success(data)

    async def _learn_from_failure(self, data: dict[str, Any]) -> None:
        """Learn from task failure pattern."""
        if hasattr(self, "_learning_system"):
            await self._learning_system.update_from_failure(data)
