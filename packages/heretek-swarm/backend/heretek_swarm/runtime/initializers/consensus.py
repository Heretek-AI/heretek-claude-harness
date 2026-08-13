"""
Consensus initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_consensus` free function configures
the MAKERConsensus engine on the swarm instance. The
main_loop ``_initialize_consensus`` method delegates
here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_consensus`` is preserved
as a thin delegate so existing call sites work
unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

from heretek_swarm_core.consensus import MAKERConsensus

logger = logging.getLogger("heretek_swarm.runtime.initializers.consensus")


async def initialize_consensus(swarm: "AutonomousSwarm") -> None:
    """Wire the MAKERConsensus engine on ``swarm``.

    Reads the consensus config block (``ahead_by_k``,
    ``min_votes``, ``red_flag_threshold``) from
    ``swarm.config``. On any failure, ``swarm.consensus``
    is set to ``None`` and a warning is logged.
    """
    try:
        consensus_config = swarm.config.get("consensus", {})
        swarm.consensus = MAKERConsensus(
            ahead_by_k=consensus_config.get("ahead_by_k", 2),
            min_votes=consensus_config.get("min_votes", 3),
            confidence_threshold=consensus_config.get(
                "red_flag_threshold", 0.3
            ),
        )
        logger.info("maker_consensus_initialized")
    except Exception as exc:
        logger.warning("consensus_init_failed", error=str(exc))
        swarm.consensus = None


__all__ = ["initialize_consensus"]
