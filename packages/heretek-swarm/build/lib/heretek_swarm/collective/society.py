"""
Agent Society - Collective Intelligence Model

Implements agent society with hierarchical coordination, emergent behavior detection,
and collective memory. Inspired by CAMEL agent society patterns and swarm intelligence.

Features:
- Hierarchical agent coordination
- Collective decision-making
- Emergent behavior detection
- Shared collective memory
- Swarm optimization algorithms
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional, cast

import structlog

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = structlog.get_logger(__name__)

# Import swarm intelligence patterns for integration
try:
    from .swarm_intelligence import (
        SwarmDecision,
        SwarmIntelligenceEngine,
        SwarmPattern,
    )

    SWARM_INTELLIGENCE_AVAILABLE = True
except ImportError:
    SWARM_INTELLIGENCE_AVAILABLE = False
    logger.warning("Swarm intelligence module not available")


class ContributionCache:
    """
    Cache for agent contributions with TTL support.

    Prevents duplicate requests and improves performance.
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize contribution cache.

        Args:
            ttl_seconds: Time to live for cached entries (default: 5 minutes)
        """
        self._cache: dict[str, dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds

    def _generate_key(self, agent_id: str, task_id: str) -> str:
        """Generate cache key from agent and task IDs."""
        return f"{agent_id}:{task_id}"

    def get(self, agent_id: str, task_id: str) -> Optional["AgentContribution"]:
        """
        Get cached contribution if not expired.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier

        Returns:
            Cached contribution or None if expired/not found
        """
        key = self._generate_key(agent_id, task_id)
        if key in self._cache:
            entry = self._cache[key]
            if datetime.fromisoformat(entry["expires_at"]) > datetime.now(UTC):
                return cast("AgentContribution", entry["contribution"])
            # Expired, remove from cache
            del self._cache[key]
        return None

    def set(self, agent_id: str, task_id: str, contribution: "AgentContribution") -> None:
        """
        Cache a contribution.

        Args:
            agent_id: Agent identifier
            task_id: Task identifier
            contribution: Contribution to cache
        """
        key = self._generate_key(agent_id, task_id)
        self._cache[key] = {
            "contribution": contribution,
            "expires_at": (datetime.now(UTC) + timedelta(seconds=self._ttl_seconds)).isoformat(),
        }
        logger.debug("contribution_cacheded", agent_id=agent_id, task_id=task_id)

    def invalidate(self, agent_id: str, task_id: str) -> None:
        """Invalidate a cached contribution."""
        key = self._generate_key(agent_id, task_id)
        if key in self._cache:
            del self._cache[key]
            logger.debug("contribution_invalidated", agent_id=agent_id, task_id=task_id)

    def clear(self) -> None:
        """Clear all cached contributions."""
        self._cache.clear()
        logger.info("contribution_cache_cleared")


class SocietyRole(StrEnum):
    """Roles within agent society."""

    LEADERSHIP = "leadership"
    ANALYSIS = "analysis"
    SUPPORT = "support"
    EXPLORATION = "exploration"
    DEVELOPMENT = "development"
    SAFETY = "safety"
    COORDINATION = "coordination"


class CollectiveTaskType(StrEnum):
    """Types of collective tasks."""

    DELIBERATION = "deliberation"
    CONSENSUS = "consensus"
    COORDINATION = "coordination"
    OPTIMIZATION = "optimization"
    LEARNING = "learning"
    MONITORING = "monitoring"
    EXPLORATION = "exploration"


@dataclass
class CollectiveTask:
    """A task requiring collective agent coordination."""

    id: str
    type: CollectiveTaskType
    description: str
    input_data: dict[str, Any]
    priority: float = 0.5
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    deadline: str | None = None
    participants: list[str] = field(default_factory=list)
    status: str = "pending"
    result: dict[str, Any] | None = None


@dataclass
class CollectiveResult:
    """Result of collective task execution."""

    task_id: str
    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None
    participants: list[str] = field(default_factory=list)
    execution_time: float = 0.0
    consensus_score: float = 0.0
    emergent_behavior: str | None = None


@dataclass
class AgentContribution:
    """Contribution of an agent to collective task."""

    agent_id: str
    task_id: str
    contribution: dict[str, Any]
    confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class EmergentBehavior:
    """Detected emergent behavior in agent society."""

    id: str
    behavior_type: str
    description: str
    participants: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    confidence: float = 0.0
    impact: str = "unknown"


class CollectiveMemory:
    """
    Shared memory for agent society.

    Stores collective knowledge, patterns, and learnings.
    """

    def __init__(self) -> None:
        self._memory: dict[str, Any] = {}
        self._patterns: list[dict[str, Any]] = []
        self._learnings: list[dict[str, Any]] = []

    async def store(
        self, key: str, value: Any, source: str = "collective", importance: float = 0.5
    ) -> None:
        """Store knowledge in collective memory."""
        self._memory[key] = {
            "value": value,
            "source": source,
            "importance": importance,
            "timestamp": datetime.now(UTC).isoformat(),
            "access_count": 0,
        }
        logger.debug("collective_memory_stored", key=key, source=source)

    async def retrieve(self, key: str) -> dict[str, Any] | None:
        """Retrieve knowledge from collective memory."""
        if key in self._memory:
            self._memory[key]["access_count"] += 1
            self._memory[key]["last_accessed"] = datetime.now(UTC).isoformat()
            return cast("dict[str, Any]", self._memory[key])
        return None

    async def add_pattern(
        self, pattern_type: str, pattern_data: dict[str, Any], confidence: float = 0.5
    ) -> None:
        """Add discovered pattern to collective memory."""
        pattern = {
            "id": str(uuid.uuid4()),
            "type": pattern_type,
            "data": pattern_data,
            "confidence": confidence,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._patterns.append(pattern)
        logger.info("pattern_discovered", type=pattern_type, confidence=confidence)

    async def add_learning(
        self, learning_type: str, learning_data: dict[str, Any], participants: list[str]
    ) -> None:
        """Add collective learning to memory."""
        learning = {
            "id": str(uuid.uuid4()),
            "type": learning_type,
            "data": learning_data,
            "participants": participants,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self._learnings.append(learning)
        logger.info("collective_learning", type=learning_type, participants=len(participants))

    async def get_patterns(
        self, pattern_type: str | None = None, min_confidence: float = 0.0
    ) -> list[dict[str, Any]]:
        """Get patterns from collective memory."""
        patterns = self._patterns
        if pattern_type:
            patterns = [p for p in patterns if p["type"] == pattern_type]
        return [p for p in patterns if p["confidence"] >= min_confidence]

    async def get_learnings(
        self, learning_type: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get learnings from collective memory."""
        learnings = self._learnings
        if learning_type:
            learnings = [learning for learning in learnings if learning["type"] == learning_type]
        return learnings[-limit:]


