"""
Pattern Extraction Module - Cross-Agent Learning

Implements pattern extraction from agent message history for emergent intelligence.
This module analyzes agent interactions to identify successful patterns, track
decision outcomes, and extract learning signals for knowledge transfer.

Features:
- Pattern extraction from agent message history
- Successful interaction pattern identification
- Decision outcome tracking
- Learning signal extraction
- Pattern confidence scoring
- Temporal pattern analysis

Zero-Trust Principles:
- All patterns validated before storage
- Source attribution required
- Confidence thresholds enforced
- Audit logging for all extractions
"""

import asyncio
import hashlib
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class PatternType(StrEnum):
    """Types of patterns that can be extracted."""

    SUCCESS = "success"
    FAILURE = "failure"
    OPTIMIZATION = "optimization"
    HANDOFF = "handoff"
    COLLABORATION = "collaboration"
    DECISION = "decision"
    COMMUNICATION = "communication"
    RESOURCE_USAGE = "resource_usage"
    ERROR_RECOVERY = "error_recovery"
    EMERGENT = "emergent"


class PatternSource(StrEnum):
    """Source of pattern extraction."""

    MESSAGE_HISTORY = "message_history"
    DECISION_LOG = "decision_log"
    PERFORMANCE_METRICS = "performance_metrics"
    ERROR_LOG = "error_log"
    CONSENSUS_VOTES = "consensus_votes"
    TASK_OUTCOMES = "task_outcomes"
    AGENT_STATE = "agent_state"
    UNKNOWN = "unknown"


class PatternStatus(StrEnum):
    """Status of a learned pattern."""

    PROVISIONAL = "provisional"
    CONFIRMED = "confirmed"
    PROVEN = "proven"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


@dataclass
class TemporalPatternData:
    """Temporal features for pattern lifecycle tracking."""

    first_observed: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_observed: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    observation_count: int = 0
    avg_interval_seconds: float = 0.0
    total_duration_seconds: float = 0.0
    frequency_hz: float = 0.0
    is_recurring: bool = False
    seasonality_detected: bool = False

    def update_timing(self, timestamp: str) -> None:
        """Update temporal data with new observation."""
        now = datetime.fromisoformat(timestamp)
        last = datetime.fromisoformat(self.last_observed)

        self.observation_count += 1
        interval = (now - last).total_seconds()
        self.total_duration_seconds += interval
        self.avg_interval_seconds = self.total_duration_seconds / max(1, self.observation_count - 1)
        self.frequency_hz = (
            1.0 / self.avg_interval_seconds if self.avg_interval_seconds > 0 else 0.0
        )
        self.is_recurring = self.observation_count > 2
        self.last_observed = timestamp


@dataclass
class CrossAgentCorrelation:
    """Cross-agent pattern correlation data."""

    agent_pair: tuple[str, str]
    interaction_strength: float = 0.0
    message_count: int = 0
    success_rate: float = 0.0
    avg_latency_ms: float = 0.0
    coordinated_actions: int = 0


@dataclass
class PatternEvolution:
    """Pattern evolution tracking over time."""

    evolution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stability_score: float = 0.0
    adaptation_rate: float = 0.0
    convergence_trend: str = "stable"
    previous_confidence: float = 0.0
    confidence_delta: float = 0.0
    trend_direction: str = "unchanged"
    mutation_count: int = 0


@dataclass
class PatternMetadata:
    """Metadata for extracted patterns."""

    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern_type: PatternType = PatternType.SUCCESS
    source: PatternSource = PatternSource.MESSAGE_HISTORY
    confidence: float = 0.0
    support_count: int = 0
    first_observed: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    last_observed: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    agents_involved: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    version: int = 1
    temporal: TemporalPatternData = field(default_factory=TemporalPatternData)
    evolution: PatternEvolution = field(default_factory=PatternEvolution)

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern metadata to dictionary for serialization."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "source": self.source.value,
            "confidence": self.confidence,
            "support_count": self.support_count,
            "first_observed": self.first_observed,
            "last_observed": self.last_observed,
            "agents_involved": self.agents_involved,
            "topics": self.topics,
            "tags": self.tags,
            "version": self.version,
            "temporal": {
                "observation_count": self.temporal.observation_count,
                "avg_interval_seconds": self.temporal.avg_interval_seconds,
                "total_duration_seconds": self.temporal.total_duration_seconds,
                "frequency_hz": self.temporal.frequency_hz,
                "is_recurring": self.temporal.is_recurring,
            },
            "evolution": {
                "stability_score": self.evolution.stability_score,
                "adaptation_rate": self.evolution.adaptation_rate,
                "convergence_trend": self.evolution.convergence_trend,
                "confidence_delta": self.evolution.confidence_delta,
                "trend_direction": self.evolution.trend_direction,
            },
        }


