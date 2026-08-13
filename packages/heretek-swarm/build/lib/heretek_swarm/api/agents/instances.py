# =============================================================================
"""Agent instances endpoints."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from heretek_swarm.channels.registry import ChannelRegistry, get_channel_registry
from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.runtime.registry_enhanced import EnhancedAgentRegistry, get_enhanced_registry

logger = structlog.get_logger()
router = APIRouter()


def get_registry() -> EnhancedAgentRegistry:
    """Dependency to get the enhanced agent registry."""
    return get_enhanced_registry()


def _build_instance_metadata(instance: Any) -> dict[str, Any] | None:
    """Build metadata dict from an agent instance, avoiding nested conditionals."""
    if instance.metadata is None:
        return None
    return {
        "type_name": instance.metadata.type_name,
        "description": instance.metadata.description,
        "capabilities": instance.metadata.capabilities,
    }


@router.get("/instances")
async def list_agent_instances(
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
    agent_type: str | None = None,
):
    """
    List all deployed agent instances.

    Args:
        agent_type: Optional filter by agent type
    """
    try:
        if agent_type:
            instances = registry.get_instances_by_type(agent_type)
        else:
            # get_all_instances returns dict[str, AgentInstance] — use .values()
            instances = list(registry.get_all_instances().values())

        return {
            "instances": [
                {
                    "instance_id": inst.instance_id,
                    "agent_type": inst.agent_type,
                    "state": inst.state.value,
                    "config": inst.config,
                    "has_actor": inst.actor is not None,
                }
                for inst in instances
            ],
            "total": len(instances),
        }
    except Exception as e:
        logger.exception("Failed to list instances: %s", e)
        raise HTTPException(500, f"Failed to list instances: {e!s}") from None


@router.get("/{instance_id}")
async def get_agent_instance(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Get details of a specific agent. Unified lookup: a registered agent
    type name (e.g. "steward") resolves to the supervisor-managed actor;
    any other id resolves to a deployed instance in the registry.

    Args:
        instance_id: Agent type name or instance ID
    """
    # F-009 (2026-06-01): check supervisor.actors first so the 23 registered
    # agent type names resolve to the supervisor payload (topics, capabilities,
    # actor state) rather than 404'ing as "unknown instance id".
    from heretek_swarm.actors.supervisor import get_supervisor

    supervisor = get_supervisor()
    if supervisor and instance_id in supervisor.actors:
        actor = supervisor.actors[instance_id]
        status = actor.get_status()
        return {
            "id": instance_id,
            "type": actor.__class__.__name__,
            "status": status.state.value if status else "unknown",
            "message_count": status.message_count if status else 0,
            "error_count": status.error_count if status else 0,
            "last_activity": (
                status.last_activity if status and status.last_activity else None
            ),
            "topics": list(actor.topics),
            "capabilities": list(actor.capabilities),
            "source": "supervisor",
        }

    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(
            404, f"Agent '{instance_id}' not found (not in supervisor or registry)"
        )

    # Get actor status if running
    actor_status = None
    if instance.actor:
        try:
            status = instance.actor.get_status()
            actor_status = {
                "agent_id": status.agent_id,
                "state": status.state.value,
                "message_count": status.message_count,
                "error_count": status.error_count,
                "mailbox_size": status.mailbox_size,
                "last_activity": status.last_activity,
            }
        except Exception as e:
            logger.warning("Failed to get actor status: %s", e)

    return {
        "instance_id": instance.instance_id,
        "agent_type": instance.agent_type,
        "state": instance.state.value,
        "config": instance.config,
        "metadata": _build_instance_metadata(instance),
        "actor_status": actor_status,
        "source": "registry",
    }


