"""
Entry Point — CLI entry point for autonomous swarm operation.

Extracted from runtime/main_loop.py to keep that module under 800 lines.
"""

from __future__ import annotations

import asyncio
import os

import structlog

from heretek_swarm.runtime.main_loop import AutonomousSwarm

logger = structlog.get_logger(__name__)


async def main() -> None:
    """Main entry point for autonomous operation."""
    from heretek_swarm.swarm_logging.config import setup_logging

    setup_logging(json_output=False, include_caller_info=False)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Set it to postgresql://user:pass@host:port/db "
            "or use docker compose."
        )

    nats_url = os.getenv("HERETEK_NATS_URL")
    if not nats_url:
        raise RuntimeError(
            "HERETEK_NATS_URL is required. Set it to nats://host:port "
            "or use docker compose."
        )
    nats_servers = [s.strip() for s in nats_url.split(",")]

    config = {
        "nats_servers": nats_servers,
        "health_check_interval": 30,
        "loop_interval": 1,
        "consciousness_interval": 5,
        "memory_maintenance_interval": 300,
        "scaling_interval": 60,
        "ephemeral": {"ttl_seconds": 3600},
        "persistent": {
            "connection_string": database_url,
        },
        "rag": {
            "embedding_provider": "openai",
            "collection_name": "heretek_documents",
        },
        "consensus": {
            "ahead_by_k": 2,
            "min_votes": 3,
            "red_flag_threshold": 0.3,
        },
    }

    try:
        swarm = AutonomousSwarm(config)
        await swarm.initialize()
        await swarm.run()
    except Exception as exc:
        logger.exception(
            "autonomous_swarm_main_failed",
            error=str(exc),
        )
        raise


if __name__ == "__main__":
    asyncio.run(main())
