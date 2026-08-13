"""
Event-mesh initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_event_mesh` free function wires the
NATS event mesh on the swarm instance. The main_loop
``_initialize_event_mesh`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_event_mesh`` is preserved
as a thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

from heretek_swarm.gateway.nats_event_mesh import NATSEventMeshWithJetStream

logger = logging.getLogger("heretek_swarm.runtime.initializers.event_mesh")


async def initialize_event_mesh(swarm: "AutonomousSwarm") -> None:
    """Connect the NATS event mesh on ``swarm``.

    On any failure, ``swarm.event_mesh`` is set to ``None`` and
    a ``event_mesh_init_failed`` warning is logged. The swarm
    stays bootable; the NATS-dependent features just run in
    fallback mode.
    """
    try:
        servers = swarm.config.get("nats_servers")
        if not servers:
            nats_url = os.getenv("HERETEK_NATS_URL")
            if not nats_url:
                raise RuntimeError(
                    "HERETEK_NATS_URL is required. Set it to nats://host:port "
                    "or use docker compose."
                )
            servers = [s.strip() for s in nats_url.split(",")]
        swarm.event_mesh = NATSEventMeshWithJetStream(servers=servers, fallback=True)
        await swarm.event_mesh.connect()
        logger.info("event_mesh_connected")
    except Exception as exc:
        logger.warning("event_mesh_init_failed", error=str(exc))
        swarm.event_mesh = None


__all__ = ["initialize_event_mesh"]
