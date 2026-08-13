"""
Rate Limiting Middleware for Heretek Swarm API.

Implements rate limiting using slowapi (FastAPI-compatible limiter).
Pattern stolen from SECURITY_AUDIT.md requirements.

Features:
- IP-based rate limiting
- Endpoint-specific limits
- Redis-backed for distributed rate limiting
- Graceful degradation when Redis unavailable

Note (Phase 1.5 of PLAN.md, §3.1 Replace): the canonical limiter
implementation now lives in :mod:`heretek_swarm_core.security.rate_limiter`.
This module is the FastAPI app wiring layer; it delegates to that
module so there is one source of truth.
"""

import os
import time
from collections.abc import Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from heretek_swarm_core.security.rate_limiter import install_rate_limiter, limiter

logger = structlog.get_logger(__name__)

# Backwards-compat flag for code that still imports ``SLOWAPI_AVAILABLE``
# from this module. Now that slowapi is a base dependency, this is
# always True; the flag is kept to avoid breaking older imports.
SLOWAPI_AVAILABLE = True


class InMemoryRateLimiter:
    """
    Simple in-memory rate limiter for when Redis/slowapi unavailable.

    Uses sliding window algorithm.
    """

    def __init__(self):
        self._requests: dict[str, list[float]] = {}
        self._lock = None  # Async lock for thread safety

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed.

        Args:
            key: Unique identifier (usually IP)
            limit: Max requests per window
            window_seconds: Time window in seconds

        Returns:
            (allowed, remaining, reset_seconds)
        """
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            now = time.time()
            window_start = now - window_seconds

            # Get or create request list
            if key not in self._requests:
                self._requests[key] = []

            # Clean old requests
            self._requests[key] = [t for t in self._requests[key] if t > window_start]

            # Check limit
            current_count = len(self._requests[key])

            if current_count >= limit:
                # Calculate reset time
                oldest = min(self._requests[key]) if self._requests[key] else now
                reset_in = int(oldest + window_seconds - now)
                return False, 0, max(0, reset_in)

            # Record request
            self._requests[key].append(now)
            remaining = limit - len(self._requests[key])
            reset_in = window_seconds

            return True, remaining, reset_in

    def cleanup_old(self, max_age_seconds: int = 3600):
        """Clean up old entries to prevent memory growth."""
        now = time.time()
        cutoff = now - max_age_seconds

        for key in list(self._requests.keys()):
            self._requests[key] = [t for t in self._requests[key] if t > cutoff]
            if not self._requests[key]:
                del self._requests[key]


# Global in-memory limiter
_memory_limiter = InMemoryRateLimiter()


# Rate limit configurations per endpoint
RATE_LIMITS = {
    # Health checks - high limit
    "/api/health": "600/minute",
    "/api/health/services": "120/minute",
    # Agent operations - moderate
    "/api/agents": "120/minute",
    "/api/agents/{agent_id}": "60/minute",
    # Memory operations - moderate
    "/api/memory": "120/minute",
    "/api/memory/search": "60/minute",
    # A2A messaging - high for real-time
    "/api/a2a/messages": "300/minute",
    # Provider CRUD - moderate
    "/api/providers": "100/minute",
    # Consensus - moderate
    "/api/consensus": "60/minute",
    "/api/consensus/{consensus_id}/vote": "30/minute",
    "/api/consensus/{consensus_id}/aggregate": "10/minute",
    "/api/consensus/deliberation/{deliberation_id}/run_round": "20/minute",
    # LiteLLM metrics - lower (expensive)
    "/api/litellm/metrics": "30/minute",
    # RAG endpoints - moderate
    "/api/rag/query": "60/minute",
    "/api/rag/ingest": "30/minute",
    # Default for unmatched endpoints
    "default": "100/minute",
}


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (reverse proxy)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take first IP (original client)
        return forwarded.split(",")[0].strip()

    # Check X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client
    if request.client:
        return request.client.host

    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware.

    Falls back to in-memory limiting if slowapi unavailable.
    """

    def __init__(
        self,
        app: FastAPI,
        default_limit: str = "100/minute",
        enabled: bool = True,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.enabled = enabled

        # Parse default limit
        self._default_requests, self._default_window = self._parse_limit(default_limit)

    def _parse_limit(self, limit: str) -> tuple[int, int]:
        """Parse rate limit string like '100/minute' into (requests, seconds)."""
        parts = limit.split("/")
        if len(parts) != 2:
            return 100, 60

        count = int(parts[0])
        unit = parts[1].lower()

        unit_seconds = {
            "second": 1,
            "seconds": 1,
            "minute": 60,
            "minutes": 60,
            "hour": 3600,
            "hours": 3600,
            "day": 86400,
            "days": 86400,
        }

        seconds = unit_seconds.get(unit, 60)
        return count, seconds

    def _get_limit_for_path(self, path: str) -> tuple[int, int]:
        """Get rate limit for a specific path."""
        # Exact match
        if path in RATE_LIMITS:
            return self._parse_limit(RATE_LIMITS[path])

        # Pattern match (for paths with parameters)
        for pattern, limit in RATE_LIMITS.items():
            if "{" in pattern:
                # Convert pattern to simple prefix match
                prefix = pattern.split("{")[0]
                if path.startswith(prefix):
                    return self._parse_limit(limit)

        # Default
        return self._default_requests, self._default_window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        if not self.enabled:
            return await call_next(request)

        # Skip rate limiting for docs and static
        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            return await call_next(request)

        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Get client IP
        client_ip = get_client_ip(request)

        # Get limit for path
        limit, window = self._get_limit_for_path(request.url.path)

        # Check rate limit
        allowed, remaining, reset_in = await _memory_limiter.is_allowed(
            key=f"{client_ip}:{request.url.path}",
            limit=limit,
            window_seconds=window,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=request.url.path,
                limit=limit,
                window=window,
            )

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "detail": f"Limit of {limit} requests per {window} seconds exceeded",
                    "retry_after": reset_in,
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_in),
                    "Retry-After": str(reset_in),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)

        return response


def setup_rate_limiting(app: FastAPI, enabled: bool = True) -> None:
    """
    Setup rate limiting for FastAPI app.

    Args:
        app: FastAPI application
        enabled: Whether rate limiting is enabled

    Notes
    -----
    Delegates to :func:`heretek_swarm_core.security.rate_limiter.install_rate_limiter`
    so the canonical limiter instance lives in one place. The
    ``REDIS_URL`` env var is honored here (where the app's config
    surface lives) rather than in the security module.
    """
    if not enabled:
        logger.info("rate_limiting_disabled")
        return

    # Configure the process-wide limiter's storage URI from REDIS_URL
    # if provided. This must happen before install_rate_limiter is
    # called so the first request sees the configured backend.
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        # slowapi/limits accept the redis:// scheme directly
        try:
            limiter._storage_uri = redis_url  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive
            logger.debug("limiter_storage_uri_set_failed", redis_url=redis_url)

    install_rate_limiter(app)
    logger.info("rate_limiting_enabled", backend="slowapi")


# Decorator for custom rate limits on endpoints
def rate_limit(limit: str):
    """
    Decorator to apply custom rate limit to an endpoint.

    Usage:
        @app.get("/api/endpoint")
        @rate_limit("10/minute")
        async def my_endpoint():
            ...
    """

    def decorator(func):
        func._rate_limit = limit
        return func

    return decorator
