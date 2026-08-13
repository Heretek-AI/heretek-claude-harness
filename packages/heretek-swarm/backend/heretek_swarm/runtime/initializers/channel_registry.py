"""
Channel-registry initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_channel_registry` free function
configures the channel + group registries on the swarm
instance. The main_loop ``_initialize_channel_registry``
method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_channel_registry`` is
preserved as a thin delegate so existing call sites work
unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

from heretek_swarm.channels import ChannelRegistry, GroupRegistry

logger = logging.getLogger("heretek_swarm.runtime.initializers.channel_registry")


async def initialize_channel_registry(swarm: "AutonomousSwarm") -> None:
    """Wire the channel + group registries on ``swarm``.

    On any failure, both handles are set to ``None`` and
    a ``channel_registry_init_failed`` warning is logged.
    The actor stays bootable; the channels layer just runs
    in degraded mode.
    """
    try:
        swarm.channel_registry = ChannelRegistry()
        swarm.group_registry = GroupRegistry(swarm.channel_registry)
        logger.info("channel_registry_initialized")
    except Exception as exc:
        logger.warning("channel_registry_init_failed", error=str(exc))
        swarm.channel_registry = None
        swarm.group_registry = None


__all__ = ["initialize_channel_registry"]
