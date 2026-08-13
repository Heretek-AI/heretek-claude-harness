"""
Election-manager initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_election_manager` free function wires
the ElectionManager instance. The main_loop
``_initialize_election_manager`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_election_manager`` is preserved
as a thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = logging.getLogger("heretek_swarm.runtime.initializers.election_manager")


async def initialize_election_manager(swarm: "AutonomousSwarm") -> None:
    """Wire the ElectionManager on ``swarm``.

    On any failure, ``swarm._election_manager`` is set to
    ``None`` and an ``election_manager_init_failed`` warning is
    logged. The swarm stays bootable; raft-based leadership
    election just runs without a manager.
    """
    try:
        from heretek_swarm_core.consensus.election_manager import ElectionManager

        swarm._election_manager = ElectionManager()
        logger.info(
            "election_manager_initialized",
            governance_agents=sorted(swarm._election_manager._rafts.keys()),
        )
    except Exception as exc:
        logger.warning("election_manager_init_failed", error=str(exc))
        swarm._election_manager = None


__all__ = ["initialize_election_manager"]
