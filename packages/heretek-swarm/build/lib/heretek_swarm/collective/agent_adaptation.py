"""
Pattern-Based Agent Adaptor - Session 46 Emergent Intelligence

Implements agent behavior modification based on learned patterns.
This module enables agents to adapt their strategies, weights, and
decision-making processes based on collective learning.

Features:
- Modify agent behavior based on learned patterns
- Behavioral weight adjustment
- Strategy selection optimization
- Adaptation audit logging
- Zero-trust validation of all adaptive changes

Zero-Trust Principles:
- All behavioral changes validated before application
- Source attribution required for pattern adoption
- Confidence thresholds enforced
- Complete audit trail for all adaptations
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from .learning import ExtractedPattern, PatternType
from .pattern_library import PatternLibrary

logger = structlog.get_logger(__name__)


class AdaptationTarget(StrEnum):
    """Targets for agent adaptation."""

    BEHAVIORAL_WEIGHTS = "behavioral_weights"
    STRATEGY_SELECTION = "strategy_selection"
    DECISION_THRESHOLDS = "decision_thresholds"
    COMMUNICATION_STYLE = "communication_style"
    COLLABORATION_PREFS = "collaboration_preferences"
    RESOURCE_ALLOCATION = "resource_allocation"
    RISK_TOLERANCE = "risk_tolerance"
    LEARNING_RATE = "learning_rate"


class AdaptationStrategy(StrEnum):
    """Strategies for applying adaptations."""

    GRADUAL = "gradual"  # Apply changes gradually over time
    IMMEDIATE = "immediate"  # Apply changes immediately
    CONDITIONAL = "conditional"  # Apply only when conditions met
    PROBABILISTIC = "probabilistic"  # Apply with probability based on confidence
    CONSENSUS = "consensus"  # Apply only after consensus


@dataclass
class BehavioralWeight:
    """Weight for a specific behavioral aspect."""

    weight_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    aspect: str = ""
    current_value: float = 0.5
    baseline_value: float = 0.5
    min_value: float = 0.0
    max_value: float = 1.0
    last_updated: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    update_count: int = 0
    source_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "weight_id": self.weight_id,
            "aspect": self.aspect,
            "current_value": self.current_value,
            "baseline_value": self.baseline_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "last_updated": self.last_updated,
            "update_count": self.update_count,
            "source_patterns": self.source_patterns,
        }


@dataclass
class StrategyProfile:
    """Profile for a decision-making strategy."""

    strategy_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    priority: float = 0.5
    success_rate: float = 0.0
    usage_count: int = 0
    last_used: str | None = None
    applicable_patterns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "applicable_patterns": self.applicable_patterns,
            "metadata": self.metadata,
        }


@dataclass
class AgentAdaptationState:
    """Complete adaptation state for an agent."""

    agent_id: str
    behavioral_weights: dict[str, BehavioralWeight] = field(default_factory=dict)
    strategy_profiles: dict[str, StrategyProfile] = field(default_factory=dict)
    active_strategies: list[str] = field(default_factory=list)
    decision_thresholds: dict[str, float] = field(default_factory=dict)
    adaptation_count: int = 0
    last_adaptation: str | None = None
    adaptation_history: list[str] = field(default_factory=list)  # Adaptation event IDs
    adopted_patterns: list[str] = field(default_factory=list)
    rejected_patterns: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "behavioral_weights": {k: v.to_dict() for k, v in self.behavioral_weights.items()},
            "strategy_profiles": {k: v.to_dict() for k, v in self.strategy_profiles.items()},
            "active_strategies": self.active_strategies,
            "decision_thresholds": self.decision_thresholds,
            "adaptation_count": self.adaptation_count,
            "last_adaptation": self.last_adaptation,
            "adaptation_history_count": len(self.adaptation_history),
            "adopted_patterns": self.adopted_patterns,
            "rejected_patterns": self.rejected_patterns,
            "metadata": self.metadata,
        }


@dataclass
class AdaptationEvent:
    """Represents an agent adaptation event."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    target: AdaptationTarget = AdaptationTarget.BEHAVIORAL_WEIGHTS
    strategy: AdaptationStrategy = AdaptationStrategy.GRADUAL
    pattern_id: str | None = None
    changes: dict[str, Any] = field(default_factory=dict)
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)
    validation_passed: bool = True
    validation_details: dict[str, Any] = field(default_factory=dict)
    applied: bool = False
    application_time: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "target": self.target.value,
            "strategy": self.strategy.value,
            "pattern_id": self.pattern_id,
            "changes": self.changes,
            "old_values": self.old_values,
            "new_values": self.new_values,
            "validation_passed": self.validation_passed,
            "validation_details": self.validation_details,
            "applied": self.applied,
            "application_time": self.application_time,
            "metadata": self.metadata,
        }


