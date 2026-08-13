"""
Nexus Agent - External Integration Specialist.

Tier 5 Coordination Agent responsible for:
- External API connections and integrations
- Protocol translation between internal and external systems
- Webhook management and event ingestion
- Third-party service orchestration
- API rate limiting and quota management

Author: Heretek Swarm Collective
Date: 2026-04-06
Version: 1.0.0
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import uuid
from typing import TYPE_CHECKING, Any

import aiohttp
import structlog

from heretek_swarm.actors.base import ActorMessage, AgentActor
from heretek_swarm.actors.mixins.deliberation import DeliberationMixin
from heretek_swarm.actors.mixins.health_reporting import HealthReportingMixin
from heretek_swarm.actors.mixins.learning import LearningMixin
from heretek_swarm.actors.mixins.memory import MemoryMixin
from heretek_swarm.actors.mixins.pattern import PatternMixin
from heretek_swarm.actors.mixins.validation import ValidationMixin
from heretek_swarm.actors.nexus.routing import NexusRoutingHelpers
from heretek_swarm.actors.nexus.types import (
    ApiResponse,
    ConnectionStatus,
    ExternalConnection,
    ProtocolType,
    WebhookConfig,
)
from heretek_swarm.actors.validation import validate_message

# INTG-02: External API Resilience
from heretek_swarm.gateway.external_api import (
    APIRequestMetrics,
    CircuitBreakerConfig,
    CircuitState,
    FallbackConfig,
    RateLimitConfig,
    ResilientAPIClient,
    RetryConfig,
    RetryStrategy,
)
from heretek_swarm_core.validation import LLMOutputValidator

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


class NexusAgent(
    HealthReportingMixin,
    ValidationMixin,
    AgentActor,
    PatternMixin,
    DeliberationMixin,
    MemoryMixin,
    LearningMixin,
    NexusRoutingHelpers,
):
    """
    External Integration Specialist.

    Responsibilities:
    - Manage external API connections
    - Handle webhook registrations and validations
    - Translate between internal and external protocols
    - Enforce rate limits and quotas
    - Provide unified API interface for all external integrations

    Message Handlers:
    - create_connection: Create new external connection
    - update_connection: Update connection configuration
    - delete_connection: Remove external connection
    - get_connection_status: Get status of a connection
    - execute_request: Execute HTTP request through connection
    - register_webhook: Register webhook endpoint
    - unregister_webhook: Remove webhook registration
    - validate_webhook: Validate webhook signature
    - get_webhook_status: Get webhook statistics
    - translate_protocol: Translate between protocols
    - get_integration_report: Generate integration status report
    """

    def __init__(
        self,
        agent_id: str | None = None,
        config: dict[str, Any] | None = None,
    ):
        super().__init__(
            agent_id=agent_id or f"nexus_{uuid.uuid4().hex[:8]}",
            config=config or {},
        )

        # Initialize routing helpers
        NexusRoutingHelpers.__init__(self)

        self._config: dict[str, Any] = config or {}

        # Connection management
        self._connections: dict[str, ExternalConnection] = {}
        self._max_connections: int = self._config.get("max_connections", 50)

        # Webhook management
        self._webhooks: dict[str, WebhookConfig] = {}
        self._webhook_handlers: dict[str, Callable] = {}
        self._max_webhooks: int = self._config.get("max_webhooks", 100)

        # HTTP session
        self._session: aiohttp.ClientSession | None = None

        # Request tracking
        self._request_log: list[dict[str, Any]] = []
        self._max_log_entries: int = self._config.get("max_request_log", 1000)

        # LLM Output Validation
        self.llm_output_validator = LLMOutputValidator(strict_mode=True)

        # ZERO-01: Hostile Input Treatment configuration
        self._max_payload_size: int = self._config.get("max_payload_size", 1024 * 1024)  # 1MB default
        self._rate_limit_window: int = self._config.get("rate_limit_window", 60)  # seconds
        self._rate_limit_max: int = self._config.get("rate_limit_max", 100)  # requests per window

        # INTG-02: External API Resilience
        self._api_client: ResilientAPIClient | None = None
        self._retry_config = RetryConfig(
            max_retries=3,
            initial_delay_ms=100,
            max_delay_ms=30000,
        )
        self._rate_limit_config = RateLimitConfig(
            requests_per_minute=60,
            auto_backoff=True,
        )
        self._circuit_breaker_config = CircuitBreakerConfig(
            failure_threshold=5,
            timeout_seconds=30.0,
        )
        self._fallback_config = FallbackConfig(enabled=False)
        self._api_metrics: list[APIRequestMetrics] = []
        self._max_metrics_entries: int = 1000

        logger.info(
            "nexus_initialized",
            agent_id=self.agent_id,
            max_connections=self._max_connections,
            max_webhooks=self._max_webhooks,
            zero_trust_enabled=True,
            max_payload_size=self._max_payload_size,
            rate_limit=f"{self._rate_limit_max}/{self._rate_limit_window}s",
        )

    async def initialize(self) -> None:
        """Initialize the Nexus agent with resilience support."""
        await super().initialize()
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self._config.get("timeout", 30)),
        )
        self._api_client = ResilientAPIClient(
            session=self._session,
            retry_config=self._retry_config,
            rate_limit_config=self._rate_limit_config,
            circuit_breaker_config=self._circuit_breaker_config,
            fallback_config=self._fallback_config,
            timeout_seconds=self._config.get("timeout", 30),
            zero_trust_enabled=True,
        )
        self._register_handlers()
        logger.info(
            "nexus_http_session_initialized",
            retry=self._retry_config.max_retries,
            rate_limit=self._rate_limit_config.requests_per_minute,
            circuit_breaker_threshold=self._circuit_breaker_config.failure_threshold,
        )

    def _register_handlers(self) -> None:
        """Register INTG-02 resilience message handlers."""
        self._message_handlers = {
            "health_check": self._handle_health_check,
            "create_connection": self._handle_create_connection,
            "update_connection": self._handle_update_connection,
            "delete_connection": self._handle_delete_connection,
            "get_connection_status": self._handle_get_connection_status,
            "execute_request": self._handle_execute_request,
            "register_webhook": self._handle_register_webhook,
            "unregister_webhook": self._handle_unregister_webhook,
            "validate_webhook": self._handle_validate_webhook,
            "get_webhook_status": self._handle_get_webhook_status,
            "translate_protocol": self._handle_translate_protocol,
            "get_integration_report": self._handle_get_integration_report,
            "get_api_metrics": self._handle_get_api_metrics,
            "configure_retry": self._handle_configure_retry,
            "configure_rate_limit": self._handle_configure_rate_limit,
            "configure_circuit_breaker": self._handle_configure_circuit_breaker,
            "add_fallback_endpoint": self._handle_add_fallback_endpoint,
            "get_resilience_status": self._handle_get_resilience_status,
            "reset_circuit_breaker": self._handle_reset_circuit_breaker,
        }

    async def terminate(self) -> None:
        """Terminate the Nexus agent."""
        if self._session:
            await self._session.close()
            self._session = None
            logger.info("nexus_http_session_closed")
        await super().terminate()

    async def _validate_message(self, message: ActorMessage) -> dict[str, Any]:
        """Validate incoming message content using ZERO-01 hostile input treatment."""
        try:
            # ZERO-01: Apply hostile input sanitization before validation
            sanitized_content = await self._sanitize_input(message.content, message.sender)
            if sanitized_content is None:
                raise ValueError(f"Input rejected by sanitization from sender: {message.sender}")
            message.content = sanitized_content

            validated = validate_message(message.message_type, message.content)
            if hasattr(validated, "dict"):
                return validated.dict()
            return validated
        except ValueError:
            raise  # Re-raise validation rejections
        except Exception as e:
            logger.warning("nexus_message_validation_failed", error=str(e))
            raise ValueError(f"Message validation failed: {e}") from e

    # =========================================================================
    # Connection Management Handlers
    # =========================================================================

    async def _handle_create_connection(self, message: ActorMessage) -> None:
        """
        Create a new external connection.

        Content:
        - connection_id: Optional[str]
        - name: str
        - protocol: str (rest|graphql|websocket|grpc|webhook|mqtt)
        - base_url: str
        - headers: Optional[Dict]
        - auth_type: Optional[str] (bearer|basic|api_key|oauth2)
        - auth_config: Optional[Dict]
        - rate_limit: Optional[int]
        - metadata: Optional[Dict]
        """
        try:
            content = await self._validate_message(message)

            if len(self._connections) >= self._max_connections:
                await self._send_error(
                    message.sender_id,
                    f"Connection limit reached ({self._max_connections})",
                    message.message_type,
                )
                return

            connection_id = content.get("connection_id") or f"conn_{uuid.uuid4().hex[:12]}"

            if connection_id in self._connections:
                await self._send_error(
                    message.sender_id,
                    f"Connection {connection_id} already exists",
                    message.message_type,
                )
                return

            protocol = ProtocolType(content.get("protocol", "rest"))
            connection = ExternalConnection(
                connection_id=connection_id,
                name=content.get("name", "Unnamed"),
                protocol=protocol,
                base_url=content.get("base_url", ""),
                headers=content.get("headers", {}),
                auth_type=content.get("auth_type"),
                auth_config=content.get("auth_config", {}),
                rate_limit=content.get("rate_limit"),
                rate_limit_remaining=content.get("rate_limit", 100),
                metadata=content.get("metadata", {}),
            )

            self._connections[connection_id] = connection

            logger.info(
                "connection_created",
                connection_id=connection_id,
                name=connection.name,
                protocol=protocol.value,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="connection_created",
                    content={"connection": connection.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("create_connection_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to create connection: {e!s}",
                message.message_type,
            )

    async def _handle_update_connection(self, message: ActorMessage) -> None:
        """
        Update an existing connection.

        Content:
        - connection_id: str
        - updates: Dict (fields to update)
        """
        try:
            content = await self._validate_message(message)
            connection_id = content.get("connection_id")

            if not connection_id or connection_id not in self._connections:
                await self._send_error(
                    message.sender_id,
                    f"Connection {connection_id} not found",
                    message.message_type,
                )
                return

            connection = self._connections[connection_id]
            updates = content.get("updates", {})

            for key, value in updates.items():
                if hasattr(connection, key):
                    setattr(connection, key, value)

            logger.info(
                "connection_updated",
                connection_id=connection_id,
                updates=list(updates.keys()),
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="connection_updated",
                    content={"connection": connection.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("update_connection_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to update connection: {e!s}",
                message.message_type,
            )

    async def _handle_delete_connection(self, message: ActorMessage) -> None:
        """
        Delete a connection.

        Content:
        - connection_id: str
        """
        try:
            content = await self._validate_message(message)
            connection_id = content.get("connection_id")

            if not connection_id or connection_id not in self._connections:
                await self._send_error(
                    message.sender_id,
                    f"Connection {connection_id} not found",
                    message.message_type,
                )
                return

            del self._connections[connection_id]

            logger.info(
                "connection_deleted",
                connection_id=connection_id,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="connection_deleted",
                    content={"connection_id": connection_id},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("delete_connection_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to delete connection: {e!s}",
                message.message_type,
            )

    async def _handle_get_connection_status(self, message: ActorMessage) -> None:
        """
        Get status of a connection.

        Content:
        - connection_id: str (optional, returns all if not provided)
        """
        try:
            content = await self._validate_message(message)
            connection_id = content.get("connection_id")

            if connection_id:
                if connection_id not in self._connections:
                    await self._send_error(
                        message.sender_id,
                        f"Connection {connection_id} not found",
                        message.message_type,
                    )
                    return
                connections = [self._connections[connection_id].to_dict()]
            else:
                connections = [conn.to_dict() for conn in self._connections.values()]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="connection_status",
                    content={"connections": connections},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_connection_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get connection status: {e!s}",
                message.message_type,
            )

    # =========================================================================
    # Request Execution
    # =========================================================================

    async def _handle_execute_request(self, message: ActorMessage) -> None:
        """
        Execute an HTTP request through a connection.

        Content:
        - connection_id: str
        - method: str (GET|POST|PUT|DELETE|PATCH)
        - path: str
        - body: Optional[Any]
        - headers: Optional[Dict]
        - params: Optional[Dict]
        """
        connection_id = None
        try:
            content = await self._validate_message(message)
            connection_id = content.get("connection_id")

            if not connection_id or connection_id not in self._connections:
                await self._send_error(
                    message.sender_id,
                    f"Connection {connection_id} not found",
                    message.message_type,
                )
                return

            connection = self._connections[connection_id]

            # Check rate limit
            if connection.rate_limit and connection.rate_limit_remaining <= 0:
                connection.status = ConnectionStatus.RATE_LIMITED
                await self._send_error(
                    message.sender_id,
                    "Rate limit exceeded",
                    message.message_type,
                )
                return

            if not self._session:
                await self._send_error(
                    message.sender_id,
                    "HTTP session not initialized",
                    message.message_type,
                )
                return

            # Build URL
            url = f"{connection.base_url}{content.get('path', '')}"

            # Prepare headers
            headers = {**connection.headers, **(content.get("headers", {}))}

            # Add auth if configured
            if connection.auth_type == "bearer" and connection.auth_config.get("token"):
                headers["Authorization"] = f"Bearer {connection.auth_config['token']}"
            elif connection.auth_type == "basic":
                creds = f"{connection.auth_config.get('username', '')}:{connection.auth_config.get('password', '')}"
                headers["Authorization"] = f"Basic {base64.b64encode(creds.encode()).decode()}"
            elif connection.auth_type == "api_key":
                headers[connection.auth_config.get("header", "X-API-Key")] = connection.auth_config.get("key", "")

            # Execute request
            start_time = datetime.now(UTC)
            method = content.get("method", "GET").upper()

            async with self._session.request(
                method,
                url,
                headers=headers,
                json=content.get("body"),
                params=content.get("params"),
            ) as response:
                latency = (datetime.now(UTC) - start_time).total_seconds() * 1000

                try:
                    data = await response.json()
                except Exception as e:
                    logger.debug("nexus_response_parse_failed", error=str(e))
                    data = await response.text()

                # Update connection stats
                connection.last_request = datetime.now(UTC)
                connection.total_requests += 1
                connection.rate_limit_remaining = max(0, connection.rate_limit_remaining - 1)

                if response.status >= 400:
                    connection.failed_requests += 1
                    connection.status = ConnectionStatus.ERROR

                api_response = ApiResponse(
                    success=200 <= response.status < 300,
                    status_code=response.status,
                    data=data,
                    headers=dict(response.headers),
                    latency_ms=int(latency),
                )

                # Log request
                self._log_request(connection_id, method, url, response.status, latency)

                await self.send(
                    message.sender_id,
                    ActorMessage(
                        message_type="request_completed",
                        content={"response": api_response.to_dict()},
                        sender_id=self.agent_id,
                    ),
                )

        except Exception as e:
            logger.error("execute_request_failed", error=str(e))
            if connection_id in self._connections:
                self._connections[connection_id].failed_requests += 1
                self._connections[connection_id].status = ConnectionStatus.ERROR
            await self._send_error(
                message.sender_id,
                f"Request failed: {e!s}",
                message.message_type,
            )

    # =========================================================================
    # Webhook Management
    # =========================================================================

    async def _handle_register_webhook(self, message: ActorMessage) -> None:
        """
        Register a webhook endpoint.

        Content:
        - webhook_id: Optional[str]
        - name: str
        - path: str
        - secret: str
        - allowed_methods: Optional[List[str]]
        - allowed_ips: Optional[List[str]]
        - rate_limit: Optional[int]
        """
        try:
            content = await self._validate_message(message)

            if len(self._webhooks) >= self._max_webhooks:
                await self._send_error(
                    message.sender_id,
                    f"Webhook limit reached ({self._max_webhooks})",
                    message.message_type,
                )
                return

            webhook_id = content.get("webhook_id") or f"webhook_{uuid.uuid4().hex[:12]}"

            webhook = WebhookConfig(
                webhook_id=webhook_id,
                name=content.get("name", "Unnamed"),
                path=content.get("path", f"/webhook/{webhook_id}"),
                secret=content.get("secret", str(uuid.uuid4())),
                allowed_methods=content.get("allowed_methods", ["POST"]),
                allowed_ips=content.get("allowed_ips"),
                rate_limit=content.get("rate_limit"),
            )

            self._webhooks[webhook_id] = webhook

            logger.info(
                "webhook_registered",
                webhook_id=webhook_id,
                path=webhook.path,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="webhook_registered",
                    content={"webhook": webhook.to_dict()},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("register_webhook_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to register webhook: {e!s}",
                message.message_type,
            )

    async def _handle_unregister_webhook(self, message: ActorMessage) -> None:
        """
        Unregister a webhook.

        Content:
        - webhook_id: str
        """
        try:
            content = await self._validate_message(message)
            webhook_id = content.get("webhook_id")

            if not webhook_id or webhook_id not in self._webhooks:
                await self._send_error(
                    message.sender_id,
                    f"Webhook {webhook_id} not found",
                    message.message_type,
                )
                return

            del self._webhooks[webhook_id]

            logger.info(
                "webhook_unregistered",
                webhook_id=webhook_id,
            )

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="webhook_unregistered",
                    content={"webhook_id": webhook_id},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("unregister_webhook_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to unregister webhook: {e!s}",
                message.message_type,
            )

    async def _handle_validate_webhook(self, message: ActorMessage) -> None:
        """
        Validate webhook signature.

        Content:
        - webhook_id: str
        - payload: Any
        - signature: str
        - timestamp: Optional[int]
        """
        try:
            content = await self._validate_message(message)
            webhook_id = content.get("webhook_id")

            if not webhook_id or webhook_id not in self._webhooks:
                await self._send_error(
                    message.sender_id,
                    f"Webhook {webhook_id} not found",
                    message.message_type,
                )
                return

            webhook = self._webhooks[webhook_id]
            payload = content.get("payload")
            signature = content.get("signature")
            timestamp = content.get("timestamp")

            # Validate timestamp (prevent replay attacks)
            if timestamp:
                now = int(datetime.now(UTC).timestamp())
                if abs(now - timestamp) > 300:  # 5 minute window
                    await self.send(
                        message.sender_id,
                        ActorMessage(
                            message_type="webhook_validation",
                            content={"valid": False, "reason": "timestamp_expired"},
                            sender_id=self.agent_id,
                        ),
                    )
                    return

            # Calculate expected signature
            payload_str = json.dumps(payload, sort_keys=True) if isinstance(payload, dict) else str(payload)
            expected_signature = hmac.new(
                webhook.secret.encode(),
                f"{payload_str}{timestamp or ''}".encode(),
                hashlib.sha256,
            ).hexdigest()

            valid = hmac.compare_digest(signature, expected_signature)

            if valid:
                webhook.request_count += 1
                webhook.last_request = datetime.now(UTC)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="webhook_validation",
                    content={"valid": valid},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("validate_webhook_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to validate webhook: {e!s}",
                message.message_type,
            )

    async def _handle_get_webhook_status(self, message: ActorMessage) -> None:
        """
        Get webhook status.

        Content:
        - webhook_id: str (optional, returns all if not provided)
        """
        try:
            content = await self._validate_message(message)
            webhook_id = content.get("webhook_id")

            if webhook_id:
                if webhook_id not in self._webhooks:
                    await self._send_error(
                        message.sender_id,
                        f"Webhook {webhook_id} not found",
                        message.message_type,
                    )
                    return
                webhooks = [self._webhooks[webhook_id].to_dict()]
            else:
                webhooks = [wh.to_dict() for wh in self._webhooks.values()]

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="webhook_status",
                    content={"webhooks": webhooks},
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_webhook_status_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to get webhook status: {e!s}",
                message.message_type,
            )

    # =========================================================================
    # Protocol Translation
    # =========================================================================

    async def _handle_translate_protocol(self, message: ActorMessage) -> None:
        """
        Translate between protocols.

        Content:
        - from_protocol: str
        - to_protocol: str
        - data: Any
        """
        try:
            content = await self._validate_message(message)
            from_proto = content.get("from_protocol", "internal")
            to_proto = content.get("to_protocol", "rest")
            data = content.get("data")

            # Translation logic
            translated = self._translate_data(from_proto, to_proto, data)

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="protocol_translated",
                    content={
                        "from": from_proto,
                        "to": to_proto,
                        "translated_data": translated,
                    },
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("translate_protocol_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to translate protocol: {e!s}",
                message.message_type,
            )

    def _translate_data(self, from_proto: str, to_proto: str, data: Any) -> Any:
        """Translate data between protocols."""
        # Simple translation - can be extended based on needs
        if from_proto == to_proto:
            return data

        # Internal to REST
        if from_proto == "internal" and to_proto == "rest":
            return {"data": data, "timestamp": datetime.now(UTC).isoformat()}

        # REST to Internal
        if from_proto == "rest" and to_proto == "internal":
            if isinstance(data, dict):
                return data.get("data", data)
            return data

        # Default: return as-is
        return data

    # =========================================================================
    # Reporting and Metrics
    # =========================================================================

    async def _handle_get_integration_report(self, message: ActorMessage) -> None:
        """
        Generate integration status report.

        Content: (none required)
        """
        try:
            # Connection statistics
            conn_stats = {
                "total": len(self._connections),
                "by_status": {},
                "by_protocol": {},
                "total_requests": sum(c.total_requests for c in self._connections.values()),
                "failed_requests": sum(c.failed_requests for c in self._connections.values()),
            }

            for conn in self._connections.values():
                status = conn.status.value
                conn_stats["by_status"][status] = conn_stats["by_status"].get(status, 0) + 1
                protocol = conn.protocol.value
                conn_stats["by_protocol"][protocol] = conn_stats["by_protocol"].get(protocol, 0) + 1

            # Webhook statistics
            webhook_stats = {
                "total": len(self._webhooks),
                "active": sum(1 for w in self._webhooks.values() if w.active),
                "total_requests": sum(w.request_count for w in self._webhooks.values()),
            }

            report = {
                "timestamp": datetime.now(UTC).isoformat(),
                "connection_statistics": conn_stats,
                "webhook_statistics": webhook_stats,
                "request_log_size": len(self._request_log),
            }

            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="integration_report",
                    content=report,
                    sender_id=self.agent_id,
                ),
            )

        except Exception as e:
            logger.error("get_integration_report_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to generate report: {e!s}",
                message.message_type,
            )

    def _log_request(
        self,
        connection_id: str,
        method: str,
        url: str,
        status: int,
        latency_ms: float,
    ) -> None:
        """Log a request for audit purposes."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "connection_id": connection_id,
            "method": method,
            "url": url,
            "status": status,
            "latency_ms": latency_ms,
        }
        self._request_log.append(entry)

        # Trim log if needed
        if len(self._request_log) > self._max_log_entries:
            self._request_log = self._request_log[-self._max_log_entries :]

    async def _send_error(
        self,
        recipient: str,
        error_message: str,
        original_type: str,
    ) -> None:
        """Send error response."""
        await self.send(
            recipient,
            ActorMessage(
                message_type="error",
                content={"error": error_message, "original_type": original_type},
                sender_id=self.agent_id,
            ),
        )

    async def _handle_get_api_metrics(self, message: ActorMessage) -> None:
        """Get API request metrics."""
        try:
            content = message.content or {}
            limit = min(content.get("limit", 100), self._max_metrics_entries)
            metrics = [m.to_dict() for m in self._api_metrics[-limit:]]
            summary = self._api_client.get_metrics() if self._api_client else {}
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="api_metrics",
                    content={"metrics": metrics, "summary": summary},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("get_api_metrics_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to get metrics: {e!s}", message.message_type)

    async def _handle_configure_retry(self, message: ActorMessage) -> None:
        """Configure retry behavior."""
        try:
            content = message.content or {}
            self._retry_config = RetryConfig(
                max_retries=content.get("max_retries", 3),
                initial_delay_ms=content.get("initial_delay_ms", 100),
                max_delay_ms=content.get("max_delay_ms", 30000),
                strategy=RetryStrategy(content.get("strategy", "exponential")),
                jitter=content.get("jitter", True),
            )
            if self._api_client:
                self._api_client._retry_config = self._retry_config
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="retry_configured",
                    content={"configured": True},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("configure_retry_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to configure retry: {e!s}", message.message_type)

    async def _handle_configure_rate_limit(self, message: ActorMessage) -> None:
        """Configure rate limit handling."""
        try:
            content = message.content or {}
            self._rate_limit_config = RateLimitConfig(
                requests_per_minute=content.get("requests_per_minute", 60),
                burst_size=content.get("burst_size"),
                auto_backoff=content.get("auto_backoff", True),
                backoff_multiplier=content.get("backoff_multiplier", 2.0),
                max_backoff_ms=content.get("max_backoff_ms", 60000),
            )
            if self._api_client:
                self._api_client._rate_limiter._config = self._rate_limit_config
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="rate_limit_configured",
                    content={"configured": True},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("configure_rate_limit_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to configure rate limit: {e!s}", message.message_type)

    async def _handle_configure_circuit_breaker(self, message: ActorMessage) -> None:
        """Configure circuit breaker."""
        try:
            content = message.content or {}
            self._circuit_breaker_config = CircuitBreakerConfig(
                failure_threshold=content.get("failure_threshold", 5),
                success_threshold=content.get("success_threshold", 2),
                timeout_seconds=content.get("timeout_seconds", 30.0),
                excluded_status_codes=content.get("excluded_status_codes", [400, 401, 403, 404]),
            )
            if self._api_client:
                self._api_client._circuit_breaker._config = self._circuit_breaker_config
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="circuit_breaker_configured",
                    content={"configured": True},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("configure_circuit_breaker_failed", error=str(e))
            await self._send_error(
                message.sender_id,
                f"Failed to configure circuit breaker: {e!s}",
                message.message_type,
            )

    async def _handle_add_fallback_endpoint(self, message: ActorMessage) -> None:
        """Add fallback endpoint for a connection."""
        try:
            content = message.content or {}
            connection_id = content.get("connection_id")
            fallback_url = content.get("fallback_url")
            if not connection_id or connection_id not in self._connections:
                await self._send_error(message.sender_id, f"Connection {connection_id} not found", message.message_type)
                return
            if fallback_url:
                self._connections[connection_id].metadata["fallback_endpoints"] = self._connections[
                    connection_id
                ].metadata.get("fallback_endpoints", [])
                self._connections[connection_id].metadata["fallback_endpoints"].append(fallback_url)
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="fallback_endpoint_added",
                    content={"connection_id": connection_id},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("add_fallback_endpoint_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to add fallback: {e!s}", message.message_type)

    async def _handle_get_resilience_status(self, message: ActorMessage) -> None:
        """Get resilience component status."""
        try:
            circuit_breakers = {}
            if self._api_client:
                for endpoint in self._api_client._circuit_breaker._states:
                    circuit_breakers[endpoint] = self._api_client._circuit_breaker.get_metrics(endpoint)
            rate_limiter_metrics = self._api_client._rate_limiter.get_metrics() if self._api_client else {}
            fallback_health = self._api_client._fallback_manager.get_health_status() if self._api_client else {}
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="resilience_status",
                    content={
                        "circuit_breakers": circuit_breakers,
                        "rate_limiter_metrics": rate_limiter_metrics,
                        "fallback_health": fallback_health,
                    },
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("get_resilience_status_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to get resilience status: {e!s}", message.message_type)

    async def _handle_reset_circuit_breaker(self, message: ActorMessage) -> None:
        """Reset circuit breaker for an endpoint."""
        try:
            content = message.content or {}
            endpoint = content.get("endpoint")
            if self._api_client:
                if endpoint:
                    self._api_client._circuit_breaker._states[endpoint] = CircuitState.CLOSED
                    self._api_client._circuit_breaker._failure_counts[endpoint] = 0
                else:
                    for ep in self._api_client._circuit_breaker._states:
                        self._api_client._circuit_breaker._states[ep] = CircuitState.CLOSED
                        self._api_client._circuit_breaker._failure_counts[ep] = 0
            await self.send(
                message.sender_id,
                ActorMessage(
                    message_type="circuit_breaker_reset",
                    content={"reset": True},
                    sender_id=self.agent_id,
                ),
            )
        except Exception as e:
            logger.error("reset_circuit_breaker_failed", error=str(e))
            await self._send_error(message.sender_id, f"Failed to reset circuit breaker: {e!s}", message.message_type)

    def _record_api_metrics(
        self,
        request_id: str,
        connection_id: str,
        method: str,
        latency_ms: int,
        success: bool,
        status_code: int,
        error: str | None,
    ) -> None:
        """Record API request metrics."""
        metric = APIRequestMetrics(
            request_id=request_id,
            latency_ms=latency_ms,
            status_code=status_code,
            error=error,
        )
        self._api_metrics.append(metric)
        if len(self._api_metrics) > self._max_metrics_entries:
            self._api_metrics = self._api_metrics[-self._max_metrics_entries :]

    def get_capabilities(self) -> list[str]:
        """Return list of capabilities this agent provides."""
        return [
            "external_api_integration",
            "webhook_management",
            "protocol_translation",
            "rate_limiting",
            "authentication_handling",
            "request_logging",
        ]


# Import datetime for timestamp in _translate_data and other methods
from datetime import UTC, datetime
