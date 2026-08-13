"""FastAPI app factory with full dependency wiring."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from tier1.api.routes import deliberations, health, ws
from tier1.config import Settings, get_settings
from tier1.dashboard.serve import mount_static
from tier1.events.nats_client import NatsClient
from tier1.llm.garage import ModelGarage
from tier1.persistence.postgres import PostgresPool
from tier1.persistence.qdrant import QdrantStore
from tier1.persistence.redis import RedisCache


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    pg = PostgresPool(settings.postgres_dsn)
    redis = RedisCache(settings.redis_url, settings.redis_ttl_s)
    nats = NatsClient(settings.nats_url)
    qdrant = QdrantStore(settings.qdrant_url, settings.qdrant_collection)
    garage = ModelGarage(settings)

    # Connect in order; if any later connect fails, close the ones that
    # succeeded so we don't leak resources.
    connected: list[tuple[str, object]] = []
    try:
        await pg.connect()
        connected.append(("pg", pg))
        await redis.connect()
        connected.append(("redis", redis))
        await nats.connect()
        connected.append(("nats", nats))
        qdrant.connect()
        connected.append(("qdrant", qdrant))
    except Exception:
        for name, client in reversed(connected):
            try:
                await client.close()
            except Exception:  # noqa: BLE001
                pass
        raise

    app.state.pg = pg
    app.state.redis = redis
    app.state.nats = nats
    app.state.qdrant = qdrant
    app.state.garage = garage

    try:
        yield
    finally:
        qdrant.close()
        await nats.close()
        await redis.close()
        await pg.close()


def create_app(settings: Settings | None = None, dashboard_path: Path | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Tier 1 Core Triad", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    # Wire observability (OTel traces + metrics + logging)
    from tier1.observability import init_telemetry

    init_telemetry(app)
    app.include_router(health.router)
    app.include_router(deliberations.router)
    app.include_router(ws.router)
    if dashboard_path is not None:
        mount_static(app, dashboard_path)
    return app
