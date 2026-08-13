"""
Heretek Swarm Infrastructure Module.

Provides foundational infrastructure for the swarm:
- A2A: Agent-to-Agent protocol for structured inter-agent communication
- NATS: Event mesh for pub/sub messaging
- OTel: OpenTelemetry for distributed tracing, metrics, and logging
- Health: Infrastructure service health checks
- Provisioner: Docker/Podman container provisioning
"""

import structlog

from heretek_swarm.infrastructure.a2a import (
    A2AMessage,
    A2AMessageType,
    A2AProtocol,
    AgentCapability,
    MessagePriority,
    create_consensus_message,
    create_delegation_message,
    create_task_request,
    create_task_response,
)
from heretek_swarm.infrastructure.health import (
    HealthCheckResult,
    check_all_infrastructure,
    check_infrastructure_health,
    check_mem0_health,
    check_nats_health,
    check_postgres_health,
    check_qdrant_health,
    check_redis_health,
)
from heretek_swarm.infrastructure.nats import (
    NATSClient,
    NATSPublisher,
    NATSSubscriber,
    get_nats_client,
)
from heretek_swarm.infrastructure.otel import (
    LoggingConfig,
    MetricsCollector,
    MetricsConfig,
    TracingConfig,
    create_span,
    get_log_config,
    get_meter,
    get_tracer,
    init_logging,
    init_metrics,
    init_tracing,
    record_metric,
    with_span,
)
from heretek_swarm.infrastructure.provisioner import (
    ConnectionStringResult,
    ContainerConfig,
    ContainerRuntime,
    detect_runtime,
    provision_all,
    provision_all_sync,
    provision_infrastructure,
    provision_infrastructure_sync,
    provision_service,
    provision_service_sync,
)

logger = structlog.get_logger(__name__)

__all__ = [
    # A2A Protocol
    "A2AMessage",
    "A2AMessageType",
    "A2AProtocol",
    "AgentCapability",
    "ConnectionStringResult",
    # Provisioner
    "ContainerConfig",
    "ContainerRuntime",
    # Health Checks
    "HealthCheckResult",
    "LoggingConfig",
    "MessagePriority",
    "MetricsCollector",
    "MetricsConfig",
    # NATS Event Mesh
    "NATSClient",
    "NATSPublisher",
    "NATSSubscriber",
    # OpenTelemetry
    "TracingConfig",
    "check_all_infrastructure",
    "check_infrastructure_health",
    "check_mem0_health",
    "check_nats_health",
    "check_postgres_health",
    "check_qdrant_health",
    "check_redis_health",
    "create_consensus_message",
    "create_delegation_message",
    "create_span",
    "create_task_request",
    "create_task_response",
    "detect_runtime",
    "get_log_config",
    "get_meter",
    "get_nats_client",
    "get_tracer",
    "init_logging",
    "init_metrics",
    "init_tracing",
    "provision_all",
    "provision_all_sync",
    "provision_infrastructure",
    "provision_infrastructure_sync",
    "provision_service",
    "provision_service_sync",
    "record_metric",
    "with_span",
]
