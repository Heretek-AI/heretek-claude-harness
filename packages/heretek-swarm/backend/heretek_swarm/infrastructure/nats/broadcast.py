"""
NATS Pattern Broadcasting for Collective Learning.

Provides NATS-based pub/sub for pattern broadcasting across agents.
Supports pattern emission, topic-based subscription, and cross-agent consumption.
"""

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.collective.learning import (
    ExtractedPattern,
    PatternMetadata,
    PatternSource,
    PatternType,
)

if TYPE_CHECKING:
    from heretek_swarm.infrastructure.nats.client import NATSClient

logger = structlog.get_logger(__name__)


class BroadcastConfig:
    """Configuration for pattern broadcasting."""

    def __init__(
        self,
        prefix: str = "patterns",
        max_queue_size: int = 1000,
        message_ttl: int = 3600,
    ) -> None:
        self.prefix = prefix
        self.max_queue_size = max_queue_size
        self.message_ttl = message_ttl


class PatternBroadcast:
    """
    NATS-based pattern broadcasting for collective learning.

    Provides pub/sub for pattern broadcasting:
    - emit_pattern: Publish patterns to NATS
    - subscribe_patterns: Subscribe to pattern topics
    - consume_patterns: Retrieve patterns from NATS
    """

    def __init__(
        self,
        client: "NATSClient | None" = None,
        config: BroadcastConfig | None = None,
    ) -> None:
        self._client = client
        self._config = config or BroadcastConfig()
        self._subscriptions: dict[str, Any] = {}
        self._subscription_counter = 0

    def _get_pattern_subject(self, pattern_type: PatternType | str) -> str:
        """Get NATS subject for a pattern type."""
        type_value = pattern_type if isinstance(pattern_type, str) else pattern_type.value
        return f"{self._config.prefix}.{type_value}"

    def _serialize_pattern(
        self,
        pattern: ExtractedPattern,
        metadata: PatternMetadata | None = None,
    ) -> str:
        """Serialize pattern to JSON string."""
        data = {
            "pattern_id": pattern.metadata.pattern_id,
            "pattern_type": pattern.metadata.pattern_type.value,
            "source": pattern.metadata.source.value,
            "confidence": pattern.metadata.confidence,
            "support_count": pattern.metadata.support_count,
            "first_observed": pattern.metadata.first_observed,
            "last_observed": pattern.metadata.last_observed,
            "agents_involved": pattern.metadata.agents_involved,
            "topics": pattern.metadata.topics,
            "tags": pattern.metadata.tags,
            "pattern_data": pattern.pattern_data,
            "context": pattern.context,
            "outcomes": pattern.outcomes,
            "preconditions": pattern.preconditions,
            "postconditions": pattern.postconditions,
            "applicability_conditions": pattern.applicability_conditions,
            "broadcast_at": datetime.now(UTC).isoformat(),
        }
        if metadata:
            data["extra_metadata"] = {
                "source_agent": metadata.agents_involved[0] if metadata.agents_involved else None,
            }
        return json.dumps(data)

    def _deserialize_pattern(self, data: str) -> ExtractedPattern | None:
        """Deserialize pattern from JSON string."""
        try:
            obj = json.loads(data)
            metadata = PatternMetadata(
                pattern_id=obj.get("pattern_id", str(uuid.uuid4())),
                pattern_type=PatternType(obj.get("pattern_type", "success")),
                source=PatternSource(obj.get("source", "message_history")),
                confidence=obj.get("confidence", 0.0),
                support_count=obj.get("support_count", 0),
                first_observed=obj.get("first_observed"),
                last_observed=obj.get("last_observed"),
                agents_involved=obj.get("agents_involved", []),
                topics=obj.get("topics", []),
                tags=obj.get("tags", []),
            )
            return ExtractedPattern(
                metadata=metadata,
                pattern_data=obj.get("pattern_data", {}),
                context=obj.get("context", {}),
                outcomes=obj.get("outcomes", []),
                preconditions=obj.get("preconditions", []),
                postconditions=obj.get("postconditions", []),
                applicability_conditions=obj.get("applicability_conditions", []),
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("failed_to_deserialize_pattern", error=str(e))
            return None

    async def emit_pattern(
        self,
        pattern: ExtractedPattern,
        pattern_type: PatternType | str | None = None,
        client: "NATSClient | None" = None,
    ) -> bool:
        """
        Emit a pattern to NATS.

        Args:
            pattern: The pattern to broadcast
            pattern_type: Override pattern type (uses pattern metadata if None)
            client: NATS client (uses internal client if None)

        Returns:
            True if published successfully
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("emit_pattern_no_client")
            return False

        if not nats_client.is_connected:
            logger.warning("emit_pattern_not_connected")
            return False

        ptype = pattern_type or pattern.metadata.pattern_type
        subject = self._get_pattern_subject(ptype)

        try:
            message = self._serialize_pattern(pattern)
            await nats_client.publish(subject, message.encode())
            logger.info(
                "pattern_emitted",
                subject=subject,
                pattern_type=ptype,
                pattern_id=pattern.metadata.pattern_id,
            )
            return True
        except Exception as e:
            logger.error("emit_pattern_failed", error=str(e), subject=subject)
            return False

    async def subscribe_patterns(
        self,
        pattern_types: list[PatternType | str],
        callback: Callable[[ExtractedPattern], Any],
        client: "NATSClient | None" = None,
        queue: str | None = None,
    ) -> str | None:
        """
        Subscribe to pattern topics.

        Args:
            pattern_types: List of pattern types to subscribe to
            callback: Async function to call with each pattern
            client: NATS client (uses internal client if None)
            queue: Optional queue group name

        Returns:
            Subscription ID if successful
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("subscribe_patterns_no_client")
            return None

        if not nats_client.is_connected:
            logger.warning("subscribe_patterns_not_connected")
            return None

        subscription_id = f"pattern_sub_{self._subscription_counter}"
        self._subscription_counter += 1

        async def wrapper_handler(msg: Any) -> None:
            """Wrapper to deserialize and callback."""
            try:
                pattern = self._deserialize_pattern(msg.data.decode())
                if pattern:
                    await callback(pattern)
            except Exception as e:
                logger.error("subscribe_callback_error", error=str(e))

        subjects = [self._get_pattern_subject(pt) for pt in pattern_types]
        for subject in subjects:
            try:
                if queue:
                    await nats_client.subscribe(subject, queue=queue)(wrapper_handler)
                else:
                    await nats_client.subscribe(subject)(wrapper_handler)
                logger.info(
                    "subscribed_to_patterns",
                    subject=subject,
                    subscription_id=subscription_id,
                )
            except Exception as e:
                logger.error("subscribe_failed", error=str(e), subject=subject)
                return None

        self._subscriptions[subscription_id] = subjects
        return subscription_id

    async def consume_patterns(
        self,
        pattern_type: PatternType | str,
        client: "NATSClient | None" = None,
        max_messages: int = 10,
        timeout_sec: float = 5.0,
    ) -> list[ExtractedPattern]:
        """
        Consume patterns from NATS.

        Args:
            pattern_type: Pattern type to consume
            client: NATS client (uses internal client if None)
            max_messages: Maximum patterns to retrieve
            timeout_sec: Timeout in seconds for each request.

        Returns:
            List of consumed patterns
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("consume_patterns_no_client")
            return []

        if not nats_client.is_connected:
            logger.warning("consume_patterns_not_connected")
            return []

        subject = self._get_pattern_subject(pattern_type)
        patterns: list[ExtractedPattern] = []

        try:
            messages = await nats_client.request(
                subject, b"", timeout=timeout_sec, max_messages=max_messages
            )
            for msg in messages:
                pattern = self._deserialize_pattern(msg.data.decode())
                if pattern:
                    patterns.append(pattern)
            logger.info("consumed_patterns", subject=subject, count=len(patterns))
        except Exception as e:
            logger.error("consume_patterns_failed", error=str(e), subject=subject)

        return patterns

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from pattern broadcasts.

        Args:
            subscription_id: Subscription ID to cancel

        Returns:
            True if unsubscribed successfully
        """
        if subscription_id not in self._subscriptions:
            logger.warning("unsubscribe_unknown_id", subscription_id=subscription_id)
            return False

        try:
            subjects = self._subscriptions.pop(subscription_id)
            for subject in subjects:
                await self._client.unsubscribe(subject)
            logger.info("unsubscribed_patterns", subscription_id=subscription_id)
            return True
        except Exception as e:
            logger.error("unsubscribe_failed", error=str(e), subscription_id=subscription_id)
            return False
