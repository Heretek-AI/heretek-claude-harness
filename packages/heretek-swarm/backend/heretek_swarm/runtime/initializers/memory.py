"""
Memory initializer — extracted from
``runtime/main_loop.py`` as part of Phase 2.6 of PLAN.md.

The :func:`initialize_memory` free function configures
the cognee reader + writer on the swarm instance. The
main_loop ``_initialize_memory`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_memory`` is preserved as a
thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

from heretek_swarm_core.memory.cognee_reader import CogneeMemoryReader
from heretek_swarm_core.memory.cognee_writer import CogneeMemoryWriter

logger = logging.getLogger("heretek_swarm.runtime.initializers.memory")


async def initialize_memory(swarm: "AutonomousSwarm") -> None:
    """Wire the cognee memory reader and writer on ``swarm``.

    On any failure, both handles are set to ``None`` and
    a ``cognee_memory_init_failed`` warning is logged. The
    actor stays bootable — other layers (rag, consensus)
    can still operate; only the memory-write path is
    disabled.
    """
    try:
        swarm._cognee_reader = CogneeMemoryReader()
        swarm._cognee_writer = CogneeMemoryWriter()
        reader_ok = await swarm._cognee_reader.health()
        writer_ok = await swarm._cognee_writer.health()
        logger.info(
            "cognee_memory_initialized",
            reader_ok=reader_ok,
            writer_ok=writer_ok,
        )
    except Exception as exc:
        logger.warning("cognee_memory_init_failed", error=str(exc))
        swarm._cognee_reader = None
        swarm._cognee_writer = None


__all__ = ["initialize_memory"]
