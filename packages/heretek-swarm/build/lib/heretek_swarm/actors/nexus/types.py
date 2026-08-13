"""
Nexus Types - Data structures for external integrations.

Re-exports types for backward compatibility when imported from nexus/__init__.py.

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import structlog


class ConnectionStatus(Enum):
    """Status of an external connection."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILED = "auth_failed"

class ProtocolType(Enum):
    """Supported external protocols."""

    REST = "rest"
    GRAPHQL = "graphql"
    WEBSOCKET = "websocket"
    GRPC = "grpc"
    WEBHOOK = "webhook"
    MQTT = "mqtt"

@dataclass
class ExternalConnection:
    """Configuration for an external service connection."""

    connection_id: str
    name: str
    protocol: ProtocolType
    base_url: str
    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    headers: dict[str, str] = field(default_factory=dict)
    auth_type: str | None = None  # bearer, basic, api_key, oauth2
    auth_config: dict[str, Any] = field(default_factory=dict)
    rate_limit: int | None = None  # requests per minute
    rate_limit_remaining: int = 0
    rate_limit_reset: datetime | None = None
    last_request: datetime | None = None
    total_requests: int = 0
    failed_requests: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "connection_id": self.connection_id,
            "name": self.name,
            "protocol": self.protocol.value,
            "base_url": self.base_url,
            "status": self.status.value,
            "auth_type": self.auth_type,
            "rate_limit": self.rate_limit,
            "rate_limit_remaining": self.rate_limit_remaining,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""

    webhook_id: str
    name: str
    path: str
    secret: str
    active: bool = True
    allowed_methods: list[str] = field(default_factory=lambda: ["POST"])
    allowed_ips: list[str] | None = None
    rate_limit: int | None = None  # requests per minute
    request_count: int = 0
    last_request: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "webhook_id": self.webhook_id,
            "name": self.name,
            "path": self.path,
            "active": self.active,
            "allowed_methods": self.allowed_methods,
            "request_count": self.request_count,
            "last_request": self.last_request.isoformat() if self.last_request else None,
            "created_at": self.created_at.isoformat(),
        }

@dataclass
class ApiResponse:
    """Standardized API response."""

    success: bool
    status_code: int
    data: Any
    headers: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "status_code": self.status_code,
            "data": self.data,
            "headers": self.headers,
            "error": self.error,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
        }

logger = structlog.get_logger(__name__)
