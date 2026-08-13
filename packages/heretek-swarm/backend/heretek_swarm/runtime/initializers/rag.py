"""
RAG initializer — extracted from ``runtime/main_loop.py``
as part of Phase 2.6 of PLAN.md.

The :func:`initialize_rag` free function configures the
RAG retriever on the swarm instance. The main_loop
``_initialize_rag`` method delegates here.

Backwards compatibility: the legacy method
``AutonomousSwarm._initialize_rag`` is preserved as a
thin delegate so existing call sites work unchanged.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heretek_swarm.runtime.main_loop import AutonomousSwarm

from heretek_swarm.rag import get_rag_retriever

logger = logging.getLogger("heretek_swarm.runtime.initializers.rag")


async def initialize_rag(swarm: "AutonomousSwarm") -> None:
    """Wire the cognee-backed RAG retriever on ``swarm``.

    On any failure, ``swarm.rag`` is set to ``None`` and
    a ``rag_init_failed`` warning is logged. The actor
    stays bootable; the RAG path is just disabled.
    """
    try:
        swarm.rag = get_rag_retriever()
        logger.info("cognee_rag_retriever_initialized")
    except Exception as exc:
        logger.warning("rag_init_failed", error=str(exc))
        swarm.rag = None


__all__ = ["initialize_rag"]
