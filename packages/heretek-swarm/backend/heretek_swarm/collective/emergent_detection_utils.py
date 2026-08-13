from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from heretek_swarm.research.emergent_detection_types import (
    EmergenceLevel,
    EmergentPatternClass,
    PatternProvenance,
)

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from heretek_swarm.research.emergent_detection import (
        AgentBehaviorSnapshot,
        CollectiveBehavior,
        EmergentPattern,
    )


def calculate_window_metrics(window: list[AgentBehaviorSnapshot]) -> dict[str, float]:
    """Calculate metrics for a temporal window of agent snapshots."""
    if not window:
        return {}

    return {
        "avg_success_rate": sum(s.success_rate for s in window) / len(window),
        "avg_interaction_count": sum(s.interaction_count for s in window) / len(window),
        "unique_agents": len({s.agent_id for s in window}),
        "total_interactions": sum(s.interaction_count for s in window),
    }


def analyze_temporal_windows(
    agent_snapshots: dict[str, list[AgentBehaviorSnapshot]],
    window_size_seconds: float,
) -> list[list[AgentBehaviorSnapshot]]:
    """Divide agent snapshots into temporal windows."""
    all_snapshots = []
    for snapshots in agent_snapshots.values():
        all_snapshots.extend(snapshots)

    if not all_snapshots:
        return []

    sorted_snapshots = sorted(all_snapshots, key=lambda s: datetime.fromisoformat(s.timestamp))

    windows = []
    current_window = []
    window_start = datetime.fromisoformat(sorted_snapshots[0].timestamp)

    for snapshot in sorted_snapshots:
        snapshot_time = datetime.fromisoformat(snapshot.timestamp)

        if (snapshot_time - window_start).total_seconds() <= window_size_seconds:
            current_window.append(snapshot)
        else:
            windows.append(current_window)
            current_window = [snapshot]
            window_start = snapshot_time

    if current_window:
        windows.append(current_window)

    return windows


def calculate_shift_score(
    prev_metrics: dict[str, float],
    curr_metrics: dict[str, float],
) -> float:
    """Calculate the shift score between two metric sets."""
    if not prev_metrics or not curr_metrics:
        return 0.0

    shifts = []
    for key in prev_metrics:
        if key in curr_metrics and prev_metrics[key] != 0:
            change = abs(curr_metrics[key] - prev_metrics[key]) / prev_metrics[key]
            shifts.append(change)

    if not shifts:
        return 0.0

    return sum(shifts) / len(shifts)


def classify_emergence_level(score: float) -> EmergenceLevel:
    """Classify the emergence level based on score."""
    if score >= 0.8:
        return EmergenceLevel.CRITICAL
    if score >= 0.6:
        return EmergenceLevel.STRONG
    if score >= 0.4:
        return EmergenceLevel.MODERATE
    return EmergenceLevel.WEAK


def measure_collective_capability(behaviors: list[CollectiveBehavior]) -> float:
    """Measure collective capability from behaviors."""
    if not behaviors:
        return 0.0

    weighted_sum = sum(b.coherence * b.intensity for b in behaviors)
    return weighted_sum / len(behaviors)


def calculate_temporal_span(behaviors: list[CollectiveBehavior]) -> float:
    """Calculate the temporal span of behaviors in seconds."""
    if not behaviors:
        return 0.0

    times = []
    for b in behaviors:
        times.append(datetime.fromisoformat(b.start_time))
        if b.end_time:
            times.append(datetime.fromisoformat(b.end_time))

    if len(times) < 2:
        return 0.0

    return (max(times) - min(times)).total_seconds()


def calculate_statistical_significance(pattern: EmergentPattern) -> float:
    """Calculate statistical significance of an emergent pattern."""
    n_agents = len(pattern.participating_agents)
    emergence_score = pattern.emergence_score

    significance = 1.0 / (n_agents * (1.0 - emergence_score + 0.01))
    return min(significance, 1.0)


