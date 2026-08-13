"""Introspection Module - Self-Model Belief/Goal Tracking with Organic Evolution

This module provides introspection capabilities for the self-model, enabling:
- Organic evolution of beliefs based on evidence accumulation
- Confidence decay/growth mechanisms
- Goal priority evolution based on system state
- Conflict detection and resolution suggestions
- Introspection reporting

Author: Heretek Swarm Collective
Date: 2026-04-10
Version: 1.0.0
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

from .self_model import Belief, Goal, GoalStatus, SelfModel

logger = structlog.get_logger("IntrospectionModule")


class ConflictResolutionStrategy(Enum):
    """Strategies for resolving conflicting beliefs."""

    CONFIDENCE_BASED = "confidence_based"  # Higher confidence belief prevails
    EVIDENCE_BASED = "evidence_based"  # More evidence supports the belief
    RECENCY_BASED = "recency_based"  # More recently updated belief prevails
    AVERAGE = "average"  # Average the confidence values


@dataclass
class BeliefEvolutionRecord:
    """Tracks the evolution history of a belief."""

    belief_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    old_confidence: float = 0.0
    new_confidence: float = 0.0
    evidence_count: int = 0
    reason: str = "update"

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief_id": self.belief_id,
            "timestamp": self.timestamp,
            "old_confidence": self.old_confidence,
            "new_confidence": self.new_confidence,
            "evidence_count": self.evidence_count,
            "reason": self.reason,
        }


@dataclass
class GoalEvolutionRecord:
    """Tracks the evolution history of a goal."""

    goal_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    old_priority: float = 0.0
    new_priority: float = 0.0
    old_progress: float = 0.0
    new_progress: float = 0.0
    old_status: str = ""
    new_status: str = ""
    reason: str = "update"

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "timestamp": self.timestamp,
            "old_priority": self.old_priority,
            "new_priority": self.new_priority,
            "old_progress": self.old_progress,
            "new_progress": self.new_progress,
            "old_status": self.old_status,
            "new_status": self.new_status,
            "reason": self.reason,
        }


@dataclass
class BeliefInsight:
    """Insight about a belief's state."""

    belief_id: str
    state: str
    confidence: float
    confidence_trend: str  # "increasing", "decreasing", "stable"
    age_seconds: float
    update_frequency: float  # updates per day
    evidence_quality: str  # "strong", "moderate", "weak"
    has_conflicts: bool
    conflict_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief_id": self.belief_id,
            "state": self.state,
            "confidence": self.confidence,
            "confidence_trend": self.confidence_trend,
            "age_seconds": self.age_seconds,
            "update_frequency": self.update_frequency,
            "evidence_quality": self.evidence_quality,
            "has_conflicts": self.has_conflicts,
            "conflict_count": self.conflict_count,
        }


@dataclass
class ConflictPair:
    """Represents a pair of conflicting beliefs."""

    belief_1_id: str
    belief_2_id: str
    belief_1_state: str
    belief_2_state: str
    belief_1_confidence: float
    belief_2_confidence: float
    resolution_suggestion: str
    resolution_strategy: ConflictResolutionStrategy

    def to_dict(self) -> dict[str, Any]:
        return {
            "belief_1_id": self.belief_1_id,
            "belief_2_id": self.belief_2_id,
            "belief_1_state": self.belief_1_state,
            "belief_2_state": self.belief_2_state,
            "belief_1_confidence": self.belief_1_confidence,
            "belief_2_confidence": self.belief_2_confidence,
            "resolution_suggestion": self.resolution_suggestion,
            "resolution_strategy": self.resolution_strategy.value,
        }


@dataclass
class IntrospectionReport:
    """Complete introspection report of the self-model."""

    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    agent_id: str = ""
    belief_count: int = 0
    goal_count: int = 0
    beliefs: list[dict[str, Any]] = field(default_factory=list)
    goals: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    confidence_distribution: dict[str, int] = field(default_factory=dict)
    goal_status_distribution: dict[str, int] = field(default_factory=dict)
    evolution_history: list[dict[str, Any]] = field(default_factory=list)
    insights: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "belief_count": self.belief_count,
            "goal_count": self.goal_count,
            "beliefs": self.beliefs,
            "goals": self.goals,
            "conflicts": self.conflicts,
            "confidence_distribution": self.confidence_distribution,
            "goal_status_distribution": self.goal_status_distribution,
            "evolution_history": self.evolution_history,
            "insights": self.insights,
        }


