"""
Global Workspace Theory (GWT) Broadcast for Heretek Swarm.

Implements consciousness-level information broadcast based on GWT theory:
- NATS pub/sub for consciousness-level broadcast
- Salience metrics-based content filtering
- Attention selection mechanism
- Integration with deliberation engine
- Rate limiting per agent
- Latency target: < 100ms

Reference: Global Workspace Theory (Baars, 1997) - Consciousness as a global broadcast.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable

    from heretek_swarm.infrastructure.nats.client import NATSClient

logger = structlog.get_logger(__name__)


class SalienceLevel(Enum):
    """Salience levels for content filtering."""

    CRITICAL = 1.0  # Must broadcast immediately
    HIGH = 0.8  # High priority
    ELEVATED = 0.6  # Above normal
    NORMAL = 0.4  # Default priority
    LOW = 0.2  # Below normal
    MINIMAL = 0.0  # Filter out


@dataclass
class GWTSalienceMetrics:
    """Salience metrics for content filtering."""

    novelty: float = 0.0  # 0-1: How novel is this information
    relevance: float = 0.0  # 0-1: Relevance to current goals
    urgency: float = 0.0  # 0-1: Time sensitivity
    impact: float = 0.0  # 0-1: Potential impact
    confidence: float = 0.0  # 0-1: Confidence in the information

    @property
    def overall_salience(self) -> float:
        """Calculate overall salience score."""
        weights = {
            "novelty": 0.2,
            "relevance": 0.3,
            "urgency": 0.2,
            "impact": 0.2,
            "confidence": 0.1,
        }
        return sum(getattr(self, key) * weight for key, weight in weights.items())

    @property
    def salience_level(self) -> SalienceLevel:
        """Get salience level classification."""
        score = self.overall_salience
        if score >= 0.9:
            return SalienceLevel.CRITICAL
        if score >= 0.7:
            return SalienceLevel.HIGH
        if score >= 0.5:
            return SalienceLevel.ELEVATED
        if score >= 0.3:
            return SalienceLevel.NORMAL
        if score >= 0.1:
            return SalienceLevel.LOW
        return SalienceLevel.MINIMAL


@dataclass
class GWTContent:
    """Content for GWT broadcast."""

    content_id: str
    source_agent: str
    content_type: str
    payload: dict[str, Any]
    salience_metrics: GWTSalienceMetrics
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    broadcast_id: str | None = None
    attention_winner: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": self.content_id,
            "source_agent": self.source_agent,
            "content_type": self.content_type,
            "payload": self.payload,
            "salience_metrics": {
                "novelty": self.salience_metrics.novelty,
                "relevance": self.salience_metrics.relevance,
                "urgency": self.salience_metrics.urgency,
                "impact": self.salience_metrics.impact,
                "confidence": self.salience_metrics.confidence,
                "overall_salience": self.salience_metrics.overall_salience,
                "salience_level": self.salience_metrics.salience_level.name.lower(),
            },
            "timestamp": self.timestamp,
            "broadcast_id": self.broadcast_id,
            "attention_winner": self.attention_winner,
        }


@dataclass
class DeliberationBroadcast:
    """Deliberation outcome for GWT broadcast."""

    deliberation_id: str
    proposal: str
    final_position: str
    consensus_score: float
    participation_rate: float
    rounds_completed: int
    minority_report: list[str]
    arguments_summary: dict[str, Any]
    broadcast_timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "deliberation_id": self.deliberation_id,
            "proposal": self.proposal,
            "final_position": self.final_position,
            "consensus_score": self.consensus_score,
            "participation_rate": self.participation_rate,
            "rounds_completed": self.rounds_completed,
            "minority_report": self.minority_report,
            "arguments_summary": self.arguments_summary,
            "broadcast_timestamp": self.broadcast_timestamp,
        }


@dataclass
class RateLimitConfig:
    """Rate limiting configuration per agent."""

    max_broadcasts_per_second: float = 10.0
    max_broadcasts_per_minute: int = 100
    burst_allowance: int = 5
    cooldown_period: float = 1.0


@dataclass
class AgentRateLimiter:
    """Rate limiter for a single agent."""

    agent_id: str
    config: RateLimitConfig
    _tokens: float = field(default=0.0)
    _last_update: float = field(default_factory=time.time)
    _minute_counter: int = 0
    _minute_reset_time: float = field(default_factory=time.time)
    _burst_used: int = 0

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(
            self.config.max_broadcasts_per_second,
            self._tokens + elapsed * self.config.max_broadcasts_per_second,
        )
        self._last_update = now

        # Reset minute counter if needed
        if now - self._minute_reset_time >= 60.0:
            self._minute_counter = 0
            self._minute_reset_time = now

    def _use_burst(self) -> bool:
        """Attempt to use burst allowance."""
        if self._burst_used < self.config.burst_allowance:
            self._burst_used += 1
            return True
        return False

    def can_broadcast(self) -> bool:
        """Check if agent can broadcast."""
        self._refill_tokens()
        if self._tokens >= 1.0:
            return True
        if self._minute_counter < self.config.max_broadcasts_per_minute:
            return self._use_burst()
        return False

    def record_broadcast(self) -> bool:
        """Record a broadcast and return success."""
        if not self.can_broadcast():
            return False
        if self._tokens >= 1.0:
            self._tokens -= 1.0
        else:
            self._minute_counter += 1
        return True


class GWTConfig:
    """Configuration for GWT broadcast."""

    def __init__(
        self,
        subject_prefix: str = "gwt",
        salience_threshold: float = 0.3,
        attention_threshold: float = 0.7,
        max_attention_items: int = 1,
        rate_limit_config: RateLimitConfig | None = None,
        broadcast_timeout_ms: float = 100.0,
        enable_rate_limiting: bool = True,
    ) -> None:
        self.subject_prefix = subject_prefix
        self.salience_threshold = salience_threshold
        self.attention_threshold = attention_threshold
        self.max_attention_items = max_attention_items
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.broadcast_timeout_ms = broadcast_timeout_ms
        self.enable_rate_limiting = enable_rate_limiting


class GlobalWorkspaceBroadcast:
    """
    Global Workspace Theory (GWT) Broadcast Implementation.

    Provides consciousness-level information broadcast across agents:
    - NATS pub/sub for consciousness-level broadcast
    - Salience metrics-based content filtering
    - Attention selection mechanism (winner-take-all)
    - Rate limiting per agent
    - Integration with deliberation engine

    Latency target: < 100ms end-to-end
    """

    def __init__(
        self,
        client: NATSClient | None = None,
        config: GWTConfig | None = None,
    ) -> None:
        self._client = client
        self._config = config or GWTConfig()
        self._subscriptions: dict[str, Any] = {}
        self._subscription_counter = 0
        self._rate_limiters: dict[str, AgentRateLimiter] = {}
        self._attention_competition: dict[str, list[GWTContent]] = defaultdict(list)
        self._broadcast_handlers: list[Callable[[GWTContent], Any]] = []
        self._deliberation_handlers: list[Callable[[DeliberationBroadcast], Any]] = []

    def _get_subject(self, suffix: str) -> str:
        """Get full NATS subject path."""
        return f"{self._config.subject_prefix}.{suffix}"

    def _get_rate_limiter(self, agent_id: str) -> AgentRateLimiter:
        """Get or create rate limiter for agent."""
        if agent_id not in self._rate_limiters:
            self._rate_limiters[agent_id] = AgentRateLimiter(
                agent_id=agent_id,
                config=self._config.rate_limit_config,
            )
        return self._rate_limiters[agent_id]

    def _filter_by_salience(self, content: GWTContent) -> bool:
        """Filter content based on salience threshold."""
        if not self._config.enable_rate_limiting:
            return True
        return content.salience_metrics.overall_salience >= self._config.salience_threshold

    def _select_attention_winners(self, contents: list[GWTContent]) -> list[GWTContent]:
        """Select attention winners through competition."""
        if not contents:
            return []

        # Sort by salience score
        sorted_contents = sorted(
            contents, key=lambda c: c.salience_metrics.overall_salience, reverse=True
        )

        # Select winners (typically 1, but can be more)
        winners = []
        for i, content in enumerate(sorted_contents):
            if i < self._config.max_attention_items:
                content.attention_winner = True
                winners.append(content)

        return winners

    def _generate_broadcast_id(self) -> str:
        """Generate unique broadcast ID."""
        return f"gwt-{uuid.uuid4().hex[:12]}"

    async def broadcast_content(
        self,
        content: GWTContent,
        client: NATSClient | None = None,
    ) -> bool:
        """
        Broadcast content to the global workspace.

        Args:
            content: Content to broadcast
            client: NATS client (uses internal if None)

        Returns:
            True if broadcast successful
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("gwt_broadcast_no_client")
            return False

        if not nats_client.is_connected:
            logger.warning("gwt_broadcast_not_connected")
            return False

        # Check rate limit
        if self._config.enable_rate_limiting:
            limiter = self._get_rate_limiter(content.source_agent)
            if not limiter.record_broadcast():
                logger.debug(
                    "gwt_rate_limited",
                    agent=content.source_agent,
                    content_id=content.content_id,
                )
                return False

        # Filter by salience
        if not self._filter_by_salience(content):
            logger.debug(
                "gwt_filtered_low_salience",
                content_id=content.content_id,
                salience=content.salience_metrics.overall_salience,
            )
            return False

        # Generate broadcast ID
        content.broadcast_id = self._generate_broadcast_id()

        # Start timing for latency tracking
        start_time = time.perf_counter()

        try:
            subject = self._get_subject("broadcast")
            message = json.dumps(content.to_dict())

            await asyncio.wait_for(
                nats_client.publish(subject, message.encode()),
                timeout=self._config.broadcast_timeout_ms / 1000.0,
            )

            # Track latency
            latency_ms = (time.perf_counter() - start_time) * 1000
            if latency_ms > self._config.broadcast_timeout_ms:
                logger.warning(
                    "gwt_latency_exceeded",
                    latency_ms=latency_ms,
                    target_ms=self._config.broadcast_timeout_ms,
                )

            logger.info(
                "gwt_broadcast_sent",
                content_id=content.content_id,
                source_agent=content.source_agent,
                content_type=content.content_type,
                salience=content.salience_metrics.overall_salience,
                latency_ms=latency_ms,
            )
            return True

        except TimeoutError:
            logger.error(
                "gwt_broadcast_timeout",
                content_id=content.content_id,
                timeout_ms=self._config.broadcast_timeout_ms,
            )
            return False
        except Exception as e:
            logger.error(
                "gwt_broadcast_failed",
                content_id=content.content_id,
                error=str(e),
            )
            return False

    async def broadcast_deliberation_outcome(
        self,
        deliberation: DeliberationBroadcast,
        client: NATSClient | None = None,
    ) -> bool:
        """
        Broadcast deliberation outcome to the global workspace.

        Args:
            deliberation: Deliberation result to broadcast
            client: NATS client (uses internal if None)

        Returns:
            True if broadcast successful
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("gwt_deliberation_no_client")
            return False

        if not nats_client.is_connected:
            logger.warning("gwt_deliberation_not_connected")
            return False

        start_time = time.perf_counter()

        try:
            subject = self._get_subject("deliberation.outcome")
            message = json.dumps(deliberation.to_dict())

            await asyncio.wait_for(
                nats_client.publish(subject, message.encode()),
                timeout=self._config.broadcast_timeout_ms / 1000.0,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "gwt_deliberation_broadcast",
                deliberation_id=deliberation.deliberation_id,
                proposal=deliberation.proposal[:50],
                consensus_score=deliberation.consensus_score,
                latency_ms=latency_ms,
            )
            return True

        except TimeoutError:
            logger.error(
                "gwt_deliberation_timeout",
                deliberation_id=deliberation.deliberation_id,
            )
            return False
        except Exception as e:
            logger.error(
                "gwt_deliberation_failed",
                deliberation_id=deliberation.deliberation_id,
                error=str(e),
            )
            return False

    async def subscribe_to_broadcasts(
        self,
        callback: Callable[[GWTContent], Any],
        content_types: list[str] | None = None,
        min_salience: float = 0.0,
        client: NATSClient | None = None,
        queue: str | None = None,
    ) -> str | None:
        """
        Subscribe to GWT broadcasts.

        Args:
            callback: Async function to call with each broadcast
            content_types: Optional filter by content types
            min_salience: Minimum salience level to receive
            client: NATS client (uses internal if None)
            queue: Optional queue group name

        Returns:
            Subscription ID if successful
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("gwt_subscribe_no_client")
            return None

        if not nats_client.is_connected:
            logger.warning("gwt_subscribe_not_connected")
            return None

        subscription_id = f"gwt_sub_{self._subscription_counter}"
        self._subscription_counter += 1

        async def handler(msg: Any) -> None:
            """Internal handler with filtering."""
            try:
                data = json.loads(msg.data.decode())
                content = self._deserialize_content(data)

                if content is None:
                    return

                # Filter by content type
                if content_types and content.content_type not in content_types:
                    return

                # Filter by salience
                if content.salience_metrics.overall_salience < min_salience:
                    return

                await callback(content)

            except Exception as e:
                logger.error("gwt_subscribe_callback_error", error=str(e))

        try:
            subject = self._get_subject("broadcast")
            if queue:
                await nats_client.subscribe(subject, queue=queue)(handler)
            else:
                await nats_client.subscribe(subject)(handler)

            self._subscriptions[subscription_id] = subject
            logger.info(
                "gwt_subscribed",
                subscription_id=subscription_id,
                subject=subject,
            )
            return subscription_id

        except Exception as e:
            logger.error("gwt_subscribe_failed", error=str(e))
            return None

    async def subscribe_to_deliberations(
        self,
        callback: Callable[[DeliberationBroadcast], Any],
        client: NATSClient | None = None,
        queue: str | None = None,
    ) -> str | None:
        """
        Subscribe to deliberation broadcasts.

        Args:
            callback: Async function to call with each deliberation
            client: NATS client (uses internal if None)
            queue: Optional queue group name

        Returns:
            Subscription ID if successful
        """
        nats_client = client or self._client
        if not nats_client:
            logger.error("gwt_deliberation_subscribe_no_client")
            return None

        if not nats_client.is_connected:
            logger.warning("gwt_deliberation_subscribe_not_connected")
            return None

        subscription_id = f"gwt_delib_sub_{self._subscription_counter}"
        self._subscription_counter += 1

        async def handler(msg: Any) -> None:
            """Internal handler."""
            try:
                data = json.loads(msg.data.decode())
                deliberation = self._deserialize_deliberation(data)
                if deliberation:
                    await callback(deliberation)
            except Exception as e:
                logger.error("gwt_deliberation_callback_error", error=str(e))

        try:
            subject = self._get_subject("deliberation.outcome")
            if queue:
                await nats_client.subscribe(subject, queue=queue)(handler)
            else:
                await nats_client.subscribe(subject)(handler)

            self._subscriptions[subscription_id] = subject
            logger.info(
                "gwt_deliberation_subscribed",
                subscription_id=subscription_id,
                subject=subject,
            )
            return subscription_id

        except Exception as e:
            logger.error("gwt_deliberation_subscribe_failed", error=str(e))
            return None

    def _deserialize_content(self, data: dict[str, Any]) -> GWTContent | None:
        """Deserialize GWT content from dict."""
        try:
            salience = GWTSalienceMetrics(
                novelty=data.get("salience_metrics", {}).get("novelty", 0.0),
                relevance=data.get("salience_metrics", {}).get("relevance", 0.0),
                urgency=data.get("salience_metrics", {}).get("urgency", 0.0),
                impact=data.get("salience_metrics", {}).get("impact", 0.0),
                confidence=data.get("salience_metrics", {}).get("confidence", 0.0),
            )
            return GWTContent(
                content_id=data.get("content_id", str(uuid.uuid4())),
                source_agent=data.get("source_agent", "unknown"),
                content_type=data.get("content_type", "unknown"),
                payload=data.get("payload", {}),
                salience_metrics=salience,
                timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
                broadcast_id=data.get("broadcast_id"),
                attention_winner=data.get("attention_winner", False),
            )
        except Exception as e:
            logger.warning("gwt_deserialize_content_failed", error=str(e))
            return None

    def _deserialize_deliberation(self, data: dict[str, Any]) -> DeliberationBroadcast | None:
        """Deserialize deliberation broadcast from dict."""
        try:
            return DeliberationBroadcast(
                deliberation_id=data.get("deliberation_id", ""),
                proposal=data.get("proposal", ""),
                final_position=data.get("final_position", ""),
                consensus_score=data.get("consensus_score", 0.0),
                participation_rate=data.get("participation_rate", 0.0),
                rounds_completed=data.get("rounds_completed", 0),
                minority_report=data.get("minority_report", []),
                arguments_summary=data.get("arguments_summary", {}),
                broadcast_timestamp=data.get("broadcast_timestamp", datetime.now(UTC).isoformat()),
            )
        except Exception as e:
            logger.warning("gwt_deserialize_deliberation_failed", error=str(e))
            return None

    async def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from broadcasts.

        Args:
            subscription_id: Subscription ID to cancel

        Returns:
            True if unsubscribed successfully
        """
        if subscription_id not in self._subscriptions:
            logger.warning("gwt_unsubscribe_unknown_id", subscription_id=subscription_id)
            return False

        try:
            subject = self._subscriptions.pop(subscription_id)
            if self._client:
                await self._client.unsubscribe(subject)
            logger.info("gwt_unsubscribed", subscription_id=subscription_id)
            return True
        except Exception as e:
            logger.error("gwt_unsubscribe_failed", error=str(e))
            return False

    def get_rate_limit_status(self, agent_id: str) -> dict[str, Any]:
        """Get rate limit status for an agent."""
        limiter = self._rate_limiters.get(agent_id)
        if not limiter:
            return {"can_broadcast": True, "reason": "no limiter created"}

        limiter._refill_tokens()
        return {
            "can_broadcast": limiter.can_broadcast(),
            "tokens": limiter._tokens,
            "minute_count": limiter._minute_counter,
            "burst_used": limiter._burst_used,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get GWT broadcast statistics."""
        return {
            "active_subscriptions": len(self._subscriptions),
            "tracked_agents": len(self._rate_limiters),
            "config": {
                "salience_threshold": self._config.salience_threshold,
                "attention_threshold": self._config.attention_threshold,
                "rate_limiting_enabled": self._config.enable_rate_limiting,
                "broadcast_timeout_ms": self._config.broadcast_timeout_ms,
            },
        }


