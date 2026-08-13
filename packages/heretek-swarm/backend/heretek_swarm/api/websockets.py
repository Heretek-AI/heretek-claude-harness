"""
Heretek Swarm WebSocket Endpoints

Provides WebSocket connections for:
- Execution updates: Real-time status of agent executions
- A2A messages: Agent-to-agent message stream monitoring
- Agent events: Live agent state change notifications

SECURITY: All WebSocket connections require authentication via token.
"""

import asyncio
import json
import os
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from heretek_swarm.api.websockets import ConnectionManager

import structlog
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from heretek_swarm.gateway.auth import TokenStore, default_token_store

logger = structlog.get_logger("api.websockets")

# =============================================================================
# Authentication Configuration
# =============================================================================


class WebSocketAuthManager:
    """Manages authentication for WebSocket connections.

    Backwards-compat shim. The previous bespoke implementation had
    subtle semantic drift from the canonical token store at
    :mod:`heretek_swarm.gateway.auth` (see PLAN.md §1.7
    "triplicated authentication"). The token-issuing / validating
    surface now delegates to :class:`heretek_swarm.gateway.auth.TokenStore`,
    sharing the process-wide store. The two extras that the canonical
    store does not model — ``HERETEK_API_KEY`` short-circuit and the
    per-user rate limit — remain on this class so existing callers
    keep working.
    """

    def __init__(self, secret_key: str | None = None, store: TokenStore | None = None) -> None:
        self.secret_key = secret_key or os.environ.get(
            "WEBSOCKET_SECRET_KEY", secrets.token_hex(32)
        )
        self._store = store or default_token_store
        self._rate_limits: dict[str, list] = {}  # Track requests per user
        self._rate_limit_window = 60  # seconds
        self._rate_limit_max = 100  # max requests per window

    def generate_token(self, user_id: str, metadata: dict | None = None) -> str:
        """Generate an authentication token for a user."""
        return self._store.generate_token(user_id, metadata=metadata)

    def validate_token(self, token: str) -> tuple[bool, str | None, str | None]:
        """
        Validate an authentication token.

        Also accepts the HERETEK_API_KEY environment variable as a valid token,
        so the same API key works for both HTTP and WebSocket auth.

        Returns:
            Tuple of (is_valid, user_id, error_message)
        """
        if not token:
            return False, None, "Token required"

        # Accept HERETEK_API_KEY env var as a valid token (WebSocket-specific)
        expected_key = os.getenv("HERETEK_API_KEY", "")
        if token == expected_key and expected_key:
            return True, "api_key_user", None

        return self._store.validate_token(token)

    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        return self._store.revoke_token(token)

    def check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user has exceeded rate limit.

        Returns:
            True if request is allowed, False if rate limited
        """
        now = datetime.now(UTC).timestamp()

        if user_id not in self._rate_limits:
            self._rate_limits[user_id] = []

        # Remove old entries outside window
        self._rate_limits[user_id] = [
            ts for ts in self._rate_limits[user_id] if now - ts < self._rate_limit_window
        ]

        # Check limit
        if len(self._rate_limits[user_id]) >= self._rate_limit_max:
            return False

        # Record this request
        self._rate_limits[user_id].append(now)
        return True

    def cleanup_expired(self) -> int:
        """Remove expired tokens. Returns count of removed tokens.

        Delegates to the canonical store; returns 0 in the common
        case where ``validate_token`` already pruned expired entries
        on access.
        """
        # TokenStore.validate_token deletes expired entries on the fly;
        # cleanup_expired is kept for the public API but is now a no-op.
        return 0


# Global auth manager instance
ws_auth_manager = WebSocketAuthManager()


async def authenticate_websocket(
    websocket: WebSocket, token: str | None
) -> tuple[bool, str | None, str | None]:
    """
    Authenticate a WebSocket connection.

    Returns:
        Tuple of (is_authenticated, user_id, error_message)
    """
    is_valid, user_id, error = ws_auth_manager.validate_token(token or "")
    if not is_valid:
        return False, None, error

    # Check rate limit
    if not ws_auth_manager.check_rate_limit(user_id):
        return False, None, "Rate limit exceeded"

    return True, user_id, None


async def _ws_authenticate_and_accept(
    websocket: WebSocket, token: str | None, error_action: str
) -> tuple[bool, str | None]:
    """
    Authenticate a WebSocket connection and accept it if valid.

    Returns:
        Tuple of (authenticated, user_id). On failure, sends error and closes.
    """
    is_authenticated, user_id, error = await authenticate_websocket(websocket, token)
    if not is_authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": f"Authentication failed: {error}"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        logger.warning("websocket_{error_action}_auth_failed", error=error)
        return False, None
    return True, user_id


async def _ws_handle_agent_subscribe(
    websocket: WebSocket,
    message: dict,
    subscribed_agents: set,
    agent_id: str | None,
    manager: "ConnectionManager",
) -> None:
    """Handle a subscribe action for an agent resource."""
    sub_agent_id = message.get("agentId") or agent_id
    if sub_agent_id:
        subscribed_agents.add(sub_agent_id)
        manager.subscribe_agent_status(sub_agent_id, websocket)
        logger.info("Subscribed to agent status", agent_id=sub_agent_id)
        if sub_agent_id in _agent_states:
            await websocket.send_json(
                {"type": "agent_status", "agentId": sub_agent_id, **_agent_states[sub_agent_id]}
            )


async def _ws_handle_agent_unsubscribe(
    subscribed_agents: set, agent_id: str | None, manager: "ConnectionManager"
) -> None:
    """Handle an unsubscribe action for an agent resource."""
    sub_agent_id = agent_id
    if sub_agent_id in subscribed_agents:
        manager.unsubscribe_agent_status(sub_agent_id)
        subscribed_agents.discard(sub_agent_id)
        logger.info("Unsubscribed from agent status", agent_id=sub_agent_id)


async def _ws_handle_workflow_subscribe(
    websocket: WebSocket,
    message: dict,
    subscribed_workflows: set,
    workflow_id: str | None,
    manager: "ConnectionManager",
) -> None:
    """Handle a subscribe action for a workflow resource."""
    sub_workflow_id = message.get("workflowId") or workflow_id
    if sub_workflow_id:
        subscribed_workflows.add(sub_workflow_id)
        manager.subscribe_workflow_progress(sub_workflow_id, websocket)
        logger.info("Subscribed to workflow progress", workflow_id=sub_workflow_id)


async def _ws_handle_workflow_unsubscribe(
    subscribed_workflows: set,
    workflow_id: str | None,
    websocket: WebSocket,
    manager: "ConnectionManager",
) -> None:
    """Handle an unsubscribe action for a workflow resource."""
    sub_workflow_id = workflow_id
    if sub_workflow_id in subscribed_workflows:
        manager.unsubscribe_workflow_progress(sub_workflow_id, websocket)
        subscribed_workflows.discard(sub_workflow_id)
        logger.info("Unsubscribed from workflow progress", workflow_id=sub_workflow_id)


async def _ws_handle_metrics_subscribe(
    websocket: WebSocket,
    message: dict,
    subscribed_agents: set,
    agent_id: str | None,
    manager: "ConnectionManager",
) -> None:
    """Handle a subscribe action for agent metrics."""
    sub_agent_id = message.get("agentId") or agent_id
    if sub_agent_id:
        subscribed_agents.add(sub_agent_id)
        manager.subscribe_metrics(sub_agent_id, websocket)
        logger.info("Subscribed to agent metrics", agent_id=sub_agent_id)


async def _ws_handle_metrics_unsubscribe(
    subscribed_agents: set, agent_id: str | None, websocket: WebSocket, manager: "ConnectionManager"
) -> None:
    """Handle an unsubscribe action for agent metrics."""
    sub_agent_id = agent_id
    if sub_agent_id in subscribed_agents:
        manager.unsubscribe_metrics(sub_agent_id, websocket)
        subscribed_agents.discard(sub_agent_id)
        logger.info("Unsubscribed from agent metrics", agent_id=sub_agent_id)


async def _ws_handle_dashboard_message(
    websocket: WebSocket, message: dict, subscriptions: dict
) -> None:
    """Handle a client message for the dashboard WebSocket."""
    action = message.get("action")

    if action == "ping":
        await websocket.send_json(
            {
                "type": "pong",
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    elif action == "subscribe":
        channel = message.get("channel")
        if channel in subscriptions:
            subscriptions[channel] = True
            logger.info("Dashboard subscribed to channel", channel=channel)
    elif action == "unsubscribe":
        channel = message.get("channel")
        if channel in subscriptions:
            subscriptions[channel] = False
            logger.info("Dashboard unsubscribed from channel", channel=channel)


# Create WebSocket router
router = APIRouter(prefix="/api/ws")

# Authentication token description constant
_AUTH_TOKEN_DESC = "Authentication token"

# =============================================================================
# Connection Manager
# =============================================================================


class ConnectionManager:
    """Manages WebSocket connections for broadcasting."""

    def __init__(self):
        self.active_connections: dict[str, set[WebSocket]] = {}
        self.execution_watchers: dict[str, set[WebSocket]] = {}
        self.a2a_listeners: set[WebSocket] = set()
        self.dashboard_listeners: set[WebSocket] = set()
        self.observability_listeners: set[WebSocket] = set()
        self.agent_status_listeners: dict[str, WebSocket] = {}  # agent_id -> websocket
        self.workflow_progress_listeners: dict[
            str, set[WebSocket]
        ] = {}  # workflow_id -> websockets
        self.metrics_listeners: dict[str, set[WebSocket]] = {}  # agent_id -> websockets
        self.log_listeners: set[WebSocket] = set()

    async def connect_execution(self, websocket: WebSocket, execution_id: str):
        """Connect to execution updates channel."""
        await websocket.accept()
        if execution_id not in self.execution_watchers:
            self.execution_watchers[execution_id] = set()
        self.execution_watchers[execution_id].add(websocket)
        logger.info("WebSocket connected to execution", execution_id=execution_id)

    def disconnect_execution(self, websocket: WebSocket, execution_id: str):
        """Disconnect from execution updates."""
        if execution_id in self.execution_watchers:
            self.execution_watchers[execution_id].discard(websocket)
            if not self.execution_watchers[execution_id]:
                del self.execution_watchers[execution_id]

    async def connect_a2a(self, websocket: WebSocket):
        """Connect to A2A message stream."""
        await websocket.accept()
        self.a2a_listeners.add(websocket)
        logger.info("WebSocket connected to A2A stream")

    def disconnect_a2a(self, websocket: WebSocket):
        """Disconnect from A2A message stream."""
        self.a2a_listeners.discard(websocket)

    async def connect_dashboard(self, websocket: WebSocket):
        """Connect to dashboard updates channel."""
        await websocket.accept()
        self.dashboard_listeners.add(websocket)
        logger.info("WebSocket connected to dashboard")

    def disconnect_dashboard(self, websocket: WebSocket):
        """Disconnect from dashboard updates."""
        self.dashboard_listeners.discard(websocket)

    async def connect_observability(self, websocket: WebSocket):
        """Connect to observability updates channel."""
        await websocket.accept()
        self.observability_listeners.add(websocket)
        logger.info("WebSocket connected to observability")

    def disconnect_observability(self, websocket: WebSocket):
        """Disconnect from observability updates."""
        self.observability_listeners.discard(websocket)

    async def broadcast_execution(self, execution_id: str, data: dict[str, Any]):
        """Broadcast execution update to all watchers."""
        if execution_id in self.execution_watchers:
            disconnected = set()
            for websocket in self.execution_watchers[execution_id]:
                try:
                    await websocket.send_json(data)
                except Exception as e:
                    logger.debug(
                        "execution_broadcast_disconnect", execution_id=execution_id, error=str(e)
                    )
                    disconnected.add(websocket)
            # Clean up disconnected
            for ws in disconnected:
                self.execution_watchers[execution_id].discard(ws)

    async def broadcast_a2a(self, data: dict[str, Any]):
        """Broadcast A2A message to all listeners."""
        disconnected = set()
        for websocket in self.a2a_listeners:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(
                    "websocket_broadcast_disconnect", websocket_id=id(websocket), error=str(e)
                )
                disconnected.add(websocket)
        for ws in disconnected:
            self.a2a_listeners.discard(ws)

    async def broadcast_dashboard(self, data: dict[str, Any]):
        """Broadcast dashboard update to all listeners."""
        disconnected = set()
        for websocket in self.dashboard_listeners:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(
                    "websocket_broadcast_disconnect", websocket_id=id(websocket), error=str(e)
                )
                disconnected.add(websocket)
        for ws in disconnected:
            self.dashboard_listeners.discard(ws)

    async def broadcast_observability(self, data: dict[str, Any]):
        """Broadcast observability update to all listeners."""
        disconnected = set()
        for websocket in self.observability_listeners:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.debug(
                    "websocket_broadcast_disconnect", websocket_id=id(websocket), error=str(e)
                )
                disconnected.add(websocket)
        for ws in disconnected:
            self.observability_listeners.discard(ws)

    async def broadcast_agent_status(self, agent_id: str, data: dict[str, Any]):
        """Broadcast agent status update to specific listener."""
        if agent_id in self.agent_status_listeners:
            websocket = self.agent_status_listeners[agent_id]
            try:
                await websocket.send_json(
                    {
                        "type": "agent_status",
                        "agentId": agent_id,
                        **data,
                    }
                )
            except Exception as e:
                logger.debug("agent_status_broadcast_disconnect", agent_id=agent_id, error=str(e))
                del self.agent_status_listeners[agent_id]

    async def broadcast_workflow_progress(self, workflow_id: str, data: dict[str, Any]):
        """Broadcast workflow progress update to all listeners."""
        if workflow_id in self.workflow_progress_listeners:
            disconnected = set()
            for websocket in self.workflow_progress_listeners[workflow_id]:
                try:
                    await websocket.send_json(
                        {
                            "type": "workflow_progress",
                            "workflowId": workflow_id,
                            **data,
                        }
                    )
                except Exception as e:
                    logger.debug(
                        "workflow_broadcast_disconnect", workflow_id=workflow_id, error=str(e)
                    )
                    disconnected.add(websocket)
            for ws in disconnected:
                self.workflow_progress_listeners[workflow_id].discard(ws)

    async def broadcast_metrics(self, agent_id: str, data: dict[str, Any]):
        """Broadcast metrics update to all listeners for an agent."""
        if agent_id in self.metrics_listeners:
            disconnected = set()
            for websocket in self.metrics_listeners[agent_id]:
                try:
                    await websocket.send_json(
                        {
                            "type": "metrics",
                            "agentId": agent_id,
                            "metrics": data,
                        }
                    )
                except Exception as e:
                    logger.debug(
                        "agent_metrics_broadcast_disconnect", agent_id=agent_id, error=str(e)
                    )
                    disconnected.add(websocket)
            for ws in disconnected:
                self.metrics_listeners[agent_id].discard(ws)

    def subscribe_agent_status(self, agent_id: str, websocket: WebSocket):
        """Subscribe to agent status updates."""
        self.agent_status_listeners[agent_id] = websocket

    def unsubscribe_agent_status(self, agent_id: str):
        """Unsubscribe from agent status updates."""
        if agent_id in self.agent_status_listeners:
            del self.agent_status_listeners[agent_id]

    def subscribe_workflow_progress(self, workflow_id: str, websocket: WebSocket):
        """Subscribe to workflow progress updates."""
        if workflow_id not in self.workflow_progress_listeners:
            self.workflow_progress_listeners[workflow_id] = set()
        self.workflow_progress_listeners[workflow_id].add(websocket)

    def unsubscribe_workflow_progress(self, workflow_id: str, websocket: WebSocket):
        """Unsubscribe from workflow progress updates."""
        if workflow_id in self.workflow_progress_listeners:
            self.workflow_progress_listeners[workflow_id].discard(websocket)
            if not self.workflow_progress_listeners[workflow_id]:
                del self.workflow_progress_listeners[workflow_id]

    def subscribe_metrics(self, agent_id: str, websocket: WebSocket):
        """Subscribe to agent metrics updates."""
        if agent_id not in self.metrics_listeners:
            self.metrics_listeners[agent_id] = set()
        self.metrics_listeners[agent_id].add(websocket)

    def unsubscribe_metrics(self, agent_id: str, websocket: WebSocket):
        """Unsubscribe from agent metrics updates."""
        if agent_id in self.metrics_listeners:
            self.metrics_listeners[agent_id].discard(websocket)
            if not self.metrics_listeners[agent_id]:
                del self.metrics_listeners[agent_id]

    async def connect_logs(self, websocket: WebSocket) -> None:
        """Connect to logs stream."""
        await websocket.accept()
        self.log_listeners.add(websocket)
        logger.info("websocket_logs_connected")

    def disconnect_logs(self, websocket: WebSocket) -> None:
        """Disconnect from logs stream."""
        self.log_listeners.discard(websocket)
        logger.info("websocket_logs_disconnected")

    async def broadcast_log(self, data: dict[str, Any]) -> None:
        """Broadcast log entry to all listeners."""
        disconnected = set()
        for websocket in self.log_listeners:
            try:
                await websocket.send_json(
                    {
                        "type": "log_entry",
                        **data,
                    }
                )
            except Exception as e:
                logger.debug("log_broadcast_failed", error=str(e))
                disconnected.add(websocket)
        for ws in disconnected:
            self.log_listeners.discard(ws)


# Global connection manager
manager = ConnectionManager()

# In-memory store for agent states
_agent_states: dict[str, dict[str, Any]] = {}


# =============================================================================
# Execution Updates WebSocket
# =============================================================================


@router.websocket("/executions/{execution_id}")
async def execution_websocket(
    websocket: WebSocket,
    execution_id: str,
    token: str | None = Query(None, description=_AUTH_TOKEN_DESC),
):
    """
    WebSocket endpoint for real-time execution updates.

    SECURITY: Requires valid authentication token.

    Clients connect to receive live updates about agent execution progress.
    Messages are sent as JSON with the following structure:
    {
        "execution_id": "...",
        "status": "running|completed|failed",
        "progress": 0.75,
        "message": "Processing step 3 of 4",
        "timestamp": "2024-01-01T12:00:00Z"
    }

    Args:
        execution_id: Unique execution identifier
        token: Authentication token (required)

    Example:
        ```javascript
        const ws = new WebSocket("ws://localhost:8000/ws/executions/exec-123?token=YOUR_TOKEN");
        ws.onmessage = (event) => {
            const update = JSON.parse(event.data);
            console.log(`Progress: ${update.progress * 100}%`);
        };
        ```
    """
    # SECURITY: Authenticate connection
    is_authenticated, _user_id, error = await authenticate_websocket(websocket, token)
    if not is_authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": f"Authentication failed: {error}"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        logger.warning("websocket_execution_auth_failed", execution_id=execution_id, error=error)
        return

    await manager.connect_execution(websocket, execution_id)

    try:
        # Send initial connection confirmation
        await websocket.send_json(
            {
                "type": "connected",
                "execution_id": execution_id,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        # Track execution state in memory (simplified - in production use Redis)
        execution_state = {
            "execution_id": execution_id,
            "status": "running",
            "progress": 0.0,
            "message": "Initializing",
            "started_at": datetime.now(UTC).isoformat(),
        }

        # Store in memory for retrieval
        _execution_store[execution_id] = execution_state

        # Keep connection alive and send periodic updates
        # In production, this would listen to actual execution events
        while True:
            try:
                # Wait for messages from client (e.g., pause, cancel)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                # Handle client commands
                if message.get("command") == "cancel":
                    execution_state["status"] = "cancelled"
                    execution_state["message"] = "Cancelled by client"
                    await manager.broadcast_execution(execution_id, execution_state)
                    break

            except TimeoutError:
                # Send heartbeat/update
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", execution_id=execution_id)
    except Exception as e:
        logger.error("WebSocket error", execution_id=execution_id, error=str(e))
    finally:
        manager.disconnect_execution(websocket, execution_id)


# In-memory execution store (use Redis in production)
_execution_store: dict[str, dict[str, Any]] = {}


async def get_execution_update(execution_id: str) -> dict[str, Any]:
    """
    Get current execution state.

    Args:
        execution_id: Unique execution identifier

    Returns:
        Current execution state or default
    """
    return _execution_store.get(
        execution_id,
        {
            "execution_id": execution_id,
            "status": "unknown",
            "message": "Execution not found",
        },
    )


# =============================================================================
# A2A Protocol WebSocket
# =============================================================================


@router.websocket("/a2a")
async def a2a_websocket(
    websocket: WebSocket, token: str | None = Query(None, description=_AUTH_TOKEN_DESC)
):
    """
    WebSocket endpoint for A2A protocol message stream.

    SECURITY: Requires valid authentication token.

    This endpoint provides real-time monitoring of agent-to-agent messages.
    All A2A messages are broadcast to connected clients.

    Message format:
    {
        "type": "message|request|response|error",
        "from": "agent-id",
        "to": "agent-id",
        "payload": {...},
        "timestamp": "2024-01-01T12:00:00Z"
    }

    Example:
        ```javascript
        const ws = new WebSocket("ws://localhost:8000/ws/a2a?token=YOUR_TOKEN");
        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            console.log(`A2A: ${msg.from} -> ${msg.to}`);
        };
        ```
    """
    # SECURITY: Authenticate connection
    is_authenticated, _user_id, error = await authenticate_websocket(websocket, token)
    if not is_authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": f"Authentication failed: {error}"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        logger.warning("websocket_a2a_auth_failed", error=error)
        return

    await manager.connect_a2a(websocket)

    # NATS bridge handles event routing via main.py startup subscription
    # Fallback: send periodic heartbeat to keep connection alive
    try:
        logger.warning("websocket_a2a_fallback_activated", user_id=_user_id)
        while True:
            # Send heartbeat every 5 seconds (reduced from 30)
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            await asyncio.sleep(5)

    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    finally:
        manager.disconnect_a2a(websocket)


# =============================================================================
# Agent Events WebSocket
# =============================================================================


@router.websocket("/agents/{agent_id}/events")
async def agent_events_websocket(
    websocket: WebSocket,
    agent_id: str,
    token: str | None = Query(None, description=_AUTH_TOKEN_DESC),
):
    """
    WebSocket endpoint for agent-specific event stream.

    SECURITY: Requires valid authentication token.

    Provides real-time events for a specific agent including:
    - State changes
    - Message receipts
    - Tool executions
    - Errors

    Args:
        agent_id: Unique agent identifier
        token: Authentication token (required)

    Message format:
    {
        "event": "state_changed|message_received|tool_executed|error",
        "agent_id": "agent-id",
        "data": {...},
        "timestamp": "2024-01-01T12:00:00Z"
    }
    """
    # SECURITY: Authenticate connection
    is_authenticated, _user_id, error = await authenticate_websocket(websocket, token)
    if not is_authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": f"Authentication failed: {error}"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        logger.warning("websocket_agent_events_auth_failed", agent_id=agent_id, error=error)
        return

    await websocket.accept()

    logger.info("Agent events WebSocket connected", agent_id=agent_id)

    try:
        # Keep connection alive and stream events
        while True:
            try:
                # Wait for client messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)

                # Handle subscription/unsubscription to event types
                if message.get("action") == "subscribe":
                    event_type = message.get("event_type")
                    logger.info("Subscribed to event", agent_id=agent_id, event_type=event_type)

            except TimeoutError:
                # Send heartbeat
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("Agent events WebSocket disconnected", agent_id=agent_id)
    except Exception as e:
        logger.error("Agent events WebSocket error", agent_id=agent_id, error=str(e))


# =============================================================================
# Agent Status Stream WebSocket
# =============================================================================


@router.websocket("/agents/status")
async def agent_status_websocket(
    websocket: WebSocket,
    agent_id: str | None = Query(None, description="Specific agent ID to monitor"),
    token: str | None = Query(None, description=_AUTH_TOKEN_DESC),
):
    """
    WebSocket endpoint for real-time agent status updates.

    SECURITY: Requires valid authentication token.

    Provides real-time status updates for agents including:
    - Status changes (active, idle, processing, error)
    - Current task
    - Last heartbeat

    Message format:
    {
        "type": "agent_status",
        "agentId": "agent-id",
        "status": "active|idle|processing|error",
        "currentTask": "task description",
        "lastHeartbeat": "2024-01-01T12:00:00Z"
    }

    Args:
        agent_id: Optional specific agent ID to monitor (if not provided, subscribes to all)
        token: Authentication token (required)
    """
    # SECURITY: Authenticate connection
    authenticated, _user_id = await authenticate_websocket(websocket, token)
    if not authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": "Authentication failed"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        return

    await websocket.accept()
    logger.info("Agent status WebSocket connected", agent_id=agent_id)

    subscribed_agents: set = set()

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    await _ws_handle_agent_subscribe(
                        websocket, message, subscribed_agents, agent_id, manager
                    )
                elif action == "unsubscribe":
                    await _ws_handle_agent_unsubscribe(subscribed_agents, agent_id, manager)

            except TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("Agent status WebSocket disconnected")
    except Exception as e:
        logger.error("Agent status WebSocket error", error=str(e))
    finally:
        for sub_agent_id in subscribed_agents:
            manager.unsubscribe_agent_status(sub_agent_id)


# =============================================================================
# Workflow Progress WebSocket
# =============================================================================


@router.websocket("/workflows/progress")
async def workflow_progress_websocket(
    websocket: WebSocket,
    workflow_id: str | None = Query(None, description="Specific workflow ID to monitor"),
    token: str | None = Query(None, description=_AUTH_TOKEN_DESC),
):
    """
    WebSocket endpoint for real-time workflow progress updates.

    SECURITY: Requires valid authentication token.

    Provides real-time progress updates for workflows including:
    - Current node being executed
    - Phase (plan, analyze, execute, validate, report)
    - Progress percentage (0-100)

    Message format:
    {
        "type": "workflow_progress",
        "workflowId": "workflow-id",
        "currentNode": "node-id",
        "phase": "plan|analyze|execute|validate|report",
        "progress": 75
    }

    Args:
        workflow_id: Optional specific workflow ID to monitor
        token: Authentication token (required)
    """
    # SECURITY: Authenticate connection
    authenticated, _user_id = await authenticate_websocket(websocket, token)
    if not authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": "Authentication failed"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        return

    await websocket.accept()
    logger.info("Workflow progress WebSocket connected", workflow_id=workflow_id)

    subscribed_workflows: set = set()

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    await _ws_handle_workflow_subscribe(
                        websocket, message, subscribed_workflows, workflow_id, manager
                    )
                elif action == "unsubscribe":
                    await _ws_handle_workflow_unsubscribe(
                        subscribed_workflows, workflow_id, websocket, manager
                    )

            except TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("Workflow progress WebSocket disconnected")
    except Exception as e:
        logger.error("Workflow progress WebSocket error", error=str(e))
    finally:
        for sub_workflow_id in subscribed_workflows:
            manager.unsubscribe_workflow_progress(sub_workflow_id, websocket)


# =============================================================================
# Agent Metrics WebSocket
# =============================================================================


@router.websocket("/agents/metrics")
async def agent_metrics_websocket(
    websocket: WebSocket,
    agent_id: str | None = Query(None, description="Specific agent ID to monitor"),
    token: str | None = Query(None, description=_AUTH_TOKEN_DESC),
):
    """
    WebSocket endpoint for real-time agent metrics updates.

    SECURITY: Requires valid authentication token.

    Provides real-time metrics for agents including:
    - Phi (consciousness metric)
    - Coherence
    - Load
    - Queue size

    Message format:
    {
        "type": "metrics",
        "agentId": "agent-id",
        "metrics": {
            "phi": 0.85,
            "coherence": 0.92,
            "load": 0.45,
            "queueSize": 3
        }
    }

    Args:
        agent_id: Optional specific agent ID to monitor
        token: Authentication token (required)
    """
    # SECURITY: Authenticate connection
    authenticated, _user_id = await _ws_authenticate_and_accept(websocket, token, "agent_metrics")
    if not authenticated:
        return

    await websocket.accept()
    logger.info("Agent metrics WebSocket connected", agent_id=agent_id)

    subscribed_agents: set = set()

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)
                action = message.get("action")

                if action == "subscribe":
                    await _ws_handle_metrics_subscribe(
                        websocket, message, subscribed_agents, agent_id, manager
                    )
                elif action == "unsubscribe":
                    await _ws_handle_metrics_unsubscribe(
                        subscribed_agents, agent_id, websocket, manager
                    )

            except TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("Agent metrics WebSocket disconnected")
    except Exception as e:
        logger.error("Agent metrics WebSocket error", error=str(e))
    finally:
        for sub_agent_id in subscribed_agents:
            manager.unsubscribe_metrics(sub_agent_id, websocket)


# =============================================================================
# Dashboard WebSocket
# =============================================================================


@router.websocket("/dashboard")
async def dashboard_websocket(
    websocket: WebSocket, token: str | None = Query(None, description=_AUTH_TOKEN_DESC)
):
    """
    WebSocket endpoint for real-time dashboard updates.

    SECURITY: Requires valid authentication token.

    Broadcasts:
    - Agent status changes
    - Memory statistics
    - A2A messages
    - Consensus state
    - System health

    Message format:
    {
        "type": "agent_update|agent_spawned|agent_terminated|a2a_message|memory_update|consensus_update|health_update",  # noqa: E501
        "data": {...},
        "timestamp": "2024-01-01T12:00:00Z"
    }
    """
    # SECURITY: Authenticate connection
    authenticated, _user_id = await _ws_authenticate_and_accept(websocket, token, "dashboard")
    if not authenticated:
        return

    await manager.connect_dashboard(websocket)
    logger.info("Dashboard WebSocket connected")

    # Track subscriptions
    subscriptions = {
        "agent_status": False,
        "workflow_progress": False,
        "metrics": False,
    }

    try:
        # Immediately try to receive — if browser already closed, we catch it here
        try:
            data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            message = json.loads(data)
            await _ws_handle_dashboard_message(websocket, message, subscriptions)
        except TimeoutError:
            # Normal: client didn't send anything immediately — that's fine
            logger.debug("Dashboard WS: client sent no initial message (heartbeat mode)")

        # Now enter the normal receive loop
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)
                await _ws_handle_dashboard_message(websocket, message, subscriptions)

            except TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info("Dashboard WebSocket disconnected")
    except Exception as e:
        logger.error("Dashboard WebSocket error", error=str(e))
    finally:
        manager.disconnect_dashboard(websocket)


# =============================================================================
# Observability WebSocket
# =============================================================================


@router.websocket("/observability")
async def observability_websocket(
    websocket: WebSocket, token: str | None = Query(None, description=_AUTH_TOKEN_DESC)
):
    """
    WebSocket endpoint for real-time observability updates.

    SECURITY: Requires valid authentication token.

    Broadcasts:
    - LLM traces
    - Agent executions
    - Performance metrics
    - Error logs

    Message format:
    {
        "type": "new_trace|execution_update|new_execution|metric_update|new_error",
        "data": {...},
        "timestamp": "2024-01-01T12:00:00Z"
    }
    """
    # SECURITY: Authenticate connection
    is_authenticated, _user_id, error = await authenticate_websocket(websocket, token)
    if not is_authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": f"Authentication failed: {error}"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        logger.warning("websocket_observability_auth_failed", error=error)
        return

    await manager.connect_observability(websocket)

    logger.info("Observability WebSocket connected")

    try:
        # Keep connection alive and stream updates
        while True:
            try:
                # Wait for client messages (heartbeat, subscriptions)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                message = json.loads(data)

                # Handle client requests
                if message.get("action") == "ping":
                    await websocket.send_json(
                        {
                            "type": "pong",
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )

            except TimeoutError:
                # Send heartbeat
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                await asyncio.sleep(30)

    except WebSocketDisconnect:
        logger.info("Observability WebSocket disconnected")
    except Exception as e:
        logger.error("Observability WebSocket error", error=str(e))
    finally:
        manager.disconnect_observability(websocket)


@router.websocket("/logs")
async def logs_websocket(
    websocket: WebSocket,
) -> None:
    """WebSocket endpoint for real-time log streaming (public - no auth required)."""
    await manager.connect_logs(websocket)

    try:
        # Send heartbeat and keep connection alive
        while True:
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            await asyncio.sleep(30)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected")
    finally:
        manager.disconnect_logs(websocket)


# =============================================================================
# Agent State Stream WebSocket
# =============================================================================


@router.websocket("/agents")
async def all_agents_websocket(
    websocket: WebSocket, token: str | None = Query(None, description=_AUTH_TOKEN_DESC)
):
    """
    WebSocket endpoint for all agent state updates.

    SECURITY: Requires valid authentication token.

    Broadcasts state changes for all agents to connected clients.
    Useful for dashboards and monitoring.

    Message format:
    {
        "event": "agent_spawned|agent_terminated|agent_state_changed",
        "agent_id": "agent-id",
        "state": "active|suspended|terminated|error",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    """
    # SECURITY: Authenticate connection
    is_authenticated, _user_id, error = await authenticate_websocket(websocket, token)
    if not is_authenticated:
        try:
            await websocket.accept()
            await websocket.send_json({"type": "error", "error": f"Authentication failed: {error}"})
            await websocket.close()
        except Exception:
            logger.debug("websocket_close_cleanup_error", exc_info=True)
        logger.warning("websocket_all_agents_auth_failed", error=error)
        return

    await websocket.accept()

    logger.info("All agents WebSocket connected")

    # Track this connection for broadcasting
    _all_agent_listeners = {websocket}

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                _ = json.loads(data)  # Consume but don't use client messages in this handler
            except TimeoutError:
                await websocket.send_json(
                    {
                        "type": "heartbeat",
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

    except WebSocketDisconnect:
        logger.info("All agents WebSocket disconnected")
    except Exception as e:
        logger.error("All agents WebSocket error", error=str(e))


# =============================================================================
# Helper Functions for Broadcasting Updates
# =============================================================================


async def send_agent_status_update(agent_id: str, status: str, current_task: str | None = None):
    """
    Send an agent status update to all subscribers.

    Also broadcasts to dashboard listeners with the envelope format
    the frontend expects (type: 'agent_status' + agentId at top level).

    Args:
        agent_id: Agent identifier
        status: Agent status (active, idle, processing, error)
        current_task: Optional current task description
    """
    update = {
        "status": status,
        "currentTask": current_task,
        "lastHeartbeat": datetime.now(UTC).isoformat(),
    }
    _agent_states[agent_id] = update
    await manager.broadcast_agent_status(agent_id, update)
    await manager.broadcast_dashboard(
        {
            "type": "agent_status",
            "agentId": agent_id,
            **update,
        }
    )


async def send_workflow_progress_update(
    workflow_id: str, current_node: str, phase: str, progress: int
):
    """
    Send a workflow progress update to all subscribers.

    Args:
        workflow_id: Workflow identifier
        current_node: Current node being executed
        phase: Workflow phase (plan, analyze, execute, validate, report)
        progress: Progress percentage (0-100)
    """
    update = {
        "currentNode": current_node,
        "phase": phase,
        "progress": progress,
    }
    await manager.broadcast_workflow_progress(workflow_id, update)


async def send_agent_metrics_update(
    agent_id: str,
    phi: float | None = None,
    coherence: float | None = None,
    load: float | None = None,
    queue_size: int | None = None,
):
    """
    Send agent metrics update to all subscribers.

    Args:
        agent_id: Agent identifier
        phi: Consciousness metric (optional)
        coherence: Coherence metric (optional)
        load: Load percentage (optional)
        queue_size: Queue size (optional)
    """
    metrics = {}
    if phi is not None:
        metrics["phi"] = phi
    if coherence is not None:
        metrics["coherence"] = coherence
    if load is not None:
        metrics["load"] = load
    if queue_size is not None:
        metrics["queueSize"] = queue_size

    await manager.broadcast_metrics(agent_id, metrics)


# Export router
__all__ = [
    "manager",
    "router",
    "send_agent_metrics_update",
    "send_agent_status_update",
    "send_workflow_progress_update",
]