@router.get("/{instance_id}/logs")
async def get_agent_logs(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
    limit: int = 100,
):
    """
    Get agent-specific logs.

    Note: This is a placeholder implementation. In production, this would
    integrate with a logging system like ELK stack or similar.

    Args:
        instance_id: Instance ID
        limit: Maximum log entries to return
    """
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Placeholder: Return agent state information as "logs"
    # In production, this would query a logging system
    logs = []

    # Add lifecycle events
    logs.append(
        {
            "timestamp": instance.config.get("created_at", "unknown"),
            "level": "info",
            "message": f"Agent instance {instance_id} deployed",
            "agent_type": instance.agent_type,
        }
    )

    if instance.actor:
        try:
            status = instance.actor.get_status()
            logs.append(
                {
                    "timestamp": status.last_activity or "unknown",
                    "level": "info",
                    "message": f"Agent processed {status.message_count} messages",
                    "message_count": status.message_count,
                    "error_count": status.error_count,
                }
            )
        except Exception as e:
            logger.debug("agent_status_log_read_failed", error=str(e))

    # Sort by timestamp (newest first) and limit
    logs = sorted(logs, key=lambda x: x.get("timestamp", ""), reverse=True)[:limit]

    return {
        "instance_id": instance_id,
        "logs": logs,
        "total": len(logs),
    }


# =============================================================================
# Agent Memory Endpoint
# =============================================================================


