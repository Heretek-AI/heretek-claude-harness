"""
Arbiter Core - Core arbitration logic and conflict detection.

This module contains:
- Conflict type enums and dataclasses
- Core ArbiterAgent class
- Conflict detection and relationship management
- Session 44 integration for collective learning and memory optimization
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm.actors.base.core import AgentActor
from heretek_swarm.actors.mixins import (
    DeliberationMixin,
    LearningMixin,
    MemoryMixin,
    PatternMixin,
)

# Session 44: Collective Learning Integration
from heretek_swarm.collective.learning import PatternExtractor, PatternType

# Session 44: Consensus Integration
from heretek_swarm.consensus.swarm_deliberation import (
    DeliberationResult,
    Position,
    SwarmDeliberationEngine,
)

# Session 44: Memory Optimization Integration
from heretek_swarm.memory.access_patterns import AccessPatternAnalyzer, AccessTier

# Session 44: Zero-Trust Validation
from heretek_swarm.security.zero_trust import ZeroTrustValidator

logger = structlog.get_logger("ArbiterAgent")


class ConflictType(StrEnum):
    """Types of inter-agent conflicts."""

    RESOURCE_CONTENTION = "resource_contention"
    TASK_OVERLAP = "task_overlap"
    PRIORITY_DISPUTE = "priority_dispute"
    COMMUNICATION_BREAKDOWN = "communication_breakdown"
    AUTHORITY_CONFLICT = "authority_conflict"
    DATA_INCONSISTENCY = "data_inconsistency"
    GOAL_MISALIGNMENT = "goal_misalignment"
    CAPABILITY_OVERLAP = "capability_overlap"
    MESSAGE_FLOOD = "message_flood"
    DEADLOCK = "deadlock"


class ConflictSeverity(StrEnum):
    """Conflict severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ResolutionStrategy(StrEnum):
    """Conflict resolution strategies."""

    NEGOTIATION = "negotiation"
    MEDIATION = "mediation"
    ARBITRATION = "arbitration"
    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    RESOURCE_POOLING = "resource_pooling"
    TASK_REASSIGNMENT = "task_reassignment"
    ESCALATION = "escalation"
    COMPROMISE = "compromise"
    CONSENSUS_VOTE = "consensus_vote"


