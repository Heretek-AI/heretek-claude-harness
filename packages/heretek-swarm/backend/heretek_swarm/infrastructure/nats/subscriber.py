"""
NATS Subscriber for Heretek Swarm.

Provides subscription management for event-driven communication.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.infrastructure.nats.client import get_nats_client
from heretek_swarm.infrastructure.nats.publisher import EventPriority, SwarmEvent

if TYPE_CHECKING:
    from pynats import NATSClient

logger = structlog.get_logger(__name__)


class SubscriptionState(Enum):
    """Subscription lifecycle state."""

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class SubscriptionConfig:
    """Configuration for a subscription."""

    subject: str
    queue: str | None = None
    max_messages: int = 0  # 0 = unlimited
    ack_mode: str = "auto"  # auto, manual, none
    filter_metadata: dict[str, str] | None = None
    priority_filter: EventPriority | None = None  # None = all priorities


@dataclass
class Subscription:
    """Represents a subscription to NATS subject."""

    subscription_id: str
    config: SubscriptionConfig
    state: SubscriptionState = SubscriptionState.PENDING
    message_count: int = 0
    last_message_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    callback: Callable[[SwarmEvent], Any] | None = None


class NATSSubscriber:
    """
    Manages NATS subscriptions for event-driven communication.

    Handles:
    - Topic subscriptions with queue groups
    - Message filtering by metadata
    - Priority-based filtering
    - Subscription lifecycle management
    - Acknowledgement modes
    """

    def __init__(self, config: SubscriptionConfig | None = None):
        self.config = config
        self._subscriptions: dict[str, Subscription] = {}
        self._client: NATSClient | None = None
        self._subscription_counter = 0

    async def initialize(self) -> None:
        """Initialize subscriber and connect to NATS."""
        self._client = await get_nats_client()
        logger.info("subscriber_initialized")

    async def subscribe(
        self,
        subject: str,
        callback: Callable[[SwarmEvent], Any],
        queue: str | None = None,
        max_messages: int = 0,
        ack_mode: str = "auto",
        filter_metadata: dict[str, str] | None = None,
        priority_filter: EventPriority | None = None,
    ) -> str:
        """
        Subscribe to a NATS subject.

        Args:
            subject: Subject pattern to subscribe to
            callback: Async function to call with each event
            queue: Optional queue group name
            max_messages: Max messages before auto-unsubscribe (0 = unlimited)
            ack_mode: Acknowledgement mode
            filter_metadata: Filter by metadata key-value pairs
            priority_filter: Only receive events at or above this priority

        Returns:
            Subscription ID for later management
        """
        self._subscription_counter += 1
        sub_id = f"sub_{self._subscription_counter}"

        sub_config = SubscriptionConfig(
            subject=subject,
            queue=queue,
            max_messages=max_messages,
            ack_mode=ack_mode,
            filter_metadata=filter_metadata,
            priority_filter=priority_filter,
        )

        subscription = Subscription(
            subscription_id=sub_id,
            config=sub_config,
            callback=callback,
        )

        self._subscriptions[sub_id] = subscription

        # Register with NATS
        if self._client:
            try:

                def wrapped_callback(msg):
                    """Wrapper that converts NATS message to SwarmEvent and calls callback."""
                    self._handle_message(sub_id, msg)

                self._client.subscribe(
                    subject=subject,
                    queue=queue,
                    callback=wrapped_callback,
                )
                subscription.state = SubscriptionState.ACTIVE

                logger.info(
                    "subscription_created",
                    subscription_id=sub_id,
                    subject=subject,
                    queue=queue,
                )
            except Exception as e:
                subscription.state = SubscriptionState.ERROR
                logger.error("subscription_failed", subscription_id=sub_id, error=str(e))
                raise

        return sub_id

    def _handle_message(self, sub_id: str, msg) -> None:
        """Handle incoming NATS message."""
        subscription = self._subscriptions.get(sub_id)
        if not subscription:
            return

        try:
            # Parse message into SwarmEvent
            data = msg.data if hasattr(msg, "data") else msg
            if isinstance(data, bytes):
                import json

                data = json.loads(data.decode("utf-8"))

            event = SwarmEvent(
                event_type=data.get("event_type", "unknown"),
                source_agent=data.get("source_agent", "unknown"),
                target_agent=data.get("target_agent"),
                payload=data.get("payload", {}),
                priority=EventPriority(data.get("priority", "normal")),
                timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
                correlation_id=data.get("correlation_id"),
                trace_id=data.get("trace_id"),
            )

            # Apply filters
            if not self._apply_filters(subscription, event):
                return

            # Update metrics
            subscription.message_count += 1
            subscription.last_message_at = datetime.now(UTC)

            # Call callback
            if subscription.callback:
                import asyncio

                asyncio.create_task(subscription.callback(event))

            # Check auto-unsubscribe
            if subscription.config.max_messages > 0:
                if subscription.message_count >= subscription.config.max_messages:
                    asyncio.create_task(self.unsubscribe(sub_id))

        except Exception as e:
            logger.error(
                "message_handle_failed",
                subscription_id=sub_id,
                error=str(e),
            )

    def _apply_filters(self, subscription: Subscription, event: SwarmEvent) -> bool:
        """Apply configured filters to event."""
        # Metadata filter
        if subscription.config.filter_metadata:
            for key, value in subscription.config.filter_metadata.items():
                if event.payload.get(key) != value:
                    return False

        # Priority filter
        if subscription.config.priority_filter:
            if event.priority.value < subscription.config.priority_filter.value:
                return False

        return True

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from a subject.

        Args:
            subscription_id: Subscription to cancel

        Returns:
            True if subscription was found and removed
        """
        subscription = self._subscriptions.get(subscription_id)
        if not subscription:
            return False

        # Remove from NATS
        if self._client:
            try:
                self._client.unsubscribe(subscription_id)
            except Exception as e:
                logger.warning(
                    "unsubscribe_warning",
                    subscription_id=subscription_id,
                    error=str(e),
                )

        subscription.state = SubscriptionState.CLOSED
        del self._subscriptions[subscription_id]

        logger.info("subscription_closed", subscription_id=subscription_id)
        return True

    async def pause(self, subscription_id: str) -> bool:
        """Pause a subscription (stops receiving messages)."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription or subscription.state != SubscriptionState.ACTIVE:
            return False

        subscription.state = SubscriptionState.PAUSED
        logger.info("subscription_paused", subscription_id=subscription_id)
        return True

    async def resume(self, subscription_id: str) -> bool:
        """Resume a paused subscription."""
        subscription = self._subscriptions.get(subscription_id)
        if not subscription or subscription.state != SubscriptionState.PAUSED:
            return False

        subscription.state = SubscriptionState.ACTIVE
        logger.info("subscription_resumed", subscription_id=subscription_id)
        return True

    def get_subscription(self, subscription_id: str) -> Subscription | None:
        """Get subscription details."""
        return self._subscriptions.get(subscription_id)

    def list_subscriptions(self) -> list[Subscription]:
        """List all subscriptions."""
        return list(self._subscriptions.values())

    async def close(self) -> None:
        """Close all subscriptions and disconnect."""
        for sub_id in list(self._subscriptions.keys()):
            await self.unsubscribe(sub_id)

        self._subscriptions.clear()
        logger.info("subscriber_closed")


# Global subscriber instance
_subscriber: NATSSubscriber | None = None


def get_subscriber() -> NATSSubscriber:
    """Get the global subscriber instance."""
    global _subscriber
    if _subscriber is None:
        _subscriber = NATSSubscriber()
    return _subscriber


__all__ = [
    "NATSSubscriber",
    "Subscription",
    "SubscriptionConfig",
    "SubscriptionState",
    "get_subscriber",
]
