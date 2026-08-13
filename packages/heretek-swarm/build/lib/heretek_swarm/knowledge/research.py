"""
Research Module for Heretek Swarm.

Provides structured research capabilities for the Explorer agent:
- Topic research and investigation
- Finding correlation detection
- Research depth management
- Contradictory findings detection
- Source credibility scoring

This module enables Explorer to perform deep research on topics,
detect patterns across sources, and identify contradictions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("ResearchModule")


class ResearchDepth(StrEnum):
    """Research depth levels."""

    SURFACE = "surface"  # Quick scan, basic info
    STANDARD = "standard"  # Normal research, multiple sources
    DEEP = "deep"  # Comprehensive, all available sources
    EXHAUSTIVE = "exhaustive"  # Maximum depth, all angles


class FindingType(StrEnum):
    """Types of research findings."""

    FACT = "fact"
    OPINION = "opinion"
    TREND = "trend"
    CORRELATION = "correlation"
    ANOMALY = "anomaly"
    CONTRADICTION = "contradiction"


class SourceCredibility(StrEnum):
    """Source credibility levels."""

    UNVERIFIED = "unverified"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


@dataclass
class ResearchSource:
    """A source for research findings."""

    source_id: str
    source_type: str  # api, web, document, database, etc.
    url: str | None = None
    name: str | None = None
    credibility: SourceCredibility = SourceCredibility.UNVERIFIED
    last_accessed: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchFinding:
    """A single finding from research."""

    finding_id: str
    topic: str
    finding_type: FindingType
    content: str
    source: ResearchSource
    confidence: float  # 0-1
    supporting_evidence: list[str] = field(default_factory=list)
    contradicting_findings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "finding_id": self.finding_id,
            "topic": self.topic,
            "finding_type": self.finding_type.value,
            "content": self.content,
            "source": {
                "source_id": self.source.source_id,
                "source_type": self.source.source_type,
                "name": self.source.name,
                "credibility": self.source.credibility.value,
            },
            "confidence": self.confidence,
            "supporting_evidence": self.supporting_evidence,
            "contradicting_findings": self.contradicting_findings,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ResearchResult:
    """Result of a research operation."""

    topic: str
    depth: ResearchDepth
    findings: list[ResearchFinding]
    summary: str
    contradictions_detected: list[ResearchFinding] = field(default_factory=list)
    correlated_findings: list[list[ResearchFinding]] = field(default_factory=list)
    sources_consulted: list[ResearchSource] = field(default_factory=list)
    research_duration_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    confidence_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "topic": self.topic,
            "depth": self.depth.value,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
            "contradictions_detected": [f.to_dict() for f in self.contradictions_detected],
            "correlated_findings": [
                [f.to_dict() for f in correlation] for correlation in self.correlated_findings
            ],
            "sources_consulted": [
                {
                    "source_id": s.source_id,
                    "source_type": s.source_type,
                    "name": s.name,
                    "credibility": s.credibility.value,
                }
                for s in self.sources_consulted
            ],
            "research_duration_ms": self.research_duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
        }


@dataclass
class ResearchQuery:
    """A research query specification."""

    query_id: str
    topic: str
    depth: ResearchDepth = ResearchDepth.STANDARD
    max_sources: int = 10
    time_range_hours: int | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    validate_contradictions: bool = True
    detect_correlations: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


class ResearchModule:
    """
    Research module for structured topic investigation.

    Provides:
    - Topic research with configurable depth
    - Finding correlation detection
    - Contradictory findings identification
    - Source credibility tracking
    - Research pattern analysis

    Usage:
        research = ResearchModule()
        result = await research.investigate(
            query=ResearchQuery(
                query_id="q1",
                topic="new AI framework",
                depth=ResearchDepth.DEEP,
            )
        )
    """

    def __init__(
        self,
        max_findings_per_topic: int = 100,
        contradiction_threshold: float = 0.7,
        correlation_threshold: float = 0.6,
    ) -> None:
        """
        Initialize the research module.

        Args:
            max_findings_per_topic: Maximum findings to store per topic
            contradiction_threshold: Confidence threshold for contradiction detection
            correlation_threshold: Similarity threshold for correlation detection
        """
        self.max_findings_per_topic = max_findings_per_topic
        self.contradiction_threshold = contradiction_threshold
        self.correlation_threshold = correlation_threshold

        # Research storage
        self._findings: dict[str, list[ResearchFinding]] = {}
        self._research_history: list[ResearchResult] = []
        self._source_credibility: dict[str, SourceCredibility] = {}

        logger.info(
            "ResearchModule initialized",
            extra={
                "max_findings": max_findings_per_topic,
                "contradiction_threshold": contradiction_threshold,
                "correlation_threshold": correlation_threshold,
            },
        )

    async def investigate(self, query: ResearchQuery) -> ResearchResult:
        """
        Investigate a research topic.

        Args:
            query: Research query specification

        Returns:
            ResearchResult with findings, contradictions, and correlations
        """
        import time

        start_time = time.time()

        logger.info(
            "Starting research investigation",
            query_id=query.query_id,
            topic=query.topic,
            depth=query.depth.value,
        )

        # Initialize storage for topic if needed
        if query.topic not in self._findings:
            self._findings[query.topic] = []

        # Perform research based on depth
        findings = await self._gather_findings(query)

        # Detect contradictions if requested
        contradictions: list[ResearchFinding] = []
        if query.validate_contradictions:
            contradictions = self._detect_contradictions(findings)

        # Detect correlations if requested
        correlated: list[list[ResearchFinding]] = []
        if query.detect_correlations:
            correlated = self._detect_correlations(findings)

        # Calculate overall confidence
        confidence = self._calculate_confidence(findings, contradictions)

        # Build result
        duration_ms = (time.time() - start_time) * 1000
        result = ResearchResult(
            topic=query.topic,
            depth=query.depth,
            findings=findings,
            summary=self._generate_summary(findings, contradictions),
            contradictions_detected=contradictions,
            correlated_findings=correlated,
            sources_consulted=self._get_sources(findings),
            research_duration_ms=duration_ms,
            confidence_score=confidence,
        )

        # Store in history
        self._research_history.append(result)
        if len(self._research_history) > 100:
            self._research_history = self._research_history[-100:]

        logger.info(
            "Research investigation complete",
            query_id=query.query_id,
            topic=query.topic,
            findings_count=len(findings),
            contradictions_count=len(contradictions),
            correlations_count=len(correlated),
            duration_ms=duration_ms,
        )

        return result

    async def _gather_findings(self, query: ResearchQuery) -> list[ResearchFinding]:
        """
        Gather findings for a research query via hybrid RAG retrieval.
        """
        findings: list[ResearchFinding] = []
        try:
            from heretek_swarm.rag.hybrid_retriever import HybridRetriever

            retriever = HybridRetriever()
            await retriever.initialize()
            chunks = await retriever.retrieve(query.topic, top_k=query.max_sources or 10)
            for i, chunk in enumerate(chunks):
                source_name = getattr(chunk, "source", None) or chunk.metadata.get("source", "rag")
                findings.append(
                    ResearchFinding(
                        finding_id=f"finding_{i}",
                        topic=query.topic,
                        content=getattr(chunk, "content", str(chunk)),
                        finding_type=FindingType.FACT,
                        source=ResearchSource(
                            source_id=str(source_name),
                            source_type="rag",
                            name=str(source_name),
                            credibility=SourceCredibility.MEDIUM,
                        ),
                        confidence=float(getattr(chunk, "score", 0.7)),
                        metadata={"query_depth": query.depth.value},
                    )
                )
        except Exception as e:
            logger.warning("research_rag_unavailable", error=str(e), topic=query.topic)

        if not findings and query.topic:
            findings.append(
                ResearchFinding(
                    finding_id="finding_0",
                    topic=query.topic,
                    content=f"No external sources retrieved for: {query.topic}",
                    finding_type=FindingType.OPINION,
                    source=ResearchSource(
                        source_id="internal",
                        source_type="internal",
                        name="internal",
                        credibility=SourceCredibility.LOW,
                    ),
                    confidence=0.3,
                )
            )
        return findings

    def _detect_contradictions(self, findings: list[ResearchFinding]) -> list[ResearchFinding]:
        """
        Detect contradictory findings.

        Args:
            findings: List of findings to analyze

        Returns:
            List of findings that have contradictions
        """
        contradictions: list[ResearchFinding] = []
        checked_pairs: set[tuple[str, str]] = set()

        for i, finding1 in enumerate(findings):
            for finding2 in findings[i + 1 :]:
                pair = tuple(sorted([finding1.finding_id, finding2.finding_id]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                # Check for contradiction
                if self._are_contradictory(finding1, finding2):
                    # Mark both as contradictory
                    if finding2 not in contradictions:
                        finding2.contradicting_findings.append(finding1.finding_id)
                        contradictions.append(finding2)
                    if finding1 not in contradictions:
                        finding1.contradicting_findings.append(finding2.finding_id)
                        contradictions.append(finding1)

        return contradictions

    def _are_contradictory(self, finding1: ResearchFinding, finding2: ResearchFinding) -> bool:
        """
        Check if two findings are contradictory.

        Args:
            finding1: First finding
            finding2: Second finding

        Returns:
            True if findings are contradictory
        """
        # High confidence findings from different sources that disagree
        if finding1.confidence >= self.contradiction_threshold:  # noqa: SIM102
            if finding2.confidence >= self.contradiction_threshold:
                # Check for opposing content
                content1 = finding1.content.lower()
                content2 = finding2.content.lower()

                # Simple keyword-based contradiction detection
                opposing_pairs = [
                    ("increase", "decrease"),
                    ("positive", "negative"),
                    ("safe", "dangerous"),
                    ("works", "fails"),
                    ("supports", "opposes"),
                    ("yes", "no"),
                    ("true", "false"),
                ]

                for pos, neg in opposing_pairs:
                    if (pos in content1 and neg in content2) or (
                        neg in content1 and pos in content2
                    ):
                        return True

        # Same source type but different conclusions
        if finding1.source.source_type == finding2.source.source_type:  # noqa: SIM102
            if finding1.confidence > 0.7 and finding2.confidence > 0.7:  # noqa: SIM102
                if abs(finding1.confidence - finding2.confidence) < 0.1:  # noqa: SIM102
                    # Similar confidence but content differs significantly
                    if not self._content_similarity(finding1.content, finding2.content):
                        return True

        return False

    def _detect_correlations(self, findings: list[ResearchFinding]) -> list[list[ResearchFinding]]:
        """
        Detect correlated findings.

        Args:
            findings: List of findings to analyze

        Returns:
            List of correlated finding groups
        """
        correlations: list[list[ResearchFinding]] = []
        used: set[str] = set()

        for i, finding1 in enumerate(findings):
            if finding1.finding_id in used:
                continue

            group: list[ResearchFinding] = [finding1]
            used.add(finding1.finding_id)

            for finding2 in findings[i + 1 :]:
                if finding2.finding_id in used:
                    continue

                if self._are_correlated(finding1, finding2):
                    group.append(finding2)
                    used.add(finding2.finding_id)

            if len(group) > 1:
                correlations.append(group)

        return correlations

    def _are_correlated(self, finding1: ResearchFinding, finding2: ResearchFinding) -> bool:
        """
        Check if two findings are correlated.

        Args:
            finding1: First finding
            finding2: Second finding

        Returns:
            True if findings are correlated
        """
        # Same topic keywords
        topic1_words = set(finding1.topic.lower().split())
        topic2_words = set(finding2.topic.lower().split())

        if topic1_words & topic2_words:
            # Shared keywords indicate correlation
            return True

        # Similar content
        if (
            self._content_similarity(finding1.content, finding2.content)
            >= self.correlation_threshold
        ):
            return True

        # Same source type
        return finding1.source.source_type == finding2.source.source_type

    def _content_similarity(self, content1: str, content2: str) -> float:
        """
        Calculate content similarity.

        Args:
            content1: First content
            content2: Second content

        Returns:
            Similarity score 0-1
        """
        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = len(words1 & words2)
        union = len(words1 | words2)

        return intersection / union if union > 0 else 0.0

    def _calculate_confidence(
        self,
        findings: list[ResearchFinding],
        contradictions: list[ResearchFinding],
    ) -> float:
        """
        Calculate overall research confidence.

        Args:
            findings: All findings
            contradictions: Contradictory findings

        Returns:
            Confidence score 0-1
        """
        if not findings:
            return 0.0

        # Base confidence from average finding confidence
        avg_confidence = sum(f.confidence for f in findings) / len(findings)

        # Reduce for contradictions
        contradiction_penalty = len(contradictions) * 0.1

        # Reduce for low credibility sources
        low_credibility_count = sum(
            1
            for f in findings
            if f.source.credibility in [SourceCredibility.UNVERIFIED, SourceCredibility.LOW]
        )
        credibility_penalty = (low_credibility_count / len(findings)) * 0.2 if findings else 0

        confidence = max(0.0, avg_confidence - contradiction_penalty - credibility_penalty)
        return min(1.0, confidence)

    def _generate_summary(
        self,
        findings: list[ResearchFinding],
        contradictions: list[ResearchFinding],
    ) -> str:
        """
        Generate a text summary of the research.

        Args:
            findings: All findings
            contradictions: Contradictory findings

        Returns:
            Summary string
        """
        summary_parts = []

        if findings:
            summary_parts.append(f"Research identified {len(findings)} findings")
        else:
            summary_parts.append("No findings identified")

        if contradictions:
            summary_parts.append(f"{len(contradictions)} contradictions detected")

        # Count by type
        by_type: dict[FindingType, int] = {}
        for f in findings:
            by_type[f.finding_type] = by_type.get(f.finding_type, 0) + 1

        if by_type:
            type_str = ", ".join(f"{t.value}: {c}" for t, c in by_type.items())
            summary_parts.append(f"Finding types: {type_str}")

        return "; ".join(summary_parts)

    def _get_sources(self, findings: list[ResearchFinding]) -> list[ResearchSource]:
        """Get unique sources from findings."""
        seen: set[str] = set()
        sources: list[ResearchSource] = []

        for f in findings:
            if f.source.source_id not in seen:
                seen.add(f.source.source_id)
                sources.append(f.source)

        return sources

    def add_finding(self, finding: ResearchFinding) -> None:
        """
        Add a finding to storage.

        Args:
            finding: Finding to add
        """
        topic = finding.topic
        if topic not in self._findings:
            self._findings[topic] = []

        # Check max size with LRU eviction
        if len(self._findings[topic]) >= self.max_findings_per_topic:
            # Remove lowest confidence finding
            self._findings[topic].sort(key=lambda f: f.confidence)
            self._findings[topic].pop(0)

        self._findings[topic].append(finding)

    def get_findings_for_topic(self, topic: str) -> list[ResearchFinding]:
        """
        Get all findings for a topic.

        Args:
            topic: Topic to query

        Returns:
            List of findings
        """
        return self._findings.get(topic, [])

    def get_research_history(self, limit: int = 10) -> list[ResearchResult]:
        """
        Get research history.

        Args:
            limit: Maximum results to return

        Returns:
            List of research results
        """
        return self._research_history[-limit:]

    def update_source_credibility(self, source_id: str, credibility: SourceCredibility) -> None:
        """
        Update source credibility.

        Args:
            source_id: Source identifier
            credibility: New credibility level
        """
        self._source_credibility[source_id] = credibility
        logger.info(
            "Source credibility updated",
            source_id=source_id,
            credibility=credibility.value,
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get research module statistics."""
        total_findings = sum(len(f) for f in self._findings.values())
        return {
            "topics_researched": len(self._findings),
            "total_findings": total_findings,
            "research_operations": len(self._research_history),
            "sources_tracked": len(self._source_credibility),
            "findings_by_topic": {
                topic: len(findings) for topic, findings in self._findings.items()
            },
        }