class AgentSociety:
    """
    Agent Society for collective intelligence.

    Manages hierarchical coordination, collective decision-making,
    and emergent behavior detection.
    """

    def __init__(
        self,
        supervisor: Any = None,
        contribution_cache_ttl: int = 300,
        enable_swarm_intelligence: bool = True,
        exploration_mode: bool = False,
    ) -> None:
        """
        Initialize agent society.

        Args:
            supervisor: ActorSupervisor for agent management
            contribution_cache_ttl: TTL for contribution cache in seconds (default: 300)
            enable_swarm_intelligence: Enable swarm intelligence patterns (default: True)
            exploration_mode: Enable dedicated exploration mode with
                swarm exploration (default: False)
        """
        self.supervisor = supervisor
        self.hierarchy = self._build_hierarchy()
        self.interaction_rules = self._define_rules()
        self.collective_memory = CollectiveMemory()
        self._active_tasks: dict[str, CollectiveTask] = {}
        self._emergent_behaviors: list[EmergentBehavior] = []
        self._contribution_cache = ContributionCache(ttl_seconds=contribution_cache_ttl)
        self.exploration_mode = exploration_mode

        # Task types routed to swarm exploration layer when exploration_mode=True
        self._exploration_task_types = {
            CollectiveTaskType.EXPLORATION,
            CollectiveTaskType.OPTIMIZATION,
        }

        # Initialize swarm intelligence engine if available
        self.swarm_engine: SwarmIntelligenceEngine | None = None
        if enable_swarm_intelligence and SWARM_INTELLIGENCE_AVAILABLE:
            self.swarm_engine = SwarmIntelligenceEngine()
            logger.info("swarm_intelligence_enabled")
        elif enable_swarm_intelligence and not SWARM_INTELLIGENCE_AVAILABLE:
            logger.warning("swarm_intelligence_requested_but_not_available")

    def _build_hierarchy(self) -> dict[str, list[str]]:
        """
        Build agent hierarchy for coordination.

        Returns:
            Dict mapping roles to agent types
        """
        return {
            SocietyRole.LEADERSHIP: ["steward", "alpha", "arbiter"],
            SocietyRole.ANALYSIS: ["alpha", "beta", "charlie", "examiner"],
            SocietyRole.SUPPORT: ["historian", "metis", "empath", "nexus"],
            SocietyRole.EXPLORATION: ["explorer", "perceiver"],
            SocietyRole.DEVELOPMENT: ["coder", "dreamer", "catalyst"],
            SocietyRole.SAFETY: ["sentinel", "sentinel-prime"],
            SocietyRole.COORDINATION: ["coordinator", "chronos"],
        }

    def _define_rules(self) -> dict[str, Any]:
        """
        Define interaction rules for agent society.

        Returns:
            Dict of interaction rules
        """
        return {
            "handoff_rules": {
                "analysis_to_support": ["alpha", "beta", "charlie"],
                "support_to_leadership": ["historian", "metis"],
                "exploration_to_analysis": ["explorer", "perceiver"],
                "development_to_safety": ["coder", "dreamer"],
            },
            "consensus_threshold": 0.7,
            "min_participants": 2,
            "max_participants": 10,
            "timeout_seconds": 300,
        }

    async def coordinate_task(self, task: CollectiveTask) -> CollectiveResult:
        """
        Coordinate agents for collective task.

        Args:
            task: Collective task to execute

        Returns:
            CollectiveResult with outcome
        """
        task_id = task.id
        logger.info(
            "coordinating_task", task_id=task_id, type=task.type, description=task.description
        )

        start_time = datetime.now(UTC)

        try:
            # Route to swarm exploration if exploration_mode enabled and task type matches
            if self.exploration_mode and task.type in self._exploration_task_types:
                return await self._execute_swarm_exploration(task)

            # Select participants based on task type
            participants = self._select_participants(task)
            task.participants = participants

            # Establish communication protocol
            protocol = self._establish_protocol(participants, task)

            # Execute coordinated action
            result = await self._execute_coordination(participants, protocol, task)

            # Store in collective memory
            await self.collective_memory.add_learning(
                learning_type=task.type, learning_data=result, participants=participants
            )

            # Detect emergent behavior
            emergent = await self._detect_emergent_behavior(participants, task, result)

            execution_time = (datetime.now(UTC) - start_time).total_seconds()

            collective_result = CollectiveResult(
                task_id=task_id,
                success=True,
                result=result,
                participants=participants,
                execution_time=execution_time,
                consensus_score=result.get("consensus_score", 0.0),
                emergent_behavior=emergent,
            )

            task.status = "completed"
            task.result = result
            self._active_tasks[task_id] = task

            logger.info(
                "task_completed",
                task_id=task_id,
                participants=len(participants),
                execution_time=execution_time,
            )

            return collective_result

        except Exception as e:
            logger.error("task_failed", task_id=task_id, error=str(e))
            return CollectiveResult(task_id=task_id, success=False, error=str(e))

    def _select_participants(self, task: CollectiveTask) -> list[str]:
        """
        Select participants based on task type and hierarchy.

        Args:
            task: Collective task

        Returns:
            List of agent IDs
        """
        # Map task types to roles
        task_role_map = {
            CollectiveTaskType.DELIBERATION: [
                SocietyRole.LEADERSHIP,
                SocietyRole.ANALYSIS,
                SocietyRole.SUPPORT,
            ],
            CollectiveTaskType.CONSENSUS: [SocietyRole.LEADERSHIP, SocietyRole.ANALYSIS],
            CollectiveTaskType.COORDINATION: [SocietyRole.COORDINATION, SocietyRole.LEADERSHIP],
            CollectiveTaskType.OPTIMIZATION: [SocietyRole.DEVELOPMENT, SocietyRole.ANALYSIS],
            CollectiveTaskType.LEARNING: [SocietyRole.SUPPORT, SocietyRole.EXPLORATION],
            CollectiveTaskType.MONITORING: [SocietyRole.SAFETY, SocietyRole.COORDINATION],
        }

        roles = task_role_map.get(task.type, [SocietyRole.LEADERSHIP])
        participants: list[str] = []

        # Get agents for each role
        for role in roles:
            agent_types = self.hierarchy.get(role, [])
            participants.extend(
                at for at in agent_types if self.supervisor and at in self.supervisor.actors
            )

        # Limit participants
        max_participants = self.interaction_rules.get("max_participants", 10)
        if len(participants) > max_participants:
            participants = participants[:max_participants]

        # Ensure minimum participants
        min_participants = self.interaction_rules.get("min_participants", 2)
        if len(participants) < min_participants:
            logger.warning(
                "insufficient_participants",
                task_type=task.type,
                available=len(participants),
                required=min_participants,
            )

        return participants

    def _establish_protocol(self, participants: list[str], task: CollectiveTask) -> dict[str, Any]:
        """
        Establish communication protocol for coordination.

        Args:
            participants: List of participant agents
            task: Collective task

        Returns:
            Protocol configuration
        """
        return {
            "task_id": task.id,
            "participants": participants,
            "communication_pattern": "broadcast",
            "consensus_threshold": self.interaction_rules.get("consensus_threshold", 0.7),
            "timeout": self.interaction_rules.get("timeout_seconds", 300),
            "rounds": 3,  # Number of deliberation rounds
        }

    async def _execute_swarm_exploration(
        self,
        task: CollectiveTask,
    ) -> CollectiveResult:
        """
        Execute task via swarm exploration layer.

        Routes to either bee_algorithm (EXPLORATION) or pso (OPTIMIZATION) via
        apply_swarm_pattern. Falls back to TRIAD hierarchy if the swarm engine is
        unavailable or apply_swarm_pattern returns None.

        Args:
            task: Collective task with EXPLORATION or OPTIMIZATION type

        Returns:
            CollectiveResult with swarm exploration outcome
        """
        pattern_map = {
            CollectiveTaskType.EXPLORATION: "bee_algorithm",
            CollectiveTaskType.OPTIMIZATION: "pso",
        }
        pattern = pattern_map.get(task.type, "bee_algorithm")

        logger.info(
            "swarm_exploration_started",
            task_id=task.id,
            task_type=task.type.value,
            pattern=pattern,
            exploration_mode=self.exploration_mode,
        )

        if not self.swarm_engine:
            logger.error("swarm_engine_not_available")
            return await self._execute_coordination_fallback(task, task.participants)

        try:
            # Build decision space from task input_data
            decision_space = {
                str(k): float(v) if isinstance(v, (int, float)) else 0.0
                for k, v in task.input_data.items()
            }
            # Seed with task description as a dimension
            if task.description:
                decision_space["_task"] = 1.0

            # Delegate to apply_swarm_pattern for consistent pattern execution
            swarm_result = await self.apply_swarm_pattern(
                pattern=pattern,
                participants=task.participants or [],
                decision_space=decision_space,
                max_iterations=50,
            )

            # Fall back to TRIAD if swarm returned None (engine unavailable)
            if swarm_result is None:
                return await self._execute_coordination_fallback(task, task.participants)

            # Extract bee/flock counts from participants for backwards-compatible result
            bee_count = min(5, len(task.participants) or 5)
            flock_count = len(task.participants) or 1

            result = {
                "swarm_decision": swarm_result,
                "swarm_pattern": pattern,
                "bee_agents": bee_count,
                "flocking_agents": flock_count,
                "confidence": swarm_result["confidence"],
                "emergence_indicators": swarm_result["emergence_indicators"],
            }

            # Store in collective memory
            await self.collective_memory.add_learning(
                learning_type="exploration",
                learning_data=result,
                participants=task.participants,
            )

            return CollectiveResult(
                task_id=task.id,
                success=True,
                result=result,
                participants=task.participants or [],
                execution_time=0.0,
                consensus_score=swarm_result["confidence"],
                emergent_behavior=(
                    swarm_result["emergence_indicators"][0]
                    if swarm_result["emergence_indicators"]
                    else None
                ),
            )

        except Exception as e:
            logger.error("swarm_exploration_failed", task_id=task.id, error=str(e))
            return await self._execute_coordination_fallback(task, task.participants)

    async def _execute_coordination_fallback(
        self,
        task: CollectiveTask,
        participants: list[str],
    ) -> CollectiveResult:
        """
        Fall back to standard TRIAD hierarchy when swarm layer is unavailable.

        Called when exploration_mode=True but the swarm engine raised an exception
        or returned None. Preserves hierarchy authority by routing through the
        established TRIAD coordination protocol.

        Args:
            task: Collective task to execute
            participants: List of participant agent IDs

        Returns:
            CollectiveResult from TRIAD coordination
        """
        logger.info(
            "swarm_exploration_fell_back_to_hierarchy",
            task_id=task.id,
            task_type=task.type.value,
            participants=len(participants),
        )
        protocol = self._establish_protocol(participants, task)
        result = await self._execute_coordination(participants, protocol, task)

        execution_time = 0.0  # Already logged above
        return CollectiveResult(
            task_id=task.id,
            success=True,
            result=result,
            participants=participants,
            execution_time=execution_time,
            consensus_score=result.get("consensus_score", 0.0),
            emergent_behavior=None,
        )

    async def _execute_coordination(
        self, participants: list[str], protocol: dict[str, Any], task: CollectiveTask
    ) -> dict[str, Any]:
        """
        Execute coordinated action among participants.

        Args:
            participants: List of participant agents
            protocol: Communication protocol
            task: Collective task

        Returns:
            Coordination result
        """
        contributions = []

        # Collect contributions from all participants
        for participant in participants:
            if self.supervisor and participant in self.supervisor.actors:
                actor = self.supervisor.actors[participant]
                try:
                    # Simulate agent contribution
                    contribution = await self._get_agent_contribution(actor, task, protocol)
                    contributions.append(contribution)
                except Exception as e:
                    logger.error("contribution_failed", participant=participant, error=str(e))

        # Aggregate contributions
        return await self._aggregate_contributions(contributions, task, protocol)

    async def _get_agent_contribution(
        self,
        actor: Any,
        task: CollectiveTask,
        protocol: dict[str, Any],
    ) -> AgentContribution:
        """
        Get contribution from an agent by invoking its process method.

        This method:
        1. Checks cache for existing contribution
        2. Calls actor's process_contribution method if available
        3. Falls back to run_with_llm if actor has LLM capabilities
        4. Waits for response with timeout
        5. Caches the contribution for future requests
        6. Returns properly formatted AgentContribution

        Args:
            actor: Agent actor (must be an AgentActor instance)
            task: Collective task to process
            protocol: Communication protocol
            timeout: Timeout in seconds for contribution request (default: 30s)

        Returns:
            AgentContribution with agent's response

        Raises:
            asyncio.TimeoutError: If actor doesn't respond within timeout
        """
        # Get actor ID
        agent_id = actor.agent_id if hasattr(actor, "agent_id") else str(type(actor).__name__)

        # Check cache first
        cached = self._contribution_cache.get(agent_id, task.id)
        if cached is not None:
            logger.debug("contribution_cache_hit", agent_id=agent_id, task_id=task.id)
            return cached

        try:
            # Try to get contribution via direct method call
            contribution_data = await self._request_contribution_from_actor(actor, task, protocol)

            # Create AgentContribution
            contribution = AgentContribution(
                agent_id=agent_id,
                task_id=task.id,
                contribution=contribution_data.get("contribution", {}),
                confidence=contribution_data.get("confidence", 0.8),
            )

            # Cache the contribution
            self._contribution_cache.set(agent_id, task.id, contribution)

            logger.info(
                "contribution_received",
                agent_id=agent_id,
                task_id=task.id,
                confidence=contribution.confidence,
            )

            return contribution

        except TimeoutError:
            logger.error("contribution_timeout", agent_id=agent_id, task_id=task.id, timeout=30.0)
            raise
        except Exception as e:
            logger.error("contribution_error", agent_id=agent_id, task_id=task.id, error=str(e))
            # Return fallback contribution on error
            return AgentContribution(
                agent_id=agent_id,
                task_id=task.id,
                contribution={
                    "analysis": f"Error retrieving contribution from {agent_id}: {e!s}",
                    "recommendation": "error_fallback",
                    "error": str(e),
                },
                confidence=0.1,  # Low confidence for error fallback
            )

    async def _request_contribution_from_actor(
        self,
        actor: Any,
        task: CollectiveTask,
        protocol: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Request contribution from an actor using available methods.

        This method tries multiple approaches:
        1. Direct process_contribution method if available
        2. run_with_llm if Swarms agent is configured
        3. Default fallback based on actor type

        Args:
            actor: Agent actor instance
            task: Collective task
            protocol: Communication protocol

        Returns:
            Dict with contribution data and confidence
        """
        # Prepare task context for the actor
        {
            "task_id": task.id,
            "task_type": task.type.value if hasattr(task.type, "value") else str(task.type),
            "description": task.description,
            "input_data": task.input_data,
            "priority": task.priority,
            "protocol": protocol,
        }

        # Try direct method call if actor has process_contribution
        if hasattr(actor, "process_contribution") and callable(actor.process_contribution):
            async with asyncio.timeout(30.0):
                return await actor.process_contribution(task, protocol)  # type: ignore[no-any-return]

        # Try using LLM if available
        if hasattr(actor, "run_with_llm") and actor.swarms_agent is not None:
            prompt = self._build_contribution_prompt(task, protocol)
            async with asyncio.timeout(30.0):
                response = await actor.run_with_llm(prompt)
            return {
                "contribution": {
                    "analysis": response,
                    "recommendation": "llm_generated",
                    "method": "run_with_llm",
                },
                "confidence": 0.75,
            }

        # Fallback: Generate contribution based on actor type
        actor_type = type(actor).__name__
        return {
            "contribution": {
                "analysis": f"Analysis from {actor_type} for task: {task.description}",
                "recommendation": f"{actor_type}_recommendation",
                "method": "fallback",
            },
            "confidence": 0.6,
        }

    def _build_contribution_prompt(self, task: CollectiveTask, protocol: dict[str, Any]) -> str:
        """
        Build a prompt for LLM-based contribution.

        Args:
            task: Collective task
            protocol: Communication protocol

        Returns:
            Formatted prompt string
        """
        return f"""You are participating in a collective task coordination.

Task Details:
- Task ID: {task.id}
- Task Type: {task.type.value if hasattr(task.type, "value") else str(task.type)}
- Description: {task.description}
- Priority: {task.priority}
- Input Data: {task.input_data}

Protocol:
- Consensus Threshold: {protocol.get("consensus_threshold", 0.7)}
- Communication Pattern: {protocol.get("communication_pattern", "broadcast")}
- Rounds: {protocol.get("rounds", 3)}

Please provide your analysis and recommendation for this collective task.
Format your response as:
1. Analysis: Your understanding of the task and key considerations
2. Recommendation: Your suggested approach or solution
"""

    async def _aggregate_contributions(
        self,
        contributions: list[AgentContribution],
        _task: CollectiveTask,
        protocol: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Aggregate contributions from multiple agents.

        Args:
            contributions: List of agent contributions
            task: Collective task
            protocol: Communication protocol

        Returns:
            Aggregated result
        """
        if not contributions:
            return {"status": "failed", "reason": "no_contributions"}

        # Calculate consensus score
        consensus_threshold = protocol.get("consensus_threshold", 0.7)
        avg_confidence = sum(c.confidence for c in contributions) / len(contributions)
        consensus_score = min(avg_confidence / consensus_threshold, 1.0)

        # Aggregate recommendations
        recommendations = [
            c.contribution.get("recommendation")
            for c in contributions
            if c.contribution.get("recommendation")
        ]

        # Simple majority voting
        if recommendations:
            from collections import Counter

            vote_counts = Counter(recommendations)
            top_recommendation = vote_counts.most_common(1)[0][0]
        else:
            top_recommendation = "no_consensus"

        return {
            "status": "completed",
            "consensus_score": consensus_score,
            "recommendation": top_recommendation,
            "participant_count": len(contributions),
            "contributions": [
                {"agent_id": c.agent_id, "confidence": c.confidence, "contribution": c.contribution}
                for c in contributions
            ],
        }

    async def _detect_emergent_behavior(
        self, participants: list[str], task: CollectiveTask, result: dict[str, Any]
    ) -> str | None:
        """
        Detect emergent behavior in agent society.

        Args:
            participants: List of participant agents
            task: Collective task
            result: Coordination result

        Returns:
            Description of emergent behavior or None
        """
        # Check for high consensus
        consensus_score = result.get("consensus_score", 0.0)
        if consensus_score > 0.9:
            behavior = EmergentBehavior(
                id=str(uuid.uuid4()),
                behavior_type="high_consensus",
                description=f"Agents achieved {consensus_score:.2f} consensus",
                participants=participants,
                confidence=consensus_score,
                impact="positive",
            )
            self._emergent_behaviors.append(behavior)
            await self.collective_memory.add_pattern(
                pattern_type="consensus",
                pattern_data={
                    "task_type": task.type,
                    "participants": participants,
                    "score": consensus_score,
                },
                confidence=consensus_score,
            )
            return behavior.description

        # Check for diverse opinions
        participant_count = len(participants)
        unique_contributions = len(result.get("contributions", []))
        if unique_contributions == participant_count and participant_count > 3:
            behavior = EmergentBehavior(
                id=str(uuid.uuid4()),
                behavior_type="diverse_perspective",
                description=f"All {participant_count} agents provided unique contributions",
                participants=participants,
                confidence=0.8,
                impact="positive",
            )
            self._emergent_behaviors.append(behavior)
            return behavior.description

        return None

    async def apply_swarm_pattern(
        self,
        pattern: str,
        participants: list[str],
        decision_space: dict[str, float],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """
        Apply a swarm intelligence pattern to a decision problem.

        This method delegates to the swarm intelligence engine to apply
        bio-inspired patterns for collective decision-making.

        Args:
            pattern: Swarm pattern to apply ("pso", "ant_colony", "bee_algorithm",
                     "flocking", "stigmergy")
            participants: List of participant agent IDs
            decision_space: Decision space as a dictionary of options and values
            **kwargs: Additional parameters for the specific pattern

        Returns:
            Dictionary with swarm decision results or None if swarm engine unavailable

        Raises:
            ValueError: If invalid pattern specified
        """
        if not self.swarm_engine:
            logger.warning("swarm_pattern_requested_but_engine_unavailable")
            return None

        pattern_map = {
            "pso": self.swarm_engine.run_pso,
            "ant_colony": self.swarm_engine.run_ant_colony,
            "bee_algorithm": self.swarm_engine.run_bee_algorithm,
            "flocking": self.swarm_engine.run_flocking,
            "stigmergy": self.swarm_engine.run_stigmergy,
        }

        if pattern.lower() not in pattern_map:
            raise ValueError(
                f"Invalid swarm pattern: {pattern}. Valid options: {list(pattern_map.keys())}"
            )

        logger.info(
            "applying_swarm_pattern",
            pattern=pattern,
            participants=len(participants),
        )

        # Execute the swarm pattern
        swarm_decision: SwarmDecision = await cast(
            "Callable[..., Awaitable[SwarmDecision]]", pattern_map[pattern.lower()]
        )(
            participants=participants,
            decision_space=decision_space,
            **kwargs,
        )

        # Store result in collective memory
        await self.collective_memory.add_pattern(
            pattern_type=f"swarm_{pattern}",
            pattern_data={
                "decision": swarm_decision.final_position,
                "confidence": swarm_decision.confidence,
                "participants": participants,
                "iterations": swarm_decision.convergence_iterations,
                "emergence_detected": bool(swarm_decision.emergence_indicators),
                "quality_metrics": swarm_decision.quality_metrics,
            },
            confidence=swarm_decision.confidence,
        )

        # Check for emergent behavior
        if swarm_decision.emergence_indicators:
            emergent = EmergentBehavior(
                id=str(uuid.uuid4()),
                behavior_type=f"swarm_{pattern}_emergence",
                description=f"Emergent behavior detected in {pattern} pattern",
                participants=participants,
                confidence=swarm_decision.confidence,
                impact=(
                    "positive"
                    if swarm_decision.quality_metrics.get("convergence_rate", 0) > 0.7
                    else "neutral"
                ),
            )
            self._emergent_behaviors.append(emergent)

        return {
            "decision": swarm_decision.final_position,
            "confidence": swarm_decision.confidence,
            "iterations": swarm_decision.convergence_iterations,
            "emergence_detected": bool(swarm_decision.emergence_indicators),
            "quality_metrics": swarm_decision.quality_metrics,
            "pattern_type": pattern,
        }

    async def run_collective_optimization(
        self,
        task: CollectiveTask,
        optimization_type: str = "pso",
        max_iterations: int = 50,
    ) -> CollectiveResult:
        """
        Run collective optimization using swarm intelligence.

        This method integrates swarm patterns into the collective task execution
        flow, enabling bio-inspired optimization for complex decision problems.

        Args:
            task: Collective task to optimize
            optimization_type: Type of optimization ("pso", "ant_colony", "bee_algorithm")
            max_iterations: Maximum optimization iterations

        Returns:
            CollectiveResult with optimization outcome
        """
        start_time = datetime.now(UTC)

        if not self.swarm_engine:
            return CollectiveResult(
                task_id=task.id,
                success=False,
                error="Swarm intelligence engine not available",
            )

        logger.info(
            "running_collective_optimization",
            task_id=task.id,
            type=optimization_type,
        )

        # Convert task to decision space
        decision_space = {
            str(k): v if isinstance(v, float) else float(v) for k, v in task.input_data.items()
        }

        # Select participants based on task requirements
        participants = task.participants or self._select_participants(task)

        try:
            # Apply swarm pattern
            result = await self.apply_swarm_pattern(
                pattern=optimization_type,
                participants=participants,
                decision_space=decision_space,
                max_iterations=max_iterations,
            )

            if result is None:
                return CollectiveResult(
                    task_id=task.id,
                    success=False,
                    error="Swarm pattern execution failed",
                )

            execution_time = (datetime.now(UTC) - start_time).total_seconds()

            return CollectiveResult(
                task_id=task.id,
                success=True,
                result=result,
                participants=participants,
                execution_time=execution_time,
                consensus_score=result.get("confidence", 0.0),
                emergent_behavior=result.get("emergence_detected", False),
            )

        except Exception as e:
            logger.exception("collective_optimization_failed", task_id=task.id, error=str(e))
            return CollectiveResult(
                task_id=task.id,
                success=False,
                error=str(e),
                participants=participants,
            )

    def set_exploration_mode(self, enabled: bool) -> None:
        """
        Toggle exploration mode at runtime without re-initializing.

        When enabled, EXPLORATION and OPTIMIZATION collective tasks are routed
        through the swarm exploration layer instead of standard coordination.

        Args:
            enabled: True to enable exploration mode, False to disable
        """
        self.exploration_mode = enabled
        logger.info("exploration_mode_updated", enabled=enabled)

    def get_swarm_status(self) -> dict[str, Any]:
        """
        Get status of swarm intelligence engine.

        Returns:
            Dictionary with swarm engine status
        """
        if not self.swarm_engine:
            return {"available": False, "enabled": False}

        return {
            "available": True,
            "enabled": True,
            "patterns_available": [p.value for p in SwarmPattern],
            "active_flocking_agents": len(self.swarm_engine.flocking_agents),
            "stigmergic_traces": len(self.swarm_engine.traces),
            "exploration_mode_active": self.exploration_mode,
            "exploration_engine_available": self.swarm_engine is not None,
        }

    async def optimize_swarm(self, metrics: dict[str, Any]) -> dict[str, Any]:
        """
        Optimize swarm based on performance metrics.

        Args:
            metrics: Performance metrics

        Returns:
            Optimization recommendations
        """
        logger.info("optimizing_swarm", metrics=metrics)

        recommendations = []

        # Analyze agent performance
        if "agent_performance" in metrics:
            for agent_id, perf in metrics["agent_performance"].items():
                if perf.get("error_rate", 0) > 0.1:
                    recommendations.append(
                        {
                            "type": "agent_reconfiguration",
                            "target": agent_id,
                            "reason": "high_error_rate",
                            "suggestion": "review_agent_configuration",
                        }
                    )

        # Analyze communication patterns
        if "communication_metrics" in metrics:
            comm_metrics = metrics["communication_metrics"]
            if comm_metrics.get("latency", 0) > 1000:  # 1 second
                recommendations.append(
                    {
                        "type": "communication_optimization",
                        "reason": "high_latency",
                        "suggestion": "optimize_message_routing",
                    }
                )

        # Analyze resource usage
        if "resource_metrics" in metrics:
            res_metrics = metrics["resource_metrics"]
            if res_metrics.get("memory_usage", 0) > 0.8:
                recommendations.append(
                    {
                        "type": "resource_management",
                        "reason": "high_memory_usage",
                        "suggestion": "implement_memory_cleanup",
                    }
                )

        return {
            "recommendations": recommendations,
            "optimization_score": self._calculate_optimization_score(metrics),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    def _calculate_optimization_score(self, metrics: dict[str, Any]) -> float:
        """
        Calculate overall optimization score.

        Args:
            metrics: Performance metrics

        Returns:
            Optimization score (0-1)
        """
        scores = []

        # Agent performance score
        if "agent_performance" in metrics:
            avg_success_rate = sum(
                p.get("success_rate", 0.5) for p in metrics["agent_performance"].values()
            ) / len(metrics["agent_performance"])
            scores.append(avg_success_rate)

        # Communication score
        if "communication_metrics" in metrics:
            latency = metrics["communication_metrics"].get("latency", 1000)
            comm_score = max(1.0 - (latency / 5000), 0.0)
            scores.append(comm_score)

        # Resource score
        if "resource_metrics" in metrics:
            memory_usage = metrics["resource_metrics"].get("memory_usage", 0.5)
            resource_score = 1.0 - memory_usage
            scores.append(resource_score)

        return sum(scores) / len(scores) if scores else 0.5

    def get_society_status(self) -> dict[str, Any]:
        """
        Get current status of agent society.

        Returns:
            Society status information including swarm intelligence status
        """
        status = {
            "hierarchy": self.hierarchy,
            "active_tasks": len(self._active_tasks),
            "emergent_behaviors": len(self._emergent_behaviors),
            "collective_memory_size": len(self.collective_memory._memory),  # noqa: SLF001
            "patterns_discovered": len(self.collective_memory._patterns),  # noqa: SLF001
            "collective_learnings": len(self.collective_memory._learnings),  # noqa: SLF001
            "interaction_rules": self.interaction_rules,
            "exploration_mode": self.exploration_mode,
        }

        # Add swarm intelligence status if available
        if self.swarm_engine:
            status["swarm_intelligence"] = self.get_swarm_status()

        return status
