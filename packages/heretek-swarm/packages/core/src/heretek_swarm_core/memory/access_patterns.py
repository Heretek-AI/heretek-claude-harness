"""
Memory Access Pattern Analyzer for Heretek Swarm

This module provides comprehensive access pattern analysis for memory optimization:
- Track memory access frequency and recency
- Identify hot/warm/cold data patterns
- Predict future access needs based on agent behavior
- Generate access pattern reports

Reference: EXPANSION_ROADMAP.md Session 43 - Memory Optimization
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Access Pattern Types and Enums
# =============================================================================


class AccessTier(StrEnum):
    """Memory access tier classification."""

    HOT = "hot"  # Frequently accessed, keep in fastest storage
    WARM = "warm"  # Moderately accessed, standard storage
    COLD = "cold"  # Rarely accessed, can be compressed/archived
    FROZEN = "frozen"  # Never accessed, candidate for deletion


class AccessPattern(StrEnum):
    """Types of access patterns detected."""

    SEQUENTIAL = "sequential"  # Accessing in order
    RANDOM = "random"  # No predictable pattern
    TEMPORAL = "temporal"  # Time-based access pattern
    SPATIAL = "spatial"  # Related memories accessed together
    BURST = "burst"  # Sudden high-frequency access
    DECAYING = "decaying"  # Decreasing access over time
    GROWING = "growing"  # Increasing access over time
    CYCLICAL = "cyclical"  # Periodic access pattern


@dataclass
class MemoryAccessRecord:
    """
    Record of a single memory access event.

    Attributes:
        memory_id: Unique memory identifier
        access_type: Type of access (read/write/delete)
        timestamp: Access timestamp
        agent_id: Agent that performed the access
        session_id: Session context
        access_latency_ms: Time taken for access
        success: Whether access succeeded
    """

    memory_id: str
    access_type: str  # read, write, delete
    timestamp: str
    agent_id: str | None = None
    session_id: str | None = None
    access_latency_ms: float = 0.0
    success: bool = True


@dataclass
class AccessStatistics:
    """
    Statistical summary of memory access patterns.

    Attributes:
        total_accesses: Total number of accesses
        unique_memories: Number of unique memories accessed
        hot_count: Count of hot memories
        warm_count: Count of warm memories
        cold_count: Count of cold memories
        frozen_count: Count of frozen memories
        avg_frequency: Average access frequency
        avg_recency: Average recency score
        hit_rate: Cache hit rate if applicable
        miss_rate: Cache miss rate if applicable
        predicted_hits: Predicted future access count
    """

    total_accesses: int = 0
    unique_memories: int = 0
    hot_count: int = 0
    warm_count: int = 0
    cold_count: int = 0
    frozen_count: int = 0
    avg_frequency: float = 0.0
    avg_recency: float = 0.0
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    predicted_hits: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "total_accesses": self.total_accesses,
            "unique_memories": self.unique_memories,
            "tier_distribution": {
                "hot": self.hot_count,
                "warm": self.warm_count,
                "cold": self.cold_count,
                "frozen": self.frozen_count,
            },
            "frequency": {
                "avg_frequency": self.avg_frequency,
                "avg_recency": self.avg_recency,
            },
            "cache_performance": {
                "hit_rate": self.hit_rate,
                "miss_rate": self.miss_rate,
            },
            "predictions": {
                "predicted_hits": self.predicted_hits,
            },
        }


@dataclass
class MemoryAccessProfile:
    """
    Access profile for a single memory entry.

    Attributes:
        memory_id: Unique memory identifier
        access_count: Total number of accesses
        first_access: Timestamp of first access
        last_access: Timestamp of most recent access
        access_timestamps: List of all access timestamps
        access_types: Count of each access type
        agents_accessed: Set of agent IDs that accessed this memory
        sessions_accessed: Set of session IDs
        tier: Current access tier classification
        frequency_score: Computed frequency score (0-1)
        recency_score: Computed recency score (0-1)
        pattern: Detected access pattern
        predicted_next_access: Predicted next access time
        confidence: Prediction confidence (0-1)
    """

    memory_id: str
    access_count: int = 0
    first_access: str | None = None
    last_access: str | None = None
    access_timestamps: list[str] = field(default_factory=list)
    access_types: dict[str, int] = field(default_factory=dict)
    agents_accessed: set = field(default_factory=set)
    sessions_accessed: set = field(default_factory=set)
    tier: AccessTier = AccessTier.COLD
    frequency_score: float = 0.0
    recency_score: float = 0.0
    pattern: AccessPattern = AccessPattern.RANDOM
    predicted_next_access: str | None = None
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "memory_id": self.memory_id,
            "access_count": self.access_count,
            "first_access": self.first_access,
            "last_access": self.last_access,
            "tier": self.tier.value,
            "pattern": self.pattern.value,
            "scores": {
                "frequency": self.frequency_score,
                "recency": self.recency_score,
                "confidence": self.confidence,
            },
            "predicted_next_access": self.predicted_next_access,
        }


@dataclass
class AccessPatternReport:
    """
    Comprehensive access pattern analysis report.

    Attributes:
        generated_at: Report generation timestamp
        analysis_window_hours: Time window analyzed
        total_memories: Total memories in system
        total_accesses: Total accesses in window
        statistics: Access statistics
        tier_distribution: Distribution across tiers
        pattern_distribution: Distribution of patterns
        predictions: Access predictions
        recommendations: Optimization recommendations
    """

    generated_at: str
    analysis_window_hours: int
    total_memories: int
    total_accesses: int
    statistics: AccessStatistics
    tier_distribution: dict[str, int]
    pattern_distribution: dict[str, int]
    predictions: dict[str, Any]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            "metadata": {
                "generated_at": self.generated_at,
                "analysis_window_hours": self.analysis_window_hours,
            },
            "summary": {
                "total_memories": self.total_memories,
                "total_accesses": self.total_accesses,
                "statistics": self.statistics.to_dict(),
            },
            "distributions": {
                "tiers": self.tier_distribution,
                "patterns": self.pattern_distribution,
            },
            "predictions": self.predictions,
            "recommendations": self.recommendations,
        }


# =============================================================================
# Access Pattern Analyzer
# =============================================================================


class AccessPatternAnalyzer:
    """
    Memory Access Pattern Analyzer

    Provides comprehensive analysis of memory access patterns:
    - Track memory access frequency and recency
    - Identify hot/warm/cold data patterns
    - Predict future access needs based on agent behavior
    - Generate access pattern reports

    Features:
    - LRU (Least Recently Used) tracking
    - LFU (Least Frequently Used) tracking
    - Temporal pattern detection
    - Spatial locality detection
    - Predictive modeling
    """

    # Tier classification thresholds
    HOT_FREQUENCY_THRESHOLD = 0.8  # Top 20% by frequency
    WARM_FREQUENCY_THRESHOLD = 0.4  # 40-80% by frequency
    COLD_FREQUENCY_THRESHOLD = 0.1  # 10-40% by frequency

    # Recency decay constants
    RECENCY_HALF_LIFE_HOURS = 24  # Half-life for recency decay
    MAX_RECENCY_AGE_HOURS = 168  # 1 week max for recency

    # Pattern detection parameters
    MIN_ACCESSES_FOR_PATTERN = 5  # Minimum accesses to detect pattern
    SEQUENTIAL_THRESHOLD = 0.7  # Correlation threshold for sequential
    CYCLICAL_THRESHOLD = 0.6  # Periodicity threshold

    def __init__(
        self,
        hot_threshold: float = 0.8,
        warm_threshold: float = 0.4,
        cold_threshold: float = 0.1,
        recency_half_life_hours: float = 24.0,
    ) -> None:
        """
        Initialize the access pattern analyzer.

        Args:
            hot_threshold: Frequency threshold for hot classification
            warm_threshold: Frequency threshold for warm classification
            cold_threshold: Frequency threshold for cold classification
            recency_half_life_hours: Half-life for recency decay
        """
        self.hot_threshold = hot_threshold
        self.warm_threshold = warm_threshold
        self.cold_threshold = cold_threshold
        self.recency_half_life_hours = recency_half_life_hours

        # Memory access profiles
        self._profiles: dict[str, MemoryAccessProfile] = {}

        # Access history for pattern detection
        self._access_history: list[MemoryAccessRecord] = []
        self._max_history_size = 100000

        # Statistics tracking
        self._total_accesses = 0
        self._cache_hits = 0
        self._cache_misses = 0

        # Agent behavior tracking
        self._agent_patterns: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"accessed_memories": [], "preferred_times": [], "session_patterns": []}
        )

        logger.info("access_pattern_analyzer_initialized")

    def record_access(
        self,
        memory_id: str,
        access_type: str = "read",
        agent_id: str | None = None,
        session_id: str | None = None,
        access_latency_ms: float = 0.0,
        success: bool = True,
    ) -> MemoryAccessProfile:
        """
        Record a memory access event.

        Args:
            memory_id: Memory identifier
            access_type: Type of access (read/write/delete)
            agent_id: Agent that performed the access
            session_id: Session context
            access_latency_ms: Time taken for access
            success: Whether access succeeded

        Returns:
            Updated memory access profile
        """
        timestamp = datetime.now(UTC).isoformat()

        # Create access record
        record = MemoryAccessRecord(
            memory_id=memory_id,
            access_type=access_type,
            timestamp=timestamp,
            agent_id=agent_id,
            session_id=session_id,
            access_latency_ms=access_latency_ms,
            success=success,
        )

        # Update history
        self._access_history.append(record)
        if len(self._access_history) > self._max_history_size:
            self._access_history = self._access_history[-self._max_history_size :]

        # Update or create profile
        if memory_id not in self._profiles:
            self._profiles[memory_id] = MemoryAccessProfile(memory_id=memory_id)

        profile = self._profiles[memory_id]
        profile.access_count += 1
        profile.access_timestamps.append(timestamp)

        if profile.first_access is None:
            profile.first_access = timestamp
        profile.last_access = timestamp

        # Update access type counts
        profile.access_types[access_type] = profile.access_types.get(access_type, 0) + 1

        # Update agent/session tracking
        if agent_id:
            profile.agents_accessed.add(agent_id)
            self._track_agent_behavior(agent_id, memory_id, timestamp, session_id)

        if session_id:
            profile.sessions_accessed.add(session_id)

        # Update statistics
        self._total_accesses += 1
        if success:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

        # Update scores and tier
        self._update_profile_scores(profile)

        return profile

    def _track_agent_behavior(
        self,
        agent_id: str,
        memory_id: str,
        timestamp: str,
        session_id: str | None,
    ) -> None:
        """Track agent-specific access patterns for prediction."""
        agent_data = self._agent_patterns[agent_id]
        agent_data["accessed_memories"].append((memory_id, timestamp))

        # Keep only last 1000 accesses per agent
        if len(agent_data["accessed_memories"]) > 1000:
            agent_data["accessed_memories"] = agent_data["accessed_memories"][-1000:]

        # Track preferred access times
        try:
            dt = datetime.fromisoformat(timestamp)
            hour = dt.hour
            agent_data["preferred_times"].append(hour)
        except (ValueError, TypeError):
            logger.debug("Memory access pattern parse fallback", exc_info=True)

        # Track session patterns
        if session_id:
            agent_data["session_patterns"].append(session_id)

    def _update_profile_scores(self, profile: MemoryAccessProfile) -> None:
        """Update frequency and recency scores for a profile."""
        now = datetime.now(UTC)

        # Calculate frequency score (normalized 0-1)
        # Using logarithmic scaling to handle wide range of access counts
        if profile.access_count > 0:
            max_possible = self._max_history_size / max(len(self._profiles), 1)
            profile.frequency_score = min(
                1.0,
                math.log(profile.access_count + 1) / math.log(max_possible + 1)
                if max_possible > 0
                else 0.5,
            )

        # Calculate recency score with exponential decay
        if profile.last_access:
            try:
                last_access_dt = datetime.fromisoformat(profile.last_access)
                age_hours = (now - last_access_dt).total_seconds() / 3600

                # Exponential decay with half-life
                profile.recency_score = math.exp(
                    -math.log(2) * age_hours / self.recency_half_life_hours
                )

                # Clamp to valid range
                profile.recency_score = max(0.0, min(1.0, profile.recency_score))
            except (ValueError, TypeError):
                profile.recency_score = 0.0

        # Update tier based on scores
        profile.tier = self._classify_tier(profile)

        # Detect access pattern
        if profile.access_count >= self.MIN_ACCESSES_FOR_PATTERN:
            profile.pattern = self._detect_pattern(profile)

            # Predict next access
            profile.predicted_next_access, profile.confidence = self._predict_next_access(profile)

    def _classify_tier(self, profile: MemoryAccessProfile) -> AccessTier:
        """Classify memory into access tier based on frequency score primarily."""
        # Use frequency score as primary classifier; recency as secondary boost
        # This ensures new items (low frequency) start in COLD tier
        freq_score = profile.frequency_score
        combined_score = freq_score * 0.8 + profile.recency_score * 0.2

        if combined_score >= self.hot_threshold:
            return AccessTier.HOT
        if combined_score >= self.warm_threshold:
            return AccessTier.WARM
        if combined_score >= self.cold_threshold:
            return AccessTier.COLD
        return AccessTier.FROZEN

    def _detect_pattern(self, profile: MemoryAccessProfile) -> AccessPattern:
        """Detect the dominant access pattern for a memory."""
        if len(profile.access_timestamps) < self.MIN_ACCESSES_FOR_PATTERN:
            return AccessPattern.RANDOM

        timestamps = profile.access_timestamps[-20:]  # Use last 20 accesses

        # Try to detect sequential pattern
        if self._is_sequential(timestamps):
            return AccessPattern.SEQUENTIAL

        # Try to detect cyclical pattern
        if self._is_cyclical(timestamps):
            return AccessPattern.CYCLICAL

        # Check for burst pattern (many accesses in short time)
        if self._is_burst(timestamps):
            return AccessPattern.BURST

        # Check for decaying pattern
        if self._is_decaying(timestamps):
            return AccessPattern.DECAYING

        # Check for growing pattern
        if self._is_growing(timestamps):
            return AccessPattern.GROWING

        return AccessPattern.RANDOM

    def _is_sequential(self, timestamps: list[str]) -> bool:
        """Check if accesses follow a sequential pattern."""
        if len(timestamps) < 3:
            return False

        try:
            times = [datetime.fromisoformat(ts) for ts in timestamps]
            intervals = [(times[i + 1] - times[i]).total_seconds() for i in range(len(times) - 1)]

            if not intervals:
                return False

            # Check if intervals are consistent (low variance)
            avg_interval = sum(intervals) / len(intervals)
            if avg_interval == 0:
                return True

            variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
            std_dev = math.sqrt(variance)
            coefficient_of_variation = std_dev / avg_interval if avg_interval > 0 else float("inf")

            return coefficient_of_variation < (1 - self.SEQUENTIAL_THRESHOLD)
        except (ValueError, TypeError):
            return False

    def _is_cyclical(self, timestamps: list[str]) -> bool:
        """Check if accesses follow a cyclical pattern."""
        if len(timestamps) < 6:
            return False

        try:
            times = [datetime.fromisoformat(ts) for ts in timestamps]
            hours = [t.hour for t in times]

            # Check for daily pattern (same hour accesses)
            hour_counts = defaultdict(int)
            for h in hours:
                hour_counts[h] += 1

            max_hour_count = max(hour_counts.values()) if hour_counts else 0
            return max_hour_count / len(hours) >= self.CYCLICAL_THRESHOLD
        except (ValueError, TypeError):
            return False

    def _is_burst(self, timestamps: list[str]) -> bool:
        """Check for burst access pattern."""
        if len(timestamps) < 5:
            return False

        try:
            times = [datetime.fromisoformat(ts) for ts in timestamps]

            # Check if many accesses happened in short time
            total_span = (times[-1] - times[0]).total_seconds()
            if total_span == 0:
                return True

            # Burst if 80% of accesses in less than 10% of total time
            burst_threshold = total_span * 0.1
            burst_count = sum(
                1
                for i in range(len(times) - 1)
                if (times[i + 1] - times[i]).total_seconds() < burst_threshold
            )

            return burst_count >= len(timestamps) * 0.8
        except (ValueError, TypeError):
            return False

    def _is_decaying(self, timestamps: list[str]) -> AccessPattern:
        """Check for decaying access pattern."""
        if len(timestamps) < 5:
            return False

        try:
            times = [datetime.fromisoformat(ts) for ts in timestamps]
            intervals = [(times[i + 1] - times[i]).total_seconds() for i in range(len(times) - 1)]

            if len(intervals) < 3:
                return False

            # Check if intervals are increasing (access becoming less frequent)
            increasing_count = sum(
                1 for i in range(len(intervals) - 1) if intervals[i + 1] > intervals[i]
            )

            return increasing_count / len(intervals) >= 0.7
        except (ValueError, TypeError):
            return False

    def _is_growing(self, timestamps: list[str]) -> AccessPattern:
        """Check for growing access pattern."""
        if len(timestamps) < 5:
            return False

        try:
            times = [datetime.fromisoformat(ts) for ts in timestamps]
            intervals = [(times[i + 1] - times[i]).total_seconds() for i in range(len(times) - 1)]

            if len(intervals) < 3:
                return False

            # Check if intervals are decreasing (access becoming more frequent)
            decreasing_count = sum(
                1 for i in range(len(intervals) - 1) if intervals[i + 1] < intervals[i]
            )

            return decreasing_count / len(intervals) >= 0.7
        except (ValueError, TypeError):
            return False

    def _predict_next_access(self, profile: MemoryAccessProfile) -> tuple[str | None, float]:
        """Predict the next access time for a memory."""
        if len(profile.access_timestamps) < self.MIN_ACCESSES_FOR_PATTERN:
            return None, 0.0

        timestamps = profile.access_timestamps[-20:]

        try:
            times = [datetime.fromisoformat(ts) for ts in timestamps]

            # Calculate average interval
            intervals = [(times[i + 1] - times[i]).total_seconds() for i in range(len(times) - 1)]

            if not intervals:
                return None, 0.0

            avg_interval = sum(intervals) / len(intervals)

            # Predict next access
            last_time = times[-1]
            predicted_time = last_time + timedelta(seconds=avg_interval)

            # Calculate confidence based on pattern consistency
            if len(intervals) > 1:
                variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
                std_dev = math.sqrt(variance)
                confidence = max(0.0, 1.0 - (std_dev / avg_interval)) if avg_interval > 0 else 0.5
            else:
                confidence = 0.5

            return predicted_time.isoformat(), confidence
        except (ValueError, TypeError, OverflowError):
            return None, 0.0

    def get_profile(self, memory_id: str) -> MemoryAccessProfile | None:
        """Get the access profile for a specific memory."""
        return self._profiles.get(memory_id)

    def get_profiles_by_tier(self, tier: AccessTier) -> list[MemoryAccessProfile]:
        """Get all profiles for a specific tier."""
        return [p for p in self._profiles.values() if p.tier == tier]

    def get_hot_memories(self) -> list[MemoryAccessProfile]:
        """Get all hot and warm memories (actively accessed)."""
        return [p for p in self._profiles.values() if p.tier in (AccessTier.HOT, AccessTier.WARM)]

    def get_cold_memories(self) -> list[MemoryAccessProfile]:
        """Get all cold memories."""
        return self.get_profiles_by_tier(AccessTier.COLD)

    def get_frozen_memories(self) -> list[MemoryAccessProfile]:
        """Get all frozen memories (candidates for deletion)."""
        return self.get_profiles_by_tier(AccessTier.FROZEN)

    def get_statistics(self) -> AccessStatistics:
        """Get overall access statistics."""
        if not self._profiles:
            return AccessStatistics()

        hot_count = sum(1 for p in self._profiles.values() if p.tier == AccessTier.HOT)
        warm_count = sum(1 for p in self._profiles.values() if p.tier == AccessTier.WARM)
        cold_count = sum(1 for p in self._profiles.values() if p.tier == AccessTier.COLD)
        frozen_count = sum(1 for p in self._profiles.values() if p.tier == AccessTier.FROZEN)

        avg_frequency = sum(p.frequency_score for p in self._profiles.values()) / len(
            self._profiles
        )
        avg_recency = sum(p.recency_score for p in self._profiles.values()) / len(self._profiles)

        total_ops = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total_ops if total_ops > 0 else 0.0
        miss_rate = self._cache_misses / total_ops if total_ops > 0 else 0.0

        # Calculate predicted hits
        predicted_hits = sum(
            1
            for p in self._profiles.values()
            if p.confidence > 0.7 and p.predicted_next_access is not None
        )

        return AccessStatistics(
            total_accesses=self._total_accesses,
            unique_memories=len(self._profiles),
            hot_count=hot_count,
            warm_count=warm_count,
            cold_count=cold_count,
            frozen_count=frozen_count,
            avg_frequency=avg_frequency,
            avg_recency=avg_recency,
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            predicted_hits=predicted_hits,
        )

    def generate_report(
        self,
        analysis_window_hours: int = 24,
    ) -> AccessPatternReport:
        """
        Generate a comprehensive access pattern report.

        Args:
            analysis_window_hours: Time window to analyze

        Returns:
            Complete access pattern report
        """
        stats = self.get_statistics()

        # Calculate tier distribution
        tier_distribution = {
            "hot": stats.hot_count,
            "warm": stats.warm_count,
            "cold": stats.cold_count,
            "frozen": stats.frozen_count,
        }

        # Calculate pattern distribution
        pattern_counts = defaultdict(int)
        for profile in self._profiles.values():
            pattern_counts[profile.pattern.value] += 1

        # Generate predictions
        predictions = self._generate_predictions(analysis_window_hours)

        # Generate recommendations
        recommendations = self._generate_recommendations(stats)

        return AccessPatternReport(
            generated_at=datetime.now(UTC).isoformat(),
            analysis_window_hours=analysis_window_hours,
            total_memories=len(self._profiles),
            total_accesses=self._total_accesses,
            statistics=stats,
            tier_distribution=tier_distribution,
            pattern_distribution=dict(pattern_counts),
            predictions=predictions,
            recommendations=recommendations,
        )

    def _generate_predictions(self, _analysis_window_hours: int) -> dict[str, Any]:
        """Generate access predictions for the analysis window."""
        high_confidence_predictions = [
            p
            for p in self._profiles.values()
            if p.confidence > 0.7 and p.predicted_next_access is not None
        ]

        # Predict tier migrations
        migrations_predicted = []
        for profile in self._profiles.values():
            if profile.tier == AccessTier.WARM and profile.recency_score < 0.2:
                migrations_predicted.append(
                    {
                        "memory_id": profile.memory_id,
                        "from_tier": "warm",
                        "to_tier": "cold",
                        "confidence": 0.8,
                    }
                )
            elif profile.tier == AccessTier.COLD and profile.frequency_score > 0.6:
                migrations_predicted.append(
                    {
                        "memory_id": profile.memory_id,
                        "from_tier": "cold",
                        "to_tier": "warm",
                        "confidence": 0.7,
                    }
                )

        return {
            "high_confidence_accesses": len(high_confidence_predictions),
            "tier_migrations": migrations_predicted[:100],  # Limit to 100
            "expected_hot_set_size": stats.hot_count if (stats := self.get_statistics()) else 0,
        }

    def _generate_recommendations(self, stats: AccessStatistics) -> list[str]:
        """Generate optimization recommendations based on statistics."""
        recommendations = []

        # Check for too many frozen memories
        if stats.frozen_count > stats.unique_memories * 0.5:
            recommendations.append(
                f"Consider archiving or deleting {stats.frozen_count} frozen memories "
                f"({stats.frozen_count / stats.unique_memories * 100:.1f}% of total)"
            )

        # Check for cache performance
        if stats.hit_rate < 0.8:
            recommendations.append(
                f"Cache hit rate is {stats.hit_rate:.1%}. Consider increasing cache size "
                "or implementing better pre-fetching strategies."
            )

        # Check for hot memory count
        if stats.hot_count > stats.unique_memories * 0.3:
            recommendations.append(
                f"High number of hot memories ({stats.hot_count}). "
                "Consider implementing more aggressive tiering."
            )

        # Check for predicted accesses
        if stats.predicted_hits > 0:
            recommendations.append(
                f"{stats.predicted_hits} memories have predictable access patterns. "
                "Consider implementing pre-fetching for these memories."
            )

        return recommendations

    def clear(self) -> None:
        """Clear all access tracking data."""
        self._profiles.clear()
        self._access_history.clear()
        self._total_accesses = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._agent_patterns.clear()
        logger.info("access_pattern_analyzer_cleared")

    def get_agent_patterns(self, agent_id: str) -> dict[str, Any]:
        """Get access patterns for a specific agent."""
        return dict(self._agent_patterns.get(agent_id, {}))

    def predict_agent_access(self, agent_id: str) -> list[str]:
        """
        Predict which memories an agent is likely to access next.

        Args:
            agent_id: Agent identifier

        Returns:
            List of predicted memory IDs
        """
        agent_data = self._agent_patterns.get(agent_id)
        if not agent_data:
            return []

        accessed = agent_data.get("accessed_memories", [])
        if not accessed:
            return []

        # Get recently accessed memories
        recent_memories = [m[0] for m in accessed[-20:]]

        # Find memories with high recency scores that agent has accessed
        predictions = []
        for memory_id in set(recent_memories):
            profile = self._profiles.get(memory_id)
            if profile and profile.recency_score > 0.5:
                predictions.append((memory_id, profile.recency_score))

        # Sort by recency score and return top predictions
        predictions.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in predictions[:10]]
