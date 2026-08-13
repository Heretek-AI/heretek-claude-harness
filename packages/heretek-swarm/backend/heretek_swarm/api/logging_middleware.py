"""
Logging Middleware for Heretek Swarm API

Provides request logging with request ID tracking and duration metrics.
"""

import time
import uuid
from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from heretek_swarm.swarm_logging.config import (
    clear_context,
    get_logger,
    log_api_request,
    set_agent_id,
    set_request_id,
    set_trace_id,
)

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all API requests with timing and request ID tracking.

    Features:
    - Generates unique request_id for each request
    - Tracks request duration
    - Logs all requests in structured JSON format
    - Handles trace_id from headers (for distributed tracing)
    - Cleans up context after request completes
    """

    # Paths to exclude from logging (health checks, metrics, etc.)
    EXCLUDED_PATHS = {
        "/api/health/live",
        "/api/health/ready",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
    }

    # Header names for tracing
    TRACE_ID_HEADERS = [
        "x-trace-id",
        "x-correlation-id",
        "x-request-id",
        "traceparent",  # W3C Trace Context
    ]

    # Agent ID header
    AGENT_ID_HEADER = "x-agent-id"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and log the result."""
        # Skip excluded paths
        if self._should_skip(request.url.path):
            return await call_next(request)

        # Generate or extract request ID
        request_id = self._get_request_id(request)
        set_request_id(request_id)

        # Extract or generate trace ID
        trace_id = self._get_trace_id(request)
        set_trace_id(trace_id)

        # Extract agent ID if present
        agent_id = request.headers.get(self.AGENT_ID_HEADER)
        if agent_id:
            set_agent_id(agent_id)

        # Record start time
        start_time = time.perf_counter()

        # Process request
        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log the request
            log_api_request(
                method=request.method,
                path=str(request.url.path),
                status_code=response.status_code,
                duration_ms=duration_ms,
                request_id=request_id,
                agent_id=agent_id,
                user_agent=request.headers.get("user-agent"),
                client_ip=self._get_client_ip(request),
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            if trace_id:
                response.headers["X-Trace-ID"] = trace_id

            return response

        except Exception as e:
            # Calculate duration for error case
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("api_request_error", path=request.url.path, error=str(e), exc_info=True)

            # Log error
            log_api_request(
                method=request.method,
                path=str(request.url.path),
                status_code=500,
                duration_ms=duration_ms,
                request_id=request_id,
                agent_id=agent_id,
                user_agent=request.headers.get("user-agent"),
                client_ip=self._get_client_ip(request),
            )

            raise

        finally:
            # Always clear context after request
            clear_context()

    def _should_skip(self, path: str) -> bool:
        """Check if path should be excluded from logging."""
        # Exact match
        if path in self.EXCLUDED_PATHS:
            return True

        # Prefix match for docs/redoc
        return bool(path.startswith(("/docs", "/redoc")))

    def _get_request_id(self, request: Request) -> str:
        """Extract or generate request ID."""
        # Check common request ID headers
        for header in ["x-request-id", "x-correlation-id"]:
            request_id = request.headers.get(header)
            if request_id:
                return request_id

        # Generate new request ID
        return str(uuid.uuid4())

    def _get_trace_id(self, request: Request) -> str:
        """Extract or generate trace ID."""
        for header in self.TRACE_ID_HEADERS:
            trace_id = request.headers.get(header)
            if trace_id:
                # Handle W3C Trace Context format (version-traceId-parentId-flags)
                if header == "traceparent" and trace_id.startswith("00-"):
                    # Extract trace ID from W3C format
                    parts = trace_id.split("-")
                    if len(parts) >= 3:
                        return parts[1]
                return trace_id

        # Generate new trace ID
        return str(uuid.uuid4())

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address, handling proxies."""
        # Check for forwarded headers (reverse proxy)
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Get first IP in chain
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Direct connection
        if request.client:
            return request.client.host

        return "unknown"


def setup_logging_middleware(app):
    """Add logging middleware to the FastAPI application."""
    app.add_middleware(LoggingMiddleware)