def calculate_confidence(pattern: EmergentPattern) -> float:
    """Calculate confidence score for an emergent pattern."""
    factors = []
    factors.append(pattern.emergence_score)
    agent_factor = min(len(pattern.participating_agents) / 10.0, 1.0)
    factors.append(agent_factor)
    factors.append(1.0 if pattern.is_validated else 0.5)
    ratio_factor = min(pattern.emergence_ratio / 2.0, 1.0) if pattern.emergence_ratio > 0 else 0
    factors.append(ratio_factor)

    return sum(factors) / len(factors)


def calculate_impact_score(pattern: EmergentPattern) -> float:
    """Calculate impact score for an emergent pattern."""
    level_impact = {
        EmergenceLevel.WEAK: 0.2,
        EmergenceLevel.MODERATE: 0.4,
        EmergenceLevel.STRONG: 0.6,
        EmergenceLevel.CRITICAL: 0.8,
    }
    base_impact = level_impact.get(pattern.emergence_level, 0.2)

    positive_patterns = [
        EmergentPatternClass.COORDINATION,
        EmergentPatternClass.OPTIMIZATION,
        EmergentPatternClass.INNOVATION,
        EmergentPatternClass.SELF_ORGANIZATION,
        EmergentPatternClass.ADAPTATION,
    ]

    negative_patterns = [
        EmergentPatternClass.CASCADE,
        EmergentPatternClass.PHASE_TRANSITION,
    ]

    if pattern.pattern_class in positive_patterns:
        class_modifier = 1.0
    elif pattern.pattern_class in negative_patterns:
        class_modifier = -0.5
    elif pattern.pattern_class == EmergentPatternClass.RESONANCE:
        if pattern.emergence_ratio > 1.5:
            class_modifier = 0.8
        elif pattern.emergence_ratio < 0.5:
            class_modifier = -0.3
        else:
            class_modifier = 0.3
    else:
        class_modifier = 0.0

    confidence_modifier = pattern.confidence * 0.2
    frequency_modifier = min(0.2, pattern.frequency * 0.02)

    impact = (base_impact * class_modifier) + confidence_modifier + frequency_modifier
    return max(-1.0, min(1.0, impact))


def generate_recommended_action(pattern: EmergentPattern) -> str | None:
    """Generate recommended action based on impact score."""
    impact_score = calculate_impact_score(pattern)

    if impact_score >= 0.7:
        return "REINFORCE: High-value emergent pattern detected. Consider reinforcing conditions that enabled this behavior."
    if impact_score >= 0.3:
        return "MONITOR: Beneficial pattern detected. Document conditions for future replication."
    if impact_score >= -0.3:
        return "OBSERVE: Neutral emergence. Continue monitoring for changes."
    if impact_score >= -0.7:
        return "INVESTIGATE: Potentially harmful pattern. Analyze root causes and consider intervention."
    return "ALERT: Harmful emergent pattern detected. Immediate intervention recommended."


def calculate_novelty_score(
    pattern: EmergentPattern,
    historical_patterns: list[EmergentPattern],
) -> float:
    """
    Calculate novelty score for an emergent pattern.

    Novelty is measured by comparing the candidate pattern against
    historical patterns based on:
    - Pattern class diversity in history
    - Agent overlap (shared agents reduce novelty)
    - Emergence level difference from average historical level
    - Whether an identical or near-identical pattern was seen before

    Returns a float in [0.0, 1.0] where 1.0 = maximally novel.
    """
    if not historical_patterns:
        # No history = maximally novel
        return 1.0

    novelty_factors: list[float] = []

    # Factor 1: Pattern class diversity
    # New class = higher novelty
    historical_classes = {p.pattern_class for p in historical_patterns}
    class_novelty = 0.5 if pattern.pattern_class in historical_classes else 1.0
    novelty_factors.append(class_novelty)

    # Factor 2: Agent overlap
    # Fewer overlapping agents = higher novelty
    historical_agents: set[str] = set()
    for p in historical_patterns:
        historical_agents.update(p.involved_agents)

    if historical_agents:
        overlap = len(set(pattern.involved_agents) & historical_agents)
        total = len(pattern.involved_agents)
        if total > 0:
            overlap_ratio = overlap / total
            agent_novelty = 1.0 - overlap_ratio
        else:
            agent_novelty = 1.0
    else:
        agent_novelty = 1.0
    novelty_factors.append(agent_novelty)

    # Factor 3: Emergence level divergence from historical average
    avg_level_score = {
        EmergenceLevel.WEAK: 0.2,
        EmergenceLevel.MODERATE: 0.5,
        EmergenceLevel.STRONG: 0.7,
        EmergenceLevel.CRITICAL: 0.9,
    }
    pattern_level = avg_level_score.get(pattern.emergence_level, 0.0)
    hist_avg = sum(avg_level_score.get(p.emergence_level, 0.0) for p in historical_patterns) / len(
        historical_patterns
    )
    level_divergence = abs(pattern_level - hist_avg)
    novelty_factors.append(level_divergence)

    # Factor 4: Whether a very similar pattern (same class + overlapping agents) was recently seen
    # Check last 10 patterns
    recent = historical_patterns[-10:]
    very_similar = any(
        p.pattern_class == pattern.pattern_class
        and len(set(p.involved_agents) & set(pattern.involved_agents))
        >= len(pattern.involved_agents) * 0.8
        for p in recent
    )
    recency_novelty = 0.0 if very_similar else 1.0
    novelty_factors.append(recency_novelty)

    return sum(novelty_factors) / len(novelty_factors)


