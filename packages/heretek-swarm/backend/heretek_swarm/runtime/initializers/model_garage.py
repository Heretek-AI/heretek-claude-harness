"""
Model-garage initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_model_garage` free function wires the
ModelGarage instance and installs it as the global model
garage for the process. The main_loop
``_initialize_model_garage`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_model_garage`` is preserved
as a thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = logging.getLogger("heretek_swarm.runtime.initializers.model_garage")


async def initialize_model_garage(swarm: "AutonomousSwarm") -> None:
    """Wire the ModelGarage on ``swarm`` and install it globally.

    On any failure, ``swarm.model_garage`` is set to ``None`` and
    a ``model_garage_init_failed`` warning is logged. The swarm
    stays bootable; LLM-dependent features just run without a
    central router (callers fall back to provider-direct paths).
    """
    try:
        from heretek_swarm_core.llm.model_garage import (
            ModelGarage,
            set_global_model_garage,
        )

        swarm.model_garage = ModelGarage()
        await swarm.model_garage.initialize()
        set_global_model_garage(swarm.model_garage)
        logger.info("model_garage_initialized")
    except Exception as exc:
        logger.warning("model_garage_init_failed", error=str(exc))
        swarm.model_garage = None


__all__ = ["initialize_model_garage"]
