"""
Infrastructure Health Checks

Provides health check functions for infrastructure services:
- PostgreSQL (pg_isready)
- Redis (PING command)
- Qdrant (/healthz endpoint)
- NATS (INFO/PING)
- Mem0 (/health endpoint)
"""

from __future__ import annotations

import asyncio
import time
from typing import NamedTuple

import httpx
import structlog

from heretek_swarm.config.models import (
    HealthStatus,
    InfrastructureService,
)
from heretek_swarm.infrastructure.otel import instrumented_httpx_client

logger = structlog.get_logger("infrastructure.health")


class HealthCheckResult(NamedTuple):
    """Result of an infrastructure health check."""

    service: InfrastructureService
    status: HealthStatus
    latency_ms: float
    error: str | None = None


async def check_postgres_health(host: str, port: int, timeout: float = 5.0) -> HealthCheckResult:
    """
    Check PostgreSQL health using pg_isready or socket connection.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        timeout: Connection timeout in seconds

    Returns:
        HealthCheckResult with status and latency
    """
    start = time.perf_counter()
    try:
        # Try to open a TCP connection to verify port is reachable
        # pg_isready is preferred but requires psql client; socket test is reliable fallback
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()

        latency_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "postgres_health_check",
            host=host,
            port=port,
            status="healthy",
            latency_ms=round(latency_ms, 2),
        )
        return HealthCheckResult(
            service=InfrastructureService.POSTGRES,
            status=HealthStatus.HEALTHY,
            latency_ms=round(latency_ms, 2),
        )
    except TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        error = f"Connection timed out after {timeout}s"
        logger.warning(
            "postgres_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.POSTGRES,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        error = str(e)
        logger.warning(
            "postgres_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.POSTGRES,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )


async def check_redis_health(host: str, port: int, timeout: float = 5.0) -> HealthCheckResult:
    """
    Check Redis health using PING command.

    Args:
        host: Redis host
        port: Redis port
        timeout: Connection timeout in seconds

    Returns:
        HealthCheckResult with status and latency
    """
    import redis.asyncio as redis

    start = time.perf_counter()
    try:
        client = redis.Redis(host=host, port=port, socket_timeout=timeout)
        response = await client.ping()
        await client.aclose()

        latency_ms = (time.perf_counter() - start) * 1000

        if response:
            logger.info(
                "redis_health_check",
                host=host,
                port=port,
                status="healthy",
                latency_ms=round(latency_ms, 2),
            )
            return HealthCheckResult(
                service=InfrastructureService.REDIS,
                status=HealthStatus.HEALTHY,
                latency_ms=round(latency_ms, 2),
            )
        error = "PING returned unexpected response"
        return HealthCheckResult(
            service=InfrastructureService.REDIS,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        error = str(e)
        logger.warning(
            "redis_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.REDIS,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )


async def check_qdrant_health(host: str, port: int, timeout: float = 5.0) -> HealthCheckResult:
    """
    Check Qdrant health via /healthz endpoint.

    Args:
        host: Qdrant host
        port: Qdrant port (gRPC default 6333)
        timeout: Request timeout in seconds

    Returns:
        HealthCheckResult with status and latency
    """
    start = time.perf_counter()
    try:
        # Qdrant health check is on port 6333 (REST) or 6334 (gRPC)
        # Try REST endpoint first
        async with instrumented_httpx_client(call_type="health_qdrant") as client:
            response = await client.get(
                f"http://{host}:{port}/healthz",
                timeout=timeout,
            )

            latency_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                logger.info(
                    "qdrant_health_check",
                    host=host,
                    port=port,
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                )
                return HealthCheckResult(
                    service=InfrastructureService.QDRANT,
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency_ms, 2),
                )
            error = f"HTTP {response.status_code}"
            return HealthCheckResult(
                service=InfrastructureService.QDRANT,
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=error,
            )
    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        error = f"Request timed out after {timeout}s"
        logger.warning(
            "qdrant_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.QDRANT,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        error = str(e)
        logger.warning(
            "qdrant_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.QDRANT,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )


async def check_nats_health(host: str, port: int, timeout: float = 5.0) -> HealthCheckResult:
    """
    Check NATS health via CONNECT with PING.

    Args:
        host: NATS host
        port: NATS port (default 4222)
        timeout: Connection timeout in seconds

    Returns:
        HealthCheckResult with status and latency
    """
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )

        # Send CONNECT with no_auth_user for basic connectivity check
        connect_payload = b'CONNECT {"verbose":false,"ping":true}\r\n'
        writer.write(connect_payload)
        await writer.drain()

        # Read INFO response
        try:
            info_response = await asyncio.wait_for(reader.readline(), timeout=timeout)
            latency_ms = (time.perf_counter() - start) * 1000

            if info_response and b"INFO" in info_response:
                # Send PING
                writer.write(b"PING\r\n")
                await writer.drain()

                # Read PONG
                pong_response = await asyncio.wait_for(reader.readline(), timeout=timeout)
                if pong_response and b"PONG" in pong_response:
                    logger.info(
                        "nats_health_check",
                        host=host,
                        port=port,
                        status="healthy",
                        latency_ms=round(latency_ms, 2),
                    )
                    writer.close()
                    await writer.wait_closed()
                    return HealthCheckResult(
                        service=InfrastructureService.NATS,
                        status=HealthStatus.HEALTHY,
                        latency_ms=round(latency_ms, 2),
                    )

            # Close connection
            writer.close()
            await writer.wait_closed()

            error = "NATS INFO/PING exchange failed"
            return HealthCheckResult(
                service=InfrastructureService.NATS,
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=error,
            )

        except TimeoutError:
            writer.close()
            await writer.wait_closed()
            latency_ms = (time.perf_counter() - start) * 1000
            error = "Timeout waiting for NATS INFO response"
            return HealthCheckResult(
                service=InfrastructureService.NATS,
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=error,
            )

    except TimeoutError:
        latency_ms = (time.perf_counter() - start) * 1000
        error = f"Connection timed out after {timeout}s"
        logger.warning(
            "nats_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.NATS,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        error = str(e)
        logger.warning(
            "nats_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.NATS,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )


async def check_mem0_health(host: str, port: int, timeout: float = 5.0) -> HealthCheckResult:
    """
    Check Mem0 health via /health endpoint.

    Args:
        host: Mem0 host
        port: Mem0 port
        timeout: Request timeout in seconds

    Returns:
        HealthCheckResult with status and latency
    """
    start = time.perf_counter()
    try:
        async with instrumented_httpx_client(call_type="health_mem0") as client:
            # Mem0 FastAPI health check
            response = await client.get(
                f"http://{host}:{port}/health",
                timeout=timeout,
            )

            latency_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                logger.info(
                    "mem0_health_check",
                    host=host,
                    port=port,
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                )
                return HealthCheckResult(
                    service=InfrastructureService.MEM0,
                    status=HealthStatus.HEALTHY,
                    latency_ms=round(latency_ms, 2),
                )
            error = f"HTTP {response.status_code}"
            return HealthCheckResult(
                service=InfrastructureService.MEM0,
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                error=error,
            )
    except httpx.TimeoutException:
        latency_ms = (time.perf_counter() - start) * 1000
        error = f"Request timed out after {timeout}s"
        logger.warning(
            "mem0_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.MEM0,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        error = str(e)
        logger.warning(
            "mem0_health_check",
            host=host,
            port=port,
            status="unhealthy",
            error=error,
        )
        return HealthCheckResult(
            service=InfrastructureService.MEM0,
            status=HealthStatus.UNHEALTHY,
            latency_ms=round(latency_ms, 2),
            error=error,
        )


async def check_infrastructure_health(
    service: InfrastructureService,
    host: str,
    port: int,
    timeout: float = 5.0,
) -> HealthCheckResult:
    """
    Dispatch health check based on service type.

    Args:
        service: Infrastructure service type
        host: Service host
        port: Service port
        timeout: Health check timeout

    Returns:
        HealthCheckResult with status and latency
    """
    health_checkers = {
        InfrastructureService.POSTGRES: check_postgres_health,
        InfrastructureService.REDIS: check_redis_health,
        InfrastructureService.QDRANT: check_qdrant_health,
        InfrastructureService.NATS: check_nats_health,
        InfrastructureService.MEM0: check_mem0_health,
    }

    checker = health_checkers.get(service)
    if checker:
        return await checker(host, port, timeout)

    return HealthCheckResult(
        service=service,
        status=HealthStatus.UNKNOWN,
        latency_ms=0.0,
        error=f"No health checker for service type: {service}",
    )


async def check_all_infrastructure(
    configs: list[dict],
    timeout: float = 5.0,
) -> list[HealthCheckResult]:
    """
    Check health of all configured infrastructure services.

    Args:
        configs: List of infrastructure config dicts with 'service', 'host', 'port'
        timeout: Health check timeout per service

    Returns:
        List of HealthCheckResult for each service
    """
    import asyncio

    tasks = []
    for config in configs:
        service_str = config.get("service")
        try:
            service = InfrastructureService(service_str)
            tasks.append(
                check_infrastructure_health(
                    service=service,
                    host=config.get("host", "localhost"),
                    port=config.get("port", 0),
                    timeout=timeout,
                )
            )
        except ValueError:
            logger.warning(
                "skip_unknown_infrastructure_service",
                service=service_str,
            )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to error results
    health_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            config = configs[i]
            health_results.append(
                HealthCheckResult(
                    service=InfrastructureService(config.get("service", "unknown")),
                    status=HealthStatus.UNHEALTHY,
                    latency_ms=0.0,
                    error=str(result),
                )
            )
        else:
            health_results.append(result)

    return health_results
