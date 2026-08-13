"""
JetStream initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_jetstream` free function creates the
default JetStream streams on the swarm's event mesh. The
main_loop ``_initialize_jetstream`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_jetstream`` is preserved as a
thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = logging.getLogger("heretek_swarm.runtime.initializers.jetstream")


async def initialize_jetstream(swarm: "AutonomousSwarm") -> None:
    """Initialize JetStream on ``swarm.event_mesh`` if available.

    Skips with a warning when the event mesh is unavailable
    (the swarm falls back to in-process pub-sub in that case).
    On JetStream failure, the swarm continues without durable
    streams (replay / persistence features are degraded).
    """
    if swarm.event_mesh is None:
        logger.warning("jetstream_skipped", message="No event mesh available")
        return
    try:
        ok = await swarm.event_mesh.initialize_jetstream(create_default_streams=True)
        if ok:
            logger.info("jetstream_streams_initialized")
        else:
            logger.warning(
                "jetstream_initialization_failed",
                message="Continuing without durable streams",
            )
    except Exception as exc:
        logger.warning("jetstream_init_failed", error=str(exc))


__all__ = ["initialize_jetstream"]
