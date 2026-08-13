"""GET /health — reports component status."""

import httpx

from fastapi import APIRouter

from tier1.api.deps import NatsDep, PgDep, QdrantDep, RedisDep
from tier1.api.schemas import HealthComponent, HealthResponse
from tier1.config import Settings, get_settings

router = APIRouter()


async def _probe_http(url: str, timeout: float = 1.0) -> bool:
    """Cheap HTTP liveness probe. Returns True iff the URL responds 2xx."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url)
        return 200 <= r.status_code < 300
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health(
    pg: PgDep,
    redis: RedisDep,
    nats: NatsDep,
    qdrant: QdrantDep,
) -> HealthResponse:
    settings: Settings = get_settings()
    components: dict[str, HealthComponent] = {"api": HealthComponent(status="ok")}
    try:
        async with pg.pool.acquire() as conn:
            await conn.execute("SELECT 1")
        components["postgres"] = HealthComponent(status="ok")
    except Exception as exc:
        components["postgres"] = HealthComponent(status="down", detail=str(exc))
    try:
        await redis.client.ping()
        components["redis"] = HealthComponent(status="ok")
    except Exception as exc:
        components["redis"] = HealthComponent(status="down", detail=str(exc))
    try:
        if await nats.health():
            components["nats"] = HealthComponent(status="ok")
        else:
            components["nats"] = HealthComponent(status="down")
    except Exception as exc:
        components["nats"] = HealthComponent(status="down", detail=str(exc))
    # Qdrant: standard probe is get_collections() (qdrant-client docs).
    try:
        if qdrant.health():
            components["qdrant"] = HealthComponent(status="ok")
        else:
            components["qdrant"] = HealthComponent(status="down")
    except Exception as exc:
        components["qdrant"] = HealthComponent(status="down", detail=str(exc))
    # Advisory: cognee/mem0. Their Docker images are not on Docker Hub
    # at the spec'd tag, so these probes are best-effort and do NOT
    # affect the overall status. They surface whether the optional
    # memory backends are reachable when an operator runs them.
    if await _probe_http(f"{settings.cognee_url}/health"):
        components["cognee"] = HealthComponent(status="ok")
    else:
        components["cognee"] = HealthComponent(status="not_probed")
    if await _probe_http(f"{settings.mem0_url}/health"):
        components["mem0"] = HealthComponent(status="ok")
    else:
        components["mem0"] = HealthComponent(status="not_probed")
    # Overall: only "ok" iff the four hard-required components are all
    # up; advisory components (cognee, mem0) don't degrade overall.
    hard_required = ("api", "postgres", "redis", "nats", "qdrant")
    overall = "ok" if all(components[k].status == "ok" for k in hard_required) else "degraded"
    return HealthResponse(status=overall, components=components)
