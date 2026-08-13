"""
Supervisor initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_supervisor` free function creates the
ActorSupervisor on the swarm instance. The main_loop
``_initialize_supervisor`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_supervisor`` is preserved as
a thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = logging.getLogger("heretek_swarm.runtime.initializers.supervisor")


async def initialize_supervisor(swarm: "AutonomousSwarm") -> None:
    """Wire the ActorSupervisor on ``swarm``.

    On any failure, ``swarm.supervisor`` is set to ``None`` and
    a ``supervisor_init_failed`` warning is logged. The swarm
    stays bootable; actors that depend on the supervisor for
    auto-restart just run without it.
    """
    try:
        from heretek_swarm.actors.supervisor import ActorSupervisor

        swarm.supervisor = ActorSupervisor(
            health_check_interval=swarm._health_check_interval,
            auto_restart=True,
            max_restarts=5,
        )
        logger.info("actor_supervisor_initialized")
    except Exception as exc:
        logger.warning("supervisor_init_failed", error=str(exc))
        swarm.supervisor = None


__all__ = ["initialize_supervisor"]