def calculate_salience(
    novelty: float = 0.0,
    relevance: float = 0.0,
    urgency: float = 0.0,
    impact: float = 0.0,
    confidence: float = 0.0,
) -> GWTSalienceMetrics:
    """
    Calculate salience metrics for content.

    Args:
        novelty: How novel is this information (0-1)
        relevance: Relevance to current goals (0-1)
        urgency: Time sensitivity (0-1)
        impact: Potential impact (0-1)
        confidence: Confidence in the information (0-1)

    Returns:
        GWTSalienceMetrics with calculated scores
    """
    return GWTSalienceMetrics(
        novelty=max(0.0, min(1.0, novelty)),
        relevance=max(0.0, min(1.0, relevance)),
        urgency=max(0.0, min(1.0, urgency)),
        impact=max(0.0, min(1.0, impact)),
        confidence=max(0.0, min(1.0, confidence)),
    )


def create_gwt_content(
    source_agent: str,
    content_type: str,
    payload: dict[str, Any],
    novelty: float = 0.5,
    relevance: float = 0.5,
    urgency: float = 0.5,
    impact: float = 0.5,
    confidence: float = 0.5,
) -> GWTContent:
    """
    Create GWT content with salience metrics.

    Args:
        source_agent: Agent generating the content
        content_type: Type of content (e.g., "decision", "insight", "alert")
        payload: Content payload
        novelty: How novel is this information (0-1)
        relevance: Relevance to current goals (0-1)
        urgency: Time sensitivity (0-1)
        impact: Potential impact (0-1)
        confidence: Confidence in the information (0-1)

    Returns:
        GWTContent ready for broadcast
    """
    salience = calculate_salience(
        novelty=novelty,
        relevance=relevance,
        urgency=urgency,
        impact=impact,
        confidence=confidence,
    )
    return GWTContent(
        content_id=f"gwt-{uuid.uuid4().hex[:12]}",
        source_agent=source_agent,
        content_type=content_type,
        payload=payload,
        salience_metrics=salience,
    )


__all__ = [
    "AgentRateLimiter",
    "DeliberationBroadcast",
    "GWTConfig",
    "GWTContent",
    "GWTSalienceMetrics",
    "GlobalWorkspaceBroadcast",
    "RateLimitConfig",
    "SalienceLevel",
    "calculate_salience",
    "create_gwt_content",
]
