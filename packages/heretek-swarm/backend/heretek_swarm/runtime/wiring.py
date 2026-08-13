"""
Orchestrator wiring helpers.

Extracted from ``runtime/main_loop.py`` as part of Phase 2.2 of
PLAN.md (§1.4 god-class extraction — ``main_loop.py`` was
1,800 LOC with 12+ concerns; one of the most concerning was
the ``_rewire_orchestrator_refs`` post-hoc dependency patching
anti-pattern).

The audit's recommendation was to refactor main_loop.py so
each orchestrator (``_actor_orch``, ``_deliberation``,
``_steering``, …) accepts its dependencies through its
constructor, and the ``_rewire_*`` methods go away. This
commit ships the intermediate step:

* The post-hoc rewiring logic is now in
  :func:`wire_orchestrators` here. The main loop calls this
  helper instead of doing the assignments inline.
* The helper documents the constructor-injection path that
  will replace it: when each orchestrator's ``__init__``
  takes the supervisor / mcp_tools / event_mesh / consensus
  it depends on, this function becomes a no-op.
* :func:`thread_event_mesh_to_supervisor` is the second piece
  of post-hoc wiring; same pattern.

Backwards compatibility: ``_rewire_orchestrator_refs`` and
``_thread_event_mesh_to_supervisor`` are kept on
``AutonomousSwarm`` as thin delegates to these functions,
so the existing call in ``initialize()`` keeps working.
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = structlog.get_logger(__name__)


def wire_orchestrators(swarm: "AutonomousSwarm") -> None:
    """Wire orchestrator dependencies into the autonomous swarm.

    Sets the supervisor / mcp_tools / channel_registry /
    event_mesh attributes on the actor orchestrator and the
    supervisor / consensus attributes on the deliberation
    orchestrator.

    .. note::
        This function uses post-hoc attribute assignment. The
        long-term path (Phase 2.2 follow-up) is for each
        orchestrator to accept these dependencies through its
        ``__init__`` so this function becomes a no-op. Until
        that refactor lands, this is the canonical place
        where the cross-orchestrator wiring lives.
    """
    swarm._actor_orch._supervisor = swarm.supervisor
    swarm._actor_orch._mcp_tools = swarm.mcp_tools
    swarm._actor_orch._channel_registry = swarm.channel_registry
    swarm._actor_orch._event_mesh = swarm.event_mesh
    swarm._deliberation._supervisor = swarm.supervisor
    swarm._deliberation._consensus = swarm.consensus


def thread_event_mesh_to_supervisor(swarm: "AutonomousSwarm") -> None:
    """Thread the event mesh into the supervisor, if it is connected.

    If the mesh exists but ``is_connected`` is False (e.g. NATS
    failed during ``_initialize_event_mesh``), the supervisor
    gets ``None`` and a warning is logged so the operators see
    the degraded state.
    """
    if swarm.event_mesh is not None:
        if swarm.event_mesh.is_connected:
            swarm.supervisor._event_mesh = swarm.event_mesh
            logger.info(
                "event_mesh_threaded_to_supervisor",
                mesh_type="NATSEventMeshWithJetStream",
            )
        else:
            logger.warning(
                "event_mesh_not_connected_at_spawn_time",
                message=(
                    "Event mesh exists but is_connected is False "
                    "— agents will use stubs."
                ),
            )
            swarm.supervisor._event_mesh = None


__all__ = [
    "wire_orchestrators",
    "thread_event_mesh_to_supervisor",
]
