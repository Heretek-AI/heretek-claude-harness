"""
Agent Management API Endpoints.

This module provides REST API endpoints for agent lifecycle management,
delegating to submodules for each functional area.

Submodules:
- chat: Chat messaging via triad deliberation
- core: Agent type discovery and deployment
- lifecycle: Agent start/stop/suspend/resume
- instances: Agent instance management (also handles supervisor.actors type lookup)
- jetstream: JetStream stream management
- profiling: Behavior profiling endpoints
- routing_rules: Content routing rules
- routing_control: Routing rule control (enable/disable)
- supervisor: Supervisor-based agent management (list, metrics, terminate)
"""

import structlog
from fastapi import APIRouter

from heretek_swarm.api.agents import (
    chat,
    core,
    instances,
    jetstream,
    lifecycle,
    profiling,
    routing_control,
    routing_rules,
    supervisor,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/api/agents")

# Include routers from submodules.
#
# Order matters: literal-path subrouters (instances, types, stats, deploy, available)
# must be registered BEFORE the supervisor router, which exposes a catch-all
# GET /{agent_id}. FastAPI/Starlette resolve paths in registration order, so
# the catch-all would otherwise shadow the literal /instances, /available, etc.
#
# F-009 (2026-06-01 cold-start validation): the bare-GET /{instance_id} route
# in instances.router is now the unified lookup endpoint — it checks
# supervisor.actors first (for registered agent types like "steward") and
# falls back to the instance registry (for deployed instance ids). This
# eliminates the routing collision with supervisor.router's /{agent_id} and
# removes the need for path-pattern constraints or router-reordering tricks.
router.include_router(chat.router, tags=["chat"])
router.include_router(core.router, tags=["core"])
router.include_router(lifecycle.router, tags=["lifecycle"])
router.include_router(instances.router, tags=["instances"])
router.include_router(jetstream.router, tags=["jetstream"])
router.include_router(profiling.router, tags=["profiling"])
router.include_router(routing_rules.router, tags=["routing_rules"])
router.include_router(routing_control.router, tags=["routing_control"])
router.include_router(supervisor.router, tags=["supervisor"])