@dataclass
class ExtractedPattern:
    """Represents an extracted pattern from agent interactions."""

    metadata: PatternMetadata
    pattern_data: dict[str, Any]
    context: dict[str, Any] = field(default_factory=dict)
    outcomes: list[dict[str, Any]] = field(default_factory=list)
    preconditions: list[str] = field(default_factory=list)
    postconditions: list[str] = field(default_factory=list)
    applicability_conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern to dictionary for serialization."""
        return {
            "pattern_id": self.metadata.pattern_id,
            "pattern_type": self.metadata.pattern_type.value,
            "source": self.metadata.source.value,
            "confidence": self.metadata.confidence,
            "support_count": self.metadata.support_count,
            "first_observed": self.metadata.first_observed,
            "last_observed": self.metadata.last_observed,
            "agents_involved": self.metadata.agents_involved,
            "topics": self.metadata.topics,
            "tags": self.metadata.tags,
            "pattern_data": self.pattern_data,
            "context": self.context,
            "outcomes": self.outcomes,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "applicability_conditions": self.applicability_conditions,
        }


@dataclass
class LearningSignal:
    """Represents a learning signal extracted from agent interactions."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    signal_type: str = "reward"
    magnitude: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source_agent: str | None = None
    target_agents: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert signal to dictionary for serialization."""
        return {
            "signal_id": self.signal_id,
            "signal_type": self.signal_type,
            "magnitude": self.magnitude,
            "timestamp": self.timestamp,
            "source_agent": self.source_agent,
            "target_agents": self.target_agents,
            "context": self.context,
            "metadata": self.metadata,
        }


@dataclass
class MessageAnalysis:
    """Analysis result for a single message."""

    message_id: str
    sender: str
    recipient: str
    message_type: str
    timestamp: str
    content_hash: str
    sentiment_score: float = 0.0
    complexity_score: float = 0.0
    topic: str | None = None
    intent: str | None = None
    outcome: str | None = None
    latency_ms: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PatternExtractor:
    """
    Extracts patterns from agent message history and interactions.

    This class implements pattern extraction algorithms for identifying
    recurring successful interactions, decision patterns, and emergent
    behaviors in the agent swarm.

    Attributes:
        min_support: Minimum number of occurrences for pattern to be valid
        min_confidence: Minimum confidence threshold for pattern acceptance
        max_pattern_age_days: Maximum age for patterns before expiration
    """

    def __init__(
        self,
        min_support: int = 3,
        min_confidence: float = 0.6,
        max_pattern_age_days: int = 30,
    ):
        """
        Initialize pattern extractor.

        Args:
            min_support: Minimum occurrences for pattern validity (default: 3)
            min_confidence: Minimum confidence threshold (default: 0.6)
            max_pattern_age_days: Maximum pattern age in days (default: 30)
        """
        self.min_support = min_support
        self.min_confidence = min_confidence
        self.max_pattern_age_days = max_pattern_age_days

        self._message_cache: list[MessageAnalysis] = []
        self._pattern_candidates: dict[str, ExtractedPattern] = {}
        self._validated_patterns: dict[str, ExtractedPattern] = {}
        self._learning_signals: list[LearningSignal] = []

        # Pattern extraction callbacks
        self._extraction_hooks: list[Callable] = []

        logger.info(
            "pattern_extractor_initialized",
            min_support=min_support,
            min_confidence=min_confidence,
            max_pattern_age_days=max_pattern_age_days,
        )

    def register_extraction_hook(self, hook: Callable) -> None:
        """
        Register a hook to be called after pattern extraction.

        Args:
            hook: Async callable that receives ExtractedPattern
        """
        self._extraction_hooks.append(hook)
        logger.debug("extraction_hook_registered", hook=hook.__name__)

    async def analyze_message(
        self,
        message_id: str,
        sender: str,
        recipient: str,
        message_type: str,
        content: dict[str, Any],
        timestamp: str | None = None,
    ) -> MessageAnalysis:
        """
        Analyze a single message for pattern extraction.

        Args:
            message_id: Unique message identifier
            sender: Sending agent ID
            recipient: Receiving agent ID or topic
            message_type: Type of message
            content: Message content dictionary
            timestamp: Message timestamp (auto-generated if None)

        Returns:
            MessageAnalysis with extracted features
        """
        ts = timestamp or datetime.now(UTC).isoformat()

        # Generate content hash for deduplication
        content_hash = self._generate_content_hash(content)

        # Analyze message characteristics
        sentiment = self._analyze_sentiment(content)
        complexity = self._analyze_complexity(content)
        topic = self._extract_topic(content)
        intent = self._infer_intent(message_type, content)

        analysis = MessageAnalysis(
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            timestamp=ts,
            content_hash=content_hash,
            sentiment_score=sentiment,
            complexity_score=complexity,
            topic=topic,
            intent=intent,
            metadata={
                "content_length": len(str(content)),
                "has_reply_to": "reply_to" in content,
                "has_correlation": "correlation_id" in content,
            },
        )

        # Cache for pattern analysis
        self._message_cache.append(analysis)

        # Trim cache if too large
        if len(self._message_cache) > 10000:
            self._message_cache = self._message_cache[-5000:]

        logger.debug(
            "message_analyzed",
            message_id=message_id,
            sender=sender,
            topic=topic,
            intent=intent,
        )

        return analysis

    async def extract_patterns(
        self,
        time_window_hours: int = 24,
        pattern_types: list[PatternType] | None = None,
    ) -> list[ExtractedPattern]:
        """
        Extract patterns from cached message history.

        Args:
            time_window_hours: Time window for pattern extraction (default: 24)
            pattern_types: Specific pattern types to extract (default: all)

        Returns:
            List of extracted patterns meeting confidence thresholds
        """
        if pattern_types is None:
            pattern_types = list(PatternType)

        # Filter messages within time window
        cutoff = datetime.now(UTC)
        from datetime import timedelta

        cutoff = cutoff - timedelta(hours=time_window_hours)

        recent_messages = [
            m for m in self._message_cache if datetime.fromisoformat(m.timestamp) >= cutoff
        ]

        logger.info(
            "extracting_patterns",
            message_count=len(recent_messages),
            time_window_hours=time_window_hours,
            pattern_types=[pt.value for pt in pattern_types],
        )

        extracted = []

        # Extract different pattern types
        for pattern_type in pattern_types:
            patterns = await self._extract_pattern_type(
                pattern_type,
                recent_messages,
            )
            extracted.extend(patterns)

        # Validate and store patterns
        validated = []
        for pattern in extracted:
            if await self._validate_pattern(pattern):
                self._validated_patterns[pattern.metadata.pattern_id] = pattern
                validated.append(pattern)

                # Call extraction hooks
                for hook in self._extraction_hooks:
                    try:
                        if asyncio.iscoroutinefunction(hook):
                            await hook(pattern)
                        else:
                            hook(pattern)
                    except Exception as e:
                        logger.error(
                            "extraction_hook_error",
                            hook=hook.__name__,
                            error=str(e),
                        )

        logger.info(
            "pattern_extraction_complete",
            total_extracted=len(extracted),
            total_validated=len(validated),
        )

        return validated

    async def track_outcome(
        self,
        pattern_id: str,
        outcome: str,
        outcome_data: dict[str, Any],
    ) -> None:
        """
        Track outcome for a specific pattern.

        Args:
            pattern_id: Pattern identifier
            outcome: Outcome type (success, failure, partial)
            outcome_data: Additional outcome data
        """
        if pattern_id in self._validated_patterns:
            pattern = self._validated_patterns[pattern_id]
            pattern.outcomes.append(
                {
                    "outcome": outcome,
                    "data": outcome_data,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            # Update confidence based on outcome
            self._update_pattern_confidence(pattern, outcome)

            logger.debug(
                "outcome_tracked",
                pattern_id=pattern_id,
                outcome=outcome,
                total_outcomes=len(pattern.outcomes),
            )

    def _generate_content_hash(self, content: dict[str, Any]) -> str:
        """Generate SHA256 hash of message content."""
        content_str = str(sorted(content.items()))
        return hashlib.sha256(content_str.encode()).hexdigest()[:16]

    def _analyze_sentiment(self, _content: dict[str, Any]) -> float:
        """
        Analyze sentiment of message content.

        Returns float between -1.0 (negative) and 1.0 (positive).
        Default implementation returns neutral 0.0.
        """
        # Placeholder for sentiment analysis
        # Could integrate with NLP library for actual analysis
        return 0.0

    def _analyze_complexity(self, content: dict[str, Any]) -> float:
        """
        Analyze complexity of message content.

        Returns float between 0.0 (simple) and 1.0 (complex).
        """
        # Measure complexity based on content structure
        content_str = str(content)
        length = len(content_str)
        nesting = content_str.count("{") + content_str.count("[")

        # Normalize complexity score
        length_score = min(length / 1000, 1.0)
        nesting_score = min(nesting / 10, 1.0)

        return (length_score + nesting_score) / 2

    def _extract_topic(self, content: dict[str, Any]) -> str | None:
        """Extract topic from message content."""
        # Look for topic indicators in content
        if "topic" in content:
            return content["topic"]
        if "subject" in content:
            return content["subject"]
        if "task_type" in content:
            return content["task_type"]
        return None

    def _infer_intent(self, message_type: str, _content: dict[str, Any]) -> str | None:
        """Infer intent from message type and content."""
        intent_map = {
            "request": "information_seeking",
            "response": "information_providing",
            "command": "action_request",
            "notification": "awareness",
            "handoff": "task_transfer",
            "collective_task": "collaboration_request",
            "collective_task_response": "collaboration_response",
            "health_check": "status_inquiry",
            "health_response": "status_report",
        }
        return intent_map.get(message_type, "unknown")

    async def _extract_pattern_type(
        self,
        pattern_type: PatternType,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns of a specific type."""
        extractors = {
            PatternType.SUCCESS: self._extract_success_patterns,
            PatternType.FAILURE: self._extract_failure_patterns,
            PatternType.OPTIMIZATION: self._extract_optimization_patterns,
            PatternType.HANDOFF: self._extract_handoff_patterns,
            PatternType.COLLABORATION: self._extract_collaboration_patterns,
            PatternType.DECISION: self._extract_decision_patterns,
            PatternType.COMMUNICATION: self._extract_communication_patterns,
            PatternType.ERROR_RECOVERY: self._extract_error_recovery_patterns,
            PatternType.EMERGENT: self._extract_emergent_patterns,
        }

        extractor = extractors.get(pattern_type)
        if extractor:
            return await extractor(messages)
        return []

    async def _extract_success_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from successful interactions."""
        patterns = []

        # Group by sender-recipient pairs
        interaction_groups: dict[tuple[str, str], list[MessageAnalysis]] = {}
        for msg in messages:
            key = (msg.sender, msg.recipient)
            if key not in interaction_groups:
                interaction_groups[key] = []
            interaction_groups[key].append(msg)

        # Find recurring successful interactions
        for (sender, recipient), group in interaction_groups.items():
            if len(group) >= self.min_support:
                # Calculate success rate based on outcomes
                successful = sum(1 for m in group if m.outcome == "success")
                success_rate = successful / len(group) if group else 0

                if success_rate >= self.min_confidence:
                    pattern = ExtractedPattern(
                        metadata=PatternMetadata(
                            pattern_type=PatternType.SUCCESS,
                            source=PatternSource.MESSAGE_HISTORY,
                            confidence=success_rate,
                            support_count=len(group),
                            agents_involved=[sender, recipient],
                            topics=list({m.topic for m in group if m.topic}),
                        ),
                        pattern_data={
                            "sender": sender,
                            "recipient": recipient,
                            "interaction_count": len(group),
                            "success_rate": success_rate,
                            "message_types": list({m.message_type for m in group}),
                        },
                        applicability_conditions=[
                            f"sender_type={sender.split('_')[0] if '_' in sender else sender}",
                            f"recipient_type={recipient.split('_')[0] if '_' in recipient else recipient}",
                        ],
                    )
                    patterns.append(pattern)

        return patterns

    async def _extract_optimization_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns for optimization opportunities."""
        patterns = []

        # Group by interaction type
        interaction_groups: dict[str, list[MessageAnalysis]] = {}
        for msg in messages:
            key = f"{msg.sender}->{msg.recipient}"
            if key not in interaction_groups:
                interaction_groups[key] = []
            interaction_groups[key].append(msg)

        # Find interactions with high latency or resource usage
        for interaction_type, group in interaction_groups.items():
            if len(group) >= self.min_support:
                # Calculate average latency
                latencies = [m.latency_ms for m in group if m.latency_ms is not None]
                if latencies:
                    avg_latency = sum(latencies) / len(latencies)
                    # Flag high-latency interactions
                    if avg_latency > 1000:  # 1 second threshold
                        pattern = ExtractedPattern(
                            metadata=PatternMetadata(
                                pattern_type=PatternType.OPTIMIZATION,
                                source=PatternSource.MESSAGE_HISTORY,
                                confidence=0.8,
                                description=f"High latency detected in {interaction_type} interactions",
                            ),
                            content=f"Average latency: {avg_latency:.2f}ms across {len(group)} interactions",
                            agents_involved=list(
                                set([m.sender for m in group] + [m.recipient for m in group])
                            ),
                            context={
                                "avg_latency_ms": avg_latency,
                                "interaction_count": len(group),
                            },
                        )
                        patterns.append(pattern)

        return patterns

    async def _extract_failure_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from failed interactions."""
        patterns = []

        # Group failures by type
        failure_groups: dict[str, list[MessageAnalysis]] = {}
        for msg in messages:
            if msg.outcome == "failure":
                key = msg.message_type
                if key not in failure_groups:
                    failure_groups[key] = []
                failure_groups[key].append(msg)

        # Find recurring failure patterns
        for failure_type, group in failure_groups.items():
            if len(group) >= self.min_support:
                pattern = ExtractedPattern(
                    metadata=PatternMetadata(
                        pattern_type=PatternType.FAILURE,
                        source=PatternSource.MESSAGE_HISTORY,
                        confidence=min(len(group) / 10, 1.0),
                        support_count=len(group),
                        agents_involved=list({m.sender for m in group}),
                        tags=["failure", failure_type],
                    ),
                    pattern_data={
                        "failure_type": failure_type,
                        "occurrence_count": len(group),
                        "affected_agents": list({m.sender for m in group}),
                        "common_characteristics": self._find_common_characteristics(group),
                    },
                    preconditions=self._extract_preconditions(group),
                )
                patterns.append(pattern)

        return patterns

    async def _extract_handoff_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from agent handoffs."""
        patterns = []

        # Find handoff message sequences
        handoffs = [m for m in messages if m.message_type == "handoff"]

        # Group by source-target agent pairs
        handoff_pairs: dict[tuple[str, str], list[MessageAnalysis]] = {}
        for handoff in handoffs:
            key = (handoff.sender, handoff.recipient)
            if key not in handoff_pairs:
                handoff_pairs[key] = []
            handoff_pairs[key].append(handoff)

        # Create patterns for frequent handoffs
        for (source, target), group in handoff_pairs.items():
            if len(group) >= self.min_support:
                pattern = ExtractedPattern(
                    metadata=PatternMetadata(
                        pattern_type=PatternType.HANDOFF,
                        source=PatternSource.MESSAGE_HISTORY,
                        confidence=min(len(group) / 5, 1.0),
                        support_count=len(group),
                        agents_involved=[source, target],
                        topics=list({m.topic for m in group if m.topic}),
                    ),
                    pattern_data={
                        "source_agent": source,
                        "target_agent": target,
                        "handoff_count": len(group),
                        "avg_handoff_time": self._calculate_avg_handoff_time(group),
                    },
                    applicability_conditions=[
                        "task_requires_specialization",
                        "source_agent_lacks_capability",
                    ],
                )
                patterns.append(pattern)

        return patterns

    async def _extract_collaboration_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from collaborative interactions."""
        patterns = []

        # Find collective task messages
        collaborative = [
            m for m in messages if m.message_type in ["collective_task", "collective_task_response"]
        ]

        if len(collaborative) >= self.min_support:
            # Analyze collaboration structures
            participants = set()
            for msg in collaborative:
                participants.add(msg.sender)
                if msg.recipient != "broadcast":
                    participants.add(msg.recipient)

            pattern = ExtractedPattern(
                metadata=PatternMetadata(
                    pattern_type=PatternType.COLLABORATION,
                    source=PatternSource.MESSAGE_HISTORY,
                    confidence=min(len(collaborative) / 10, 1.0),
                    support_count=len(collaborative),
                    agents_involved=list(participants),
                    topics=list({m.topic for m in collaborative if m.topic}),
                ),
                pattern_data={
                    "participant_count": len(participants),
                    "collaboration_count": len(collaborative),
                    "collaboration_types": list({m.message_type for m in collaborative}),
                },
                applicability_conditions=[
                    "complex_task_requires_multiple_agents",
                    "consensus_needed",
                ],
            )
            patterns.append(pattern)

        return patterns

    async def _extract_decision_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from decision-making processes."""
        patterns = []

        # Find decision-related messages
        decisions = [
            m for m in messages if "decision" in m.intent or "consensus" in (m.topic or "")
        ]

        if len(decisions) >= self.min_support:
            pattern = ExtractedPattern(
                metadata=PatternMetadata(
                    pattern_type=PatternType.DECISION,
                    source=PatternSource.MESSAGE_HISTORY,
                    confidence=min(len(decisions) / 5, 1.0),
                    support_count=len(decisions),
                    agents_involved=list({m.sender for m in decisions}),
                ),
                pattern_data={
                    "decision_count": len(decisions),
                    "decision_makers": list({m.sender for m in decisions}),
                    "avg_decision_time": self._calculate_avg_decision_time(decisions),
                },
            )
            patterns.append(pattern)

        return patterns

    async def _extract_communication_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from communication flows."""
        patterns = []

        # Analyze communication frequency and patterns
        comm_matrix: dict[str, dict[str, int]] = {}
        for msg in messages:
            if msg.sender not in comm_matrix:
                comm_matrix[msg.sender] = {}
            if msg.recipient not in comm_matrix[msg.sender]:
                comm_matrix[msg.sender][msg.recipient] = 0
            comm_matrix[msg.sender][msg.recipient] += 1

        # Find high-frequency communication pairs
        for sender, recipients in comm_matrix.items():
            for recipient, count in recipients.items():
                if count >= self.min_support:
                    pattern = ExtractedPattern(
                        metadata=PatternMetadata(
                            pattern_type=PatternType.COMMUNICATION,
                            source=PatternSource.MESSAGE_HISTORY,
                            confidence=min(count / 10, 1.0),
                            support_count=count,
                            agents_involved=[sender, recipient],
                        ),
                        pattern_data={
                            "sender": sender,
                            "recipient": recipient,
                            "message_count": count,
                            "communication_frequency": count / len(messages) if messages else 0,
                        },
                    )
                    patterns.append(pattern)

        return patterns

    async def _extract_error_recovery_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract patterns from error recovery scenarios."""
        patterns = []

        # Find error and recovery sequences
        errors = [m for m in messages if m.outcome == "error"]

        if len(errors) >= self.min_support:
            pattern = ExtractedPattern(
                metadata=PatternMetadata(
                    pattern_type=PatternType.ERROR_RECOVERY,
                    source=PatternSource.MESSAGE_HISTORY,
                    confidence=min(len(errors) / 10, 1.0),
                    support_count=len(errors),
                    agents_involved=list({m.sender for m in errors}),
                    tags=["error", "recovery"],
                ),
                pattern_data={
                    "error_count": len(errors),
                    "error_types": list({m.message_type for m in errors}),
                    "affected_agents": list({m.sender for m in errors}),
                },
                preconditions=self._extract_preconditions(errors),
            )
            patterns.append(pattern)

        return patterns

    async def _extract_emergent_patterns(
        self,
        messages: list[MessageAnalysis],
    ) -> list[ExtractedPattern]:
        """Extract emergent behavior patterns."""
        patterns = []

        # Look for patterns that span multiple agents
        multi_agent_sequences = self._find_multi_agent_sequences(messages)

        for sequence in multi_agent_sequences:
            if len(sequence["agents"]) >= 3:  # At least 3 agents involved
                pattern = ExtractedPattern(
                    metadata=PatternMetadata(
                        pattern_type=PatternType.EMERGENT,
                        source=PatternSource.MESSAGE_HISTORY,
                        confidence=min(len(sequence["occurrences"]) / 3, 1.0),
                        support_count=len(sequence["occurrences"]),
                        agents_involved=sequence["agents"],
                        tags=["emergent", "multi-agent"],
                    ),
                    pattern_data={
                        "agent_sequence": sequence["agents"],
                        "occurrence_count": len(sequence["occurrences"]),
                        "avg_sequence_length": sequence.get("avg_length", 0),
                    },
                    applicability_conditions=[
                        "complex_task_requires_coordination",
                        "multiple_specialists_needed",
                    ],
                )
                patterns.append(pattern)

        return patterns

    def _find_multi_agent_sequences(
        self,
        messages: list[MessageAnalysis],
    ) -> list[dict[str, Any]]:
        """Find message sequences involving multiple agents."""
        sequences = []

        # Sort messages by timestamp
        sorted_messages = sorted(messages, key=lambda m: m.timestamp)

        # Find sequences where messages chain through multiple agents
        current_sequence = []
        current_agents = set()

        for msg in sorted_messages:
            if not current_sequence:
                current_sequence = [msg]
                current_agents = {msg.sender, msg.recipient}
            elif msg.sender in current_agents:
                current_sequence.append(msg)
                current_agents.add(msg.recipient)
            else:
                # Sequence ended
                if len(current_agents) >= 3:
                    sequences.append(
                        {
                            "agents": list(current_agents),
                            "occurrences": [current_sequence.copy()],
                            "avg_length": len(current_sequence),
                        }
                    )
                current_sequence = [msg]
                current_agents = {msg.sender, msg.recipient}

        return sequences

    def _extract_preconditions(self, messages: list[MessageAnalysis]) -> list[str]:
        """Extract common preconditions from a group of messages."""
        preconditions = []

        # Find common characteristics
        if messages:
            # Check for common message types
            type_counts: dict[str, int] = {}
            for msg in messages:
                type_counts[msg.message_type] = type_counts.get(msg.message_type, 0) + 1

            dominant_type = max(type_counts, key=type_counts.get)
            if type_counts[dominant_type] > len(messages) * 0.5:
                preconditions.append(f"message_type={dominant_type}")

            # Check for common topics
            topics = [m.topic for m in messages if m.topic]
            if topics:
                topic_counts: dict[str, int] = {}
                for topic in topics:
                    topic_counts[topic] = topic_counts.get(topic, 0) + 1

                dominant_topic = max(topic_counts, key=topic_counts.get)
                if topic_counts[dominant_topic] > len(topics) * 0.3:
                    preconditions.append(f"topic={dominant_topic}")

        return preconditions

    def _find_common_characteristics(self, messages: list[MessageAnalysis]) -> list[str]:
        """Find common characteristics in a group of messages."""
        characteristics = []

        if messages:
            # Analyze complexity distribution
            avg_complexity = sum(m.complexity_score for m in messages) / len(messages)
            if avg_complexity > 0.7:
                characteristics.append("high_complexity")
            elif avg_complexity < 0.3:
                characteristics.append("low_complexity")

            # Analyze sentiment distribution
            avg_sentiment = sum(m.sentiment_score for m in messages) / len(messages)
            if avg_sentiment < -0.3:
                characteristics.append("negative_sentiment")

        return characteristics

    def _calculate_avg_handoff_time(self, handoffs: list[MessageAnalysis]) -> float:
        """Calculate average time between handoffs."""
        if len(handoffs) < 2:
            return 0.0

        sorted_handoffs = sorted(handoffs, key=lambda m: m.timestamp)
        deltas = []

        for i in range(1, len(sorted_handoffs)):
            t1 = datetime.fromisoformat(sorted_handoffs[i - 1].timestamp)
            t2 = datetime.fromisoformat(sorted_handoffs[i].timestamp)
            deltas.append((t2 - t1).total_seconds())

        return sum(deltas) / len(deltas) if deltas else 0.0

    def _calculate_avg_decision_time(self, _decisions: list[MessageAnalysis]) -> float:
        """Calculate average decision time."""
        # Placeholder - would need correlation with decision outcomes
        return 0.0

    async def _validate_pattern(self, pattern: ExtractedPattern) -> bool:
        """
        Validate a pattern before storing.

        Zero-trust validation:
        - Pattern ID must be valid UUID
        - Confidence must be in valid range
        - Support count must meet minimum
        - Pattern data must be non-empty
        """
        try:
            # Validate UUID
            uuid.UUID(pattern.metadata.pattern_id)

            # Validate confidence range
            if not 0.0 <= pattern.metadata.confidence <= 1.0:
                logger.warning(
                    "pattern_validation_failed",
                    reason="invalid_confidence",
                    confidence=pattern.metadata.confidence,
                )
                return False

            # Validate support count
            if pattern.metadata.support_count < self.min_support:
                logger.warning(
                    "pattern_validation_failed",
                    reason="insufficient_support",
                    support_count=pattern.metadata.support_count,
                )
                return False

            # Validate pattern data non-empty
            if not pattern.pattern_data:
                logger.warning(
                    "pattern_validation_failed",
                    reason="empty_pattern_data",
                )
                return False

            logger.debug(
                "pattern_validated",
                pattern_id=pattern.metadata.pattern_id,
                pattern_type=pattern.metadata.pattern_type.value,
                confidence=pattern.metadata.confidence,
            )

            return True

        except (ValueError, TypeError) as e:
            logger.warning(
                "pattern_validation_error",
                error=str(e),
                pattern_id=pattern.metadata.pattern_id,
            )
            return False

    def _update_pattern_confidence(
        self,
        pattern: ExtractedPattern,
        outcome: str,
    ) -> None:
        """Update pattern confidence based on outcome."""
        # Simple exponential moving average
        alpha = 0.1  # Learning rate

        if outcome == "success":
            new_confidence = (1 - alpha) * pattern.metadata.confidence + alpha * 1.0
        elif outcome == "failure":
            new_confidence = (1 - alpha) * pattern.metadata.confidence + alpha * 0.0
        else:
            new_confidence = pattern.metadata.confidence

        pattern.metadata.confidence = max(0.0, min(1.0, new_confidence))
        pattern.metadata.last_observed = datetime.now(UTC).isoformat()

    def get_validated_patterns(
        self,
        pattern_type: PatternType | None = None,
        min_confidence: float = 0.0,
    ) -> list[ExtractedPattern]:
        """
        Get validated patterns with optional filtering.

        Args:
            pattern_type: Filter by pattern type (default: all)
            min_confidence: Minimum confidence threshold (default: 0.0)

        Returns:
            List of matching patterns
        """
        patterns = list(self._validated_patterns.values())

        if pattern_type:
            patterns = [p for p in patterns if p.metadata.pattern_type == pattern_type]

        patterns = [p for p in patterns if p.metadata.confidence >= min_confidence]

        return sorted(
            patterns,
            key=lambda p: p.metadata.confidence,
            reverse=True,
        )

    def generate_learning_signal(
        self,
        pattern: ExtractedPattern,
        outcome: str,
    ) -> LearningSignal:
        """
        Generate a learning signal from a pattern outcome.

        Args:
            pattern: Source pattern
            outcome: Pattern outcome (success, failure, partial)

        Returns:
            LearningSignal for distribution
        """
        magnitude = pattern.metadata.confidence

        if outcome == "failure":
            magnitude = -magnitude
        elif outcome == "partial":
            magnitude = magnitude * 0.5

        signal = LearningSignal(
            signal_type="pattern_outcome",
            magnitude=magnitude,
            source_agent=pattern.metadata.agents_involved[0]
            if pattern.metadata.agents_involved
            else None,
            target_agents=pattern.metadata.agents_involved,
            context={
                "pattern_id": pattern.metadata.pattern_id,
                "pattern_type": pattern.metadata.pattern_type.value,
                "outcome": outcome,
            },
        )

        self._learning_signals.append(signal)

        # Trim signal history
        if len(self._learning_signals) > 10000:
            self._learning_signals = self._learning_signals[-5000:]

        return signal


