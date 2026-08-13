"""
SlowAPI-backed rate limiting shim.

Replaces the bespoke ``RateLimiter`` token-bucket implementation in
``security/ddos_protection.py`` (Phase 1.5 of PLAN.md, §3.1 Replace).

Why
---
- The hand-rolled ``RateLimiter`` is 200+ LOC of sliding-window + token
  bucket math that is not exercised by tests in CI. Slowapi has the
  same algorithms implemented against the battle-tested ``limits``
  library (storage backends in-memory, Redis, Memcached).
- Slowapi plugs into FastAPI as middleware, which is the existing
  pattern in ``api/main.py``. The previous code-path was an
  in-process ``RateLimiter`` instance shared across requests, which is
  unsafe under multiple workers.

Scope
-----
- This module is the canonical entry point for new code. The legacy
  ``RateLimiter`` in ``ddos_protection.py`` is kept for backward
  compatibility (DDoS detection uses it) but new request-path
  rate limiting should call into this shim.
- DDoS-specific detection (request-spike, geo-anomaly, pattern
  detection) is **not** in scope for slowapi and stays in
  ``ddos_protection.py``. The two layers compose: this shim is the
  per-request gate; ``DDoSDetector`` is the pattern-level guard.

Usage
-----
>>> from heretek_swarm_core.security.rate_limiter import limiter
>>> from slowapi.util import get_remote_address
>>> @limiter.limit("100/minute")
... async def my_route(request: Request): ...

Or in middleware form (added to ``app.state.limiter`` in ``main.py``).
"""

from __future__ import annotations

from typing import Any

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Process-wide Limiter. storage_uri is intentionally None (in-memory)
# because the application already runs behind a load balancer that
# terminates per-client rate limits; per-worker counters are sufficient
# for the soft-limit tier (e.g. "100/minute" UI dashboards). For
# cluster-wide limits, set storage_uri to "redis://..." — slowapi will
# pick it up at construction time.
limiter: Limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
    strategy="moving-window",
    swallow_errors=True,  # never let a limiter error break the request path
)


def _client_key(request: Request) -> str:
    """Default key: remote IP. Override by passing ``key_func=`` to
    :func:`limiter.limit` on the specific route."""
    return get_remote_address(request)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> Response:
    """Default 429 response with the standard ``Retry-After`` header.

    Slowapi's built-in handler is JSON but does not set Retry-After.
    We override so clients (and the dashboard) can back off correctly.
    """
    retry_after = getattr(exc, "retry_after", None) or 60
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": str(exc),
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


def install_rate_limiter(app: Any) -> None:
    """Wire slowapi into a FastAPI app.

    Idempotent. Safe to call multiple times; only the first call wires
    the state. The state name (``limiter``) is what route decorators
    resolve against, so renaming it would require updating every
    ``@limiter.limit`` call.
    """
    if getattr(app.state, "limiter", None) is None:
        app.state.limiter = limiter

    # Register the exception handler only if not already present.
    existing = getattr(app, "exception_handlers", {}) or {}
    if RateLimitExceeded not in existing:
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


__all__ = [
    "limiter",
    "rate_limit_exceeded_handler",
    "install_rate_limiter",
]