class ResolutionStatus(StrEnum):
    """Resolution process status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    PARTIALLY_RESOLVED = "partially_resolved"
    FAILED = "failed"
    ESCALATED = "escalated"


@dataclass
class Conflict:
    """Record of an inter-agent conflict."""

    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    status: ResolutionStatus
    timestamp: datetime
    parties: list[str]  # Agent IDs involved
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    proposed_resolutions: list[dict[str, Any]] = field(default_factory=list)
    selected_resolution: dict[str, Any] | None = None
    resolved_at: datetime | None = None
    resolution_notes: str = ""


@dataclass
class Relationship:
    """Inter-agent relationship health record."""

    agent_a: str
    agent_b: str
    health_score: float  # 0.0 - 1.0
    interaction_count: int
    conflict_count: int
    cooperation_count: int
    last_interaction: datetime
    trust_level: float  # 0.0 - 1.0
    tags: list[str] = field(default_factory=list)


@dataclass
class ArbitrationReport:
    """Comprehensive arbitration report."""

    report_id: str
    timestamp: datetime
    active_conflicts: int
    resolved_conflicts: int
    failed_resolutions: int
    conflicts_by_type: dict[str, int]
    conflicts_by_severity: dict[str, int]
    relationship_health: dict[str, float]
    recommendations: list[str]


class ArbiterAgent(DeliberationMixin, PatternMixin, MemoryMixin, LearningMixin, AgentActor):
    """
    Arbiter Agent - Conflict Resolution Specialist for the Heretek Swarm Collective.

    The Arbiter mediates disputes, resolves resource contentions, and maintains
    healthy inter-agent relationships across the Collective.
    """

    def __init__(
        self,
        agent_id: str | None = None,
        name: str = "Arbiter",
        description: str = "Conflict Resolution & Dispute Mediation",
        config: dict[str, Any] | None = None,
        db_pool: Any | None = None,
        redis_client: Any | None = None,
        # Session 44: Integration components
        pattern_extractor: PatternExtractor | None = None,
        deliberation_engine: SwarmDeliberationEngine | None = None,
        access_analyzer: AccessPatternAnalyzer | None = None,
        zero_trust_validator: ZeroTrustValidator | None = None,
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            description=description,
            topics=["arbiter", "conflict-resolution", "mediation"],
            capabilities=[
                "conflict-resolution",
                "mediation",
                "arbitration",
                "relationship-management",
            ],
            config=config,
            db_pool=db_pool,
            redis_client=redis_client,
            pattern_extractor=pattern_extractor,
            deliberation_engine=deliberation_engine,
            access_analyzer=access_analyzer,
            zero_trust_validator=zero_trust_validator,
        )

        # Configuration
        self._auto_resolution = config.get("auto_resolution", True) if config else True
        self._escalation_threshold = (
            config.get("escalation_threshold", ConflictSeverity.HIGH.value)
            if config
            else ConflictSeverity.HIGH.value
        )
        self._max_conflicts = config.get("max_conflicts", 1000) if config else 1000
        self._relationship_decay = config.get("relationship_decay", 0.01) if config else 0.01

        # State
        self._conflicts: dict[str, Conflict] = {}
        self._conflict_history: list[str] = []  # LRU keys
        self._relationships: dict[tuple[str, str], Relationship] = {}
        self._pending_arbitrations: dict[str, list[str]] = {}  # conflict_id -> waiting agents

        # Statistics
        self._stats = {
            "total_conflicts": 0,
            "conflicts_by_type": defaultdict(int),
            "conflicts_by_severity": defaultdict(int),
            "resolutions_successful": 0,
            "resolutions_failed": 0,
            "resolutions_escalated": 0,
            "average_resolution_time": 0.0,
        }

        # Session 44: Integration state
        self._active_deliberations: dict[str, str] = {}  # conflict_id -> deliberation_id
        self._pattern_emitted_conflicts: set[str] = set()  # Track which conflicts emitted patterns

        # Resolution strategies registry - will be set by strategies module
        self._resolution_strategies: dict[ResolutionStrategy, Any] = {}

        # Register handlers and strategies
        self._register_handlers()
        self._register_strategies()

        logger.info(
            "Arbiter Agent initialized",
            agent_id=self.agent_id,
            auto_resolution=self._auto_resolution,
            escalation_threshold=self._escalation_threshold,
        )

    def _register_handlers(self) -> None:
        """Register message handlers from handlers module."""
        # Import here to avoid circular imports
        from heretek_swarm.actors.arbiter import handlers

        # Create bound methods from standalone handler functions
        self._message_handlers = {
            "report_conflict": lambda msg: handlers._handle_report_conflict(self, msg),  # noqa: SLF001
            "request_arbitration": lambda msg: handlers._handle_request_arbitration(self, msg),  # noqa: SLF001
            "mediate_dispute": lambda msg: handlers._handle_mediate_dispute(self, msg),  # noqa: SLF001
            "resolve_contention": lambda msg: handlers._handle_resolve_contention(self, msg),  # noqa: SLF001
            "get_conflict_details": lambda msg: handlers._handle_get_conflict_details(self, msg),  # noqa: SLF001
            "get_active_conflicts": lambda msg: handlers._handle_get_active_conflicts(self, msg),  # noqa: SLF001
            "propose_resolution": lambda msg: handlers._handle_propose_resolution(self, msg),  # noqa: SLF001
            "accept_resolution": lambda msg: handlers._handle_accept_resolution(self, msg),  # noqa: SLF001
            "get_relationship_status": lambda msg: handlers._handle_get_relationship_status(  # noqa: SLF001
                self, msg
            ),
            "get_relationship_health": lambda msg: handlers._handle_get_relationship_health(  # noqa: SLF001
                self, msg
            ),
            "update_relationship": lambda msg: handlers._handle_update_relationship(self, msg),  # noqa: SLF001
            "get_arbitration_report": lambda msg: handlers._handle_get_arbitration_report(  # noqa: SLF001
                self, msg
            ),
            "register_interaction": lambda msg: handlers._handle_register_interaction(self, msg),  # noqa: SLF001
        }

    def _register_strategies(self) -> None:
        """Register resolution strategies from strategies module."""
        # Import here to avoid circular imports
        from heretek_swarm.actors.arbiter import strategies

        self._resolution_strategies = {
            ResolutionStrategy.NEGOTIATION: lambda c: strategies._resolve_negotiation(self, c),  # noqa: SLF001
            ResolutionStrategy.MEDIATION: lambda c: strategies._resolve_mediation(self, c),  # noqa: SLF001
            ResolutionStrategy.ARBITRATION: lambda c: strategies._resolve_arbitration(self, c),  # noqa: SLF001
            ResolutionStrategy.PRIORITY_BASED: lambda c: strategies._resolve_priority_based(  # noqa: SLF001
                self, c
            ),
            ResolutionStrategy.ROUND_ROBIN: lambda c: strategies._resolve_round_robin(self, c),  # noqa: SLF001
            ResolutionStrategy.RESOURCE_POOLING: lambda c: strategies._resolve_resource_pooling(  # noqa: SLF001
                self, c
            ),
            ResolutionStrategy.TASK_REASSIGNMENT: lambda c: strategies._resolve_task_reassignment(  # noqa: SLF001
                self, c
            ),
            ResolutionStrategy.ESCALATION: lambda c: strategies._resolve_escalation(self, c),  # noqa: SLF001
            ResolutionStrategy.COMPROMISE: lambda c: strategies._resolve_compromise(self, c),  # noqa: SLF001
            ResolutionStrategy.CONSENSUS_VOTE: lambda c: strategies._resolve_consensus_vote(  # noqa: SLF001
                self, c
            ),
        }

    def _create_conflict_id(self) -> str:
        """Generate unique conflict ID."""
        import hashlib

        timestamp = datetime.now(UTC).timestamp()
        random_suffix = hashlib.sha256(str(timestamp).encode()).hexdigest()[:8]
        return f"CONFLICT_{int(timestamp)}_{random_suffix}"

    def _update_relationships_for_conflict(self, conflict: Conflict) -> None:
        """Update relationship records when a conflict is reported."""
        # Decrement health for all party pairs
        for i, party_a in enumerate(conflict.parties):
            for party_b in conflict.parties[i + 1 :]:
                key = tuple(sorted([party_a, party_b]))

                if key not in self._relationships:
                    self._relationships[key] = Relationship(
                        agent_a=key[0],
                        agent_b=key[1],
                        health_score=0.7,
                        interaction_count=0,
                        conflict_count=0,
                        cooperation_count=0,
                        last_interaction=datetime.now(UTC),
                        trust_level=0.5,
                    )

                relationship = self._relationships[key]
                relationship.conflict_count += 1
                relationship.health_score = max(0.0, relationship.health_score - 0.1)
                relationship.trust_level = max(0.0, relationship.trust_level - 0.05)

    def _update_relationships_for_resolution(self, conflict: Conflict) -> None:
        """Update relationship records when a conflict is resolved."""
        for i, party_a in enumerate(conflict.parties):
            for party_b in conflict.parties[i + 1 :]:
                key = tuple(sorted([party_a, party_b]))

                if key in self._relationships:
                    relationship = self._relationships[key]
                    relationship.health_score = min(1.0, relationship.health_score + 0.1)
                    relationship.trust_level = min(1.0, relationship.trust_level + 0.05)

    async def _attempt_auto_resolution(self, conflict: Conflict) -> dict[str, Any] | None:
        """Attempt automatic resolution based on conflict type and severity."""
        # Select strategy based on conflict type
        strategy_map = {
            ConflictType.RESOURCE_CONTENTION: ResolutionStrategy.RESOURCE_POOLING,
            ConflictType.TASK_OVERLAP: ResolutionStrategy.TASK_REASSIGNMENT,
            ConflictType.PRIORITY_DISPUTE: ResolutionStrategy.PRIORITY_BASED,
            ConflictType.COMMUNICATION_BREAKDOWN: ResolutionStrategy.MEDIATION,
            ConflictType.AUTHORITY_CONFLICT: ResolutionStrategy.ARBITRATION,
            ConflictType.DATA_INCONSISTENCY: ResolutionStrategy.CONSENSUS_VOTE,
            ConflictType.GOAL_MISALIGNMENT: ResolutionStrategy.NEGOTIATION,
            ConflictType.CAPABILITY_OVERLAP: ResolutionStrategy.ROUND_ROBIN,
            ConflictType.MESSAGE_FLOOD: ResolutionStrategy.MEDIATION,
            ConflictType.DEADLOCK: ResolutionStrategy.ESCALATION,
        }

        strategy = strategy_map.get(conflict.conflict_type, ResolutionStrategy.MEDIATION)

        # Skip auto-resolution for critical conflicts
        if conflict.severity == ConflictSeverity.CRITICAL:
            return {"status": "escalated", "reason": "critical_severity"}

        # Execute resolution strategy
        if strategy in self._resolution_strategies:
            return await self._resolution_strategies[strategy](conflict)

        return None

    def _get_next_steps(self, conflict: Conflict) -> list[str]:
        """Get recommended next steps for a conflict."""
        steps = []

        if conflict.status == ResolutionStatus.PENDING:
            steps.append("Awaiting auto-resolution or manual intervention")
            if conflict.severity in [ConflictSeverity.HIGH, ConflictSeverity.CRITICAL]:
                steps.append("Consider escalation due to high severity")

        elif conflict.status == ResolutionStatus.IN_PROGRESS:
            steps.append("Resolution process underway")
            steps.append("Monitor for party cooperation")

        elif conflict.status == ResolutionStatus.RESOLVED:
            steps.append("Implement resolution terms")
            steps.append("Monitor for compliance")

        return steps

    def _generate_recommendations(self) -> list[str]:
        """
        Generate strategic recommendations based on conflict patterns.

        Session 44: Enhanced with collective learning pattern analysis
        and memory access pattern insights.
        """
        recommendations = []

        # Check conflict volume
        if self._stats["total_conflicts"] > 50:
            recommendations.append(
                f"High conflict volume ({self._stats['total_conflicts']}) - review agent coordination protocols"  # noqa: E501
            )

        # Check resolution success rate
        if self._stats["resolutions_failed"] > 10:
            recommendations.append(
                "Multiple failed resolutions - consider alternative resolution strategies"
            )

        # Check relationship health
        unhealthy_relationships = [r for r in self._relationships.values() if r.health_score < 0.3]
        if unhealthy_relationships:
            recommendations.append(
                f"{len(unhealthy_relationships)} relationships need attention - schedule mediation"
            )

        # Session 44: Add collective learning insights
        if self.pattern_extractor:
            validated_patterns = self.pattern_extractor.get_validated_patterns(
                pattern_type=PatternType.FAILURE,
                min_confidence=0.5,
            )
            if validated_patterns:
                recommendations.append(
                    f"Collective learning identified {len(validated_patterns)} failure patterns - review for systemic issues"  # noqa: E501
                )

        # Session 44: Add memory optimization insights
        if self.access_analyzer:
            stats = self.access_analyzer.get_statistics()
            if stats.frozen_count > stats.unique_memories * 0.5:
                recommendations.append(
                    f"High frozen memory ratio ({stats.frozen_count}/{stats.unique_memories}) - consider archive cleanup"  # noqa: E501
                )

        if not recommendations:
            recommendations.append("Collective harmony stable - continue monitoring")

        return recommendations

    # =========================================================================
    # Session 44: Collective Learning Integration Methods
    # =========================================================================

    async def _emit_conflict_pattern(self, conflict: Conflict, outcome: str) -> None:
        """
        Emit pattern for collective learning when conflict is resolved.

        Args:
            conflict: The resolved conflict
            outcome: Resolution outcome (success, failure, partial)
        """
        if not self.pattern_extractor:
            return

        if conflict.conflict_id in self._pattern_emitted_conflicts:
            return  # Already emitted

        # Emit pattern for collective learning
        try:
            # Analyze conflict resolution as a pattern
            await self.pattern_extractor.analyze_message(
                message_id=f"conflict_{conflict.conflict_id}",
                sender=self.agent_id,
                recipient="broadcast",
                message_type="conflict_resolution",
                content={
                    "conflict_type": conflict.conflict_type.value,
                    "severity": conflict.severity.value,
                    "parties": conflict.parties,
                    "outcome": outcome,
                    "resolution_strategy": conflict.selected_resolution.get("strategy")
                    if conflict.selected_resolution
                    else None,
                },
                timestamp=conflict.timestamp.isoformat(),
            )

            self._pattern_emitted_conflicts.add(conflict.conflict_id)

            logger.info(
                "conflict_pattern_emitted",
                conflict_id=conflict.conflict_id,
                outcome=outcome,
            )
        except Exception as e:
            logger.warning(
                "failed_to_emit_conflict_pattern",
                conflict_id=conflict.conflict_id,
                error=str(e),
            )

    async def _consume_resolution_patterns(self) -> list[dict[str, Any]]:
        """
        Consume patterns from collective learning for resolution guidance.

        Returns:
            List of relevant patterns for current conflict resolution
        """
        if not self.pattern_extractor:
            return []

        try:
            # Extract patterns from recent history
            patterns = await self.pattern_extractor.extract_patterns(
                time_window_hours=24,
                pattern_types=[PatternType.SUCCESS, PatternType.HANDOFF, PatternType.DECISION],
            )

            # Return high-confidence patterns for resolution guidance
            return [p.to_dict() for p in patterns if p.metadata.confidence >= 0.7]
        except Exception as e:
            logger.warning(
                "failed_to_consume_patterns",
                error=str(e),
            )
            return []

    # =========================================================================
    # Session 44: Consensus Deliberation Integration Methods
    # =========================================================================

    async def _initiate_deliberation_for_conflict(
        self,
        conflict: Conflict,
        participating_agents: list[str],
    ) -> str | None:
        """
        Initiate swarm deliberation for complex conflict resolution.

        Args:
            conflict: Conflict requiring deliberation
            participating_agents: List of agent IDs to participate

        Returns:
            Deliberation ID if initiated, None otherwise
        """
        if not self.deliberation_engine:
            return None

        try:
            deliberation_id = f"delib_{conflict.conflict_id}"

            # Start deliberation with conflict domain
            self.deliberation_engine.start_deliberation(
                deliberation_id=deliberation_id,
                proposal=f"Resolve conflict: {conflict.description[:100]}",
                participants=participating_agents,
                domain="conflict_resolution",
            )

            # Store mapping
            self._active_deliberations[conflict.conflict_id] = deliberation_id

            logger.info(
                "deliberation_initiated",
                deliberation_id=deliberation_id,
                conflict_id=conflict.conflict_id,
                participants=len(participating_agents),
            )

            return deliberation_id
        except Exception as e:
            logger.error(
                "failed_to_initiate_deliberation",
                conflict_id=conflict.conflict_id,
                error=str(e),
            )
            return None

    async def _submit_deliberation_position(
        self,
        conflict: Conflict,
        agent_id: str,
        position: Position,
        confidence: float,
        argument: str,
    ) -> bool:
        """
        Submit agent position in conflict deliberation.

        Args:
            conflict: Related conflict
            agent_id: Submitting agent
            position: Agent position (AGREE, DISAGREE, etc.)
            confidence: Confidence level
            argument: Supporting argument

        Returns:
            True if position submitted successfully
        """
        if not self.deliberation_engine:
            return False

        deliberation_id = self._active_deliberations.get(conflict.conflict_id)
        if not deliberation_id:
            return False

        try:
            success = self.deliberation_engine.submit_position(
                deliberation_id=deliberation_id,
                agent_id=agent_id,
                position=position,
                confidence=confidence,
                argument=argument,
            )

            if success:  # noqa: SIM102
                # Track memory access for deliberation
                if self.access_analyzer:
                    self.access_analyzer.record_access(
                        memory_id=f"delib_{deliberation_id}_{agent_id}",
                        access_type="write",
                        agent_id=agent_id,
                    )

            return success
        except Exception as e:
            logger.error(
                "failed_to_submit_deliberation_position",
                deliberation_id=deliberation_id,
                error=str(e),
            )
            return False

    async def _finalize_deliberation(self, conflict: Conflict) -> DeliberationResult | None:
        """
        Finalize deliberation and apply result to conflict.

        Args:
            conflict: Related conflict

        Returns:
            Deliberation result if successful
        """
        if not self.deliberation_engine:
            return None

        deliberation_id = self._active_deliberations.get(conflict.conflict_id)
        if not deliberation_id:
            return None

        try:
            result = self.deliberation_engine.finalize_deliberation(deliberation_id)

            if result:
                # Apply deliberation result to conflict
                conflict.selected_resolution = {
                    "strategy": "consensus_deliberation",
                    "deliberation_id": deliberation_id,
                    "final_position": result.final_position.value,
                    "consensus_score": result.consensus_score,
                    "minority_report": result.minority_report,
                }
                conflict.status = ResolutionStatus.RESOLVED
                conflict.resolved_at = datetime.now(UTC)

                # Clean up deliberation
                self.deliberation_engine.cleanup_deliberation(deliberation_id)
                del self._active_deliberations[conflict.conflict_id]

                logger.info(
                    "deliberation_finalized",
                    deliberation_id=deliberation_id,
                    consensus_score=result.consensus_score,
                )

            return result
        except Exception as e:
            logger.error(
                "failed_to_finalize_deliberation",
                deliberation_id=deliberation_id,
                error=str(e),
            )
            return None

    # =========================================================================
    # Session 44: Memory Optimization Integration Methods
    # =========================================================================

    def _track_resolution_memory_access(self, conflict_id: str, access_type: str = "read") -> None:
        """
        Track memory access patterns for conflict resolution data.

        Args:
            conflict_id: Conflict identifier
            access_type: Type of access (read/write/delete)
        """
        if not self.access_analyzer:
            return

        memory_id = f"conflict_{conflict_id}"
        self.access_analyzer.record_access(
            memory_id=memory_id,
            access_type=access_type,
            agent_id=self.agent_id,
        )

    def _get_conflict_memory_tier(self, conflict_id: str) -> AccessTier:
        """
        Get memory tier classification for a conflict.

        Args:
            conflict_id: Conflict identifier

        Returns:
            Access tier (HOT, WARM, COLD, FROZEN)
        """
        if not self.access_analyzer:
            return AccessTier.COLD

        memory_id = f"conflict_{conflict_id}"
        profile = self.access_analyzer.get_profile(memory_id)

        return profile.tier if profile else AccessTier.COLD

    # -------------------------------------------------------------------------
    # Delegation methods - forward to standalone functions in strategies module
    # -------------------------------------------------------------------------

    async def _conduct_mediation(
        self,
        sender: str,
        other_party: str,
        dispute: str,
        proposed_solution: str | None = None,
    ) -> dict[str, Any]:
        """Conduct mediation between two parties."""
        from heretek_swarm.actors.arbiter import strategies

        return await strategies._conduct_mediation(  # noqa: SLF001
            self, sender, other_party, dispute, proposed_solution
        )

    async def _resolve_resource_contention(
        self,
        resource: str | None,
        competing_agents: list[str],
        priority_override: dict[str, int],
    ) -> dict[str, Any]:
        """Resolve contention over a resource."""
        from heretek_swarm.actors.arbiter import strategies

        return await strategies._resolve_resource_contention(  # noqa: SLF001
            self, resource, competing_agents, priority_override
        )

    async def _resolve_task_contention(
        self,
        competing_agents: list[str],
        priority_override: dict[str, int],
    ) -> dict[str, Any]:
        """Resolve contention over task ownership."""
        from heretek_swarm.actors.arbiter import strategies

        return await strategies._resolve_task_contention(self, competing_agents, priority_override)  # noqa: SLF001

    async def _resolve_generic_contention(
        self,
        contention_type: str,
        competing_agents: list[str],
    ) -> dict[str, Any]:
        """Resolve generic contention."""
        from heretek_swarm.actors.arbiter import strategies

        return await strategies._resolve_generic_contention(self, contention_type, competing_agents)  # noqa: SLF001

    async def _prefetch_relevant_conflicts(self, agent_id: str) -> list[str]:
        """
        Prefetch conflicts an agent is likely to need based on access patterns.

        Args:
            agent_id: Agent identifier

        Returns:
            List of predicted conflict IDs to prefetch
        """
        if not self.access_analyzer:
            return []

        try:
            predicted_memories = self.access_analyzer.predict_agent_access(agent_id)

            # Extract conflict IDs from memory IDs
            return [
                mem.replace("conflict_", "")
                for mem in predicted_memories
                if mem.startswith("conflict_")
            ]

        except Exception as e:
            logger.warning(
                "failed_to_prefetch_conflicts",
                agent_id=agent_id,
                error=str(e),
            )
            return []
