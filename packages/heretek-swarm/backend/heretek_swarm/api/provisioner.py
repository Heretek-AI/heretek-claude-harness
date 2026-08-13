"""
Provisioner API Endpoints

HTTP endpoints for provisioning infrastructure services (PostgreSQL, Redis, Qdrant, NATS)
via Docker/Podman containers.

Tenet #2: "Container-First (No SQLite for Core Services)"
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from heretek_swarm.config.models import (
    InfrastructureConfigCreate,
    InfrastructureConfigUpdate,
    InfrastructureService,
)
from heretek_swarm.config.service import get_config_service
from heretek_swarm.gateway.auth import verify_auth
from heretek_swarm.infrastructure.nats.publisher import (
    SwarmEvent,
    get_nats_publisher,
)
from heretek_swarm.infrastructure.provisioner import (
    ContainerRuntime,
    detect_runtime,
    provision_all,
)
from heretek_swarm.infrastructure.provisioner import (
    InfrastructureService as InfraService,
)

logger = structlog.get_logger("api.provisioner")

router = APIRouter(
    prefix="/api/wizard/provision",
    tags=["Provisioner"],
    dependencies=[Depends(verify_auth)],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class RuntimeChoice(StrEnum):
    """Container runtime choice."""

    AUTO = "auto"
    PODMAN = "podman"
    DOCKER = "docker"


class ProvisionRequest(BaseModel):
    """Request to provision infrastructure services."""

    services: list[str]  # e.g., ["postgres", "redis", "qdrant", "nats"]
    runtime: RuntimeChoice = RuntimeChoice.AUTO


class ProvisionResponse(BaseModel):
    """Response from provision operation."""

    status: str  # "provisioning" | "completed" | "failed"
    results: dict[str, Any]
    connection_strings: dict[str, str]
    errors: list[str]
    total_provisioned: int = 0
    total_failed: int = 0


class ServiceProgressEvent(BaseModel):
    """Progress event for a single service."""

    service: str
    status: str  # "pending" | "pulling" | "starting" | "healthy" | "failed"
    message: str | None = None
    error: str | None = None


# =============================================================================
# NATS Event Emission
# =============================================================================


async def _emit_progress_event(
    services: list[str],
    status: str,
    service: str | None = None,
    message: str | None = None,
    error: str | None = None,
) -> None:
    """
    Emit a provision.progress SwarmEvent to NATS.

    Args:
        services: List of all services being provisioned
        status: Overall status or service-specific status
        service: Specific service that changed status (if applicable)
        message: Human-readable message
        error: Error message if failed
    """
    try:
        publisher = await get_nats_publisher()

        event = SwarmEvent(
            event_type="provision.progress",
            source_agent="wizard",
            target_agent=None,
            payload={
                "services": services,
                "status": status,
                "service": service,
                "message": message,
                "error": error,
            },
        )

        await publisher.publish_event(event)
        logger.debug(
            "provision_progress_event_emitted",
            status=status,
            service=service,
        )

    except Exception as e:
        # Gracefully handle NATS unavailable - log but don't fail provisioning
        logger.warning(
            "provision_progress_event_failed",
            error=str(e),
            status=status,
            service=service,
        )


# =============================================================================
# Service Mapping
# =============================================================================


def _map_service_name(name: str) -> InfrastructureService:
    """Map string service name to InfrastructureService enum."""
    name_lower = name.lower().strip()
    mapping = {
        "postgres": InfrastructureService.POSTGRES,
        "postgresql": InfrastructureService.POSTGRES,
        "redis": InfrastructureService.REDIS,
        "qdrant": InfrastructureService.QDRANT,
        "qdrant_vector": InfrastructureService.QDRANT,
        "nats": InfrastructureService.NATS,
        "nats_server": InfrastructureService.NATS,
        "mem0": InfrastructureService.MEM0,
    }
    if name_lower not in mapping:
        raise ValueError(
            f"Unknown service: '{name}'. Valid services: postgres, redis, qdrant, nats"
        )
    return mapping[name_lower]


def _map_to_infra_service(service: InfrastructureService) -> InfraService:
    """Map config model service to provisioner service."""
    mapping = {
        InfrastructureService.POSTGRES: InfraService.POSTGRES,
        InfrastructureService.REDIS: InfraService.REDIS,
        InfrastructureService.QDRANT: InfraService.QDRANT,
        InfrastructureService.NATS: InfraService.NATS,
        InfrastructureService.MEM0: InfraService.MEM0,
    }
    return mapping[service]


# =============================================================================
# Provisioning Logic
# =============================================================================


async def _store_infrastructure_config(
    service: InfrastructureService,
    host: str,
    port: int,
    connection_url: str,
) -> None:
    """
    Store infrastructure configuration in the database.

    Args:
        service: Infrastructure service type
        host: Service host (usually localhost)
        port: Service port
        connection_url: Full connection string
    """
    try:
        config_service = get_config_service()

        # Check if config already exists for this service
        existing = await config_service.get_infrastructure_config_by_service(service.value)

        config_data = InfrastructureConfigCreate(
            service=service,
            host=host,
            port=port,
            connection_url=connection_url,
            is_enabled=True,
        )

        if existing:
            # Update existing config
            await config_service.update_infrastructure_config(
                existing.id,
                InfrastructureConfigUpdate(
                    host=host,
                    port=port,
                    connection_url=connection_url,
                    is_enabled=True,
                ),
            )
            logger.info(
                "infrastructure_config_updated",
                service=service.value,
                host=host,
                port=port,
            )
        else:
            # Create new config
            await config_service.create_infrastructure_config(config_data)
            logger.info(
                "infrastructure_config_created",
                service=service.value,
                host=host,
                port=port,
            )

    except Exception as e:
        # Log but don't fail provisioning - config storage is secondary
        logger.warning(
            "infrastructure_config_storage_failed",
            service=service.value,
            error=str(e),
        )


# =============================================================================
# API Endpoints
# =============================================================================


@router.post("")
async def provision_services(request: ProvisionRequest) -> ProvisionResponse:
    """
    Provision infrastructure services by starting Docker/Podman containers.

    This endpoint:
    1. Detects the available container runtime (Podman or Docker)
    2. Stops any existing heretek-* containers (idempotent)
    3. Starts containers for the requested services in parallel
    4. Polls health checks until all services are healthy (up to 60s timeout)
    5. Stores connection strings in the database via ConfigurationService
    6. Emits NATS progress events for real-time frontend updates

    Args:
        request: Provision request with services list and runtime preference

    Returns:
        ProvisionResponse with status, results, and connection strings
    """
    # Validate services
    if not request.services:
        raise HTTPException(400, "At least one service must be specified")

    # Map service names
    try:
        services = [_map_service_name(name) for name in request.services]
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    # Remove duplicates while preserving order
    seen: set[InfrastructureService] = set()
    unique_services: list[InfrastructureService] = []
    for svc in services:
        if svc not in seen:
            seen.add(svc)
            unique_services.append(svc)

    service_names = [s.value for s in unique_services]

    # Emit initial progress event
    await _emit_progress_event(
        services=service_names,
        status="pending",
        message="Starting provisioning...",
    )

    # Detect or validate runtime
    try:
        if request.runtime == RuntimeChoice.AUTO:
            runtime = detect_runtime()
        elif request.runtime == RuntimeChoice.PODMAN:
            runtime = ContainerRuntime.PODMAN
        else:
            runtime = ContainerRuntime.DOCKER

        logger.info(
            "provisioning_started",
            services=service_names,
            runtime=runtime.value,
        )

    except RuntimeError as e:
        logger.error("runtime_detection_failed", error=str(e))
        raise HTTPException(500, f"Container runtime not available: {e}") from e

    # Emit status for each pending service
    for svc in unique_services:
        await _emit_progress_event(
            services=service_names,
            status="pulling",
            service=svc.value,
            message=f"Pulling image for {svc.value}...",
        )

    # Map to provisioner services
    infra_services = [_map_to_infra_service(s) for s in unique_services]

    # Emit starting status for each service
    for svc in infra_services:
        await _emit_progress_event(
            services=service_names,
            status="starting",
            service=svc.value,
            message=f"Starting {svc.value} container...",
        )

    # Run provisioning
    try:
        results = await provision_all(infra_services)

        # Process results
        provision_results: dict[str, Any] = {}
        connection_strings: dict[str, str] = {}
        errors: list[str] = []
        total_provisioned = 0
        total_failed = 0

        for infra_svc, result in results.items():
            service_key = infra_svc.value

            if not result.success:
                error_msg = result.error or "Unknown error"
                errors.append(f"{service_key}: {error_msg}")
                provision_results[service_key] = {
                    "success": False,
                    "error": error_msg,
                    "latency_ms": result.latency_ms,
                }
                total_failed += 1

                # Emit failed event
                await _emit_progress_event(
                    services=service_names,
                    status="failed",
                    service=service_key,
                    error=error_msg,
                )

                # Skip storing config for failed services
                continue

            # Success - store connection string and config
            total_provisioned += 1
            connection_strings[service_key] = result.connection_string or ""
            provision_results[service_key] = {
                "success": True,
                "host": result.host,
                "port": result.port,
                "connection_string": result.connection_string,
                "latency_ms": result.latency_ms,
            }

            # Map back to config model service for storage
            config_service = None
            for cfg_svc in unique_services:
                if cfg_svc.value == service_key:
                    config_service = cfg_svc
                    break

            if config_service and result.connection_string:
                # Store in database asynchronously
                await _store_infrastructure_config(
                    service=config_service,
                    host=result.host,
                    port=result.port,
                    connection_url=result.connection_string,
                )

            # Emit healthy event
            await _emit_progress_event(
                services=service_names,
                status="healthy",
                service=service_key,
                message=f"{service_key} is healthy",
            )

        # Determine overall status
        if total_failed == 0:
            overall_status = "completed"
        elif total_provisioned == 0:
            overall_status = "failed"
        else:
            overall_status = "completed"  # Partial success still returns completed

        logger.info(
            "provisioning_completed",
            total=len(unique_services),
            provisioned=total_provisioned,
            failed=total_failed,
            status=overall_status,
        )

        return ProvisionResponse(
            status=overall_status,
            results=provision_results,
            connection_strings=connection_strings,
            errors=errors,
            total_provisioned=total_provisioned,
            total_failed=total_failed,
        )

    except Exception as e:
        logger.error("provisioning_failed", error=str(e))

        # Emit failed event for all services
        for svc in service_names:
            await _emit_progress_event(
                services=service_names,
                status="failed",
                service=svc,
                error=str(e),
            )

        raise HTTPException(500, f"Provisioning failed: {e}") from e


@router.get("/status")
async def get_provision_status() -> dict[str, Any]:
    """
    Get the current provisioning status of all infrastructure services.

    Returns:
        Status of all known infrastructure services
    """
    from heretek_swarm.infrastructure.provisioner import detect_runtime

    try:
        runtime = detect_runtime()
    except RuntimeError:
        return {
            "runtime": None,
            "services": {},
            "error": "No container runtime available",
        }

    # Check which heretek-* containers are running
    import subprocess

    try:
        result = subprocess.run(
            [runtime.value, "ps", "--filter", "name=heretek-", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        running_containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    except Exception:
        running_containers = []

    # Get stored infrastructure configs
    config_service = get_config_service()
    stored_configs = await config_service.list_infrastructure_configs(include_disabled=True)

    configs_by_service = {c.service: c for c in stored_configs}

    # Build status response
    services_status: dict[str, dict[str, Any]] = {}
    for service in InfrastructureService:
        service_key = service.value

        # Check if container is running
        container_name = f"heretek-{service_key}"
        is_running = container_name in running_containers

        # Check if we have a stored config
        config = configs_by_service.get(service)
        has_config = config is not None and config.connection_url is not None

        services_status[service_key] = {
            "container_running": is_running,
            "configured": has_config,
            "connection_url": config.connection_url if config else None,
            "health_status": config.health_status if config else "unknown",
        }

    return {
        "runtime": runtime.value,
        "services": services_status,
        "running_containers": running_containers,
    }


@router.post("/stop")
async def stop_infrastructure() -> dict[str, Any]:
    """
    Stop all heretek-* containers.

    Returns:
        Stop operation result
    """
    from heretek_swarm.infrastructure.provisioner import detect_runtime

    try:
        runtime = detect_runtime()
    except RuntimeError as e:
        raise HTTPException(500, f"No container runtime available: {e}") from e

    # Find all heretek-* containers
    import subprocess

    try:
        result = subprocess.run(
            [runtime.value, "ps", "--filter", "name=heretek-", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        containers = [c.strip() for c in result.stdout.strip().split("\n") if c.strip()]
    except Exception as e:
        raise HTTPException(500, f"Failed to list containers: {e}") from e

    if not containers:
        return {
            "success": True,
            "stopped": [],
            "message": "No heretek-* containers running",
        }

    # Stop each container
    stopped = []
    failed = []

    for container in containers:
        try:
            subprocess.run(
                [runtime.value, "stop", container],
                capture_output=True,
                timeout=30,
            )
            stopped.append(container)
            logger.info("container_stopped", container=container)
        except Exception as e:
            failed.append(container)
            logger.error("container_stop_failed", container=container, error=str(e))

    return {
        "success": len(failed) == 0,
        "stopped": stopped,
        "failed": failed,
        "message": f"Stopped {len(stopped)} containers"
        if failed
        else f"Stopped {len(stopped)} containers",
    }
