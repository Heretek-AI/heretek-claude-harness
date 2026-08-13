"""
AgentSkillRegistry - Centralized registry for agent capabilities and skills.

Provides:
- Skill discovery and lookup
- Dynamic skill registration
- Capability-based agent queries
- Skill metadata and versioning

Inspired by OpenClaw's SKILL.md discovery system.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SkillCategory(Enum):
    """Categories for agent skills."""

    ANALYSIS = "analysis"
    COORDINATION = "coordination"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    MEMORY = "memory"
    GOVERNANCE = "governance"
    SECURITY = "security"
    LEARNING = "learning"
    CUSTOM = "custom"


@dataclass
class SkillMetadata:
    """Metadata for a registered skill."""

    name: str
    description: str
    category: SkillCategory
    version: str = "1.0.0"
    author: str = "unknown"
    tags: list[str] = field(default_factory=list)
    agent_ids: list[str] = field(default_factory=list)  # Agents that implement this skill
    registered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "runtime"  # "runtime" | "plugin" | "workspace"
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkspaceContext:
    """Workspace context for agent prompt injection."""

    workspace_id: str
    skill_name: str
    base_prompt: str = ""
    injected_prompts: list[str] = field(default_factory=list)
    variables: dict[str, Any] = field(default_factory=dict)
    priority: int = 0  # Higher = more specific, overrides lower


class AgentSkillRegistry:
    """
    Centralized registry for agent capabilities and skills.

    Provides skill discovery, registration, and lookup for the swarm.
    Agents can register their skills at init time, and other agents
    can discover skills by capability without knowing specific agent IDs.

    Example:
        registry = AgentSkillRegistry()

        # Agent registers a skill
        registry.register_skill(
            agent_id="alpha",
            skill=SkillMetadata(
                name="primary-analysis",
                description="Performs multi-perspective analysis",
                category=SkillCategory.ANALYSIS,
                tags=["analysis", "decision-making"],
            )
        )

        # Find agents with a capability
        agent_ids = registry.find_agents_by_skill("primary-analysis")
    """

    def __init__(self) -> None:
        """Initialize the skill registry."""
        self._skills: dict[str, SkillMetadata] = {}
        self._agent_skills: dict[str, set[str]] = defaultdict(set)  # agent_id -> set of skill names
        self._category_index: dict[SkillCategory, set[str]] = defaultdict(
            set
        )  # category -> skill names
        self._tag_index: dict[str, set[str]] = defaultdict(set)  # tag -> skill names
        self._workspace_contexts: dict[str, WorkspaceContext] = {}

        logger.info("[AgentSkillRegistry] Registry initialized")

    def register_skill(
        self,
        agent_id: str,
        skill: SkillMetadata,
        workspace_context: WorkspaceContext | None = None,
    ) -> None:
        """
        Register a skill for an agent.

        Args:
            agent_id: ID of the agent implementing this skill
            skill: Skill metadata
            workspace_context: Optional workspace context for prompt injection
        """
        if skill.name in self._skills:
            # Update existing skill: add agent to the list
            existing = self._skills[skill.name]
            if agent_id not in existing.agent_ids:
                existing.agent_ids.append(agent_id)
            if workspace_context:
                existing.parameters["workspace"] = vars(workspace_context)
        else:
            # New skill
            skill.agent_ids = [agent_id]
            self._skills[skill.name] = skill

            # Update indexes
            self._category_index[skill.category].add(skill.name)
            for tag in skill.tags:
                self._tag_index[tag].add(skill.name)

        # Index agent -> skill
        self._agent_skills[agent_id].add(skill.name)

        logger.info(
            "[AgentSkillRegistry] Skill registered",
            agent_id=agent_id,
            skill=skill.name,
            category=skill.category.value,
        )

    def unregister_skill(self, agent_id: str, skill_name: str) -> bool:
        """
        Remove a skill registration for an agent.

        Args:
            agent_id: ID of the agent
            skill_name: Name of the skill

        Returns:
            True if unregistered, False if not found
        """
        if skill_name not in self._skills:
            return False

        skill = self._skills[skill_name]

        if agent_id in skill.agent_ids:
            skill.agent_ids.remove(agent_id)

        if agent_id in self._agent_skills:
            self._agent_skills[agent_id].discard(skill_name)
            if not self._agent_skills[agent_id]:
                del self._agent_skills[agent_id]

        # If no agents left, remove the skill
        if not skill.agent_ids:
            del self._skills[skill_name]
            self._category_index[skill.category].discard(skill_name)
            for tag in skill.tags:
                self._tag_index[tag].discard(skill_name)
            logger.info("[AgentSkillRegistry] Skill removed (no agents)", skill=skill_name)

        return True

    def find_agents_by_skill(self, skill_name: str) -> list[str]:
        """
        Find all agents that implement a given skill.

        Args:
            skill_name: Name of the skill

        Returns:
            List of agent IDs
        """
        if skill_name not in self._skills:
            return []
        return list(self._skills[skill_name].agent_ids)

    def find_agents_by_category(self, category: SkillCategory) -> list[str]:
        """
        Find all agents with skills in a given category.

        Args:
            category: Skill category

        Returns:
            List of agent IDs with skills in the category
        """
        agents: set[str] = set()
        for skill_name in self._category_index.get(category, []):
            agents.update(self._skills[skill_name].agent_ids)
        return list(agents)

    def find_agents_by_tag(self, tag: str) -> list[str]:
        """
        Find all agents with skills having a given tag.

        Args:
            tag: Tag to search for

        Returns:
            List of agent IDs
        """
        agents: set[str] = set()
        for skill_name in self._tag_index.get(tag, []):
            agents.update(self._skills[skill_name].agent_ids)
        return list(agents)

    def search_skills(
        self,
        query: str | None = None,
        category: SkillCategory | None = None,
        tags: list[str] | None = None,
    ) -> list[SkillMetadata]:
        """
        Search skills by query, category, and/or tags.

        Args:
            query: Text search in skill name and description
            category: Filter by skill category
            tags: Filter by required tags

        Returns:
            List of matching skills
        """
        # Start with all skills
        all_skills = set(self._skills.keys())

        # Filter by category
        if category:
            all_skills &= self._category_index.get(category, set())

        # Filter by tags (all must match)
        if tags:
            for tag in tags:
                if tag in self._tag_index:
                    all_skills &= self._tag_index[tag]
                else:
                    return []  # No skills match all required tags

        # Filter by query (name or description contains query)
        if query:
            query_lower = query.lower()
            filtered = {
                name
                for name in all_skills
                if query_lower in name.lower()
                or query_lower in self._skills[name].description.lower()
            }
            all_skills = filtered

        return [self._skills[name] for name in all_skills]

    def get_agent_skills(self, agent_id: str) -> list[SkillMetadata]:
        """
        Get all skills registered for a specific agent.

        Args:
            agent_id: Agent ID

        Returns:
            List of skill metadata
        """
        skill_names = self._agent_skills.get(agent_id, set())
        return [self._skills[name] for name in skill_names if name in self._skills]

    def get_all_skills(self) -> list[SkillMetadata]:
        """
        Get all registered skills.

        Returns:
            List of all skill metadata
        """
        return list(self._skills.values())

    def get_skill(self, skill_name: str) -> SkillMetadata | None:
        """
        Get metadata for a specific skill.

        Args:
            skill_name: Name of the skill

        Returns:
            Skill metadata or None
        """
        return self._skills.get(skill_name)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Statistics dict with counts by category
        """
        by_category: dict[str, int] = {}
        for category in SkillCategory:
            by_category[category.value] = len(self._category_index.get(category, []))

        return {
            "total_skills": len(self._skills),
            "total_agents": len(self._agent_skills),
            "by_category": by_category,
        }

    def register_workspace_context(
        self,
        workspace_id: str,
        context: WorkspaceContext,
    ) -> None:
        """
        Register a workspace context for prompt injection.

        Args:
            workspace_id: Workspace identifier
            context: Workspace context
        """
        self._workspace_contexts[workspace_id] = context
        logger.info(
            "[AgentSkillRegistry] Workspace context registered",
            workspace_id=workspace_id,
            skill=context.skill_name,
        )

    def get_workspace_context(self, workspace_id: str) -> WorkspaceContext | None:
        """
        Get workspace context for prompt injection.

        Args:
            workspace_id: Workspace identifier

        Returns:
            Workspace context or None
        """
        return self._workspace_contexts.get(workspace_id)

    def build_injected_prompt(
        self,
        base_prompt: str,
        workspace_ids: list[str] | None = None,
    ) -> str:
        """
        Build a prompt with workspace injection.

        Args:
            base_prompt: Base system prompt
            workspace_ids: List of workspace IDs to inject from (priority order)

        Returns:
            Prompt with injected workspace context
        """
        result = base_prompt
        injected_parts: list[str] = []

        if workspace_ids:
            for wid in workspace_ids:
                ctx = self._workspace_contexts.get(wid)
                if ctx:
                    injected_parts.extend(ctx.injected_prompts)

        if injected_parts:
            result += "\n\n## Workspace Context\n"
            result += "\n".join(f"- {p}" for p in injected_parts)

        return result


# Global registry instance
_global_registry: AgentSkillRegistry | None = None


def get_agent_skill_registry() -> AgentSkillRegistry:
    """
    Get the global agent skill registry instance.

    Returns:
        AgentSkillRegistry singleton
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = AgentSkillRegistry()

    return _global_registry
