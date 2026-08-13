"""
Agent Skills API

Provides endpoints for:
- Skill discovery and search
- Capability-based agent lookup
- Dynamic skill registration
- Workspace context management

Inspired by OpenClaw's SKILL.md discovery system.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.agents.skills import (
    SkillCategory,
    SkillMetadata,
    WorkspaceContext,
    get_agent_skill_registry,
)
from heretek_swarm.gateway.auth import verify_auth

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def get_all_skills(
    category: SkillCategory | None = None,
    tags: str | None = None,
    query: str | None = None,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    List all registered skills with optional filters.

    - **category**: Filter by skill category (analysis, coordination, execution, etc.)
    - **tags**: Comma-separated tags to filter by
    - **query**: Text search in skill name and description
    """
    registry = get_agent_skill_registry()

    tag_list = [t.strip() for t in tags.split(",")] if tags else None

    skills = registry.search_skills(
        query=query,
        category=category,
        tags=tag_list,
    )

    return {
        "skills": [_skill_to_dict(s) for s in skills],
        "total": len(skills),
    }


@router.get("/agents")
async def get_all_agents_with_skills(
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    List all agents with their registered skills.

    Returns agent ID -> skills mapping.
    """
    registry = get_agent_skill_registry()

    agent_skills: dict[str, list[dict[str, Any]]] = {}

    for skill in registry.get_all_skills():
        for agent_id in skill.agent_ids:
            if agent_id not in agent_skills:
                agent_skills[agent_id] = []
            agent_skills[agent_id].append(
                {
                    "name": skill.name,
                    "category": skill.category.value,
                    "description": skill.description,
                }
            )

    return {
        "agents": agent_skills,
        "total_agents": len(agent_skills),
    }


@router.get("/agents/by-skill/{skill_name}")
async def get_agents_by_skill(
    skill_name: str,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Find all agents that implement a specific skill.

    Returns list of agent IDs that have registered this skill.
    """
    registry = get_agent_skill_registry()
    agent_ids = registry.find_agents_by_skill(skill_name)

    skill = registry.get_skill(skill_name)
    description = skill.description if skill else None

    return {
        "skill_name": skill_name,
        "agents": agent_ids,
        "count": len(agent_ids),
        "description": description,
    }


@router.get("/agents/by-category/{category}")
async def get_agents_by_category(
    category: SkillCategory,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Find all agents with skills in a given category.
    """
    registry = get_agent_skill_registry()
    agent_ids = registry.find_agents_by_category(category)

    return {
        "category": category.value,
        "agents": agent_ids,
        "count": len(agent_ids),
    }


@router.get("/agents/by-tag/{tag}")
async def get_agents_by_tag(
    tag: str,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Find all agents with skills tagged with a specific tag.
    """
    registry = get_agent_skill_registry()
    agent_ids = registry.find_agents_by_tag(tag)

    return {
        "tag": tag,
        "agents": agent_ids,
        "count": len(agent_ids),
    }


@router.get("/agents/{agent_id}")
async def get_agent_skills(
    agent_id: str,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Get all skills registered for a specific agent.
    """
    registry = get_agent_skill_registry()
    skills = registry.get_agent_skills(agent_id)

    if not skills:
        # Try the agent registry for unregistered agents
        from heretek_swarm.runtime.registry_enhanced import get_enhanced_registry

        registry2 = get_enhanced_registry()
        instance = registry2.get_instance(agent_id)

        if instance:
            # Agent exists but has no skills in the registry
            return {
                "agent_id": agent_id,
                "skills": [],
                "message": "Agent exists but no skills registered. "
                "Agent capabilities may not be configured for skill registry.",
            }

        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "agent_id": agent_id,
        "skills": [_skill_to_dict(s) for s in skills],
        "count": len(skills),
    }


@router.get("/statistics")
async def get_skill_statistics(
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Get skill registry statistics.
    """
    registry = get_agent_skill_registry()
    stats = registry.get_statistics()

    return {
        "total_skills": stats["total_skills"],
        "total_agents": stats["total_agents"],
        "by_category": stats["by_category"],
    }


@router.post("")
async def register_skill(
    skill_data: dict[str, Any],
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Register a new skill (admin/operator use).

    Expects:
    - **name**: Skill name
    - **description**: Skill description
    - **category**: Skill category enum value
    - **agent_id**: ID of the agent implementing this skill
    - **tags**: Optional list of tags
    - **version**: Optional version string (default: "1.0.0")
    """
    registry = get_agent_skill_registry()

    required = ["name", "description", "category", "agent_id"]
    for field in required:
        if field not in skill_data:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field}",
            )

    category = skill_data["category"]
    if isinstance(category, str):
        try:
            category = SkillCategory(category)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category: {category}. Valid: {[c.value for c in SkillCategory]}",
            )

    skill = SkillMetadata(
        name=skill_data["name"],
        description=skill_data["description"],
        category=category,
        version=skill_data.get("version", "1.0.0"),
        tags=skill_data.get("tags", []),
        source="api",
    )

    registry.register_skill(
        agent_id=skill_data["agent_id"],
        skill=skill,
    )

    return {
        "registered": True,
        "skill": _skill_to_dict(skill),
        "agent_id": skill_data["agent_id"],
    }


@router.delete("/{agent_id}/{skill_name}")
async def unregister_skill(
    agent_id: str,
    skill_name: str,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Remove a skill registration for an agent.
    """
    registry = get_agent_skill_registry()
    success = registry.unregister_skill(agent_id, skill_name)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Skill not found: {skill_name} for agent: {agent_id}",
        )

    return {"unregistered": True, "agent_id": agent_id, "skill_name": skill_name}


@router.post("/workspace")
async def register_workspace(
    workspace_data: dict[str, Any],
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Register a workspace context for prompt injection.

    Expects:
    - **workspace_id**: Workspace identifier
    - **skill_name**: Skill this workspace applies to
    - **base_prompt**: Base prompt for the skill
    - **injected_prompts**: List of injected prompt fragments
    - **variables**: Dict of variables for prompt interpolation
    - **priority**: Priority level (higher = more specific)
    """
    registry = get_agent_skill_registry()

    required = ["workspace_id", "skill_name"]
    for field in required:
        if field not in workspace_data:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required field: {field}",
            )

    context = WorkspaceContext(
        workspace_id=workspace_data["workspace_id"],
        skill_name=workspace_data["skill_name"],
        base_prompt=workspace_data.get("base_prompt", ""),
        injected_prompts=workspace_data.get("injected_prompts", []),
        variables=workspace_data.get("variables", {}),
        priority=workspace_data.get("priority", 0),
    )

    registry.register_workspace_context(workspace_data["workspace_id"], context)

    return {
        "registered": True,
        "workspace_id": workspace_data["workspace_id"],
        "skill_name": workspace_data["skill_name"],
    }


@router.get("/workspace/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Get a workspace context for prompt injection.
    """
    registry = get_agent_skill_registry()
    ctx = registry.get_workspace_context(workspace_id)

    if not ctx:
        raise HTTPException(status_code=404, detail=f"Workspace not found: {workspace_id}")

    return {
        "workspace_id": ctx.workspace_id,
        "skill_name": ctx.skill_name,
        "base_prompt": ctx.base_prompt,
        "injected_prompts": ctx.injected_prompts,
        "variables": ctx.variables,
        "priority": ctx.priority,
    }


@router.post("/workspace/inject")
async def build_injected_prompt(
    request: dict[str, Any],
    auth: dict = Depends(verify_auth),
) -> dict[str, Any]:
    """
    Build a prompt with workspace injection.

    Expects:
    - **base_prompt**: Base system prompt
    - **workspace_ids**: Optional list of workspace IDs to inject from
    """
    registry = get_agent_skill_registry()

    base_prompt = request.get("base_prompt", "")
    workspace_ids = request.get("workspace_ids", [])

    injected = registry.build_injected_prompt(base_prompt, workspace_ids)

    return {
        "original": base_prompt,
        "injected": injected,
        "workspace_ids": workspace_ids,
    }


def _skill_to_dict(skill: SkillMetadata) -> dict[str, Any]:
    """Convert SkillMetadata to dict for JSON serialization."""
    return {
        "name": skill.name,
        "description": skill.description,
        "category": skill.category.value,
        "version": skill.version,
        "author": skill.author,
        "tags": skill.tags,
        "agent_ids": skill.agent_ids,
        "registered_at": skill.registered_at,
        "source": skill.source,
        "parameters": skill.parameters,
    }
