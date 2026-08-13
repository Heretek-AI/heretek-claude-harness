# =============================================================================
"""Core agent endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.runtime.registry_enhanced import EnhancedAgentRegistry, get_enhanced_registry

logger = structlog.get_logger()
router = APIRouter()


class DeployAgentRequest(BaseModel):
    """Request body for agent deployment."""

    agent_type: str
    config: dict[str, Any] | None = None
    instance_id: str | None = None


def get_registry() -> EnhancedAgentRegistry:
    """Dependency to get the enhanced agent registry."""
    return get_enhanced_registry()


@router.get("/available")
async def list_available_agents(
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    List all available agent types that can be deployed.

    Returns metadata about each agent type including:
    - Type name and description
    - Capabilities
    - Default topics
    - Configuration schema
    """
    try:
        agent_types = registry.get_available_agents()

        return {
            "available_agents": [
                {
                    "type_name": agent.type_name,
                    "module_path": agent.module_path,
                    "description": agent.description,
                    "capabilities": agent.capabilities,
                    "topics": agent.topics,
                    "config_schema": agent.config_schema,
                    "actor_type": agent.actor_type,
                }
                for agent in agent_types
            ],
            "total": len(agent_types),
        }
    except Exception as e:
        logger.exception("Failed to list available agents: %s", e)
        raise HTTPException(500, f"Failed to list available agents: {e!s}") from None


@router.get("/types/{agent_type}")
async def get_agent_type_metadata(
    agent_type: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Get metadata for a specific agent type.

    Args:
        agent_type: Agent type name
    """
    metadata = registry.get_agent_metadata(agent_type)

    if not metadata:
        raise HTTPException(404, f"Agent type '{agent_type}' not found")

    return {
        "type_name": metadata.type_name,
        "module_path": metadata.module_path,
        "description": metadata.description,
        "capabilities": metadata.capabilities,
        "topics": metadata.topics,
        "config_schema": metadata.config_schema,
        "actor_type": metadata.actor_type,
    }


# =============================================================================
# Agent Deployment Endpoints
# =============================================================================


@router.post("/deploy")
async def deploy_agent(
    request: DeployAgentRequest,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Deploy a new agent instance.

    Args:
        request: Deployment request containing agent_type and optional config
        registry: Agent registry dependency
        authenticated: Authentication dependency

    Returns:
        Deployed agent instance information
    """
    # Validate agent type exists
    metadata = registry.get_agent_metadata(request.agent_type)
    if not metadata:
        raise HTTPException(400, f"Unknown agent type: {request.agent_type}")

    try:
        # Deploy the agent
        instance = await registry.deploy_agent(
            agent_type=request.agent_type,
            config=request.config,
            instance_id=request.instance_id,
        )

        if not instance:
            raise HTTPException(500, "Failed to deploy agent")

        return {
            "instance_id": instance.instance_id,
            "agent_type": instance.agent_type,
            "config": instance.config,
            "state": instance.state.value,
            "status": "deployed",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to deploy agent: %s", e)
        raise HTTPException(500, f"Failed to deploy agent: {e!s}") from None


@router.delete("/{instance_id}")
async def remove_agent(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Remove an agent instance.

    Args:
        instance_id: Instance ID to remove
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        success = await registry.remove_agent(instance_id)

        if not success:
            raise HTTPException(500, "Failed to remove agent")

        return {
            "instance_id": instance_id,
            "status": "removed",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove agent: %s", e)
        raise HTTPException(500, f"Failed to remove agent: {e!s}") from None


# =============================================================================