def classify_pattern_provenance(
    novelty_score: float,
    validation_rate: float,
    novelty_threshold: float = 0.5,
    validation_threshold: float = 0.6,
) -> PatternProvenance:
    """
    Classify a pattern as PROVEN or UNPROVEN.

    A pattern is PROVEN when it has sufficient novelty AND sufficient
    validation rate. Both conditions must be met.

    Args:
        novelty_score: Score from 0.0 (identical to history) to 1.0 (completely novel)
        validation_rate: Fraction of validations that passed [0.0, 1.0]
        novelty_threshold: Minimum novelty to be considered proven (default 0.5)
        validation_threshold: Minimum validation rate to be considered proven (default 0.6)

    Returns:
        PatternProvenance.PROVEN if both thresholds are met, else UNPROVEN
    """
    if novelty_score >= novelty_threshold and validation_rate >= validation_threshold:
        return PatternProvenance.PROVEN
    return PatternProvenance.UNPROVEN


def _compute_problem_novelty(
    problem_signature: dict[str, Any],
    historical_patterns: list[EmergentPattern],
) -> float:
    """Compute problem novelty factor for solution novelty."""
    historical_signatures = [p.evidence.get("problem_signature", {}) for p in historical_patterns]
    if not historical_signatures:
        return 1.0
    signature_diffs = [
        _calculate_signature_difference(problem_signature, hs) for hs in historical_signatures
    ]
    return sum(signature_diffs) / len(signature_diffs)


def _compute_approach_novelty(
    approach_used: str,
    historical_patterns: list[EmergentPattern],
) -> float:
    """Compute approach novelty factor for solution novelty."""
    if not approach_used:
        return 0.5
    historical_approaches = [p.evidence.get("approach_used", "") for p in historical_patterns]
    total = len(historical_approaches)
    if total == 0:
        return 1.0
    seen_count = sum(1 for a in historical_approaches if a == approach_used)
    approach_frequency = seen_count / total
    return 1.0 - approach_frequency


def _compute_result_novelty(
    actual_performance: float,
    expected_performance: float | None,
    historical_patterns: list[EmergentPattern],
) -> float:
    """Compute result novelty factor for solution novelty."""
    if expected_performance is not None and expected_performance > 0:
        performance_ratio = actual_performance / expected_performance
        performance_ratio = max(0.0, min(performance_ratio, 3.0))
        if performance_ratio > 1.0:
            return min(performance_ratio - 1.0, 1.0)
        return 0.0
    # No baseline — compare against historical average impact
    hist_avg = sum(p.impact_score for p in historical_patterns) / len(historical_patterns)
    if hist_avg > 0:
        impact_ratio = actual_performance / hist_avg
        return min(max(impact_ratio - 1.0, 0.0), 1.0)
    return 0.5


