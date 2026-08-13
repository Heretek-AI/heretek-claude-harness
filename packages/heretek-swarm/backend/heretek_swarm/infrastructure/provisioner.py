"""
Docker/Podman Provisioner for Heretek Swarm.

Provides container provisioning for infrastructure services:
- PostgreSQL, Redis, Qdrant, NATS (mem0 is embedded in the API container)

Uses subprocess to invoke podman/docker CLI (same pattern as CLI, no new Docker SDK dependency).
Idempotent: stops any existing heretek-* containers before re-provisioning.
"""

from __future__ import annotations

import asyncio
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import structlog

from heretek_swarm.config.models import (
    HealthStatus,
    InfrastructureService,
)

logger = structlog.get_logger("infrastructure.provisioner")


class ContainerRuntime(StrEnum):
    """Supported container runtimes."""

    PODMAN = "podman"
    DOCKER = "docker"


@dataclass
class ContainerConfig:
    """Configuration for a container to be provisioned."""

    service: InfrastructureService
    image: str
    ports: dict[str, str] = field(default_factory=dict)  # host_port: container_port
    env_vars: dict[str, str] = field(default_factory=dict)
    container_name: str | None = None
    health_check_port: int | None = None
    health_check_timeout: float = 5.0

    def __post_init__(self) -> None:
        if self.container_name is None:
            self.container_name = f"heretek-{self.service.value}"


@dataclass
class ConnectionStringResult:
    """Result of provisioning a single service."""

    service: InfrastructureService
    success: bool
    connection_string: str | None = None
    host: str = "localhost"
    port: int = 0
    error: str | None = None
    latency_ms: float = 0.0


# Default container images
DEFAULT_IMAGES: dict[InfrastructureService, str] = {
    InfrastructureService.POSTGRES: "docker.io/postgres:16-alpine",
    InfrastructureService.REDIS: "docker.io/redis:7-alpine",
    InfrastructureService.QDRANT: "docker.io/qdrant/qdrant:v1.7.4",
    InfrastructureService.NATS: "docker.io/nats:2.10-alpine",
}

# Default ports
DEFAULT_PORTS: dict[InfrastructureService, int] = {
    InfrastructureService.POSTGRES: 5432,
    InfrastructureService.REDIS: 6379,
    InfrastructureService.QDRANT: 6333,
    InfrastructureService.NATS: 4222,
}


def detect_runtime() -> ContainerRuntime:
    """
    Detect available container runtime.

    Checks podman first, falls back to docker.

    Returns:
        ContainerRuntime enum value

    Raises:
        RuntimeError: If neither podman nor docker is available
    """
    # Check podman first
    if shutil.which("podman") is not None:
        logger.info("container_runtime_detected", runtime="podman")
        return ContainerRuntime.PODMAN

    # Fall back to docker
    if shutil.which("docker") is not None:
        logger.info("container_runtime_detected", runtime="docker")
        return ContainerRuntime.DOCKER

    error = "Neither podman nor docker is available. Please install one of them."
    logger.error("container_runtime_not_found", error=error)
    raise RuntimeError(error)


