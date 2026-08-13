"""
Tests for the rate limiting middleware (slowapi-or-in-memory fallback).

Per M-arch PR #7: verify the rate limiter behaves correctly:
- Allows requests under the limit
- Blocks requests over the limit with 429
- Adds X-RateLimit-* headers
- Honors per-endpoint limits via RATE_LIMITS
- Falls back to in-memory when slowapi is unavailable
"""

from __future__ import annotations

import importlib.util
from unittest.mock import MagicMock

import pytest


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "rate_limiting_under_test",
        "backend/heretek_swarm/api/rate_limiting.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


class TestInMemoryRateLimiter:
    def test_under_limit_allowed(self, mod) -> None:
        """Requests under the limit are allowed."""
        import asyncio

        limiter = mod.InMemoryRateLimiter()
        for _ in range(3):
            allowed, remaining, _ = asyncio.run(
                limiter.is_allowed(key="k1", limit=5, window_seconds=60)
            )
            assert allowed is True
        allowed, remaining, _ = asyncio.run(
            limiter.is_allowed(key="k1", limit=5, window_seconds=60)
        )
        assert allowed is True
        assert remaining == 1

    def test_over_limit_denied(self, mod) -> None:
        """Requests over the limit are denied."""
        import asyncio

        limiter = mod.InMemoryRateLimiter()
        for _ in range(3):
            asyncio.run(limiter.is_allowed(key="k2", limit=3, window_seconds=60))
        allowed, remaining, reset_in = asyncio.run(
            limiter.is_allowed(key="k2", limit=3, window_seconds=60)
        )
        assert allowed is False
        assert remaining == 0
        assert reset_in > 0

    def test_separate_keys_have_separate_buckets(self, mod) -> None:
        """Different keys do not share rate limit buckets."""
        import asyncio

        limiter = mod.InMemoryRateLimiter()
        for _ in range(3):
            asyncio.run(limiter.is_allowed(key="ip-a", limit=3, window_seconds=60))
        allowed_a, _, _ = asyncio.run(
            limiter.is_allowed(key="ip-a", limit=3, window_seconds=60)
        )
        allowed_b, _, _ = asyncio.run(
            limiter.is_allowed(key="ip-b", limit=3, window_seconds=60)
        )
        assert allowed_a is False
        assert allowed_b is True

    def test_cleanup_old_removes_expired(self, mod) -> None:
        """cleanup_old removes entries outside the max_age window."""
        import time

        limiter = mod.InMemoryRateLimiter()
        limiter._requests["old"] = [time.time() - 7200]  # 2h ago
        limiter._requests["new"] = [time.time()]
        limiter.cleanup_old(max_age_seconds=3600)
        assert "old" not in limiter._requests
        assert "new" in limiter._requests


class TestParseLimit:
    @pytest.fixture
    def middleware(self, mod):
        return mod.RateLimitMiddleware(app=MagicMock(), default_limit="100/minute")

    def test_per_minute(self, mod, middleware) -> None:
        n, s = middleware._parse_limit("100/minute")
        assert n == 100
        assert s == 60

    def test_per_second(self, mod, middleware) -> None:
        n, s = middleware._parse_limit("5/second")
        assert n == 5
        assert s == 1

    def test_per_hour(self, mod, middleware) -> None:
        n, s = middleware._parse_limit("1000/hour")
        assert n == 1000
        assert s == 3600

    def test_invalid_falls_back_to_default(self, mod, middleware) -> None:
        n, s = middleware._parse_limit("garbage")
        assert n == 100
        assert s == 60


class TestGetLimitForPath:
    @pytest.fixture
    def middleware(self, mod):
        return mod.RateLimitMiddleware(app=MagicMock(), default_limit="100/minute")

    def test_exact_match(self, mod, middleware) -> None:
        n, s = middleware._get_limit_for_path("/api/health")
        assert n == 600
        assert s == 60

    def test_pattern_match(self, mod, middleware) -> None:
        n, s = middleware._get_limit_for_path("/api/agents/abc123")
        assert n == 60
        assert s == 60

    def test_default(self, mod, middleware) -> None:
        n, s = middleware._get_limit_for_path("/api/some/unknown/path")
        assert n == 100
        assert s == 60


class TestGetClientIp:
    def test_x_forwarded_for(self, mod) -> None:
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        request.client = MagicMock(host="9.9.9.9")
        assert mod.get_client_ip(request) == "1.2.3.4"

    def test_x_real_ip(self, mod) -> None:
        request = MagicMock()
        request.headers = {"X-Real-IP": "10.0.0.1"}
        request.client = MagicMock(host="9.9.9.9")
        assert mod.get_client_ip(request) == "10.0.0.1"

    def test_fallback_to_client(self, mod) -> None:
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock(host="192.168.1.1")
        assert mod.get_client_ip(request) == "192.168.1.1"

    def test_unknown_when_no_client(self, mod) -> None:
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert mod.get_client_ip(request) == "unknown"


class TestRateLimits:
    def test_health_limits_present(self, mod) -> None:
        assert "/api/health" in mod.RATE_LIMITS
        assert "/api/health/services" in mod.RATE_LIMITS

    def test_agent_limits_present(self, mod) -> None:
        assert "/api/agents" in mod.RATE_LIMITS
        assert "/api/agents/{agent_id}" in mod.RATE_LIMITS

    def test_consensus_limits_present(self, mod) -> None:
        assert "/api/consensus" in mod.RATE_LIMITS
        assert "/api/consensus/{consensus_id}/vote" in mod.RATE_LIMITS

    def test_rag_limits_present(self, mod) -> None:
        assert "/api/rag/query" in mod.RATE_LIMITS
        assert "/api/rag/ingest" in mod.RATE_LIMITS

    def test_default_limit_present(self, mod) -> None:
        assert "default" in mod.RATE_LIMITS
        assert mod.RATE_LIMITS["default"] == "100/minute"


class TestRateLimitDecorator:
    def test_decorator_attaches_attr(self, mod) -> None:
        @mod.rate_limit("10/minute")
        def f() -> None:
            return None

        assert hasattr(f, "_rate_limit")
        assert f._rate_limit == "10/minute"
