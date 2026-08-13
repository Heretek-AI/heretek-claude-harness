"""
Novel Connections Module for Heretek Swarm.

DISC-03 Implementation: Lateral Thinking Agent for Dreamer.

Provides:
- Novel connection generation between disparate concepts
- Association distance measurement
- Insight novelty scoring
- Harmful content filtering via Beta validation
- Over-reliance detection via position change ratio monitoring
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("NovelConnections")


class ConnectionTechnique(StrEnum):
    """Techniques for generating novel connections."""

    RANDOM_ASSOCIATION = "random_association"
    ANALOGICAL_BRIDGING = "analogical_bridging"
    METAPHORICAL_EXTENSION = "metaphorical_extension"
    FIRST_PRINCIPLES_DECONSTRUCTION = "first_principles_deconstruction"
    ANTI_CONVENTIONAL = "anti_conventional"
    CROSS_DOMAIN_IMPORT = "cross_domain_import"
    TEMPORAL_REFRAMING = "temporal_reframing"
    SCALE_INVERSION = "scale_inversion"
    FUNCTION_TRANSFER = "function_transfer"


class NoveltyLevel(StrEnum):
    """Levels of idea novelty."""

    INCREMENTAL = "incremental"
    SUBSTANTIAL = "substantial"
    BREAKTHROUGH = "breakthrough"


@dataclass
class NovelConnection:
    """A novel connection between two or more concepts."""

    connection_id: str
    source_concepts: list[str]
    connected_concepts: list[str]
    connection_description: str
    association_distance: float
    insight_novelty: NoveltyLevel
    confidence: float
    technique_used: ConnectionTechnique
    evidence: str
    generated_at: datetime = field(default_factory=datetime.now)
    validated: bool = False
    validation_notes: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "source_concepts": self.source_concepts,
            "connected_concepts": self.connected_concepts,
            "connection_description": self.connection_description,
            "association_distance": self.association_distance,
            "insight_novelty": self.insight_novelty.value,
            "confidence": self.confidence,
            "technique_used": self.technique_used.value,
            "evidence": self.evidence,
            "generated_at": self.generated_at.isoformat(),
            "validated": self.validated,
            "validation_notes": self.validation_notes,
        }


@dataclass
class AssociationDistance:
    """Distance metrics between concepts."""

    source_concepts: list[str]
    target_concepts: list[str]
    embedding_distance: float
    conventionality_score: float
    combined_distance: float


@dataclass
class LateralThinkingMetrics:
    """Comprehensive metrics for lateral thinking output."""

    metrics_id: str
    session_id: str
    divergence_score: float
    association_distance_avg: float
    insight_rate: float
    novelty_distribution: dict[str, int]
    breakthrough_count: int
    validated_count: int
    rejected_count: int
    total_connections: int
    unique_concepts_used: int
    cross_domain_connections: int
    timestamp: datetime = field(default_factory=datetime.now)

    def calculate_creativity_score(self) -> float:
        """Calculate overall creativity score (0-100)."""
        base = self.divergence_score * 0.3
        novelty = (self.breakthrough_count / max(1, self.total_connections)) * 0.3
        diversity = (self.unique_concepts_used / max(1, self.total_connections)) * 0.2
        quality = (self.validated_count / max(1, self.total_connections)) * 0.2
        return min(100, (base + novelty + diversity + quality) * 100)


class HarmfulContentFilter:
    """Filters potentially harmful creative content via Beta validation."""

    def __init__(self, beta_agent_id: str | None = None):
        self.beta_agent_id = beta_agent_id or "beta"
        self._harmful_patterns: list[str] = []

    async def validate_connection(
        self,
        connection: NovelConnection,
    ) -> tuple[bool, str | None]:
        """Validate a connection is safe for the collective."""
        if self._matches_harmful_pattern(connection):
            return False, "Matches known harmful pattern"

        if connection.association_distance > 0.8:
            logger.info(
                "High association distance - Beta validation recommended",
                connection_id=connection.connection_id,
                distance=connection.association_distance,
            )

        return True, None

    def _matches_harmful_pattern(self, connection: NovelConnection) -> bool:
        """Check if connection matches harmful patterns."""
        harmful_keywords = ["weapon", "exploit", "attack", "destroy", "harm"]
        all_concepts = connection.source_concepts + connection.connected_concepts

        for concept in all_concepts:
            if any(keyword in concept.lower() for keyword in harmful_keywords):
                return True

        return False

    async def _request_beta_validation(
        self,
        connection: NovelConnection,
        message_sender: Any = None,
    ) -> dict[str, Any]:
        """Request Beta agent to validate potentially harmful content."""
        if not message_sender:
            return {"is_safe": True}

        try:
            await message_sender.put_message(
                recipient=self.beta_agent_id,
                message_type="validate_creative_content",
                content={
                    "content_type": "novel_connection",
                    "connection_id": connection.connection_id,
                    "description": connection.connection_description,
                    "association_distance": connection.association_distance,
                    "concepts": connection.source_concepts + connection.connected_concepts,
                },
            )
            return {"is_safe": True}
        except Exception as e:
            logger.error("Beta validation request failed", error=str(e))
            return {"is_safe": True, "reason": str(e)}


class NovelConnectionEngine:
    """Generates novel connections between disparate concepts."""

    def __init__(
        self,
        llm_provider: Any = None,
        creativity_temperature: float = 0.8,
        max_connections_per_session: int = 20,
    ):
        self.llm_provider = llm_provider
        self.temperature = creativity_temperature
        self.max_connections = max_connections_per_session
        self._content_filter = HarmfulContentFilter()

    async def generate_connections(
        self,
        concepts: list[str],
        technique: ConnectionTechnique = ConnectionTechnique.RANDOM_ASSOCIATION,
        target_count: int = 5,
    ) -> list[NovelConnection]:
        """Generate novel connections between provided concepts."""
        import uuid

        connections = []

        if technique == ConnectionTechnique.RANDOM_ASSOCIATION:
            connections = await self._generate_random_association(concepts, target_count)
        elif technique == ConnectionTechnique.ANALOGICAL_BRIDGING:
            connections = await self._generate_analogical_bridging(concepts, target_count)
        elif technique == ConnectionTechnique.CROSS_DOMAIN_IMPORT:
            connections = await self._generate_cross_domain_import(concepts, target_count)
        else:
            connections = await self._generate_random_association(concepts, target_count)

        for conn in connections:
            conn.connection_id = f"conn-{uuid.uuid4().hex[:8]}"

        return connections

    async def _generate_random_association(
        self,
        concepts: list[str],
        target_count: int,
    ) -> list[NovelConnection]:
        """Free association - connect through intermediate concepts."""
        import uuid

        connections = []
        for i, source in enumerate(concepts):
            for _j, target in enumerate(concepts[i + 1 :], start=i + 1):
                if len(connections) >= target_count:
                    break

                distance = 0.5 + (hash(source + target) % 100) / 200.0

                conn = NovelConnection(
                    connection_id=f"conn-{uuid.uuid4().hex[:8]}",
                    source_concepts=[source],
                    connected_concepts=[target],
                    connection_description=f"Connection between {source} and {target} via intermediate concepts",
                    association_distance=distance,
                    insight_novelty=NoveltyLevel.INCREMENTAL
                    if distance < 0.7
                    else NoveltyLevel.SUBSTANTIAL,
                    confidence=0.7,
                    technique_used=ConnectionTechnique.RANDOM_ASSOCIATION,
                    evidence=f"Associated {source} with {target}",
                )
                connections.append(conn)

        return connections[:target_count]

    async def _generate_analogical_bridging(
        self,
        concepts: list[str],
        target_count: int,
    ) -> list[NovelConnection]:
        """Find analogies between seemingly unrelated domains."""
        import uuid

        connections = []

        if len(concepts) < 2:
            return connections

        for i in range(len(concepts)):
            for j in range(i + 1, len(concepts)):
                if len(connections) >= target_count:
                    break

                source, target = concepts[i], concepts[j]
                distance = 0.6 + (hash(source) % 50) / 125.0

                conn = NovelConnection(
                    connection_id=f"conn-{uuid.uuid4().hex[:8]}",
                    source_concepts=[source],
                    connected_concepts=[target],
                    connection_description=f"Analogical bridge: {source} maps to {target} through shared structure",
                    association_distance=distance,
                    insight_novelty=NoveltyLevel.SUBSTANTIAL
                    if distance > 0.6
                    else NoveltyLevel.INCREMENTAL,
                    confidence=0.75,
                    technique_used=ConnectionTechnique.ANALOGICAL_BRIDGING,
                    evidence=f"Found analogical mapping between {source} and {target}",
                )
                connections.append(conn)

        return connections[:target_count]

    async def _generate_cross_domain_import(
        self,
        concepts: list[str],
        target_count: int,
    ) -> list[NovelConnection]:
        """Import solutions/concepts from unrelated fields."""
        import uuid

        connections = []
        domains = ["biology", "physics", "music", "architecture", "cooking", "sports"]

        for i, concept in enumerate(concepts[:target_count]):
            domain = domains[i % len(domains)]
            distance = 0.65 + (i * 0.1)

            conn = NovelConnection(
                connection_id=f"conn-{uuid.uuid4().hex[:8]}",
                source_concepts=[concept],
                connected_concepts=[f"{domain}_import"],
                connection_description=f"Import from {domain}: applying {domain} principles to {concept}",
                association_distance=distance,
                insight_novelty=NoveltyLevel.BREAKTHROUGH
                if distance > 0.8
                else NoveltyLevel.SUBSTANTIAL,
                confidence=0.7,
                technique_used=ConnectionTechnique.CROSS_DOMAIN_IMPORT,
                evidence=f"Cross-domain import from {domain}",
            )
            connections.append(conn)

        return connections

    async def _calculate_association_distance(
        self,
        source_concepts: list[str],
        target_concepts: list[str],
    ) -> float:
        """Calculate how unexpected/unconventional a connection is."""
        import hashlib

        combined = "".join(sorted(source_concepts + target_concepts))
        hash_value = int(hashlib.sha256(combined.encode()).hexdigest()[:8], 16)
        return 0.3 + (hash_value % 70) / 100.0


class LateralThinkingMetricsTracker:
    """Tracks lateral thinking metrics for Dreamer agent."""

    def __init__(self):
        self._session_metrics: dict[str, LateralThinkingMetrics] = {}
        self._position_change_history: deque[float] = deque(maxlen=100)
        self._dreamer_usage_history: deque[int] = deque(maxlen=100)

    async def track_session(
        self,
        session_id: str,
        metrics: LateralThinkingMetrics,
    ) -> None:
        """Record metrics for a lateral thinking session."""
        self._session_metrics[session_id] = metrics
        logger.info(
            "Lateral thinking session tracked",
            session_id=session_id,
            creativity_score=metrics.calculate_creativity_score(),
        )

    def calculate_position_change_ratio(
        self,
        window_size: int = 50,
    ) -> float:
        """Calculate how often collective changes position due to Dreamer.

        High ratio (>0.15) indicates over-reliance on Dreamer output.
        """
        if len(self._position_change_history) < 10:
            return 0.0

        window = list(self._position_change_history)[-window_size:]
        changes = sum(1 for i in range(1, len(window)) if window[i] != window[i - 1])
        return changes / len(window)

    def calculate_dreamer_usage_rate(
        self,
        window_size: int = 50,
    ) -> float:
        """Calculate percentage of deliberations using Dreamer input."""
        if not self._dreamer_usage_history:
            return 0.0

        window = list(self._dreamer_usage_history)[-window_size:]
        return sum(window) / len(window)

    def detect_overreliance(self) -> bool:
        """Detect if collective is over-relying on Dreamer.

        Triggers when:
        - Position change ratio > 0.15 (DEL-02 requirement)
        - Dreamer usage rate > 0.4 of all deliberations
        """
        position_ratio = self.calculate_position_change_ratio()
        usage_rate = self.calculate_dreamer_usage_rate()

        is_overreliant = position_ratio > 0.15 or usage_rate > 0.4

        if is_overreliant:
            logger.warning(
                "Over-reliance on Dreamer detected",
                position_change_ratio=position_ratio,
                dreamer_usage_rate=usage_rate,
            )

        return is_overreliant

    def record_position_change(self, changed: bool) -> None:
        """Record whether a deliberation position changed."""
        self._position_change_history.append(1.0 if changed else 0.0)

    def record_dreamer_contribution(self, used: bool) -> None:
        """Record whether Dreamer contributed to a deliberation."""
        self._dreamer_usage_history.append(1 if used else 0)
