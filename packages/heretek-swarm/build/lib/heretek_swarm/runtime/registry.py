"""
Agent Registry for Heretek Swarm.

This module provides a centralized registry for all collective agents,
their roles, capabilities, and character definitions.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import structlog

# Import Character and CharacterStyle from the package __init__
from . import Character

logger = structlog.get_logger("AgentRegistry")


class AgentRole(Enum):
    """Classification of agent roles within the collective."""

    # Orchestration
    ORCHESTRATOR = "orchestrator"
    ORCHESTRATOR_SUPPORT = "orchestrator_support"
    COORDINATOR = "coordinator"

    # Triad (Decision Making)
    TRIAD_NODE = "triad_node"

    # Safety & Alignment
    SAFETY_REVIEWER = "safety_reviewer"
    GUARDIAN_PRIME = "guardian_prime"

    # Intelligence & Analysis
    INTELLIGENCE_GATHERER = "intelligence_gatherer"
    PERSPECTIVE_ANALYST = "perspective_analyst"
    SENSOR = "sensor"
    QUESTIONER = "questioner"

    # Implementation
    IMPLEMENTER = "implementer"

    # Communication & Relationships
    COMMUNICATOR = "communicator"
    RELATIONSHIP_MANAGER = "relationship_manager"
    INTEGRATOR = "integrator"

    # Processing & Synthesis
    SYNTHESIZER = "synthesizer"
    SAGE = "sage"
    MEDIATOR = "mediator"

    # Specialized
    TIMEKEEPER = "timekeeper"
    BEHAVIOR_ARCHITECT = "behavior_architect"
    CHANGE_AGENT = "change_agent"


@dataclass
class AgentInfo:
    """
    Complete information about an agent in the collective.

    Attributes:
        name: Agent's name
        role: Agent's role classification
        character: Full character definition
        capabilities: List of agent capabilities
        dependencies: Other agents this agent depends on
        topics_subscribed: Message topics this agent subscribes to
        priority: Agent priority level (higher = more critical)
    """

    name: str
    role: AgentRole
    character: Character
    capabilities: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    topics_subscribed: list[str] = field(default_factory=list)
    priority: int = 5  # 1-10 scale, 10 = most critical


class AgentRegistry:
    """
    Central registry for all collective agents.

    Provides access to agent definitions, capabilities, and relationships.
    Supports dynamic loading and querying of agent information.
    """

    # Agent name to role mapping
    AGENT_ROLES: dict[str, AgentRole] = {  # noqa: RUF012
        # Core Orchestration
        "Steward": AgentRole.ORCHESTRATOR,
        "Coordinator": AgentRole.ORCHESTRATOR_SUPPORT,
        # Triad
        "Alpha": AgentRole.TRIAD_NODE,
        "Beta": AgentRole.TRIAD_NODE,
        "Charlie": AgentRole.TRIAD_NODE,
        # Safety
        "Sentinel": AgentRole.SAFETY_REVIEWER,
        "Sentinel-Prime": AgentRole.GUARDIAN_PRIME,
        # Intelligence & Analysis
        "Explorer": AgentRole.INTELLIGENCE_GATHERER,
        "Examiner": AgentRole.QUESTIONER,
        "Perceiver": AgentRole.SENSOR,
        "Prism": AgentRole.PERSPECTIVE_ANALYST,
        # Implementation
        "Coder": AgentRole.IMPLEMENTER,
        # Communication
        "Echo": AgentRole.COMMUNICATOR,
        "Empath": AgentRole.RELATIONSHIP_MANAGER,
        "Nexus": AgentRole.INTEGRATOR,
        # Processing
        "Dreamer": AgentRole.SYNTHESIZER,
        "Metis": AgentRole.SAGE,
        "Arbiter": AgentRole.MEDIATOR,
        # Specialized
        "Chronos": AgentRole.TIMEKEEPER,
        "Habit-Forge": AgentRole.BEHAVIOR_ARCHITECT,
        "Catalyst": AgentRole.CHANGE_AGENT,
        "Historian": AgentRole.SYNTHESIZER,  # Memory keeper
    }

    # Agent dependencies (who they need to work with)
    AGENT_DEPENDENCIES: dict[str, list[str]] = {  # noqa: RUF012
        "Steward": ["Coordinator", "Chronos"],
        "Coordinator": ["Steward", "Chronos"],
        "Alpha": ["Beta", "Charlie", "Historian"],
        "Beta": ["Alpha", "Charlie", "Examiner"],
        "Charlie": ["Alpha", "Beta", "Sentinel"],
        "Sentinel": ["Sentinel-Prime", "Nexus"],
        "Sentinel-Prime": ["Sentinel"],
        "Explorer": ["Perceiver", "Historian"],
        "Examiner": ["Alpha", "Beta", "Charlie"],
        "Perceiver": ["Echo", "Empath"],
        "Prism": ["Metis", "Examiner"],
        "Coder": ["Sentinel", "Coordinator"],
        "Echo": ["Empath", "Nexus"],
        "Empath": ["Echo", "Historian"],
        "Nexus": ["Sentinel", "Coder"],
        "Dreamer": ["Historian", "Metis"],
        "Metis": ["Historian", "Dreamer"],
        "Arbiter": ["Alpha", "Beta", "Charlie"],
        "Chronos": ["Coordinator"],
        "Habit-Forge": ["Dreamer", "Historian"],
        "Catalyst": ["Explorer", "Coordinator"],
        "Historian": [],
    }

    # Agent capabilities
    AGENT_CAPABILITIES: dict[str, list[str]] = {  # noqa: RUF012
        "Steward": ["orchestration", "task_routing", "agent_coordination"],
        "Coordinator": ["workflow_management", "task_tracking", "dependency_management"],
        "Alpha": ["deliberation", "synthesis", "consensus"],
        "Beta": ["critical_analysis", "assumption_challenge", "risk_assessment"],
        "Charlie": ["process_validation", "consensus", "completeness_check"],
        "Sentinel": ["safety_review", "risk_detection", "security_analysis"],
        "Sentinel-Prime": ["strategic_safety", "alignment", "protocol_development"],
        "Explorer": ["intelligence_gathering", "opportunity_detection", "anomaly_discovery"],
        "Examiner": ["questioning", "assumption_probing", "failure_mode_analysis"],
        "Perceiver": ["input_processing", "pattern_detection", "signal_routing"],
        "Prism": ["perspective_analysis", "bias_detection", "stakeholder_mapping"],
        "Coder": ["implementation", "code_generation", "technical_execution"],
        "Echo": ["communication", "message_formatting", "output_generation"],
        "Empath": ["user_modeling", "emotional_intelligence", "personalization"],
        "Nexus": ["integration", "protocol_translation", "external_connections"],
        "Dreamer": ["pattern_synthesis", "creative_insights", "memory_consolidation"],
        "Metis": ["wisdom_synthesis", "strategic_counsel", "insight_generation"],
        "Arbiter": ["mediation", "conflict_resolution", "consensus_building"],
        "Chronos": ["time_management", "scheduling", "deadline_tracking"],
        "Habit-Forge": ["habit_formation", "behavior_analysis", "pattern_optimization"],
        "Catalyst": ["change_management", "innovation", "experiment_design"],
        "Historian": ["memory_keeping", "knowledge_storage", "historical_analysis"],
    }

    def __init__(self, characters_dir: Path | None = None):
        """
        Initialize the agent registry.

        Args:
            characters_dir: Directory containing character JSON files.
                          Defaults to the runtime/characters directory.
        """
        if characters_dir is None:
            characters_dir = Path(__file__).parent / "characters"

        self.characters_dir = Path(characters_dir)
        self._agents: dict[str, AgentInfo] = {}
        self._loaded = False

        logger.info("AgentRegistry initialized with characters_dir: {self.characters_dir}")

    def load_all(self) -> None:
        """Load all agent definitions from character files."""
        if self._loaded:
            return

        for char_file in self.characters_dir.glob("*.json"):
            try:
                character = Character.from_json(char_file)
                name = character.name

                role = self.AGENT_ROLES.get(name, AgentRole.IMPLEMENTER)
                capabilities = self.AGENT_CAPABILITIES.get(name, [])
                dependencies = self.AGENT_DEPENDENCIES.get(name, [])

                # Generate subscribed topics based on role and capabilities
                topics = self._generate_topics(name, role, capabilities)

                # Determine priority based on role
                priority = self._get_priority(role)

                self._agents[name] = AgentInfo(
                    name=name,
                    role=role,
                    character=character,
                    capabilities=capabilities,
                    dependencies=dependencies,
                    topics_subscribed=topics,
                    priority=priority,
                )

                logger.debug("Loaded agent: {name} with role {role.value}")

            except Exception:
                logger.error("Failed to load character from {char_file}: {e}")

        self._loaded = True
        logger.info("Loaded {len(self._agents)} agents into registry")

    def _generate_topics(self, name: str, role: AgentRole, capabilities: list[str]) -> list[str]:
        """Generate message topics this agent should subscribe to."""
        topics = [f"agent.{name.lower()}", "broadcast.all"]

        # Add role-based topics
        if role in [AgentRole.TRIAD_NODE, AgentRole.ORCHESTRATOR]:
            topics.append("triad.deliberation")

        if role in [AgentRole.SAFETY_REVIEWER, AgentRole.GUARDIAN_PRIME]:
            topics.append("safety.review")

        if role == AgentRole.MEDIATOR:
            topics.append("conflict.resolution")

        # Add capability-based topics
        for cap in capabilities:
            topics.append(f"capability.{cap}")  # noqa: PERF401

        return list(set(topics))

    def _get_priority(self, role: AgentRole) -> int:
        """Get priority level for a role (1-10 scale)."""
        priorities = {
            AgentRole.ORCHESTRATOR: 10,
            AgentRole.GUARDIAN_PRIME: 9,
            AgentRole.TRIAD_NODE: 9,
            AgentRole.SAFETY_REVIEWER: 8,
            AgentRole.SAGE: 7,
            AgentRole.MEDIATOR: 7,
            AgentRole.ORCHESTRATOR_SUPPORT: 7,
            AgentRole.INTELLIGENCE_GATHERER: 6,
            AgentRole.SYNTHESIZER: 6,
            AgentRole.IMPLEMENTER: 6,
            AgentRole.COMMUNICATOR: 5,
            AgentRole.RELATIONSHIP_MANAGER: 5,
            AgentRole.INTEGRATOR: 5,
            AgentRole.SENSOR: 5,
            AgentRole.QUESTIONER: 5,
            AgentRole.PERSPECTIVE_ANALYST: 5,
            AgentRole.TIMEKEEPER: 4,
            AgentRole.BEHAVIOR_ARCHITECT: 4,
            AgentRole.CHANGE_AGENT: 4,
        }
        return priorities.get(role, 5)

    def get_agent(self, name: str) -> AgentInfo | None:
        """
        Get agent information by name.

        Args:
            name: Agent name (case-sensitive)

        Returns:
            AgentInfo if found, None otherwise
        """
        if not self._loaded:
            self.load_all()
        return self._agents.get(name)

    def get_all_agents(self) -> dict[str, AgentInfo]:
        """
        Get all registered agents.

        Returns:
            Dictionary mapping agent names to their info
        """
        if not self._loaded:
            self.load_all()
        return self._agents.copy()

    def get_agents_by_role(self, role: AgentRole) -> list[AgentInfo]:
        """
        Get all agents with a specific role.

        Args:
            role: Role to filter by

        Returns:
            List of agents with the specified role
        """
        if not self._loaded:
            self.load_all()
        return [info for info in self._agents.values() if info.role == role]

    def get_agents_by_capability(self, capability: str) -> list[AgentInfo]:
        """
        Get all agents with a specific capability.

        Args:
            capability: Capability to filter by

        Returns:
            List of agents with the specified capability
        """
        if not self._loaded:
            self.load_all()
        return [info for info in self._agents.values() if capability in info.capabilities]

    def get_agent_dependencies(self, name: str) -> list[AgentInfo]:
        """
        Get agents that the specified agent depends on.

        Args:
            name: Agent name

        Returns:
            List of agents that are dependencies
        """
        if not self._loaded:
            self.load_all()

        agent = self._agents.get(name)
        if not agent:
            return []

        return [self._agents[dep] for dep in agent.dependencies if dep in self._agents]

    def get_agent_dependents(self, name: str) -> list[AgentInfo]:
        """
        Get agents that depend on the specified agent.

        Args:
            name: Agent name

        Returns:
            List of agents that depend on this agent
        """
        if not self._loaded:
            self.load_all()

        return [info for info in self._agents.values() if name in info.dependencies]

    def get_collective_roster(self) -> dict[str, dict[str, Any]]:
        """
        Get the complete collective roster with summary information.

        Returns:
            Dictionary with agent names as keys and role/capability summaries
        """
        if not self._loaded:
            self.load_all()

        return {
            name: {
                "role": info.role.value,
                "bio": info.character.bio[:100] + "..."
                if len(info.character.bio) > 100
                else info.character.bio,
                "capabilities": info.capabilities,
                "priority": info.priority,
                "dependencies": info.dependencies,
            }
            for name, info in self._agents.items()
        }

    def get_registry_stats(self) -> dict[str, Any]:
        """
        Get statistics about the registry.

        Returns:
            Dictionary with registry statistics
        """
        if not self._loaded:
            self.load_all()

        roles = {}
        capabilities = {}

        for info in self._agents.values():
            role = info.role.value
            roles[role] = roles.get(role, 0) + 1

            for cap in info.capabilities:
                capabilities[cap] = capabilities.get(cap, 0) + 1

        return {
            "total_agents": len(self._agents),
            "roles": roles,
            "top_capabilities": dict(
                sorted(capabilities.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "avg_priority": sum(info.priority for info in self._agents.values()) / len(self._agents)
            if self._agents
            else 0,
        }


# Singleton registry instance
_registry: AgentRegistry | None = None


def get_registry(characters_dir: Path | None = None) -> AgentRegistry:
    """
    Get the global agent registry instance.

    Args:
        characters_dir: Optional directory for character files (only used on first call)

    Returns:
        The global AgentRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = AgentRegistry(characters_dir)
    return _registry
