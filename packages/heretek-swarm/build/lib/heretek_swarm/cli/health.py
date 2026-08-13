"""
Infrastructure health-check functions and container-runtime detection.

All async health-check helpers, the ``_make_result`` factory, and the
synchronous ``check_container_runtime`` / ``check_compose_plugin`` utilities.
Also includes infrastructure-config loading helpers used by multiple CLI
commands.
"""

from __future__ import annotations

import asyncio
import subprocess
import time
from typing import Any

import click
import structlog

from heretek_swarm.cli.config_loader import load_infrastructure_config
from heretek_swarm.config.models import HealthStatus, InfrastructureService

logger = structlog.get_logger("cli.health")


# ---------------------------------------------------------------------------
# Infrastructure config helpers (shared by run / serve / status)
# ---------------------------------------------------------------------------


def _load_infrastructure_config_and_echo() -> dict[str, Any] | None:
    """Load infrastructure config from database and echo any warnings."""
    try:
        return load_infrastructure_config()
    except RuntimeError as e:
        click.echo(f"\n  ⚠ {e}")
        return None


def _print_infrastructure_config(result: dict[str, Any] | None) -> None:
    """Print loaded infrastructure config values to stdout."""
    if result is None:
        return

    any_set = any(entry.get("set", False) for entry in result.values())
    if not any_set:
        click.echo("  Infrastructure: loaded from environment variables")
        return

    for service_name, entry in result.items():
        url = entry.get("url") if entry else None
        if url:
            click.echo(f"  {service_name.capitalize()}: {url}")


# ---------------------------------------------------------------------------
# Health check helpers
# ---------------------------------------------------------------------------


def _make_result(
    service: InfrastructureService,
    status: HealthStatus,
    start: float,
    error: str | None = None,
) -> dict[str, Any]:
    """Create a health check result dict."""
    latency_ms = (time.perf_counter() - start) * 1000
    return {
        "service": service.value,
        "status": status.value,
        "latency_ms": round(latency_ms, 2),
        "error": error,
    }


async def _check_postgres(
    host: str, port: int, timeout: float, start: float
) -> dict[str, Any]:
    """Check PostgreSQL health via TCP socket."""
    try:
        _reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return _make_result(InfrastructureService.POSTGRES, HealthStatus.HEALTHY, start)
    except TimeoutError:
        return _make_result(
            InfrastructureService.POSTGRES, HealthStatus.UNHEALTHY, start, "Connection timed out"
        )
    except Exception as e:
        return _make_result(InfrastructureService.POSTGRES, HealthStatus.UNHEALTHY, start, str(e))


async def _check_redis(
    host: str, port: int, timeout: float, start: float
) -> dict[str, Any]:
    """Check Redis health via PING."""
    import redis.asyncio as redis

    try:
        client = redis.Redis(host=host, port=port, socket_timeout=timeout)
        await client.ping()
        await client.aclose()
        return _make_result(InfrastructureService.REDIS, HealthStatus.HEALTHY, start)
    except Exception as e:
        return _make_result(InfrastructureService.REDIS, HealthStatus.UNHEALTHY, start, str(e))


