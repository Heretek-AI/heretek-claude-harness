"""
CLI Configuration Loader

Synchronously loads infrastructure configuration from the database and sets
environment variables for downstream services. Used by `run` and `serve` commands
to bridge wizard-configured infrastructure with the runtime environment.

This module deliberately avoids importing ConfigurationService (which is async)
to prevent import-time side effects and allow the CLI to function with minimal
dependencies.
"""

from __future__ import annotations

import os
import warnings
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from heretek_swarm.config.db_models import (
    InfrastructureConfig as InfrastructureConfigORM,
)

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

import structlog

logger = structlog.get_logger(__name__)


class LoadResult(TypedDict):
    """Result of loading infrastructure configuration."""

    postgres: dict[str, bool | str | None]  # 'set': True/False, 'url': str or None
    redis: dict[str, bool | str | None]
    qdrant: dict[str, bool | str | None]
    nats: dict[str, bool | str | None]


# Environment variable names
ENV_DATABASE_URL = "DATABASE_URL"
ENV_REDIS_URL = "REDIS_URL"
ENV_QDRANT_HOST = "QDRANT_HOST"
ENV_HERETEK_NATS_URL = "HERETEK_NATS_URL"


def load_infrastructure_config() -> LoadResult:
    """
    Load infrastructure configuration from the database and set environment variables.

    Reads DATABASE_URL from the environment, connects to the database synchronously,
    and queries the infrastructure_config table for enabled services. Sets environment
    variables for each service if not already present.

    Environment Variables Set:
        - DATABASE_URL: PostgreSQL connection URL (from postgres service connection_url)
        - REDIS_URL: Redis connection URL (redis://host:port)
        - QDRANT_HOST: Qdrant server URL (http://host:port)
        - HERETEK_NATS_URL: NATS server URL (nats://host:port)

    Returns:
        LoadResult dict with 'postgres', 'redis', 'qdrant', 'nats' keys.
        Each entry contains:
            - 'set': True if the env var was set by this function, False if skipped
            - 'url': The URL/host that was set or pre-existing value

    Raises:
        RuntimeError: If DATABASE_URL is not set in the environment.
    """
    database_url = os.environ.get(ENV_DATABASE_URL)

    if not database_url:
        raise RuntimeError(
            f"Cannot load infrastructure config: {ENV_DATABASE_URL} is not set. "
            "Either set DATABASE_URL manually or run the wizard to configure infrastructure."
        )

    # Convert async driver URL to sync driver URL if needed
    # postgresql+asyncpg:// -> postgresql+psycopg2:// or postgresql://
    sync_url = _to_sync_url(database_url)

    # Create sync engine
    engine: Engine = create_engine(sync_url, echo=False)

    try:
        return _query_and_set_env(engine)
    finally:
        engine.dispose()


def _to_sync_url(async_url: str) -> str:
    """
    Convert an async database URL to a sync equivalent.

    Args:
        async_url: Database URL potentially using async drivers.

    Returns:
        Sync-compatible database URL.
    """
    # asyncpg uses postgresql+asyncpg://
    if "+asyncpg" in async_url:
        return async_url.replace("+asyncpg", "")
    # aiOPG uses postgresql+aiopg://
    if "+aiopg" in async_url:
        return async_url.replace("+aiopg", "")
    # Already sync (postgresql://) or other
    return async_url


def _query_and_set_env(engine: Engine) -> LoadResult:
    """
    Query infrastructure config and set environment variables.

    Args:
        engine: SQLAlchemy sync engine.

    Returns:
        LoadResult dict showing what was set vs skipped.
    """
    SessionFactory = sessionmaker(bind=engine)
    session: Session = SessionFactory()

    result: LoadResult = {
        "postgres": {"set": False, "url": os.environ.get(ENV_DATABASE_URL)},
        "redis": {"set": False, "url": os.environ.get(ENV_REDIS_URL)},
        "qdrant": {"set": False, "url": os.environ.get(ENV_QDRANT_HOST)},
        "nats": {"set": False, "url": os.environ.get(ENV_HERETEK_NATS_URL)},
    }

    try:
        # Query all enabled infrastructure configs
        stmt = select(InfrastructureConfigORM).where(
            InfrastructureConfigORM.is_enabled
        )
        configs = session.execute(stmt).scalars().all()

        if not configs:
            warnings.warn(
                "No infrastructure configuration found in database. "
                "Set environment variables manually or run the wizard to configure infrastructure.",
                stacklevel=2,
            )
            return result

        # Map configs to environment variables
        for config in configs:
            service = config.service

            if service == "postgres":
                _set_postgres_env(config, result)
            elif service == "redis":
                _set_redis_env(config, result)
            elif service == "qdrant":
                _set_qdrant_env(config, result)
            elif service == "nats":
                _set_nats_env(config, result)

        return result

    except Exception as exc:
        # Gracefully handle missing table (first-run before migrations)
        exc_str = str(exc)
        if "UndefinedTable" in exc_str or "does not exist" in exc_str:
            logger.warning(
                "infrastructure_config_table_missing",
                hint="Run migrations to create the infrastructure_config table. "
                     "Falling back to environment variables.",
            )
            warnings.warn(
                "infrastructure_config table does not exist yet. "
                "Run migrations or the setup wizard. Falling back to environment variables.",
                stacklevel=3,
            )
            session.rollback()
            return result
        raise

    finally:
        session.close()


def _set_postgres_env(config: InfrastructureConfigORM, result: LoadResult) -> None:
    """Set PostgreSQL environment variable from config."""
    if ENV_DATABASE_URL in os.environ:
        return  # Already set, skip

    if config.connection_url:
        os.environ[ENV_DATABASE_URL] = config.connection_url
    else:
        # Fallback: construct from host/port
        os.environ[ENV_DATABASE_URL] = f"postgresql://{config.host}:{config.port}"

    result["postgres"] = {"set": True, "url": os.environ[ENV_DATABASE_URL]}


def _set_redis_env(config: InfrastructureConfigORM, result: LoadResult) -> None:
    """Set Redis environment variable from config."""
    if ENV_REDIS_URL in os.environ:
        return  # Already set, skip

    redis_url = f"redis://{config.host}:{config.port}"
    os.environ[ENV_REDIS_URL] = redis_url
    result["redis"] = {"set": True, "url": redis_url}


def _set_qdrant_env(config: InfrastructureConfigORM, result: LoadResult) -> None:
    """Set Qdrant environment variable from config."""
    if ENV_QDRANT_HOST in os.environ:
        return  # Already set, skip

    qdrant_url = f"http://{config.host}:{config.port}"
    os.environ[ENV_QDRANT_HOST] = qdrant_url
    result["qdrant"] = {"set": True, "url": qdrant_url}


def _set_nats_env(config: InfrastructureConfigORM, result: LoadResult) -> None:
    """Set NATS environment variable from config."""
    if ENV_HERETEK_NATS_URL in os.environ:
        return  # Already set, skip

    nats_url = f"nats://{config.host}:{config.port}"
    os.environ[ENV_HERETEK_NATS_URL] = nats_url
    result["nats"] = {"set": True, "url": nats_url}
