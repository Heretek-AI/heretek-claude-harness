"""Paradigm shift detection for change management."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

class ShiftType(Enum):
    """Types of paradigm shifts."""

    TECHNOLOGICAL = "technological"
    BEHAVIORAL = "behavioral"
    ARCHITECTURAL = "architectural"
    PROTOCOL = "protocol"
    OPERATIONAL = "operational"

class ShiftMagnitude(Enum):
    """Magnitude of detected shift."""

    MINOR = "minor"
    MODERATE = "moderate"
    MAJOR = "major"
    CRITICAL = "critical"

class ShiftConfidence(Enum):
    """Confidence level of shift detection."""

    SPECULATIVE = "speculative"
    POSSIBLE = "possible"
    LIKELY = "likely"
    PROBABLE = "probable"
    CONFIRMED = "confirmed"

class ShiftStatus(Enum):
    """Status of a detected paradigm shift."""

    DETECTED = "detected"
    VALIDATING = "validating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    MITIGATED = "mitigated"
    ESCALATED = "escalated"

class ChangeType(Enum):
    """Type of change request."""

    CONFIGURATION = "configuration"
    DEPLOYMENT = "deployment"
    MIGRATION = "migration"
    UPGRADE = "upgrade"
    PATCH = "patch"
    HOTFIX = "hotfix"
    ROLLBACK = "rollback"

@dataclass
class ChangeRequest:
    """A change request under management."""

    change_id: str
    title: str
    description: str
    change_type: ChangeType
    requested_by: str = ""
    affected_components: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ShiftIndicator:
    """A single indicator contributing to shift detection."""

    indicator_id: str
    shift_type: ShiftType
    description: str
    first_detected: datetime = field(default_factory=lambda: datetime.now(UTC))
    occurrences: int = 0
    agents_involved: set[str] = field(default_factory=set)
    affected_components: list[str] = field(default_factory=list)
    confidence_boost: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "indicator_id": self.indicator_id,
            "shift_type": self.shift_type.value,
            "description": self.description,
            "first_detected": self.first_detected.isoformat(),
            "occurrences": self.occurrences,
            "agents_involved": list(self.agents_involved),
            "affected_components": self.affected_components,
            "confidence_boost": self.confidence_boost,
        }

@dataclass
class ParadigmShift:
    """A detected paradigm shift."""

    shift_id: str
    shift_type: ShiftType
    magnitude: ShiftMagnitude
    confidence: ShiftConfidence
    status: ShiftStatus = ShiftStatus.DETECTED
    indicators: list[ShiftIndicator] = field(default_factory=list)
    first_detected: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    detection_count: int = 0
    affected_components: list[str] = field(default_factory=list)
    impacted_agents: list[str] = field(default_factory=list)
    impact_score: float = 0.0
    related_shifts: list[str] = field(default_factory=list)
    cumulative_impact: float = 0.0
    validation_beta: str | None = None
    deliberation_id: str | None = None
    core_triad_notified: bool = False
    resolution_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "shift_id": self.shift_id,
            "shift_type": self.shift_type.value,
            "magnitude": self.magnitude.value,
            "confidence": self.confidence.value,
            "status": self.status.value,
            "indicators": [i.to_dict() for i in self.indicators],
            "first_detected": self.first_detected.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "detection_count": self.detection_count,
            "affected_components": self.affected_components,
            "impacted_agents": self.impacted_agents,
            "impact_score": self.impact_score,
            "related_shifts": self.related_shifts,
            "cumulative_impact": self.cumulative_impact,
            "validation_beta": self.validation_beta,
            "deliberation_id": self.deliberation_id,
            "core_triad_notified": self.core_triad_notified,
            "resolution_notes": self.resolution_notes,
        }

class ParadigmDetector:
    """Detects paradigm shifts in swarm behavior and operations."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        beta_agent_id: str = "beta",
        steward_agent_id: str = "steward",
        min_shift_interval: timedelta = field(default_factory=lambda: timedelta(minutes=5)),
        max_shifts_per_hour: int = 10,
        indicator_threshold: int = 3,
        velocity_threshold: float = 2.0,
        confidence_threshold: float = 0.70,
    ):
        self._config = config or {}
        self._shifts: dict[str, ParadigmShift] = {}
        self._indicators: dict[str, list[ShiftIndicator]] = defaultdict(list)
        self._shift_history: list[ParadigmShift] = []
        self._min_shift_interval = min_shift_interval
        self._max_shifts_per_hour = max_shifts_per_hour
        self._recent_shift_times: list[datetime] = []
        self._indicator_threshold = indicator_threshold
        self._velocity_threshold = velocity_threshold
        self._confidence_threshold = confidence_threshold
        self._beta_agent_id = beta_agent_id
        self._steward_agent_id = steward_agent_id
        self._change_timestamps: list[datetime] = []
        self._change_types: list[str] = []
        self._on_shift_detected: Any = None
        self._on_shift_confirmed: Any = None
        self._on_false_positive: Any = None

    async def analyze_change_velocity(self) -> dict[str, Any]:
        """Analyze change velocity to detect rapid successive shifts."""
        now = datetime.now(UTC)
        self._change_timestamps = [
            ts for ts in self._change_timestamps if now - ts < timedelta(hours=1)
        ]
        if len(self._change_timestamps) < 2:
            return {
                "velocity": 0.0,
                "is_rapid": False,
                "cluster_type": None,
                "recommendation": "normal",
            }
        time_span = (now - self._change_timestamps[0]).total_seconds() / 60
        velocity = len(self._change_timestamps) / max(time_span, 1.0)
        is_rapid = velocity >= self._velocity_threshold
        return {
            "velocity": velocity,
            "is_rapid": is_rapid,
            "cluster_type": None,
            "recommendation": "rate_limit" if is_rapid else "normal",
        }

    async def record_change(self, change: ChangeRequest) -> None:
        """Record a change for velocity tracking."""
        self._change_timestamps.append(datetime.now(UTC))
        self._change_types.append(change.change_type.value)
        await self._check_shift_indicators(change)

    async def _check_shift_indicators(self, change: ChangeRequest) -> None:
        """Check if a change contributes to paradigm shift indicators."""
        indicators = self._extract_indicators_from_change(change)
        for indicator in indicators:
            self._indicators[indicator.shift_type.value].append(indicator)
            if len(self._indicators[indicator.shift_type.value]) >= self._indicator_threshold:
                shift_type = indicator.shift_type
                await self._evaluate_shift(shift_type)

    def _extract_indicators_from_change(self, change: ChangeRequest) -> list[ShiftIndicator]:
        """Extract paradigm shift indicators from a change request."""
        indicators = []
        type_mapping = {
            ChangeType.DEPLOYMENT: ShiftType.TECHNOLOGICAL,
            ChangeType.UPGRADE: ShiftType.TECHNOLOGICAL,
            ChangeType.MIGRATION: ShiftType.ARCHITECTURAL,
            ChangeType.CONFIGURATION: ShiftType.OPERATIONAL,
            ChangeType.PATCH: ShiftType.TECHNOLOGICAL,
        }
        shift_type = type_mapping.get(change.change_type)
        if not shift_type:
            return indicators
        indicator = ShiftIndicator(
            indicator_id=f"ind_{uuid.uuid4().hex[:12]}",
            shift_type=shift_type,
            description=f"Change pattern: {change.change_type.value} on {change.affected_components}",
            occurrences=1,
            agents_involved={change.requested_by},
            affected_components=change.affected_components,
            confidence_boost=self._calculate_indicator_boost(change),
        )
        indicators.append(indicator)
        if len(self._get_agents_for_component(change.affected_components)) >= 3:
            behavioral = ShiftIndicator(
                indicator_id=f"ind_{uuid.uuid4().hex[:12]}",
                shift_type=ShiftType.BEHAVIORAL,
                description=f"Multi-agent coordination on {change.affected_components}",
                occurrences=1,
                agents_involved=self._get_agents_for_component(change.affected_components),
                affected_components=change.affected_components,
                confidence_boost=0.15,
            )
            indicators.append(behavioral)
        return indicators

    def _calculate_indicator_boost(self, change: ChangeRequest) -> float:
        """Calculate confidence boost for an indicator."""
        boost = 0.1
        if len(change.affected_components) > 5:
            boost += 0.1
        return min(boost, 0.3)

    def _get_agents_for_component(self, components: list[str]) -> set[str]:
        """Get agents that have worked on components."""
        agents = set()
        for indicator_list in self._indicators.values():
            for ind in indicator_list:
                if any(c in ind.affected_components for c in components):
                    agents.update(ind.agents_involved)
        return agents

    async def _evaluate_shift(self, shift_type: ShiftType) -> ParadigmShift | None:
        """Evaluate if indicators constitute a paradigm shift."""
        indicators = self._indicators.get(shift_type.value, [])
        if len(indicators) < self._indicator_threshold:
            return None
        confidence = self._calculate_shift_confidence(indicators)
        magnitude = self._calculate_shift_magnitude(indicators)
        shift = ParadigmShift(
            shift_id=f"shift_{uuid.uuid4().hex[:12]}",
            shift_type=shift_type,
            magnitude=magnitude,
            confidence=confidence,
            indicators=indicators,
            affected_components=self._get_affected_components(indicators),
            impacted_agents=list(self._get_impacted_agents(indicators)),
            impact_score=self._calculate_impact_score(indicators),
        )
        self._shifts[shift.shift_id] = shift
        if await self._is_rate_limited(shift):
            return shift
        if shift.magnitude in (ShiftMagnitude.MAJOR, ShiftMagnitude.CRITICAL):
            await self._notify_core_triad(shift)
        return shift

    def _calculate_shift_confidence(self, indicators: list[ShiftIndicator]) -> ShiftConfidence:
        """Calculate confidence level from indicators."""
        if not indicators:
            return ShiftConfidence.SPECULATIVE
        total_boost = sum(i.confidence_boost for i in indicators)
        total_occurrences = sum(i.occurrences for i in indicators)
        recurrence_factor = min(total_occurrences / 10, 0.2)
        all_agents = set()
        for i in indicators:
            all_agents.update(i.agents_involved)
        diversity_factor = min(len(all_agents) / 10, 0.15)
        confidence_score = min(1.0, total_boost + recurrence_factor + diversity_factor)
        if confidence_score < 0.50:
            return ShiftConfidence.SPECULATIVE
        if confidence_score < 0.70:
            return ShiftConfidence.POSSIBLE
        if confidence_score < 0.85:
            return ShiftConfidence.LIKELY
        if confidence_score < 0.95:
            return ShiftConfidence.PROBABLE
        return ShiftConfidence.CONFIRMED

    def _calculate_shift_magnitude(self, indicators: list[ShiftIndicator]) -> ShiftMagnitude:
        """Calculate magnitude based on indicators."""
        total_occurrences = sum(i.occurrences for i in indicators)
        affected_count = len({c for i in indicators for c in i.affected_components})
        if total_occurrences >= 10 and affected_count >= 10:
            return ShiftMagnitude.CRITICAL
        if total_occurrences >= 5 and affected_count >= 5:
            return ShiftMagnitude.MAJOR
        if total_occurrences >= 3:
            return ShiftMagnitude.MODERATE
        return ShiftMagnitude.MINOR

    def _get_affected_components(self, indicators: list[ShiftIndicator]) -> list[str]:
        """Get all affected components from indicators."""
        return list({c for i in indicators for c in i.affected_components})

    def _get_impacted_agents(self, indicators: list[ShiftIndicator]) -> set[str]:
        """Get all impacted agents from indicators."""
        return {a for i in indicators for a in i.agents_involved}

    def _calculate_impact_score(self, indicators: list[ShiftIndicator]) -> float:
        """Calculate impact score based on indicators."""
        base_score = len(indicators) * 0.1
        component_factor = len(self._get_affected_components(indicators)) * 0.05
        agent_factor = len(self._get_impacted_agents(indicators)) * 0.03
        return min(1.0, base_score + component_factor + agent_factor)

    async def _is_rate_limited(self, _shift: ParadigmShift) -> bool:
        """Check if a shift should be rate-limited."""
        now = datetime.now(UTC)
        if self._recent_shift_times:
            last_shift = self._recent_shift_times[-1]
            if now - last_shift < self._min_shift_interval:
                return True
        self._recent_shift_times = [
            ts for ts in self._recent_shift_times if now - ts < timedelta(hours=1)
        ]
        if len(self._recent_shift_times) >= self._max_shifts_per_hour:
            return True
        self._recent_shift_times.append(now)
        return False

    async def get_cumulative_impact(self, shift_id: str) -> dict[str, Any]:
        """Calculate cumulative impact of related shifts."""
        shift = self._shifts.get(shift_id)
        if not shift:
            return {"cumulative_impact": 0.0, "related_shifts": []}
        related = []
        now = datetime.now(UTC)
        for other_id, other in self._shifts.items():
            if other_id == shift_id:
                continue
            if other.shift_type != shift.shift_type:
                continue
            if (now - other.first_detected) > timedelta(hours=1):
                continue
            related.append(other_id)
        total_impact = shift.impact_score
        for related_id in related:
            related_shift = self._shifts[related_id]
            total_impact += related_shift.impact_score * 0.5
        cumulative = min(1.0, total_impact)
        shift.cumulative_impact = cumulative
        shift.related_shifts = related
        return {
            "cumulative_impact": cumulative,
            "related_shifts": related,
            "is_significant": cumulative > 0.7,
        }

    async def _notify_core_triad(self, shift: ParadigmShift) -> None:
        """Notify Core Triad (Steward) of high-magnitude shift."""
        shift.core_triad_notified = True

    async def trigger_validation(self, shift: ParadigmShift) -> str:
        """Trigger Beta validation for a detected shift."""
        shift.status = ShiftStatus.VALIDATING
        shift.validation_beta = self._beta_agent_id
        return f"val_{uuid.uuid4().hex[:12]}"

    async def handle_validation_result(
        self,
        shift_id: str,
        is_false_positive: bool,
        validation_details: dict[str, Any] | None = None,
    ) -> None:
        """Handle result from Beta validation."""
        shift = self._shifts.get(shift_id)
        if not shift:
            return
        if is_false_positive:
            shift.status = ShiftStatus.FALSE_POSITIVE
            shift.resolution_notes = (
                f"Beta validation: {validation_details.get('reason', 'False positive')}"
            )
            if self._on_false_positive:
                self._on_false_positive(shift)
        else:
            shift.status = ShiftStatus.CONFIRMED

    async def trigger_deliberation(self, shift: ParadigmShift) -> str:
        """Trigger deliberation for ambiguous shifts."""
        shift.status = ShiftStatus.ESCALATED
        shift.deliberation_id = f"delib_{uuid.uuid4().hex[:12]}"
        return shift.deliberation_id