class CollectiveLearning:
    """
    Orchestrates collective learning across the agent swarm.

    This class coordinates pattern extraction, knowledge transformation,
    and distributed learning for emergent intelligence.

    Attributes:
        extractor: PatternExtractor instance
        patterns: Dictionary of extracted patterns
        learning_signals: List of generated learning signals
    """

    def __init__(
        self,
        min_support: int = 3,
        min_confidence: float = 0.6,
    ):
        """
        Initialize collective learning system.

        Args:
            min_support: Minimum pattern support (default: 3)
            min_confidence: Minimum pattern confidence (default: 0.6)
        """
        self.extractor = PatternExtractor(
            min_support=min_support,
            min_confidence=min_confidence,
        )
        self._patterns: dict[str, ExtractedPattern] = {}
        self._learning_signals: list[LearningSignal] = []

        logger.info(
            "collective_learning_initialized",
            min_support=min_support,
            min_confidence=min_confidence,
        )

    async def process_message(
        self,
        message_id: str,
        sender: str,
        recipient: str,
        message_type: str,
        content: dict[str, Any],
        timestamp: str | None = None,
    ) -> MessageAnalysis:
        """
        Process a message for pattern extraction.

        Args:
            message_id: Unique message identifier
            sender: Sending agent ID
            recipient: Receiving agent ID or topic
            message_type: Type of message
            content: Message content
            timestamp: Message timestamp

        Returns:
            MessageAnalysis result
        """
        return await self.extractor.analyze_message(
            message_id=message_id,
            sender=sender,
            recipient=recipient,
            message_type=message_type,
            content=content,
            timestamp=timestamp,
        )

    async def extract_and_validate(
        self,
        time_window_hours: int = 24,
    ) -> list[ExtractedPattern]:
        """
        Extract and validate patterns from message history.

        Args:
            time_window_hours: Time window for extraction (default: 24)

        Returns:
            List of validated patterns
        """
        patterns = await self.extractor.extract_patterns(
            time_window_hours=time_window_hours,
        )

        for pattern in patterns:
            self._patterns[pattern.metadata.pattern_id] = pattern

        return patterns

    def get_patterns(
        self,
        pattern_type: PatternType | None = None,
        min_confidence: float = 0.0,
    ) -> list[ExtractedPattern]:
        """
        Get stored patterns with optional filtering.

        Args:
            pattern_type: Filter by pattern type
            min_confidence: Minimum confidence threshold

        Returns:
            List of matching patterns
        """
        return self.extractor.get_validated_patterns(
            pattern_type=pattern_type,
            min_confidence=min_confidence,
        )

    async def record_outcome(
        self,
        pattern_id: str,
        outcome: str,
        outcome_data: dict[str, Any],
    ) -> LearningSignal | None:
        """
        Record outcome for a pattern and generate learning signal.

        Args:
            pattern_id: Pattern identifier
            outcome: Outcome type (success, failure, partial)
            outcome_data: Additional outcome data

        Returns:
            Generated learning signal or None if pattern not found
        """
        if pattern_id in self._patterns:
            pattern = self._patterns[pattern_id]
            await self.extractor.track_outcome(pattern_id, outcome, outcome_data)
            signal = self.extractor.generate_learning_signal(pattern, outcome)
            self._learning_signals.append(signal)
            return signal
        return None

    def get_learning_status(self) -> dict[str, Any]:
        """
        Get current learning system status.

        Returns:
            Status dictionary with metrics
        """
        patterns = list(self._patterns.values())

        return {
            "total_patterns": len(patterns),
            "patterns_by_type": {
                pt.value: len([p for p in patterns if p.metadata.pattern_type == pt])
                for pt in PatternType
            },
            "avg_confidence": (
                sum(p.metadata.confidence for p in patterns) / len(patterns) if patterns else 0.0
            ),
            "total_learning_signals": len(self._learning_signals),
            "message_cache_size": len(self.extractor._message_cache),
            "extraction_hooks": len(self.extractor._extraction_hooks),
        }
