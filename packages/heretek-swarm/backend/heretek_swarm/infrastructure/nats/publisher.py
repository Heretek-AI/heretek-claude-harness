"""
NATS Publisher for Heretek Swarm.

Provides structured event publishing to NATS topics.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from heretek_swarm.infrastructure.nats.client import NATSClient, get_nats_client

logger = structlog.get_logger("nats.publisher")


class EventPriority(Enum):
    """Event priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SwarmEvent:
    """Standardized event format for swarm communication."""

    event_type: str
    source_agent: str
    target_agent: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    correlation_id: str | None = None
    trace_id: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "event_type": self.event_type,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "payload": self.payload,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


@dataclass
class NATSPublisher:
    """
    Structured event publisher for NATS.

    Publishes events to standardized swarm topics:
    - agents.{agent_id}.messages
    - agents.{agent_id}.events
    - consensus.{topic}
    - consciousness.metrics
    - swarm.events
    """

    client: NATSClient = field(default=None)
    _default_source: str = "heretek-swarm"

    async def initialize(self, source: str = "heretek-swarm") -> None:
        """Initialize publisher with NATS client."""
        self._default_source = source
        self.client = await get_nats_client()
        if not self.client.is_connected:
            await self.client.connect()

    def _get_topic(self, target: str | None, event_type: str) -> str:
        """Determine NATS topic from event type."""
        if target:
            if event_type == "message":
                return f"agents.{target}.messages"
            return f"agents.{target}.events"

        if event_type.startswith("consensus"):
            return f"consensus.{event_type.split('.', 1)[1]}"

        if event_type.startswith("consciousness"):
            return f"consciousness.{event_type.split('.', 1)[1]}"

        return f"swarm.{event_type}"

    async def publish_event(self, event: SwarmEvent) -> bool:
        """
        Publish a swarm event.

        Args:
            event: The event to publish

        Returns:
            True if published successfully
        """
        if not self.client:
            logger.warning("publisher_not_initialized")
            return False

        topic = self._get_topic(event.target_agent, event.event_type)
        return await self.client.publish(topic, event.to_json())

    async def send_message(
        self,
        source: str,
        target: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send message from one agent to another."""
        event = SwarmEvent(
            event_type="message",
            source_agent=source,
            target_agent=target,
            payload={
                "content": content,
                "metadata": metadata or {},
            },
        )
        return await self.publish_event(event)

    async def emit_agent_event(
        self,
        agent_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> bool:
        """Emit event from an agent."""
        event = SwarmEvent(
            event_type=event_type,
            source_agent=agent_id,
            payload=data,
        )
        return await self.publish_event(event)

    async def emit_consensus_event(
        self,
        topic: str,
        data: dict[str, Any],
    ) -> bool:
        """Emit consensus-related event."""
        event = SwarmEvent(
            event_type=f"consensus.{topic}",
            source_agent=self._default_source,
            payload=data,
        )
        return await self.publish_event(event)

    async def emit_consciousness_metric(
        self,
        metric_type: str,
        value: float,
        agent_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Emit consciousness metric."""
        event = SwarmEvent(
            event_type=f"consciousness.{metric_type}",
            source_agent=agent_id or self._default_source,
            payload={
                "value": value,
                "metadata": metadata or {},
            },
        )
        return await self.publish_event(event)


# Global publisher instance
_publisher: NATSPublisher | None = None


async def get_nats_publisher() -> NATSPublisher:
    """Get or create global NATS publisher."""
    global _publisher
    if _publisher is None:
        _publisher = NATSPublisher()
        await _publisher.initialize()
    return _publisher


__all__ = [
    "EventPriority",
    "NATSPublisher",
    "SwarmEvent",
    "get_nats_publisher",
]