def pull_image(runtime: ContainerRuntime, image: str) -> bool:
    """
    Pull a container image.

    Args:
        runtime: Container runtime to use
        image: Image name to pull

    Returns:
        True if pull succeeded, False otherwise
    """
    cmd = [runtime.value, "pull", image]
    logger.info("pulling_image", runtime=runtime.value, image=image)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for image pulls
        )

        if result.returncode == 0:
            logger.info("image_pulled", runtime=runtime.value, image=image)
            return True
        logger.error(
            "image_pull_failed",
            runtime=runtime.value,
            image=image,
            stderr=result.stderr,
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error("image_pull_timeout", runtime=runtime.value, image=image)
        return False
    except Exception as e:
        logger.error("image_pull_error", runtime=runtime.value, image=image, error=str(e))
        return False


def stop_container(runtime: ContainerRuntime, name: str) -> None:
    """
    Stop a container by name (idempotent).

    Errors are ignored - this is intended to be safe to call even if
    the container doesn't exist.

    Args:
        runtime: Container runtime to use
        name: Container name to stop
    """
    cmd = [runtime.value, "stop", name]
    logger.debug("stopping_container", runtime=runtime.value, container=name)

    try:
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        logger.debug("container_stopped", container=name)
    except subprocess.TimeoutExpired:
        # Force kill if stop times out
        try:
            subprocess.run(
                [runtime.value, "kill", name],
                capture_output=True,
                timeout=10,
            )
            logger.warning("container_force_killed", container=name)
        except Exception:
            logger.debug("container_cleanup_error", exc_info=True)
            # Intentionally ignored - idempotent operation
    except Exception as e:
        # Ignore all errors - idempotent operation
        logger.debug("container_stop_ignored", container=name, error=str(e))


def start_container(runtime: ContainerRuntime, config: ContainerConfig) -> bool:
    """
    Start a container with the given configuration.

    Args:
        runtime: Container runtime to use
        config: Container configuration

    Returns:
        True if container started successfully, False otherwise
    """
    container_name = config.container_name
    assert container_name is not None, "Container name should be set in __post_init__"

    # Build the run command
    cmd: list[str] = [
        runtime.value,
        "run",
        "--detach",
        "--name",
        container_name,
        "--rm",  # Auto-remove when stopped
    ]

    # Add port mappings
    for host_port, container_port in config.ports.items():
        cmd.extend(["--publish", f"{host_port}:{container_port}"])

    # Add environment variables
    for key, value in config.env_vars.items():
        cmd.extend(["--env", f"{key}={value}"])

    # Add the image
    cmd.append(config.image)

    logger.info(
        "starting_container",
        runtime=runtime.value,
        container=container_name,
        image=config.image,
        ports=config.ports,
    )

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            container_id = result.stdout.strip()[:12]  # Short ID
            logger.info(
                "container_started",
                container=container_name,
                container_id=container_id,
            )
            return True
        logger.error(
            "container_start_failed",
            container=container_name,
            stderr=result.stderr,
            stdout=result.stdout,
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error("container_start_timeout", container=container_name)
        return False
    except Exception as e:
        logger.error("container_start_error", container=container_name, error=str(e))
        return False


async def wait_for_health(
    service: InfrastructureService,
    host: str,
    port: int,
    timeout: float = 60.0,
    poll_interval: float = 2.0,
) -> tuple[bool, float]:
    """
    Wait for a service to become healthy by polling health checks.

    Args:
        service: Infrastructure service type
        host: Service host
        port: Service port
        timeout: Maximum time to wait in seconds
        poll_interval: Time between health checks in seconds

    Returns:
        Tuple of (is_healthy, latency_ms)
    """
    from heretek_swarm.infrastructure.health import check_infrastructure_health

    start_time = time.monotonic()
    deadline = start_time + timeout

    logger.info(
        "health_check_start",
        service=service.value,
        host=host,
        port=port,
        timeout=timeout,
    )

    while time.monotonic() < deadline:
        elapsed = time.monotonic() - start_time

        result = await check_infrastructure_health(
            service=service,
            host=host,
            port=port,
            timeout=5.0,
        )

        if result.status == HealthStatus.HEALTHY:
            latency_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "health_check_passed",
                service=service.value,
                host=host,
                port=port,
                elapsed_ms=round(latency_ms, 2),
            )
            return True, latency_ms

        # Log progress periodically (every 10 seconds of elapsed time)
        if int(elapsed) % 10 == 0 and elapsed > 0:
            logger.debug(
                "health_check_polling",
                service=service.value,
                elapsed_ms=round(elapsed * 1000, 2),
                last_status=result.status.value,
            )

        # Wait before next check
        await asyncio.sleep(min(poll_interval, deadline - time.monotonic()))

    # Timeout reached
    final_elapsed = time.monotonic() - start_time
    logger.warning(
        "health_check_timeout",
        service=service.value,
        host=host,
        port=port,
        timeout=timeout,
        elapsed_ms=round(final_elapsed * 1000, 2),
    )
    return False, final_elapsed * 1000


def generate_postgres_connection_string(
    host: str,
    port: int,
    password: str,
    user: str = "postgres",
    database: str = "postgres",
) -> str:
    """Generate PostgreSQL connection string."""
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def generate_redis_connection_string(
    host: str,
    port: int,
    password: str | None = None,
) -> str:
    """Generate Redis connection string."""
    if password:
        return f"redis://:{password}@{host}:{port}"
    return f"redis://{host}:{port}"


def generate_qdrant_connection_string(
    host: str,
    port: int,
) -> str:
    """Generate Qdrant connection string."""
    return f"http://{host}:{port}"


def generate_nats_connection_string(
    host: str,
    port: int,
) -> str:
    """Generate NATS connection string."""
    return f"nats://{host}:{port}"


def generate_connection_string(
    service: InfrastructureService,
    host: str,
    port: int,
    password: str | None = None,
    user: str = "postgres",
    database: str = "postgres",
) -> str | None:
    """
    Generate connection string for a service.

    Args:
        service: Infrastructure service type
        host: Service host
        port: Service port
        password: Optional password (for postgres/redis)
        user: Database user (for postgres)
        database: Database name (for postgres)

    Returns:
        Connection string or None if service not supported
    """
    generators = {
        InfrastructureService.POSTGRES: lambda: generate_postgres_connection_string(
            host, port, password or "", user, database
        ),
        InfrastructureService.REDIS: lambda: generate_redis_connection_string(host, port, password),
        InfrastructureService.QDRANT: lambda: generate_qdrant_connection_string(host, port),
        InfrastructureService.NATS: lambda: generate_nats_connection_string(host, port),
    }

    generator = generators.get(service)
    if generator:
        return generator()

    logger.warning("unsupported_service_for_connection_string", service=service.value)
    return None


async def provision_service(
    service: InfrastructureService,
    runtime: ContainerRuntime,
    runtime_config: dict[str, Any] | None = None,
) -> ConnectionStringResult:
    """
    Provision a single infrastructure service.

    This function:
    1. Stops any existing container with the same name (idempotent)
    2. Pulls the container image
    3. Starts the container with appropriate configuration
    4. Waits for the service to become healthy
    5. Generates and returns the connection string

    Args:
        service: Infrastructure service to provision
        runtime: Container runtime to use
        runtime_config: Optional runtime-specific configuration overrides

    Returns:
        ConnectionStringResult with success status and connection details
    """
    runtime_config = runtime_config or {}
    start_time = time.monotonic()

    # Skip mem0 — embedded in the API container, no standalone container needed
    if service == InfrastructureService.MEM0:
        logger.info("mem0_is_embedded_service")
        return ConnectionStringResult(
            service=service,
            success=True,
            error="mem0 is embedded in the API container — no standalone container needed",
        )

    logger.info("provisioning_service", service=service.value, runtime=runtime.value)

    # Get image and default configuration
    image = runtime_config.get("image", DEFAULT_IMAGES.get(service))
    if not image:
        return ConnectionStringResult(
            service=service,
            success=False,
            error=f"No image configured for service: {service.value}",
        )

    port = runtime_config.get("port", DEFAULT_PORTS.get(service, 0))
    container_name = f"heretek-{service.value}"

    # Build environment variables based on service
    env_vars: dict[str, str] = {}
    password: str | None = None

    if service == InfrastructureService.POSTGRES:
        # Generate random password for postgres (~16 chars)
        password = secrets.token_urlsafe(12)
        env_vars = {
            "POSTGRES_USER": "postgres",
            "POSTGRES_PASSWORD": password,
            "POSTGRES_DB": "postgres",
        }
    elif service == InfrastructureService.REDIS:
        # Optional redis password
        if runtime_config.get("require_auth", False):
            password = secrets.token_urlsafe(12)
            env_vars["REDIS_PASSWORD"] = password
    elif service == InfrastructureService.NATS:
        # NATS user authentication (optional)
        if runtime_config.get("require_auth", False):
            nats_user = runtime_config.get("nats_user", "admin")
            nats_pass = secrets.token_urlsafe(12)
            env_vars["NATS_USER"] = nats_user
            env_vars["NATS_PASSWORD"] = nats_pass

    # Create container config
    container_config = ContainerConfig(
        service=service,
        image=image,
        ports={str(port): str(port)},
        env_vars=env_vars,
        container_name=container_name,
        health_check_port=port,
    )

    # Step 1: Stop any existing container (idempotent)
    stop_container(runtime, container_name)

    # Step 2: Pull the image
    if not pull_image(runtime, image):
        latency_ms = (time.monotonic() - start_time) * 1000
        return ConnectionStringResult(
            service=service,
            success=False,
            error=f"Failed to pull image: {image}",
            latency_ms=latency_ms,
        )

    # Step 3: Start the container
    if not start_container(runtime, container_config):
        latency_ms = (time.monotonic() - start_time) * 1000
        return ConnectionStringResult(
            service=service,
            success=False,
            error=f"Failed to start container: {container_name}",
            latency_ms=latency_ms,
        )

    # Step 4: Wait for health
    # Give the container a moment to initialize
    await asyncio.sleep(2)

    is_healthy, health_latency_ms = await wait_for_health(
        service=service,
        host="localhost",
        port=port,
        timeout=runtime_config.get("health_timeout", 60.0),
    )

    total_latency_ms = (time.monotonic() - start_time) * 1000

    if not is_healthy:
        return ConnectionStringResult(
            service=service,
            success=False,
            host="localhost",
            port=port,
            error="Service did not become healthy within timeout",
            latency_ms=total_latency_ms,
        )

    # Step 5: Generate connection string
    connection_string = generate_connection_string(
        service=service,
        host="localhost",
        port=port,
        password=password,
    )

    logger.info(
        "service_provisioned",
        service=service.value,
        connection_string=connection_string,
        health_latency_ms=health_latency_ms,
        total_latency_ms=round(total_latency_ms, 2),
    )

    return ConnectionStringResult(
        service=service,
        success=True,
        connection_string=connection_string,
        host="localhost",
        port=port,
        latency_ms=total_latency_ms,
    )


async def provision_all(
    services: list[InfrastructureService],
    runtime_config: dict[str, Any] | None = None,
) -> dict[InfrastructureService, ConnectionStringResult]:
    """
    Provision all specified infrastructure services.

    Args:
        services: List of services to provision
        runtime_config: Optional configuration overrides

    Returns:
        Dictionary mapping each service to its provisioning result
    """
    runtime_config = runtime_config or {}

    # Detect runtime once for all services
    try:
        runtime = detect_runtime()
    except RuntimeError as e:
        logger.error("runtime_detection_failed", error=str(e))
        return {
            service: ConnectionStringResult(
                service=service,
                success=False,
                error=str(e),
            )
            for service in services
        }

    logger.info(
        "provisioning_all_services",
        services=[s.value for s in services],
        runtime=runtime.value,
    )

    # Provision each service
    results: dict[InfrastructureService, ConnectionStringResult] = {}

    for service in services:
        # Skip mem0 — embedded in the API container
        if service == InfrastructureService.MEM0:
            logger.info("mem0_is_embedded_service")
            results[service] = ConnectionStringResult(
                service=service,
                success=True,
                error="mem0 is embedded in the API container — no standalone container needed",
            )
            continue

        result = await provision_service(service, runtime, runtime_config)
        results[service] = result

        # If this service failed, log but continue with others
        if not result.success:
            logger.warning(
                "service_provisioning_failed",
                service=service.value,
                error=result.error,
            )

    # Summary
    successful = sum(1 for r in results.values() if r.success)
    logger.info(
        "provisioning_complete",
        total=len(services),
        successful=successful,
        failed=len(services) - successful,
    )

    return results


async def provision_infrastructure(
    postgres: bool = True,
    redis: bool = True,
    qdrant: bool = True,
    nats: bool = True,
    mem0: bool = False,  # mem0 is embedded in API container — no standalone provisioning needed
    runtime_config: dict[str, Any] | None = None,
) -> dict[InfrastructureService, ConnectionStringResult]:
    """
    Convenience function to provision infrastructure services.

    Args:
        postgres: Provision PostgreSQL
        redis: Provision Redis
        qdrant: Provision Qdrant
        nats: Provision NATS
        mem0: Provision Mem0 (default False — mem0 is embedded, no standalone container)
        runtime_config: Optional configuration overrides

    Returns:
        Dictionary mapping each service to its provisioning result
    """
    services: list[InfrastructureService] = []

    if postgres:
        services.append(InfrastructureService.POSTGRES)
    if redis:
        services.append(InfrastructureService.REDIS)
    if qdrant:
        services.append(InfrastructureService.QDRANT)
    if nats:
        services.append(InfrastructureService.NATS)
    if mem0:
        services.append(InfrastructureService.MEM0)

    return await provision_all(services, runtime_config)


# Synchronous wrappers for non-async contexts


def provision_service_sync(
    service: InfrastructureService,
    runtime_config: dict[str, Any] | None = None,
) -> ConnectionStringResult:
    """Synchronous wrapper for provision_service."""
    try:
        runtime = detect_runtime()
    except RuntimeError as e:
        return ConnectionStringResult(
            service=service,
            success=False,
            error=str(e),
        )

    return asyncio.run(provision_service(service, runtime, runtime_config))


def provision_all_sync(
    services: list[InfrastructureService],
    runtime_config: dict[str, Any] | None = None,
) -> dict[InfrastructureService, ConnectionStringResult]:
    """Synchronous wrapper for provision_all."""
    return asyncio.run(provision_all(services, runtime_config))


def provision_infrastructure_sync(
    postgres: bool = True,
    redis: bool = True,
    qdrant: bool = True,
    nats: bool = True,
    mem0: bool = False,
    runtime_config: dict[str, Any] | None = None,
) -> dict[InfrastructureService, ConnectionStringResult]:
    """Synchronous wrapper for provision_infrastructure."""
    return asyncio.run(
        provision_infrastructure(
            postgres=postgres,
            redis=redis,
            qdrant=qdrant,
            nats=nats,
            mem0=mem0,
            runtime_config=runtime_config,
        )
    )
