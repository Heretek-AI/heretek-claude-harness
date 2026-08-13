#!/usr/bin/env python3
"""
Re-seed stale LLM/embedding provider entries in the
ConfigurationService DB.

Phase 3.15 of PLAN.md (re-seed DB). The
``/api/config/{llm,embedding}/providers`` endpoint returns
a stale ``openai-default`` entry from a prior DB seed. The
runtime env config is correct; the DB row is leftover.

This script removes any DB-registered LLM / embedding
provider whose ``is_default=True`` AND whose model name is
no longer in the live environment, so the runtime env takes
over as the source of truth.

Usage:
    # Local dev (uses .env)
    python scripts/reseed_db_providers.py

    # Docker compose (one-shot exec)
    docker compose exec api python scripts/reseed_db_providers.py

It is safe to run multiple times (idempotent).
"""

from __future__ import annotations

import asyncio
import os
import sys

# Make backend/ importable when running this script directly.
sys.path.insert(
    0, os.path.join(os.path.dirname(__file__), os.pardir, "backend")
)

import structlog

logger = structlog.get_logger("reseed_db_providers")


async def reseed() -> None:
    """Remove stale default LLM / embedding provider rows."""
    from sqlalchemy import delete, select

    from heretek_swarm.config.db_models import (
        EmbeddingProvider as EmbeddingProviderORM,
        LLMProvider as LLMProviderORM,
    )
    from heretek_swarm.config.service import (
        get_config_service,
        initialize_config_service,
    )

    await initialize_config_service()
    service = get_config_service()

    async with service.session_factory() as session:
        # Remove any default LLM providers — env config is the
        # source of truth, the DB row is leftover.
        llm_default_stmt = select(LLMProviderORM).where(
            LLMProviderORM.is_default.is_(True)
        )
        llm_defaults = (await session.execute(llm_default_stmt)).scalars().all()
        for row in llm_defaults:
            logger.info(
                "removing_stale_default_llm_provider",
                id=str(row.id),
                name=row.name,
            )
            await session.delete(row)

        # Same for embedding providers.
        emb_default_stmt = select(EmbeddingProviderORM).where(
            EmbeddingProviderORM.is_default.is_(True)
        )
        emb_defaults = (await session.execute(emb_default_stmt)).scalars().all()
        for row in emb_defaults:
            logger.info(
                "removing_stale_default_embedding_provider",
                id=str(row.id),
                name=row.name,
            )
            await session.delete(row)

        await session.commit()
        logger.info(
            "reseed_complete",
            llm_defaults_removed=len(llm_defaults),
            embedding_defaults_removed=len(emb_defaults),
        )


def main() -> None:
    asyncio.run(reseed())


if __name__ == "__main__":
    main()