async def _check_qdrant(
    host: str, port: int, timeout: float, start: float
) -> dict[str, Any]:
    """Check Qdrant health via /healthz endpoint."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{host}:{port}/healthz", timeout=timeout)
            if response.status_code == 200:
                return _make_result(InfrastructureService.QDRANT, HealthStatus.HEALTHY, start)
            return _make_result(
                InfrastructureService.QDRANT,
                HealthStatus.UNHEALTHY,
                start,
                f"HTTP {response.status_code}",
            )
    except httpx.TimeoutException:
        return _make_result(
            InfrastructureService.QDRANT, HealthStatus.UNHEALTHY, start, "Request timed out"
        )
    except Exception as e:
        return _make_result(InfrastructureService.QDRANT, HealthStatus.UNHEALTHY, start, str(e))


async def _check_nats(
    host: str, port: int, timeout: float, start: float
) -> dict[str, Any]:
    """Check NATS health via CONNECT/PING exchange."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )

        # Send CONNECT
        writer.write(b'CONNECT {"verbose":false,"ping":true}\r\n')
        await writer.drain()

        # Read INFO
        info_response = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not (info_response and b"INFO" in info_response):
            writer.close()
            await writer.wait_closed()
            return _make_result(
                InfrastructureService.NATS, HealthStatus.UNHEALTHY, start, "No INFO response"
            )

        # Send PING
        writer.write(b"PING\r\n")
        await writer.drain()

        # Read PONG
        pong_response = await asyncio.wait_for(reader.readline(), timeout=timeout)
        writer.close()
        await writer.wait_closed()

        if pong_response and b"PONG" in pong_response:
            return _make_result(InfrastructureService.NATS, HealthStatus.HEALTHY, start)
        return _make_result(
            InfrastructureService.NATS, HealthStatus.UNHEALTHY, start, "No PONG response"
        )
    except TimeoutError:
        return _make_result(
            InfrastructureService.NATS, HealthStatus.UNHEALTHY, start, "Connection timed out"
        )
    except Exception as e:
        return _make_result(InfrastructureService.NATS, HealthStatus.UNHEALTHY, start, str(e))


async def _check_mem0(
    host: str, port: int, timeout: float, start: float
) -> dict[str, Any]:
    """Check Mem0 health via /health endpoint."""
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://{host}:{port}/health", timeout=timeout)
            if response.status_code == 200:
                return _make_result(InfrastructureService.MEM0, HealthStatus.HEALTHY, start)
            return _make_result(
                InfrastructureService.MEM0,
                HealthStatus.UNHEALTHY,
                start,
                f"HTTP {response.status_code}",
            )
    except httpx.TimeoutException:
        return _make_result(
            InfrastructureService.MEM0, HealthStatus.UNHEALTHY, start, "Request timed out"
        )
    except Exception as e:
        return _make_result(InfrastructureService.MEM0, HealthStatus.UNHEALTHY, start, str(e))


async def _check_service_health(
    service: InfrastructureService,
    host: str,
    port: int,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Perform health check for a single service, dispatching by type."""
    start = time.perf_counter()

    try:
        if service == InfrastructureService.POSTGRES:
            return await _check_postgres(host, port, timeout, start)
        if service == InfrastructureService.REDIS:
            return await _check_redis(host, port, timeout, start)
        if service == InfrastructureService.QDRANT:
            return await _check_qdrant(host, port, timeout, start)
        if service == InfrastructureService.NATS:
            return await _check_nats(host, port, timeout, start)
        if service == InfrastructureService.MEM0:
            return await _check_mem0(host, port, timeout, start)
        return _make_result(service, HealthStatus.UNKNOWN, start, f"Unknown service: {service}")
    except Exception as e:
        logger.warning("health_check_error", service=service.value, error=str(e))
        return _make_result(service, HealthStatus.UNHEALTHY, start, str(e))


# ---------------------------------------------------------------------------
# Container runtime detection
# ---------------------------------------------------------------------------


def check_container_runtime() -> tuple[str | None, str]:
    """Detect available container runtime (Docker or Podman).

    Returns:
        Tuple of (runtime_name, version_string) or (None, error_message).
    """
    for runtime in ["docker", "podman"]:
        try:
            result = subprocess.run(  # noqa: S603
                [runtime, "--version"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info("container_runtime_detected", runtime=runtime, version=version)
                return runtime, version
        except (subprocess.SubprocessError, FileNotFoundError):
            continue

    logger.warning("no_container_runtime_detected")
    return None, "Neither Docker nor Podman found"


def check_compose_plugin(runtime: str) -> bool:
    """Check if the compose plugin is available for *runtime*."""
    try:
        result = subprocess.run(  # noqa: S603
            [runtime, "compose", "version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except subprocess.SubprocessError:
        return False
