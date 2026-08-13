# =============================================================================
"""Agent lifecycle management endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException

from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.runtime.registry_enhanced import (
    AgentLifecycleState,
    EnhancedAgentRegistry,
    get_enhanced_registry,
)

logger = structlog.get_logger()
router = APIRouter()


def get_registry() -> EnhancedAgentRegistry:
    """Dependency to get the enhanced agent registry."""
    return get_enhanced_registry()


@router.post("/{instance_id}/start")
async def start_agent(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Start a deployed agent instance.

    Args:
        instance_id: Instance ID to start
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        success = await registry.start_agent(instance_id)

        if not success:
            raise HTTPException(500, "Failed to start agent")

        return {
            "instance_id": instance_id,
            "status": "running",
            "state": AgentLifecycleState.RUNNING.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to start agent: {e}")
        raise HTTPException(500, f"Failed to start agent: {e!s}") from e


@router.post("/{instance_id}/stop")
async def stop_agent(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Stop a running agent instance.

    Args:
        instance_id: Instance ID to stop
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        success = await registry.stop_agent(instance_id)

        if not success:
            raise HTTPException(500, "Failed to stop agent")

        return {
            "instance_id": instance_id,
            "status": "stopped",
            "state": AgentLifecycleState.STOPPED.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to stop agent: {e}")
        raise HTTPException(500, f"Failed to stop agent: {e!s}") from e


@router.post("/{instance_id}/suspend")
async def suspend_agent(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Suspend a running agent instance.

    Args:
        instance_id: Instance ID to suspend
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        success = await registry.suspend_agent(instance_id)

        if not success:
            raise HTTPException(500, "Failed to suspend agent")

        return {
            "instance_id": instance_id,
            "status": "suspended",
            "state": AgentLifecycleState.SUSPENDED.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to suspend agent: {e}")
        raise HTTPException(500, f"Failed to suspend agent: {e!s}") from e


@router.post("/{instance_id}/resume")
async def resume_agent(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Resume a suspended agent instance.

    Args:
        instance_id: Instance ID to resume
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        success = await registry.resume_agent(instance_id)

        if not success:
            raise HTTPException(500, "Failed to resume agent")

        return {
            "instance_id": instance_id,
            "status": "running",
            "state": AgentLifecycleState.RUNNING.value,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to resume agent: {e}")
        raise HTTPException(500, f"Failed to resume agent: {e!s}") from e


# =============================================================================
# Agent Configuration Endpoints
# =============================================================================


@router.put("/{instance_id}/config")
async def update_agent_config(
    instance_id: str,
    config: dict[str, Any],
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Update agent configuration.

    Args:
        instance_id: Instance ID
        config: New configuration dictionary
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        success = registry.update_agent_config(instance_id, config)

        if not success:
            raise HTTPException(500, "Failed to update configuration")

        return {
            "instance_id": instance_id,
            "config": instance.config,
            "status": "updated",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update config: {e}")
        raise HTTPException(500, f"Failed to update configuration: {e!s}") from e


# =============================================================================