class IntrospectionModule:
    """Introspection Module for Self-Model Belief/Goal Tracking.

    This module provides mechanisms for:
    - Organic evolution of beliefs based on evidence
    - Confidence decay/growth over time
    - Goal priority evolution
    - Conflict detection and resolution
    - Introspection reporting
    """

    # Configuration constants
    CONFIDENCE_DECAY_RATE = 0.01  # Per day decay rate for beliefs without evidence
    CONFIDENCE_GROWTH_RATE = 0.05  # Confidence increase per strong evidence
    CONFIDENCE_MIN = 0.01
    CONFIDENCE_MAX = 0.99
    EVIDENCE_HALF_LIFE_DAYS = 30  # Evidence weight halves after this period
    MAX_EVOLUTION_HISTORY = 500
    BELIEF_AGE_WEIGHT = 0.1  # Weight given to belief age in confidence calculation

    def __init__(self, self_model: SelfModel):
        """Initialize the IntrospectionModule.

        Args:
            self_model: The SelfModel instance to introspect.
        """
        self.self_model = self_model
        self._belief_evolution_history: list[BeliefEvolutionRecord] = []
        self._goal_evolution_history: list[GoalEvolutionRecord] = []
        self._belief_update_counts: dict[str, int] = {}
        self._belief_last_update: dict[str, datetime] = {}
        self._belief_initial_time: dict[str, datetime] = {}

        # Initialize tracking for existing beliefs
        for belief_id, belief in self_model.beliefs.items():
            self._belief_update_counts[belief_id] = 0
            try:
                self._belief_initial_time[belief_id] = datetime.fromisoformat(belief.created_at)
            except (ValueError, TypeError):
                self._belief_initial_time[belief_id] = datetime.now(UTC)

        logger.info(
            "IntrospectionModule initialized",
            extra={
                "agent_id": self_model.agent_id,
                "tracked_beliefs": len(self._belief_update_counts),
            },
        )

    def reflect_on_beliefs(self) -> dict[str, Any]:
        """Analyze current belief state and return insights.

        Returns:
            Dictionary containing:
            - confidence_distribution: Count of beliefs in confidence ranges
            - insights: List of BeliefInsight objects
            - average_confidence: Mean confidence across all beliefs
            - confidence_variance: Variance in confidence values
            - evidence_quality_summary: Summary of evidence quality across beliefs
        """
        now = datetime.now(UTC)
        insights: list[BeliefInsight] = []
        confidence_distribution = {
            "very_low": 0,
            "low": 0,
            "moderate": 0,
            "high": 0,
            "very_high": 0,
        }
        evidence_quality_summary = {"strong": 0, "moderate": 0, "weak": 0}

        confidences = []

        for belief in self.self_model.beliefs.values():
            confidences.append(belief.confidence)

            # Calculate confidence distribution
            if belief.confidence < 0.2:
                confidence_distribution["very_low"] += 1
            elif belief.confidence < 0.4:
                confidence_distribution["low"] += 1
            elif belief.confidence < 0.6:
                confidence_distribution["moderate"] += 1
            elif belief.confidence < 0.8:
                confidence_distribution["high"] += 1
            else:
                confidence_distribution["very_high"] += 1

            # Calculate belief age
            initial_time = self._belief_initial_time.get(belief.belief_id, now)
            age_seconds = (now - initial_time).total_seconds()

            # Calculate update frequency (updates per day)
            update_count = self._belief_update_counts.get(belief.belief_id, 0)
            age_days = age_seconds / 86400 if age_seconds > 0 else 1
            update_frequency = update_count / age_days if age_days > 0 else update_count

            # Determine confidence trend
            trend = self._get_confidence_trend(belief.belief_id)

            # Assess evidence quality
            evidence_quality = self._assess_evidence_quality(belief)
            if evidence_quality == "strong":
                evidence_quality_summary["strong"] += 1
            elif evidence_quality == "moderate":
                evidence_quality_summary["moderate"] += 1
            else:
                evidence_quality_summary["weak"] += 1

            # Check for conflicts
            has_conflicts = len(belief.conflicting_beliefs) > 0

            insight = BeliefInsight(
                belief_id=belief.belief_id,
                state=belief.state,
                confidence=belief.confidence,
                confidence_trend=trend,
                age_seconds=age_seconds,
                update_frequency=update_frequency,
                evidence_quality=evidence_quality,
                has_conflicts=has_conflicts,
                conflict_count=len(belief.conflicting_beliefs),
            )
            insights.append(insight)

        # Calculate statistics
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        confidence_variance = (
            sum((c - avg_confidence) ** 2 for c in confidences) / len(confidences)
            if len(confidences) > 1
            else 0.0
        )

        result = {
            "confidence_distribution": confidence_distribution,
            "insights": [i.to_dict() for i in insights],
            "average_confidence": avg_confidence,
            "confidence_variance": confidence_variance,
            "evidence_quality_summary": evidence_quality_summary,
            "total_beliefs": len(self.self_model.beliefs),
            "beliefs_with_conflicts": sum(1 for i in insights if i.has_conflicts),
        }

        logger.debug("Belief reflection completed", extra={"insight_count": len(insights)})
        return result

    def update_belief_from_outcome(
        self,
        belief_id: str,
        outcome: dict[str, Any],
        evidence: dict[str, Any],
    ) -> Belief | None:
        """Update belief confidence based on observed outcomes.

        Args:
            belief_id: The ID of the belief to update.
            outcome: Dictionary containing outcome data with keys:
                - success: bool indicating if outcome matched belief prediction
                - actual_value: Optional actual observed value
                - expected_value: Optional expected value based on belief
            evidence: Dictionary containing evidence data with keys:
                - source: str describing evidence source
                - strength: float 0-1 indicating evidence strength
                - timestamp: Optional ISO format timestamp
                - details: Optional additional details

        Returns:
            Updated Belief object, or None if belief not found.
        """
        if belief_id not in self.self_model.beliefs:
            logger.warning("Belief not found", extra={"belief_id": belief_id})
            return None

        belief = self.self_model.beliefs[belief_id]
        old_confidence = belief.confidence

        # Calculate confidence adjustment based on outcome
        outcome_success = outcome.get("success", True)
        evidence_strength = evidence.get("strength", 0.5)

        # Base adjustment from outcome
        if outcome_success:
            # Positive outcome - increase confidence
            adjustment = self.CONFIDENCE_GROWTH_RATE * evidence_strength
        else:
            # Negative outcome - decrease confidence
            adjustment = -self.CONFIDENCE_GROWTH_RATE * evidence_strength

        # Apply evidence quality bonus
        evidence_quality = self._assess_evidence_quality(belief)
        if evidence_quality == "strong":
            adjustment *= 1.5
        elif evidence_quality == "weak":
            adjustment *= 0.5

        # Calculate new confidence with bounds
        new_confidence = max(
            self.CONFIDENCE_MIN, min(self.CONFIDENCE_MAX, old_confidence + adjustment)
        )

        # Record the evolution
        evolution_record = BeliefEvolutionRecord(
            belief_id=belief_id,
            old_confidence=old_confidence,
            new_confidence=new_confidence,
            evidence_count=len(belief.supporting_evidence) + 1,
            reason="outcome_update",
        )
        self._belief_evolution_history.append(evolution_record)
        self._trim_evolution_history()

        # Update belief
        belief.confidence = new_confidence
        belief.updated_at = datetime.now(UTC).isoformat()

        # Add evidence to supporting evidence
        evidence_source = evidence.get("source", "unknown")
        if evidence_source not in belief.supporting_evidence:
            belief.supporting_evidence.append(evidence_source)

        # Update tracking
        self._belief_update_counts[belief_id] = self._belief_update_counts.get(belief_id, 0) + 1
        self._belief_last_update[belief_id] = datetime.now(UTC)

        # Check for conflicts if confidence changed significantly
        if abs(new_confidence - old_confidence) > 0.2:
            self.self_model._detect_belief_conflict(belief, old_confidence)  # noqa: SLF001

        self.self_model._update_count += 1  # noqa: SLF001
        self.self_model._maybe_take_snapshot()  # noqa: SLF001

        logger.info(
            "Belief updated from outcome",
            extra={
                "belief_id": belief_id,
                "old_confidence": old_confidence,
                "new_confidence": new_confidence,
                "adjustment": adjustment,
            },
        )

        return belief

    def evolve_goals(self, current_state: dict[str, Any]) -> dict[str, Any]:
        """Update goal priorities and progress based on current system state."""
        updated_goals: list[str] = []
        priority_changes: dict[str, float] = {}
        status_changes: dict[str, tuple[str, str]] = {}
        new_blocked_goals: list[str] = []

        completed_tasks = set(current_state.get("completed_tasks", []))
        achievements = current_state.get("achievements", [])
        resources = current_state.get("resources", {})
        constraints = current_state.get("constraints", [])

        for goal_id, goal in self.self_model.goals.items():
            old_priority = goal.priority
            old_status = goal.status.value
            old_progress = goal.progress

            self._update_goal_progress(goal, completed_tasks)
            self._check_goal_completion(goal, goal_id, old_status, status_changes, updated_goals)
            self._adjust_priority_from_achievements(goal, achievements)
            self._check_constraint_blocks(goal, goal_id, old_status, constraints,
                                          status_changes, new_blocked_goals, updated_goals)
            self._adjust_priority_from_resources(goal, resources)
            self._record_goal_evolution(goal, goal_id, old_priority, old_status, old_progress,
                                        priority_changes, updated_goals)

        self._trim_evolution_history()

        result = {
            "updated_goals": updated_goals,
            "priority_changes": priority_changes,
            "status_changes": status_changes,
            "new_blocked_goals": new_blocked_goals,
            "total_active_goals": sum(
                1 for g in self.self_model.goals.values() if g.status == GoalStatus.ACTIVE
            ),
        }

        logger.info(
            "Goal evolution completed",
            extra={
                "updated_count": len(updated_goals),
                "priority_changes_count": len(priority_changes),
            },
        )
        return result

    def _update_goal_progress(self, goal: Goal, completed_tasks: set[str]) -> None:
        """Update goal progress based on completed tasks."""
        if goal.goal_id in completed_tasks or any(
            sg in completed_tasks for sg in goal.sub_goals
        ):
            goal.progress = min(1.0, goal.progress + 0.1)

    def _check_goal_completion(
        self, goal: Goal, goal_id: str, old_status: str,
        status_changes: dict[str, tuple[str, str]], updated_goals: list[str],
    ) -> None:
        """Check if goal should be marked completed."""
        if goal.progress >= 1.0 and goal.status != GoalStatus.COMPLETED:
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = datetime.now(UTC).isoformat()
            status_changes[goal_id] = (old_status, GoalStatus.COMPLETED.value)
            updated_goals.append(goal_id)

    def _adjust_priority_from_achievements(
        self, goal: Goal, achievements: list[str]
    ) -> None:
        """Adjust goal priority based on achievements."""
        goal_desc_lower = goal.description.lower()
        for achievement in achievements:
            if any(word in achievement.lower() for word in goal_desc_lower.split()):
                goal.priority = min(1.0, goal.priority + 0.05)

    def _check_constraint_blocks(
        self, goal: Goal, goal_id: str, old_status: str,
        constraints: list[str], status_changes: dict[str, tuple[str, str]],
        new_blocked_goals: list[str], updated_goals: list[str],
    ) -> None:
        """Check for blocking constraints and update goal status."""
        if not constraints:
            return

        goal_desc_lower = goal.description.lower()
        constraint_blocks = any(
            c.lower() in goal_desc_lower for c in constraints
        )

        if constraint_blocks and goal.status == GoalStatus.ACTIVE:
            goal.status = GoalStatus.BLOCKED
            goal.blocked_by.append("constraint")
            status_changes[goal_id] = (old_status, GoalStatus.BLOCKED.value)
            new_blocked_goals.append(goal_id)
            updated_goals.append(goal_id)
        elif not constraint_blocks and goal.status == GoalStatus.BLOCKED:
            goal.status = GoalStatus.ACTIVE
            if "constraint" in goal.blocked_by:
                goal.blocked_by.remove("constraint")
            status_changes[goal_id] = (old_status, GoalStatus.ACTIVE.value)
            updated_goals.append(goal_id)

    def _adjust_priority_from_resources(
        self, goal: Goal, resources: dict[str, Any]
    ) -> None:
        """Adjust goal priority based on resource availability."""
        if not resources:
            return
        resource_availability = sum(1 for v in resources.values() if v > 0.5) / max(
            1, len(resources)
        )
        if resource_availability > 0.8 and goal.priority < 0.7:
            goal.priority = min(1.0, goal.priority + 0.1)
        elif resource_availability < 0.3 and goal.priority > 0.3:
            goal.priority = max(0.0, goal.priority - 0.1)

    def _record_goal_evolution(
        self, goal: Goal, goal_id: str, old_priority: float, old_status: str,
        old_progress: float, priority_changes: dict[str, float],
        updated_goals: list[str],
    ) -> None:
        """Record goal evolution if changes occurred."""
        if goal.priority == old_priority and goal.status.value == old_status:
            return

        evolution_record = GoalEvolutionRecord(
            goal_id=goal_id,
            old_priority=old_priority,
            new_priority=goal.priority,
            old_progress=old_progress,
            new_progress=goal.progress,
            old_status=old_status,
            new_status=goal.status.value,
            reason="state_evolution",
        )
        self._goal_evolution_history.append(evolution_record)

        if goal.priority != old_priority:
            priority_changes[goal_id] = goal.priority - old_priority

        updated_goals.append(goal_id)

    def detect_conflicting_beliefs(
        self,
        strategy: ConflictResolutionStrategy = ConflictResolutionStrategy.CONFIDENCE_BASED,
    ) -> list[ConflictPair]:
        """Find beliefs with contradictory states.

        Args:
            strategy: The resolution strategy to use for suggestions.

        Returns:
            List of ConflictPair objects representing conflicting belief pairs.
        """
        conflicts: list[ConflictPair] = []
        belief_list = list(self.self_model.beliefs.values())

        for i, belief_1 in enumerate(belief_list):
            for belief_2 in belief_list[i + 1 :]:
                if self._are_beliefs_in_conflict(belief_1, belief_2):
                    resolution_suggestion, resolution_strategy = self._suggest_resolution(
                        belief_1, belief_2, strategy
                    )

                    conflict_pair = ConflictPair(
                        belief_1_id=belief_1.belief_id,
                        belief_2_id=belief_2.belief_id,
                        belief_1_state=belief_1.state,
                        belief_2_state=belief_2.state,
                        belief_1_confidence=belief_1.confidence,
                        belief_2_confidence=belief_2.confidence,
                        resolution_suggestion=resolution_suggestion,
                        resolution_strategy=resolution_strategy,
                    )
                    conflicts.append(conflict_pair)

                    # Update the beliefs' conflicting_beliefs lists
                    if belief_2.belief_id not in belief_1.conflicting_beliefs:
                        belief_1.conflicting_beliefs.append(belief_2.belief_id)
                    if belief_1.belief_id not in belief_2.conflicting_beliefs:
                        belief_2.conflicting_beliefs.append(belief_1.belief_id)

        logger.info("Conflict detection completed", extra={"conflict_count": len(conflicts)})

        return conflicts

    def track_goal_progress(self, goal_id: str, outcome: dict[str, Any]) -> bool:
        """Update specific goal progress based on outcomes.

        Args:
            goal_id: The ID of the goal to update.
            outcome: Dictionary containing outcome data with keys:
                - success: bool indicating if goal-related action succeeded
                - progress_delta: Optional float indicating progress change
                - completion: Optional bool indicating if goal was completed
                - blockers: Optional list of new blockers

        Returns:
            True if goal was updated, False if goal not found.
        """
        if goal_id not in self.self_model.goals:
            logger.warning("Goal not found", extra={"goal_id": goal_id})
            return False

        goal = self.self_model.goals[goal_id]
        old_progress = goal.progress
        old_status = goal.status
        old_priority = goal.priority

        # Apply progress delta
        progress_delta = outcome.get("progress_delta", 0.0)
        if progress_delta != 0:
            goal.progress = max(0.0, min(1.0, goal.progress + progress_delta))

        # Handle completion
        if outcome.get("completion", False) or goal.progress >= 1.0:
            goal.status = GoalStatus.COMPLETED
            goal.completed_at = datetime.now(UTC).isoformat()
            goal.progress = 1.0

            # Update parent goal progress if applicable
            if goal.parent_goal_id and goal.parent_goal_id in self.self_model.goals:
                self.self_model._update_parent_progress(goal.parent_goal_id)  # noqa: SLF001

            # Unblock dependent goals
            self.self_model._unblock_dependent_goals(goal_id)  # noqa: SLF001

        # Handle success/failure
        success = outcome.get("success")
        if success is not None:
            if success:
                # Positive outcome - slight priority boost
                goal.priority = min(1.0, goal.priority + 0.02)
            else:
                # Negative outcome - check if goal should be paused
                if goal.progress < 0.3:
                    goal.status = GoalStatus.PAUSED

        # Handle new blockers
        blockers = outcome.get("blockers", [])
        if blockers and goal.status != GoalStatus.COMPLETED:
            goal.status = GoalStatus.BLOCKED
            for blocker in blockers:
                if blocker not in goal.blocked_by:
                    goal.blocked_by.append(blocker)

        # Record evolution
        evolution_record = GoalEvolutionRecord(
            goal_id=goal_id,
            old_priority=old_priority,
            new_priority=goal.priority,
            old_progress=old_progress,
            new_progress=goal.progress,
            old_status=old_status.value,
            new_status=goal.status.value,
            reason="outcome_tracking",
        )
        self._goal_evolution_history.append(evolution_record)
        self._trim_evolution_history()

        self.self_model._update_count += 1  # noqa: SLF001
        self.self_model._maybe_take_snapshot()  # noqa: SLF001

        logger.info(
            "Goal progress tracked",
            extra={
                "goal_id": goal_id,
                "old_progress": old_progress,
                "new_progress": goal.progress,
                "new_status": goal.status.value,
            },
        )

        return True

    def get_introspection_report(self) -> IntrospectionReport:
        """Generate a complete introspection report.

        Returns:
            IntrospectionReport containing:
            - Current self-model state summary
            - List of all beliefs with confidence levels
            - List of all goals with progress
            - Detected conflicts
            - Evolution history (recent changes)
        """
        # Get belief insights
        belief_reflection = self.reflect_on_beliefs()

        # Detect conflicts
        conflicts = self.detect_conflicting_beliefs()

        # Build belief list
        beliefs = []
        for belief in self.self_model.beliefs.values():
            belief_data = belief.to_dict()
            belief_data["update_count"] = self._belief_update_counts.get(belief.belief_id, 0)
            belief_data["age_seconds"] = (
                datetime.now(UTC)
                - self._belief_initial_time.get(belief.belief_id, datetime.now(UTC))
            ).total_seconds()
            beliefs.append(belief_data)

        # Build goal list
        goals = [goal.to_dict() for goal in self.self_model.goals.values()]

        # Build goal status distribution
        goal_status_distribution: dict[str, int] = {}
        for goal in self.self_model.goals.values():
            status = goal.status.value
            goal_status_distribution[status] = goal_status_distribution.get(status, 0) + 1

        # Build evolution history
        evolution_history = []
        for record in self._belief_evolution_history[-50:]:
            evolution_history.append(record.to_dict())  # noqa: PERF401
        for record in self._goal_evolution_history[-50:]:
            evolution_history.append(record.to_dict())  # noqa: PERF401

        # Sort by timestamp
        evolution_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        report = IntrospectionReport(
            agent_id=self.self_model.agent_id,
            belief_count=len(self.self_model.beliefs),
            goal_count=len(self.self_model.goals),
            beliefs=beliefs,
            goals=goals,
            conflicts=[c.to_dict() for c in conflicts],
            confidence_distribution=belief_reflection["confidence_distribution"],
            goal_status_distribution=goal_status_distribution,
            evolution_history=evolution_history[:100],
            insights=belief_reflection["insights"][:50],
        )

        logger.info(
            "Introspection report generated",
            extra={
                "belief_count": report.belief_count,
                "goal_count": report.goal_count,
                "conflict_count": len(conflicts),
            },
        )

        return report

    def apply_confidence_decay(self, days_elapsed: float = 1.0) -> dict[str, float]:
        """Apply confidence decay to beliefs without recent evidence.

        Args:
            days_elapsed: Number of days to simulate decay for.

        Returns:
            Dictionary mapping belief_id to confidence change.
        """
        changes: dict[str, float] = {}
        now = datetime.now(UTC)

        for belief_id, belief in self.self_model.beliefs.items():
            # Check if belief has recent updates
            last_update = self._belief_last_update.get(belief_id)
            if last_update is None:
                last_update = self._belief_initial_time.get(belief_id, now)

            days_since_update = (now - last_update).total_seconds() / 86400

            # Apply decay if no recent updates
            if days_since_update > 1:
                decay_factor = math.exp(-self.CONFIDENCE_DECAY_RATE * days_elapsed)
                old_confidence = belief.confidence
                new_confidence = max(
                    self.CONFIDENCE_MIN,
                    old_confidence * decay_factor
                    + (1 - decay_factor) * 0.5,  # Decay toward neutral
                )

                if abs(new_confidence - old_confidence) > 0.001:
                    belief.confidence = new_confidence
                    changes[belief_id] = new_confidence - old_confidence

                    # Record evolution
                    evolution_record = BeliefEvolutionRecord(
                        belief_id=belief_id,
                        old_confidence=old_confidence,
                        new_confidence=new_confidence,
                        evidence_count=len(belief.supporting_evidence),
                        reason="time_decay",
                    )
                    self._belief_evolution_history.append(evolution_record)

        self._trim_evolution_history()

        if changes:
            self.self_model._update_count += 1  # noqa: SLF001
            self.self_model._maybe_take_snapshot()  # noqa: SLF001

        logger.debug("Confidence decay applied", extra={"affected_beliefs": len(changes)})

        return changes

    def get_belief_evolution_history(self, belief_id: str) -> list[dict[str, Any]]:
        """Get evolution history for a specific belief.

        Args:
            belief_id: The ID of the belief.

        Returns:
            List of evolution records for the belief.
        """
        return [
            record.to_dict()
            for record in self._belief_evolution_history
            if record.belief_id == belief_id
        ]

    def get_goal_evolution_history(self, goal_id: str) -> list[dict[str, Any]]:
        """Get evolution history for a specific goal.

        Args:
            goal_id: The ID of the goal.

        Returns:
            List of evolution records for the goal.
        """
        return [
            record.to_dict() for record in self._goal_evolution_history if record.goal_id == goal_id
        ]

    def _get_confidence_trend(self, belief_id: str) -> str:
        """Determine the confidence trend for a belief.

        Args:
            belief_id: The ID of the belief.

        Returns:
            "increasing", "decreasing", or "stable"
        """
        history = [r for r in self._belief_evolution_history if r.belief_id == belief_id][
            -5:
        ]  # Last 5 records

        if len(history) < 2:
            return "stable"

        changes = [r.new_confidence - r.old_confidence for r in history]
        avg_change = sum(changes) / len(changes)

        if avg_change > 0.01:
            return "increasing"
        if avg_change < -0.01:
            return "decreasing"
        return "stable"

    def _assess_evidence_quality(self, belief: Belief) -> str:
        """Assess the quality of evidence for a belief.

        Args:
            belief: The Belief to assess.

        Returns:
            "strong", "moderate", or "weak"
        """
        evidence_count = len(belief.supporting_evidence)
        conflict_count = len(belief.conflicting_beliefs)

        # Simple heuristic based on evidence count and conflicts
        if evidence_count >= 5 and conflict_count == 0:
            return "strong"
        if evidence_count >= 3 and conflict_count <= 1:
            return "moderate"
        if evidence_count >= 1:
            return "weak"
        return "weak"

    def _are_beliefs_in_conflict(self, b1: Belief, b2: Belief) -> bool:
        """Check if two beliefs are in conflict.

        Args:
            b1: First belief.
            b2: Second belief.

        Returns:
            True if beliefs are in conflict.
        """
        # Use existing method from SelfModel
        return self.self_model._are_beliefs_conflicting(b1, b2)  # noqa: SLF001

    def _suggest_resolution(
        self,
        b1: Belief,
        b2: Belief,
        strategy: ConflictResolutionStrategy,
    ) -> tuple[str, ConflictResolutionStrategy]:
        """Suggest a resolution for conflicting beliefs.

        Args:
            b1: First belief.
            b2: Second belief.
            strategy: The resolution strategy to use.

        Returns:
            Tuple of (resolution suggestion string, strategy used).
        """
        if strategy == ConflictResolutionStrategy.CONFIDENCE_BASED:
            if b1.confidence > b2.confidence:
                return (
                    f"Prefer belief '{b1.state[:50]}...' (confidence: {b1.confidence:.2f}) "
                    f"over '{b2.state[:50]}...' (confidence: {b2.confidence:.2f})",
                    ConflictResolutionStrategy.CONFIDENCE_BASED,
                )
            return (
                f"Prefer belief '{b2.state[:50]}...' (confidence: {b2.confidence:.2f}) "
                f"over '{b1.state[:50]}...' (confidence: {b1.confidence:.2f})",
                ConflictResolutionStrategy.CONFIDENCE_BASED,
            )

        if strategy == ConflictResolutionStrategy.EVIDENCE_BASED:
            evidence_1 = len(b1.supporting_evidence)
            evidence_2 = len(b2.supporting_evidence)
            if evidence_1 > evidence_2:
                return (
                    f"Prefer belief '{b1.state[:50]}...' ({evidence_1} evidence sources) "
                    f"over '{b2.state[:50]}...' ({evidence_2} evidence sources)",
                    ConflictResolutionStrategy.EVIDENCE_BASED,
                )
            return (
                f"Prefer belief '{b2.state[:50]}...' ({evidence_2} evidence sources) "
                f"over '{b1.state[:50]}...' ({evidence_1} evidence sources)",
                ConflictResolutionStrategy.EVIDENCE_BASED,
            )

        if strategy == ConflictResolutionStrategy.RECENCY_BASED:
            try:
                time_1 = datetime.fromisoformat(b1.updated_at)
                time_2 = datetime.fromisoformat(b2.updated_at)
                if time_1 > time_2:
                    return (
                        f"Prefer belief '{b1.state[:50]}...' (updated: {b1.updated_at[:10]}) "
                        f"over '{b2.state[:50]}...' (updated: {b2.updated_at[:10]})",
                        ConflictResolutionStrategy.RECENCY_BASED,
                    )
                return (
                    f"Prefer belief '{b2.state[:50]}...' (updated: {b2.updated_at[:10]}) "
                    f"over '{b1.state[:50]}...' (updated: {b1.updated_at[:10]})",
                    ConflictResolutionStrategy.RECENCY_BASED,
                )
            except (ValueError, TypeError):
                return (
                    "Unable to determine recency - falling back to confidence-based resolution",
                    ConflictResolutionStrategy.CONFIDENCE_BASED,
                )

        else:  # AVERAGE
            avg_confidence = (b1.confidence + b2.confidence) / 2
            return (
                f"Consider averaging confidence values: ({b1.confidence:.2f} + {b2.confidence:.2f}) / 2 = {avg_confidence:.2f}",  # noqa: E501
                ConflictResolutionStrategy.AVERAGE,
            )

    def _trim_evolution_history(self) -> None:
        """Trim evolution history to maximum size."""
        if len(self._belief_evolution_history) > self.MAX_EVOLUTION_HISTORY:
            self._belief_evolution_history = self._belief_evolution_history[
                -self.MAX_EVOLUTION_HISTORY :
            ]
        if len(self._goal_evolution_history) > self.MAX_EVOLUTION_HISTORY:
            self._goal_evolution_history = self._goal_evolution_history[
                -self.MAX_EVOLUTION_HISTORY :
            ]