def calculate_solution_novelty(
    pattern: EmergentPattern,
    historical_patterns: list[EmergentPattern],
    problem_signature: dict[str, Any] | None = None,
    approach_used: str | None = None,
    expected_performance: float | None = None,
) -> float:
    """
    Calculate solution novelty score measuring outcome novelty.

    Solution novelty distinguishes outcome novelty from pattern novelty.
    While pattern novelty measures whether a method emerged (pattern formation),
    solution novelty measures whether the solution itself is unique.

    Three factors determine solution novelty:
    - problem_novelty: Is the problem signature different from prior solutions?
    - approach_novelty: Is the solution method different from programmed baselines?
    - result_novelty: Does the outcome exceed expected performance?

    Returns a float in [0.0, 1.0] where 1.0 = maximally novel solution.

    Args:
        pattern: The emergent pattern with solution data
        historical_patterns: Prior solutions for comparison
        problem_signature: Dict representing the problem characteristics
        approach_used: String identifier of the solution approach/method
        expected_performance: Baseline performance to compare against

    Returns:
        Float in [0.0, 1.0] representing solution novelty
    """
    if not historical_patterns:
        # No history = maximally novel
        return 1.0

    problem_sig = (
        problem_signature
        if problem_signature is not None
        else pattern.evidence.get("problem_signature", {})
    )
    approach = (
        approach_used if approach_used is not None else pattern.evidence.get("approach_used", "")
    )
    expected_perf = (
        expected_performance
        if expected_performance is not None
        else pattern.evidence.get("expected_performance", None)
    )

    novelty_factors: list[float] = []
    novelty_factors.append(_compute_problem_novelty(problem_sig, historical_patterns))
    novelty_factors.append(_compute_approach_novelty(approach, historical_patterns))
    novelty_factors.append(
        _compute_result_novelty(pattern.impact_score, expected_perf, historical_patterns)
    )

    return sum(novelty_factors) / len(novelty_factors)


def _diff_value_pair(v1: Any, v2: Any) -> float:
    """Compute diff for a single key-value pair in signature comparison."""
    if v1 == v2:
        return 0.0
    if v1 is None or v2 is None:
        return 1.0
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        max_val = max(abs(v1), abs(v2), 1.0)
        return min(abs(v1 - v2) / max_val, 1.0)
    if isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
        max_len = max(len(v1), len(v2), 1)
        common = sum(1 for a, b in zip(v1, v2, strict=True) if a == b)
        return 1.0 - (common / max_len)
    return 1.0


def _calculate_signature_difference(
    sig1: dict[str, Any],
    sig2: dict[str, Any],
) -> float:
    """Calculate difference between two problem signatures [0.0, 1.0]."""
    if not sig1 and not sig2:
        return 0.0
    if not sig1 or not sig2:
        return 1.0

    # Get all keys from both signatures
    all_keys = set(sig1.keys()) | set(sig2.keys())
    if not all_keys:
        return 0.0

    differences = []
    for key in all_keys:
        v1 = sig1.get(key)
        v2 = sig2.get(key)
        differences.append(_diff_value_pair(v1, v2))

    return sum(differences) / len(differences)


def classify_solution_provenance(
    solution_novelty: float,
    validation_rate: float,
    solution_threshold: float = 0.5,
    validation_threshold: float = 0.6,
) -> PatternProvenance:
    """
    Classify a solution as PROVEN or UNPROVEN based on novelty.

    This mirrors classify_pattern_provenance but uses a distinct threshold
    parameter (solution_threshold) for configuration flexibility.
    Threshold alignment is a stakeholder decision - the appropriate threshold
    depends on how conservative vs permissive the validation should be.

    A solution is PROVEN when it has sufficient novelty AND sufficient
    validation rate. Both conditions must be met.

    Args:
        solution_novelty: Score from 0.0 (identical to history) to 1.0 (completely novel)
        validation_rate: Fraction of validations that passed [0.0, 1.0]
        solution_threshold: Minimum novelty to be considered proven (default 0.5)
            Note: This threshold is a stakeholder decision - higher values
            require more novel solutions, lower values are more permissive
        validation_threshold: Minimum validation rate to be considered proven (default 0.6)

    Returns:
        PatternProvenance.PROVEN if both thresholds are met, else UNPROVEN
    """
    if solution_novelty >= solution_threshold and validation_rate >= validation_threshold:
        return PatternProvenance.PROVEN
    return PatternProvenance.UNPROVEN