@router.get("/{instance_id}/memory")
async def get_agent_memory(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
    limit: int = 20,
):
    """
    Get per-agent memory statistics.

    Queries the persistent memory store for memory entries belonging to
    a specific agent instance. Falls back gracefully through multiple
    backends: SQLAlchemy (memory_store), mem0, and finally returns
    status 'unavailable'.

    Args:
        instance_id: Agent instance ID
        limit: Maximum recent entries to return (default 20)

    Returns:
        agent_id, total_memories, by_type breakdown, recent_entries, and status
    """
    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Lazy import to avoid circular import at module level
    from heretek_swarm.api.main import mem0_backend, memory_store

    # ---- SQLAlchemy path (primary, when memory_store is available) ------------------
    if memory_store is not None:
        try:
            from sqlalchemy import func, select

            from heretek_swarm.memory.persistent import MemoryEntryModel

            async with memory_store._session_factory() as session:  # noqa: SLF001
                # Total count for this agent
                count_stmt = (
                    select(func.count())
                    .select_from(MemoryEntryModel)
                    .where(MemoryEntryModel.agent_id == instance_id)
                )
                result = await session.execute(count_stmt)
                total = result.scalar() or 0

                # By type breakdown
                type_stmt = (
                    select(MemoryEntryModel.memory_type, func.count())
                    .where(MemoryEntryModel.agent_id == instance_id)
                    .group_by(MemoryEntryModel.memory_type)
                )
                type_result = await session.execute(type_stmt)
                by_type: dict[str, int] = {row[0]: row[1] for row in type_result.all()}

                # Recent entries (newest first)
                recent_stmt = (
                    select(MemoryEntryModel)
                    .where(MemoryEntryModel.agent_id == instance_id)
                    .order_by(MemoryEntryModel.created_at.desc())
                    .limit(limit)
                )
                recent_result = await session.execute(recent_stmt)
                recent_entries = [
                    {
                        "id": row.id,
                        "content": row.content,
                        "memory_type": row.memory_type,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                    for row in recent_result.scalars().all()
                ]

            logger.info(
                "agent_memory_fetched",
                agent_id=instance_id,
                total=total,
                source="sqlalchemy",
            )
            return {
                "agent_id": instance_id,
                "total_memories": total,
                "by_type": by_type,
                "recent_entries": recent_entries,
                "status": "available",
            }
        except Exception as e:
            logger.error(
                "agent_memory_failed",
                agent_id=instance_id,
                error=str(e),
                source="sqlalchemy",
            )
            return {
                "agent_id": instance_id,
                "total_memories": 0,
                "by_type": {},
                "recent_entries": [],
                "status": "error",
                "error": "Failed to retrieve agent memories",
            }

    # ---- mem0 backend path (fallback) -----------------------------------------------
    if mem0_backend is not None:
        try:
            entries = mem0_backend.get_all(agent_id=instance_id)
            total = len(entries)

            # Build by_type breakdown
            by_type = {}
            for entry in entries:
                mt = str(entry.memory_type) if entry.memory_type else "unknown"
                by_type[mt] = by_type.get(mt, 0) + 1

            # Recent entries sorted by created_at descending
            sorted_entries = sorted(
                entries, key=lambda e: e.created_at or "", reverse=True
            )[:limit]
            recent_entries = [
                {
                    "id": e.id,
                    "content": e.content if isinstance(e.content, str) else str(e.content),
                    "memory_type": str(e.memory_type) if e.memory_type else "unknown",
                    "created_at": e.created_at,
                }
                for e in sorted_entries
            ]

            logger.info(
                "agent_memory_fetched",
                agent_id=instance_id,
                total=total,
                source="mem0",
            )
            return {
                "agent_id": instance_id,
                "total_memories": total,
                "by_type": by_type,
                "recent_entries": recent_entries,
                "status": "available",
            }
        except Exception as e:
            logger.error(
                "agent_memory_failed",
                agent_id=instance_id,
                error=str(e),
                source="mem0",
            )
            return {
                "agent_id": instance_id,
                "total_memories": 0,
                "by_type": {},
                "recent_entries": [],
                "status": "error",
                "error": "Failed to fetch agent memory",
            }

    # ---- Neither backend available --------------------------------------------------
    logger.info(
        "agent_memory_fetched",
        agent_id=instance_id,
        total=0,
        status="unavailable",
    )
    return {
        "agent_id": instance_id,
        "total_memories": 0,
        "by_type": {},
        "recent_entries": [],
        "status": "unavailable",
    }


# =============================================================================
# Agent Tools Endpoint
# =============================================================================


# Testable dependency for supervisor injection — tests override this
def _get_tasks_supervisor():
    """Lazily import and return the global supervisor."""
    from heretek_swarm.actors.supervisor import get_supervisor

    return get_supervisor()


# =============================================================================
# Agent Tools Endpoint (continued)
# =============================================================================


@router.get("/{instance_id}/tools")
async def get_agent_tools(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Get aggregated tools and skills for an agent instance.

    Combines per-agent skills (from AgentSkillRegistry) with system-wide
    plugins (from PluginRuntime) into a single response.

    Args:
        instance_id: Agent instance ID

    Returns:
        agent_id, skills list, plugins list, and total count
    """
    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    # Lazy imports to avoid circular import at module level
    from heretek_swarm.agents.skills import get_agent_skill_registry
    from heretek_swarm.plugins.manager import get_plugin_runtime

    skills: list[dict] = []
    plugins: list[dict] = []

    # ---- Per-agent skills --------------------------------------------------
    try:
        skill_registry = get_agent_skill_registry()
        agent_skills = skill_registry.get_agent_skills(instance_id)
        skills = [
            {
                "name": s.name,
                "category": s.category.value,
                "description": s.description,
                "version": s.version,
                "tags": s.tags,
                "source": s.source,
            }
            for s in agent_skills
        ]

        logger.info(
            "agent_tools_fetched",
            agent_id=instance_id,
            skills_count=len(skills),
            source="skill_registry",
        )
    except Exception as e:
        logger.error(
            "agent_tools_failed",
            agent_id=instance_id,
            error=str(e),
            source="skill_registry",
        )

    # ---- System-wide plugins -----------------------------------------------
    try:
        plugin_runtime = get_plugin_runtime()
        plugin_list = plugin_runtime.list_plugins()
        plugins = [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "author": p.author,
            }
            for p in plugin_list
        ]

        logger.info(
            "agent_tools_fetched",
            agent_id=instance_id,
            plugins_count=len(plugins),
            source="plugin_runtime",
        )
    except Exception as e:
        logger.error(
            "agent_tools_failed",
            agent_id=instance_id,
            error=str(e),
            source="plugin_runtime",
        )

    return {
        "agent_id": instance_id,
        "skills": skills,
        "plugins": plugins,
        "total": len(skills) + len(plugins),
    }


# =============================================================================
# Agent Tasks Endpoint
# =============================================================================


@router.get("/{instance_id}/tasks")
async def get_agent_tasks(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Get agent task/activity status from the supervisor.

    Reads the ActorStatus for a given agent from the ActorSupervisor.
    Agents that exist in the registry but are not managed by the
    supervisor return status:'not_running'.

    Args:
        instance_id: Agent instance ID

    Returns:
        agent_id, status, capabilities, topics, message_count,
        error_count, last_activity, uptime_seconds
    """
    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        supervisor = _get_tasks_supervisor()
    except Exception as e:
        logger.error(
            "agent_tasks_failed",
            agent_id=instance_id,
            error=str(e),
            stage="supervisor_import",
        )
        return {
            "agent_id": instance_id,
            "status": "not_running",
            "capabilities": [],
            "topics": [],
            "message_count": 0,
            "error_count": 0,
            "last_activity": None,
            "uptime_seconds": 0,
        }

    # Check supervisor is initialized and has actors
    if supervisor is None or not getattr(supervisor, "actors", None):
        logger.info(
            "agent_tasks_fetched",
            agent_id=instance_id,
            status="not_running",
            reason="supervisor_not_ready",
        )
        return {
            "agent_id": instance_id,
            "status": "not_running",
            "capabilities": [],
            "topics": [],
            "message_count": 0,
            "error_count": 0,
            "last_activity": None,
            "uptime_seconds": 0,
        }

    # Try to get actor from supervisor
    try:
        actor = supervisor.actors.get(instance_id)
        if actor is None:
            logger.info(
                "agent_tasks_fetched",
                agent_id=instance_id,
                status="not_running",
                reason="actor_not_found",
            )
            return {
                "agent_id": instance_id,
                "status": "not_running",
                "capabilities": [],
                "topics": [],
                "message_count": 0,
                "error_count": 0,
                "last_activity": None,
                "uptime_seconds": 0,
            }

        status = actor.get_status()

        uptime_seconds = _uptime_seconds(status.created_at)

        logger.info(
            "agent_tasks_fetched",
            agent_id=instance_id,
            status=status.state.value,
            message_count=status.message_count,
            error_count=status.error_count,
        )
        return {
            "agent_id": instance_id,
            "status": status.state.value,
            "capabilities": status.capabilities,
            "topics": status.topics,
            "message_count": status.message_count,
            "error_count": status.error_count,
            "last_activity": status.last_activity,
            "uptime_seconds": uptime_seconds,
        }
    except Exception as e:
        logger.error(
            "agent_tasks_failed",
            agent_id=instance_id,
            error=str(e),
        )
        return {
            "agent_id": instance_id,
            "status": "not_running",
            "capabilities": [],
            "topics": [],
            "message_count": 0,
            "error_count": 0,
            "last_activity": None,
            "uptime_seconds": 0,
        }


def _uptime_seconds(created_at: str | None) -> int | None:
    """Compute uptime seconds from an ISO datetime string.

    Returns None if created_at is None or unparseable.
    """
    if not created_at:
        return None
    try:
        created = datetime.fromisoformat(created_at)
        return int((datetime.now(UTC) - created).total_seconds())
    except (ValueError, TypeError):
        return None


# =============================================================================
# Registry Statistics Endpoint
# =============================================================================


@router.get("/stats")
async def get_registry_stats(
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    authenticated: Annotated[str, Depends(verify_auth)],
):
    """
    Get registry statistics.

    Returns statistics about agent types and instances.
    """
    try:
        return registry.get_registry_stats()
    except Exception as e:
        logger.exception("Failed to get registry stats: %s", e)
        raise HTTPException(500, f"Failed to get registry stats: {e!s}") from None


# =============================================================================
# Channel Subscription Models
# =============================================================================


class ChannelType(StrEnum):
    """Channel type enumeration."""

    EVENT = "event"
    COMMAND = "command"
    RESPONSE = "response"
    METRIC = "metric"


class ChannelDirection(StrEnum):
    """Channel direction enumeration."""

    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"


class ChannelSubscriptionCreate(BaseModel):
    """Request model for creating a channel subscription."""

    channelName: str = Field(..., description="Channel name")
    channelType: ChannelType = Field(..., description="Channel type")
    direction: ChannelDirection = Field(..., description="Channel direction")
    dataType: str | None = Field(None, description="Data type handled by channel")
    description: str | None = Field(None, description="Channel description")


class ChannelSubscriptionResponse(BaseModel):
    """Response model for channel subscription."""

    channelName: str
    channelType: ChannelType
    direction: ChannelDirection
    dataType: str | None = None
    description: str | None = None
    subscribedAt: str


class ChannelSubscriptionsListResponse(BaseModel):
    """Response model for listing channel subscriptions."""

    agentId: str
    subscriptions: list[ChannelSubscriptionResponse]
    total: int


# =============================================================================
# Channel Subscription Endpoints
# =============================================================================


def get_channel_registry_instance() -> ChannelRegistry:
    """Dependency to get the channel registry."""
    return get_channel_registry()


@router.get("/{instance_id}/channels")
async def get_agent_channels(
    instance_id: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    channel_registry: Annotated[ChannelRegistry, Depends(get_channel_registry_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> ChannelSubscriptionsListResponse:
    """
    Get all channel subscriptions for an agent.

    Args:
        instance_id: Agent instance ID

    Returns:
        List of channel subscriptions for the agent
    """
    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        # Get subscriptions from channel registry
        subscriptions = channel_registry.get_subscriptions(instance_id)

        # Format response
        subscription_list = []
        for sub in subscriptions:
            # Get channel details
            channel = channel_registry.get_channel(sub)
            if channel:
                subscription_list.append(
                    ChannelSubscriptionResponse(
                        channelName=channel.name,
                        channelType=ChannelType.EVENT,  # Default type
                        direction=ChannelDirection.BIDIRECTIONAL,  # Default direction
                        description=channel.description,
                        subscribedAt=(
                            channel_registry.get_stats(channel.name).get("created_at", "")
                            if channel_registry.get_stats(channel.name)
                            else ""
                        ),
                    )
                )

        return ChannelSubscriptionsListResponse(
            agentId=instance_id,
            subscriptions=subscription_list,
            total=len(subscription_list),
        )
    except Exception as e:
        logger.exception("Failed to get agent channels: %s", e)
        raise HTTPException(500, f"Failed to get agent channels: {e!s}") from None


@router.post("/{instance_id}/channels")
async def add_agent_channel_subscription(
    instance_id: str,
    subscription: ChannelSubscriptionCreate,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    channel_registry: Annotated[ChannelRegistry, Depends(get_channel_registry_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> ChannelSubscriptionResponse:
    """
    Add a channel subscription for an agent.

    Args:
        instance_id: Agent instance ID
        subscription: Channel subscription details

    Returns:
        Created subscription details
    """
    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        # Subscribe agent to channel
        success = channel_registry.subscribe_agent(instance_id, subscription.channelName)

        if not success:
            raise HTTPException(400, f"Failed to subscribe to channel '{subscription.channelName}'")

        logger.info(
            "agent_channel_subscribed",
            agent_id=instance_id,
            channel=subscription.channelName,
            type=subscription.channelType.value,
        )

        return ChannelSubscriptionResponse(
            channelName=subscription.channelName,
            channelType=subscription.channelType,
            direction=subscription.direction,
            dataType=subscription.dataType,
            description=subscription.description,
            subscribedAt=datetime.now(UTC).isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to add channel subscription: %s", e)
        raise HTTPException(500, f"Failed to add channel subscription: {e!s}") from None


@router.delete("/{instance_id}/channels/{channel_name}")
async def remove_agent_channel_subscription(
    instance_id: str,
    channel_name: str,
    registry: Annotated[EnhancedAgentRegistry, Depends(get_registry)],
    channel_registry: Annotated[ChannelRegistry, Depends(get_channel_registry_instance)],
    authenticated: Annotated[str, Depends(verify_auth)],
) -> dict[str, str]:
    """
    Remove a channel subscription from an agent.

    Args:
        instance_id: Agent instance ID
        channel_name: Channel name to unsubscribe from

    Returns:
        Success status
    """
    # Verify agent exists
    instance = registry.get_instance(instance_id)
    if not instance:
        raise HTTPException(404, f"Agent instance '{instance_id}' not found")

    try:
        # Unsubscribe agent from channel
        success = channel_registry.unsubscribe_agent(instance_id, channel_name)

        if not success:
            raise HTTPException(400, f"Agent not subscribed to channel '{channel_name}'")

        logger.info(
            "agent_channel_unsubscribed",
            agent_id=instance_id,
            channel=channel_name,
        )

        return {"status": "success", "message": f"Unsubscribed from channel '{channel_name}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to remove channel subscription: %s", e)
        raise HTTPException(500, f"Failed to remove channel subscription: {e!s}") from None


# =============================================================================