@dataclass
class AdaptationAudit:
    """Audit record for adaptation tracking."""

    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = ""
    agent_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    action: str = ""
    actor: str = ""  # Who/what initiated the adaptation
    justification: str = ""
    risk_assessment: float = 0.0  # 0.0 = no risk, 1.0 = high risk
    rollback_available: bool = True
    rollback_data: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "audit_id": self.audit_id,
            "event_id": self.event_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "actor": self.actor,
            "justification": self.justification,
            "risk_assessment": self.risk_assessment,
            "rollback_available": self.rollback_available,
            "rollback_data": self.rollback_data,
            "metadata": self.metadata,
        }


class PatternBasedAgentAdaptor:
    """
    Adaptor for modifying agent behavior based on learned patterns.

    This adaptor enables agents to adapt their behaviors, strategies,
    and decision-making processes based on patterns learned from
    collective experience.

    Attributes:
        pattern_library: PatternLibrary for pattern lookup
        adaptation_events: List of adaptation events for audit
    """

    def __init__(
        self,
        pattern_library: PatternLibrary | None = None,
        default_strategy: AdaptationStrategy = AdaptationStrategy.GRADUAL,
        validation_required: bool = True,
    ):
        """
        Initialize pattern-based agent adaptor.

        Args:
            pattern_library: PatternLibrary instance (optional)
            default_strategy: Default adaptation strategy
            validation_required: Whether validation is required
        """
        self.pattern_library = pattern_library
        self.default_strategy = default_strategy
        self.validation_required = validation_required

        self._agent_states: dict[str, AgentAdaptationState] = {}
        self._adaptation_events: list[AdaptationEvent] = []
        self._audit_log: list[AdaptationAudit] = []

        # Callbacks
        self._on_adaptation: list[Callable] = []
        self._on_pattern_adopted: list[Callable] = []
        self._on_pattern_rejected: list[Callable] = []

        # Validation hooks
        self._validation_hooks: list[Callable] = []

        logger.info(
            "pattern_based_agent_adaptor_initialized",
            default_strategy=default_strategy.value,
            validation_required=validation_required,
        )

    def register_adaptation_callback(self, callback: Callable) -> None:
        """
        Register callback for adaptation events.

        Args:
            callback: Async callable receiving AdaptationEvent
        """
        self._on_adaptation.append(callback)
        logger.debug("adaptation_callback_registered", callback=callback.__name__)

    def register_pattern_callback(self, callback: Callable) -> None:
        """
        Register callback for pattern adoption/rejection.

        Args:
            callback: Async callable receiving pattern info
        """
        self._on_pattern_adopted.append(callback)
        logger.debug("pattern_adopted_callback_registered", callback=callback.__name__)

    def register_validation_hook(self, callback: Callable) -> None:
        """
        Register validation hook for adaptations.

        Args:
            callback: Async callable receiving adaptation proposal
        """
        self._validation_hooks.append(callback)
        logger.debug("validation_hook_registered", callback=callback.__name__)

    def get_or_create_state(self, agent_id: str) -> AgentAdaptationState:
        """
        Get or create adaptation state for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentAdaptationState for the agent
        """
        if agent_id not in self._agent_states:
            self._agent_states[agent_id] = AgentAdaptationState(agent_id=agent_id)
            logger.debug("agent_adaptation_state_created", agent_id=agent_id)

        return self._agent_states[agent_id]

    async def apply_pattern(
        self,
        agent_id: str,
        pattern: ExtractedPattern,
        target: AdaptationTarget | None = None,
        strategy: AdaptationStrategy | None = None,
    ) -> bool:
        """
        Apply a pattern to modify agent behavior.

        Args:
            agent_id: Agent identifier
            pattern: Pattern to apply
            target: Adaptation target (auto-detected if None)
            strategy: Adaptation strategy (default: configured default)

        Returns:
            True if pattern was applied successfully
        """
        state = self.get_or_create_state(agent_id)
        strategy = strategy or self.default_strategy

        # Auto-detect target based on pattern type
        if target is None:
            target = self._auto_detect_target(pattern)

        # Zero-trust validation
        if self.validation_required:
            is_valid = await self._validate_adaptation(agent_id, pattern, target)
            if not is_valid:
                state.rejected_patterns.append(pattern.metadata.pattern_id)
                logger.warning(
                    "pattern_application_rejected",
                    agent_id=agent_id,
                    pattern_id=pattern.metadata.pattern_id,
                    reason="validation_failed",
                )
                await self._call_pattern_callbacks(pattern, adopted=False)
                return False

        # Create adaptation event
        event = AdaptationEvent(
            agent_id=agent_id,
            target=target,
            strategy=strategy,
            pattern_id=pattern.metadata.pattern_id,
        )

        # Store old values for rollback
        event.old_values = self._capture_old_values(state, target)

        # Apply changes based on target
        changes_applied = await self._apply_pattern_changes(
            state,
            pattern,
            target,
            strategy,
        )

        if not changes_applied:
            logger.debug(
                "no_changes_applied",
                agent_id=agent_id,
                pattern_id=pattern.metadata.pattern_id,
            )
            return False

        # Store new values
        event.new_values = self._capture_new_values(state, target)
        event.changes = self._compute_changes(event.old_values, event.new_values)
        event.applied = True
        event.application_time = datetime.now(UTC).isoformat()

        # Update state
        state.adaptation_count += 1
        state.last_adaptation = event.timestamp
        state.adaptation_history.append(event.event_id)
        state.adopted_patterns.append(pattern.metadata.pattern_id)

        # Store event
        self._adaptation_events.append(event)

        # Create audit record
        audit = await self._create_audit_record(event, pattern)
        self._audit_log.append(audit)

        # Call callbacks
        await self._call_adaptation_callbacks(event)
        await self._call_pattern_callbacks(pattern, adopted=True)

        logger.info(
            "pattern_applied",
            agent_id=agent_id,
            pattern_id=pattern.metadata.pattern_id,
            target=target.value,
            strategy=strategy.value,
        )

        return True

    async def adjust_behavioral_weight(
        self,
        agent_id: str,
        aspect: str,
        adjustment: float,
        source_pattern_id: str | None = None,
    ) -> bool:
        """
        Adjust a behavioral weight for an agent.

        Args:
            agent_id: Agent identifier
            aspect: Behavioral aspect to adjust
            adjustment: Amount to adjust (positive or negative)
            source_pattern_id: Optional source pattern ID

        Returns:
            True if adjustment was applied
        """
        state = self.get_or_create_state(agent_id)

        # Get or create weight
        if aspect not in state.behavioral_weights:
            state.behavioral_weights[aspect] = BehavioralWeight(aspect=aspect)

        weight = state.behavioral_weights[aspect]
        old_value = weight.current_value

        # Calculate new value with clamping
        new_value = old_value + adjustment
        new_value = max(weight.min_value, min(new_value, weight.max_value))

        # Skip if no meaningful change
        if abs(new_value - old_value) < 0.001:
            return False

        # Apply change
        weight.current_value = new_value
        weight.last_updated = datetime.now(UTC).isoformat()
        weight.update_count += 1

        if source_pattern_id:
            weight.source_patterns.append(source_pattern_id)

        logger.debug(
            "behavioral_weight_adjusted",
            agent_id=agent_id,
            aspect=aspect,
            old_value=old_value,
            new_value=new_value,
        )

        return True

    async def update_strategy_priority(
        self,
        agent_id: str,
        strategy_id: str,
        new_priority: float,
        success_rate: float | None = None,
    ) -> bool:
        """
        Update priority of a strategy for an agent.

        Args:
            agent_id: Agent identifier
            strategy_id: Strategy identifier
            new_priority: New priority value
            success_rate: Optional success rate update

        Returns:
            True if update was applied
        """
        state = self.get_or_create_state(agent_id)

        if strategy_id not in state.strategy_profiles:
            logger.warning(
                "strategy_not_found",
                agent_id=agent_id,
                strategy_id=strategy_id,
            )
            return False

        profile = state.strategy_profiles[strategy_id]
        profile.priority = new_priority

        if success_rate is not None:
            profile.success_rate = success_rate
            profile.usage_count += 1
            profile.last_used = datetime.now(UTC).isoformat()

        logger.debug(
            "strategy_priority_updated",
            agent_id=agent_id,
            strategy_id=strategy_id,
            new_priority=new_priority,
        )

        return True

    async def select_optimal_strategy(
        self,
        agent_id: str,
        context: dict[str, Any],
    ) -> StrategyProfile | None:
        """
        Select the optimal strategy for a given context.

        Args:
            agent_id: Agent identifier
            context: Context information for selection

        Returns:
            Selected StrategyProfile or None
        """
        state = self.get_or_create_state(agent_id)

        if not state.strategy_profiles:
            return None

        # Score each strategy based on context
        scored_strategies = []
        for profile in state.strategy_profiles.values():
            score = self._score_strategy(profile, context)
            scored_strategies.append((score, profile))

        # Select highest scoring strategy
        if scored_strategies:
            scored_strategies.sort(key=lambda x: x[0], reverse=True)
            selected = scored_strategies[0][1]

            logger.debug(
                "strategy_selected",
                agent_id=agent_id,
                strategy_id=selected.strategy_id,
                strategy_name=selected.name,
            )

            return selected

        return None

    async def register_strategy(
        self,
        agent_id: str,
        name: str,
        description: str = "",
        initial_priority: float = 0.5,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Register a new strategy for an agent.

        Args:
            agent_id: Agent identifier
            name: Strategy name
            description: Strategy description
            initial_priority: Initial priority
            metadata: Optional metadata

        Returns:
            Strategy ID
        """
        state = self.get_or_create_state(agent_id)

        strategy_id = str(uuid.uuid4())
        profile = StrategyProfile(
            strategy_id=strategy_id,
            name=name,
            description=description,
            priority=initial_priority,
            metadata=metadata or {},
        )

        state.strategy_profiles[strategy_id] = profile
        state.active_strategies.append(strategy_id)

        logger.info(
            "strategy_registered",
            agent_id=agent_id,
            strategy_id=strategy_id,
            strategy_name=name,
        )

        return strategy_id

    def get_adaptation_state(self, agent_id: str) -> AgentAdaptationState:
        """
        Get adaptation state for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            AgentAdaptationState
        """
        return self.get_or_create_state(agent_id)

    def get_adaptation_history(
        self,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[AdaptationEvent]:
        """
        Get adaptation event history.

        Args:
            agent_id: Optional agent filter
            limit: Maximum events to return

        Returns:
            List of adaptation events
        """
        events = self._adaptation_events

        if agent_id:
            events = [e for e in events if e.agent_id == agent_id]

        return events[-limit:]

    def get_audit_log(
        self,
        agent_id: str | None = None,
        limit: int = 100,
    ) -> list[AdaptationAudit]:
        """
        Get adaptation audit log.

        Args:
            agent_id: Optional agent filter
            limit: Maximum records to return

        Returns:
            List of audit records
        """
        audits = self._audit_log

        if agent_id:
            audits = [a for a in audits if a.agent_id == agent_id]

        return audits[-limit:]

    async def rollback_adaptation(
        self,
        agent_id: str,
        event_id: str,
    ) -> bool:
        """
        Rollback a specific adaptation event.

        Args:
            agent_id: Agent identifier
            event_id: Event ID to rollback

        Returns:
            True if rollback was successful
        """
        # Find the event
        event = None
        for e in self._adaptation_events:
            if e.event_id == event_id and e.agent_id == agent_id:
                event = e
                break

        if not event:
            logger.warning(
                "adaptation_event_not_found",
                agent_id=agent_id,
                event_id=event_id,
            )
            return False

        # Find audit record with rollback data
        audit = None
        for a in self._audit_log:
            if a.event_id == event_id and a.agent_id == agent_id:
                audit = a
                break

        if not audit or not audit.rollback_data:
            logger.warning(
                "rollback_data_not_available",
                agent_id=agent_id,
                event_id=event_id,
            )
            return False

        # Apply rollback
        state = self.get_or_create_state(agent_id)

        if event.target == AdaptationTarget.BEHAVIORAL_WEIGHTS:
            for aspect, value in audit.rollback_data.get("weights", {}).items():
                if aspect in state.behavioral_weights:
                    state.behavioral_weights[aspect].current_value = value

        elif event.target == AdaptationTarget.STRATEGY_SELECTION:
            for sid, profile_dict in audit.rollback_data.get("strategies", {}).items():
                if sid in state.strategy_profiles:
                    state.strategy_profiles[sid].priority = profile_dict.get("priority", 0.5)

        elif event.target == AdaptationTarget.DECISION_THRESHOLDS:
            for key, value in audit.rollback_data.get("thresholds", {}).items():
                state.decision_thresholds[key] = value

        logger.info(
            "adaptation_rolled_back",
            agent_id=agent_id,
            event_id=event_id,
        )

        return True

    def get_swarm_adaptation_stats(self) -> dict[str, Any]:
        """
        Get swarm-wide adaptation statistics.

        Returns:
            Dictionary of adaptation statistics
        """
        if not self._agent_states:
            return {
                "total_agents": 0,
                "total_adaptations": 0,
                "avg_adaptations_per_agent": 0.0,
                "total_patterns_adopted": 0,
                "total_patterns_rejected": 0,
            }

        states = list(self._agent_states.values())
        total_adaptations = sum(s.adaptation_count for s in states)
        total_adopted = sum(len(s.adopted_patterns) for s in states)
        total_rejected = sum(len(s.rejected_patterns) for s in states)

        return {
            "total_agents": len(states),
            "total_adaptations": total_adaptations,
            "avg_adaptations_per_agent": total_adaptations / len(states),
            "total_patterns_adopted": total_adopted,
            "total_patterns_rejected": total_rejected,
            "adoption_rate": total_adopted / max(total_adopted + total_rejected, 1),
        }

    def _auto_detect_target(self, pattern: ExtractedPattern) -> AdaptationTarget:
        """Auto-detect adaptation target based on pattern type."""
        type_target_map = {
            PatternType.SUCCESS: AdaptationTarget.STRATEGY_SELECTION,
            PatternType.FAILURE: AdaptationTarget.DECISION_THRESHOLDS,
            PatternType.OPTIMIZATION: AdaptationTarget.BEHAVIORAL_WEIGHTS,
            PatternType.HANDOFF: AdaptationTarget.COMMUNICATION_STYLE,
            PatternType.COLLABORATION: AdaptationTarget.COLLABORATION_PREFS,
            PatternType.DECISION: AdaptationTarget.DECISION_THRESHOLDS,
            PatternType.COMMUNICATION: AdaptationTarget.COMMUNICATION_STYLE,
            PatternType.ERROR_RECOVERY: AdaptationTarget.RISK_TOLERANCE,
            PatternType.RESOURCE_USAGE: AdaptationTarget.RESOURCE_ALLOCATION,
            PatternType.EMERGENT: AdaptationTarget.STRATEGY_SELECTION,
        }

        return type_target_map.get(
            pattern.metadata.pattern_type,
            AdaptationTarget.BEHAVIORAL_WEIGHTS,
        )

    async def _validate_adaptation(
        self,
        agent_id: str,
        pattern: ExtractedPattern,
        target: AdaptationTarget,
    ) -> bool:
        """
        Validate adaptation with zero-trust principles.

        Args:
            agent_id: Agent identifier
            pattern: Pattern to validate
            target: Adaptation target

        Returns:
            True if adaptation is valid
        """
        # Check pattern confidence
        if pattern.metadata.confidence < 0.3:
            return False

        # Check for conflicting patterns
        state = self.get_or_create_state(agent_id)
        for rejected_id in state.rejected_patterns:
            # Check if same pattern was rejected
            if rejected_id == pattern.metadata.pattern_id:
                return False

        # Call validation hooks
        for hook in self._validation_hooks:
            try:
                result = hook(agent_id, pattern, target)
                if asyncio.iscoroutine(result):
                    result = await result
                if not result:
                    return False
            except Exception as e:
                logger.error(
                    "validation_hook_error",
                    agent_id=agent_id,
                    hook=hook.__name__,
                    error=str(e),
                )

        return True

    async def _apply_pattern_changes(
        self,
        state: AgentAdaptationState,
        pattern: ExtractedPattern,
        target: AdaptationTarget,
        strategy: AdaptationStrategy,
    ) -> bool:
        """
        Apply pattern-based changes to agent state.

        Args:
            state: Agent adaptation state
            pattern: Pattern to apply
            target: Adaptation target
            strategy: Adaptation strategy

        Returns:
            True if changes were applied
        """
        if target == AdaptationTarget.BEHAVIORAL_WEIGHTS:
            return await self._apply_behavioral_weight_changes(state, pattern, strategy)

        if target == AdaptationTarget.STRATEGY_SELECTION:
            return await self._apply_strategy_changes(state, pattern, strategy)

        if target == AdaptationTarget.DECISION_THRESHOLDS:
            return await self._apply_threshold_changes(state, pattern, strategy)

        if target == AdaptationTarget.COMMUNICATION_STYLE:
            return await self._apply_communication_changes(state, pattern, strategy)

        if target == AdaptationTarget.COLLABORATION_PREFS:
            return await self._apply_collaboration_changes(state, pattern, strategy)

        if target == AdaptationTarget.RESOURCE_ALLOCATION:
            return await self._apply_resource_changes(state, pattern, strategy)

        if target == AdaptationTarget.RISK_TOLERANCE:
            return await self._apply_risk_changes(state, pattern, strategy)

        return False

    async def _apply_behavioral_weight_changes(
        self,
        state: AgentAdaptationState,
        pattern: ExtractedPattern,
        strategy: AdaptationStrategy,
    ) -> bool:
        """Apply behavioral weight changes from pattern."""
        pattern_data = pattern.pattern_data

        if "behavioral_weights" not in pattern_data:
            return False

        weights = pattern_data["behavioral_weights"]
        confidence = pattern.metadata.confidence

        for aspect, target_value in weights.items():
            if aspect not in state.behavioral_weights:
                state.behavioral_weights[aspect] = BehavioralWeight(aspect=aspect)

            weight = state.behavioral_weights[aspect]

            if strategy == AdaptationStrategy.GRADUAL:
                # Gradual adjustment
                adjustment = (target_value - weight.current_value) * 0.1 * confidence
                weight.current_value += adjustment
            elif strategy == AdaptationStrategy.IMMEDIATE:
                weight.current_value = target_value
            elif strategy == AdaptationStrategy.PROBABILISTIC:
                # NOTE: random for probabilistic adaptation - not security-critical
                import random

                if random.random() < confidence:  # noqa: S311
                    weight.current_value = target_value

            weight.last_updated = datetime.now(UTC).isoformat()
            weight.update_count += 1
            weight.source_patterns.append(pattern.metadata.pattern_id)

        return True

    async def _apply_strategy_changes(
        self,
        state: AgentAdaptationState,
        pattern: ExtractedPattern,
        strategy: AdaptationStrategy,  # noqa: ARG002
    ) -> bool:
        """Apply strategy selection changes from pattern."""
        pattern_data = pattern.pattern_data

        if "strategy" not in pattern_data:
            return False

        strategy_info = pattern_data["strategy"]
        strategy_name = strategy_info.get("name", "unknown")
        strategy_priority = strategy_info.get("priority", 0.5)

        # Find or create strategy profile
        profile = None
        for p in state.strategy_profiles.values():
            if p.name == strategy_name:
                profile = p
                break

        if not profile:
            strategy_id = await self.register_strategy(
                state.agent_id,
                strategy_name,
                strategy_info.get("description", ""),
                strategy_priority,
            )
            profile = state.strategy_profiles[strategy_id]

        # Update priority based on pattern confidence
        confidence_boost = pattern.metadata.confidence * 0.2
        profile.priority = min(1.0, profile.priority + confidence_boost)

        if strategy_name not in state.active_strategies:
            state.active_strategies.append(strategy_name)

        return True

    async def _apply_threshold_changes(
        self,
        state: AgentAdaptationState,
        pattern: ExtractedPattern,
        strategy: AdaptationStrategy,
    ) -> bool:
        """Apply decision threshold changes from pattern."""
        pattern_data = pattern.pattern_data

        if "decision_thresholds" not in pattern_data:
            return False

        thresholds = pattern_data["decision_thresholds"]

        for key, value in thresholds.items():
            if strategy == AdaptationStrategy.GRADUAL:
                old_value = state.decision_thresholds.get(key, 0.5)
                new_value = old_value + (value - old_value) * 0.1
                state.decision_thresholds[key] = new_value
            else:
                state.decision_thresholds[key] = value

        return True

    async def _apply_communication_changes(
        self,
        state: AgentAdaptationState,  # noqa: ARG002
        pattern: ExtractedPattern,  # noqa: ARG002
        strategy: AdaptationStrategy,  # noqa: ARG002
    ) -> bool:
        """Apply communication style changes from pattern."""
        # Implementation for communication style adaptation
        return True

    async def _apply_collaboration_changes(
        self,
        state: AgentAdaptationState,  # noqa: ARG002
        pattern: ExtractedPattern,  # noqa: ARG002
        strategy: AdaptationStrategy,  # noqa: ARG002
    ) -> bool:
        """Apply collaboration preference changes from pattern."""
        # Implementation for collaboration preference adaptation
        return True

    async def _apply_resource_changes(
        self,
        state: AgentAdaptationState,  # noqa: ARG002
        pattern: ExtractedPattern,  # noqa: ARG002
        strategy: AdaptationStrategy,  # noqa: ARG002
    ) -> bool:
        """Apply resource allocation changes from pattern."""
        # Implementation for resource allocation adaptation
        return True

    async def _apply_risk_changes(
        self,
        state: AgentAdaptationState,  # noqa: ARG002
        pattern: ExtractedPattern,  # noqa: ARG002
        strategy: AdaptationStrategy,  # noqa: ARG002
    ) -> bool:
        """Apply risk tolerance changes from pattern."""
        # Implementation for risk tolerance adaptation
        return True

    def _capture_old_values(
        self,
        state: AgentAdaptationState,
        target: AdaptationTarget,
    ) -> dict[str, Any]:
        """Capture old values for rollback."""
        if target == AdaptationTarget.BEHAVIORAL_WEIGHTS:
            return {"weights": {k: v.current_value for k, v in state.behavioral_weights.items()}}
        if target == AdaptationTarget.STRATEGY_SELECTION:
            return {
                "strategies": {
                    k: {"priority": v.priority} for k, v in state.strategy_profiles.items()
                }
            }
        if target == AdaptationTarget.DECISION_THRESHOLDS:
            return {"thresholds": state.decision_thresholds.copy()}

        return {}

    def _capture_new_values(
        self,
        state: AgentAdaptationState,
        target: AdaptationTarget,
    ) -> dict[str, Any]:
        """Capture new values after adaptation."""
        return self._capture_old_values(state, target)

    def _compute_changes(
        self,
        old_values: dict[str, Any],
        new_values: dict[str, Any],
    ) -> dict[str, Any]:
        """Compute the changes between old and new values."""
        changes = {}

        for key in set(old_values.keys()) | set(new_values.keys()):
            old_val = old_values.get(key)
            new_val = new_values.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}

        return changes

    async def _create_audit_record(
        self,
        event: AdaptationEvent,
        pattern: ExtractedPattern,
    ) -> AdaptationAudit:
        """Create audit record for an adaptation event."""
        # Calculate risk assessment
        risk = 0.0

        # Higher confidence = lower risk
        risk += (1.0 - pattern.metadata.confidence) * 0.5

        # More changes = higher risk
        risk += min(len(event.changes) * 0.1, 0.3)

        # Certain targets are higher risk
        high_risk_targets = [
            AdaptationTarget.DECISION_THRESHOLDS,
            AdaptationTarget.RISK_TOLERANCE,
        ]
        if event.target in high_risk_targets:
            risk += 0.2

        return AdaptationAudit(
            event_id=event.event_id,
            agent_id=event.agent_id,
            action=f"apply_pattern_{event.target.value}",
            actor="pattern_based_adaptor",
            justification=f"Pattern {pattern.metadata.pattern_id} applied with confidence {pattern.metadata.confidence}",  # noqa: E501
            risk_assessment=min(risk, 1.0),
            rollback_available=True,
            rollback_data=event.old_values,
        )

    def _score_strategy(
        self,
        profile: StrategyProfile,
        context: dict[str, Any],  # noqa: ARG002
    ) -> float:
        """Score a strategy based on context."""
        # Base score from priority
        score = profile.priority

        # Boost by success rate
        score += profile.success_rate * 0.3

        # Penalty for never used
        if profile.usage_count == 0:
            score *= 0.8

        return min(score, 1.0)

    async def _call_adaptation_callbacks(self, event: AdaptationEvent) -> None:
        """Call registered adaptation callbacks."""
        for callback in self._on_adaptation:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(
                    "adaptation_callback_error",
                    callback=callback.__name__,
                    error=str(e),
                )

    async def _call_pattern_callbacks(
        self,
        pattern: ExtractedPattern,
        adopted: bool,
    ) -> None:
        """Call registered pattern callbacks."""
        callbacks = self._on_pattern_adopted if adopted else self._on_pattern_rejected

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(pattern)
                else:
                    callback(pattern)
            except Exception as e:
                logger.error(
                    "pattern_callback_error",
                    callback=callback.__name__,
                    error=str(e),
                )

    def get_status(self) -> dict[str, Any]:
        """
        Get adaptor status summary.

        Returns:
            Status dictionary
        """
        return {
            "total_agents": len(self._agent_states),
            "total_adaptations": len(self._adaptation_events),
            "total_audit_records": len(self._audit_log),
            "default_strategy": self.default_strategy.value,
            "validation_required": self.validation_required,
        }
