"""
PatternMixin - Collective pattern emission and consumption.

Provides methods for emitting patterns to collective learning
and consuming patterns from other agents.
"""

from datetime import UTC, datetime
from typing import Any

import structlog

from heretek_swarm.collective.learning import PatternExtractor, PatternType

logger = structlog.get_logger("PatternMixin")


class PatternMixin:
    """
    Mixin providing collective pattern learning methods.

    Requires the host actor to have:
        - pattern_extractor: PatternExtractor | None
        - _pattern_emitted: set[str]

    Methods:
        _emit_pattern: Emit a pattern to collective learning
        _consume_patterns: Consume patterns from collective learning
    """

    pattern_extractor: PatternExtractor | None = None
    _pattern_emitted: set[str] = None

    async def _emit_pattern(
        self,
        item_id: str,
        item_type: str,
        outcome: str,
        content: dict[str, Any],
    ) -> None:
        """
        Emit a pattern for collective learning.

        Args:
            item_id: Unique identifier for the item
            item_type: Type of item (e.g., "code", "decision")
            outcome: Outcome of the pattern (e.g., "success", "failure")
            content: Pattern content/metadata
        """
        if not self.pattern_extractor:
            raise TypeError("_emit_pattern requires pattern_extractor")

        if item_id in (self._pattern_emitted or set()):
            return

        try:
            await self.pattern_extractor.analyze_message(
                message_id=f"{item_type}_{item_id}",
                sender=self.agent_id,
                recipient="broadcast",
                message_type=f"{item_type}_completion",
                content=content,
                timestamp=datetime.now(UTC).isoformat(),
            )

            self._pattern_emitted.add(item_id)
            logger.info(
                f"{item_type}_pattern_emitted",  # noqa: G004
                item_id=item_id,
                outcome=outcome,
            )
        except Exception as e:
            logger.warning("failed_to_emit_pattern", item_id=item_id, error=str(e))

    async def _consume_patterns(
        self,
        pattern_types: list[PatternType] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Consume patterns from collective learning.

        Args:
            pattern_types: Filter by specific pattern types

        Returns:
            List of validated pattern dictionaries
        """
        if not self.pattern_extractor:
            raise TypeError("_consume_patterns requires pattern_extractor")

        try:
            patterns = await self.pattern_extractor.extract_patterns(
                time_window_hours=24,
                pattern_types=pattern_types
                or [
                    PatternType.SUCCESS,
                    PatternType.DECISION,
                ],
            )
            return [p.to_dict() for p in patterns if p.metadata.confidence >= 0.7]
        except Exception as e:
            logger.warning("failed_to_consume_patterns", error=str(e))
            return []
