"""External API client with automatic backoff, circuit breaker, and fallback support."""

import asyncio
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

class RetryStrategy(Enum):
    """Retry backoff strategies."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIBONACCI = "fibonacci"

class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

class ApiResponse:
    """Standardized API response for external requests."""

    def __init__(
        self,
        success: bool,
        status_code: int,
        data: Any = None,
        headers: dict[str, str] | None = None,
        error: str | None = None,
        request_id: str | None = None,
        latency_ms: int = 0,
        rate_limited: bool = False,
        circuit_open: bool = False,
        fallback_used: bool = False,
        total_retries: int = 0,
    ):
        self.success = success
        self.status_code = status_code
        self.data = data
        self.headers = headers or {}
        self.error = error
        self.request_id = request_id or str(uuid.uuid4())
        self.latency_ms = latency_ms
        self.rate_limited = rate_limited
        self.circuit_open = circuit_open
        self.fallback_used = fallback_used
        self.total_retries = total_retries

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status_code": self.status_code,
            "data": self.data,
            "headers": self.headers,
            "error": self.error,
            "request_id": self.request_id,
            "latency_ms": self.latency_ms,
            "rate_limited": self.rate_limited,
            "circuit_open": self.circuit_open,
            "fallback_used": self.fallback_used,
            "total_retries": self.total_retries,
        }

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 30000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    jitter: bool = True

    @property
    def jitter_factor(self) -> float:
        return 0.1 if self.jitter else 0.0

@dataclass
class RateLimitConfig:
    """Configuration for rate limit handling."""

    requests_per_minute: int = 60
    burst_size: int | None = None
    auto_backoff: bool = True
    backoff_multiplier: float = 2.0
    max_backoff_ms: int = 60000

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 30.0
    excluded_status_codes: list[int] = field(default_factory=lambda: [400, 401, 403, 404])

@dataclass
class FallbackConfig:
    """Configuration for fallback endpoints."""

    enabled: bool = False
    fallback_endpoints: list[str] = field(default_factory=list)
    health_check_interval_seconds: float = 30.0
    require_all_healthy: bool = False

@dataclass
class APIRequestMetrics:
    """Metrics for an API request."""

    request_id: str
    attempt: int = 0
    total_retries: int = 0
    latency_ms: int = 0
    status_code: int | None = None
    error: str | None = None
    rate_limited: bool = False
    circuit_open: bool = False
    fallback_used: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "attempt": self.attempt,
            "total_retries": self.total_retries,
            "latency_ms": self.latency_ms,
            "status_code": self.status_code,
            "error": self.error,
            "rate_limited": self.rate_limited,
            "circuit_open": self.circuit_open,
            "fallback_used": self.fallback_used,
            "timestamp": self.timestamp.isoformat(),
        }

class RateLimitHandler:
    """Handles rate limiting with automatic backoff."""

    def __init__(self, config: RateLimitConfig | None = None):
        self._config = config or RateLimitConfig()
        self._request_times: dict[str, list[datetime]] = {}
        self._rate_limited_until: dict[str, datetime | None] = {}
        self._current_backoff_ms: dict[str, float] = {}
        self._total_rate_limits: int = 0
        self._total_requests: int = 0

    def check_rate_limit(self, endpoint: str) -> bool:
        """Check if request to endpoint is allowed."""
        now = datetime.now(UTC)
        if self._rate_limited_until.get(endpoint):  # noqa: SIM102
            if now < self._rate_limited_until[endpoint]:
                return False
        if endpoint in self._request_times:
            recent = [t for t in self._request_times[endpoint] if (now - t).total_seconds() < 60]
            self._request_times[endpoint] = recent
            if len(recent) >= self._config.requests_per_minute:
                return False
        return True

    def record_response(
        self, endpoint: str, status_code: int, retry_after: int | None = None
    ) -> None:
        """Record response from API endpoint."""
        now = datetime.now(UTC)
        self._total_requests += 1
        if endpoint not in self._request_times:
            self._request_times[endpoint] = []
        self._request_times[endpoint].append(now)
        if status_code == 429:
            self._total_rate_limits += 1
            self._current_backoff_ms[endpoint] = (
                self._config.backoff_multiplier
                * self._current_backoff_ms.get(endpoint, self._config.initial_delay_ms)
            )
            self._current_backoff_ms[endpoint] = min(
                self._current_backoff_ms[endpoint], self._config.max_backoff_ms
            )
            if retry_after:
                self._rate_limited_until[endpoint] = now + timedelta(seconds=retry_after)
            elif self._config.auto_backoff:
                self._rate_limited_until[endpoint] = now + timedelta(
                    milliseconds=self._current_backoff_ms[endpoint]
                )
        else:
            if endpoint in self._current_backoff_ms:
                self._current_backoff_ms[endpoint] = max(0, self._current_backoff_ms[endpoint] / 2)
            self._rate_limited_until[endpoint] = None

    def get_backoff_delay(self, endpoint: str) -> float:
        """Get backoff delay for retry."""
        base_delay = self._current_backoff_ms.get(endpoint, self._config.initial_delay_ms)
        if self._config.jitter:
            jitter_range = base_delay * 0.1
            base_delay += random.uniform(-jitter_range, jitter_range)  # noqa: S311
        return base_delay / 1000.0

    async def wait_if_needed(self, endpoint: str) -> None:
        """Wait if endpoint is rate limited."""
        if not self.check_rate_limit(endpoint):
            delay = self.get_backoff_delay(endpoint)
            if delay > 0:
                await asyncio.sleep(delay)

    def get_metrics(self) -> dict[str, Any]:
        """Get rate limiting metrics."""
        return {
            "total_rate_limits": self._total_rate_limits,
            "total_requests": self._total_requests,
            "current_backoff_ms": self._current_backoff_ms,
        }

class CircuitBreaker:
    """Circuit breaker pattern implementation for API resilience."""

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self._config = config or CircuitBreakerConfig()
        self._states: dict[str, CircuitState] = {}
        self._failure_counts: dict[str, int] = {}
        self._success_counts: dict[str, int] = {}
        self._last_failure_time: dict[str, datetime | None] = {}
        self._opened_at: dict[str, datetime | None] = {}

    def can_execute(self, endpoint: str) -> tuple[bool, CircuitState]:
        """Check if request can execute."""
        state = self._states.get(endpoint, CircuitState.CLOSED)
        if state == CircuitState.CLOSED:
            return True, state
        if state == CircuitState.OPEN:
            if self._opened_at.get(endpoint):
                timeout = datetime.now(UTC) - self._opened_at[endpoint]
                if timeout.total_seconds() >= self._config.timeout_seconds:
                    self._states[endpoint] = CircuitState.HALF_OPEN
                    self._success_counts[endpoint] = 0
                    return True, CircuitState.HALF_OPEN
            return False, state
        return True, state

    def record_success(self, endpoint: str) -> None:
        """Record successful request."""
        state = self._states.get(endpoint, CircuitState.CLOSED)
        if state == CircuitState.HALF_OPEN:
            self._success_counts[endpoint] = self._success_counts.get(endpoint, 0) + 1
            if self._success_counts[endpoint] >= self._config.success_threshold:
                self._states[endpoint] = CircuitState.CLOSED
                self._failure_counts[endpoint] = 0
        elif state == CircuitState.CLOSED:
            self._failure_counts[endpoint] = 0

    def record_failure(self, endpoint: str, status_code: int | None = None) -> None:
        """Record failed request."""
        state = self._states.get(endpoint, CircuitState.CLOSED)
        if status_code in self._config.excluded_status_codes:
            return
        if state == CircuitState.HALF_OPEN:
            self._states[endpoint] = CircuitState.OPEN
            self._opened_at[endpoint] = datetime.now(UTC)
        elif state == CircuitState.CLOSED:
            self._failure_counts[endpoint] = self._failure_counts.get(endpoint, 0) + 1
            self._last_failure_time[endpoint] = datetime.now(UTC)
            if self._failure_counts[endpoint] >= self._config.failure_threshold:
                self._states[endpoint] = CircuitState.OPEN
                self._opened_at[endpoint] = datetime.now(UTC)

    def get_state(self, endpoint: str) -> CircuitState:
        """Get circuit state for endpoint."""
        return self._states.get(endpoint, CircuitState.CLOSED)

    def get_metrics(self, endpoint: str) -> dict[str, Any]:
        """Get circuit breaker metrics for endpoint."""
        return {
            "state": self.get_state(endpoint).value,
            "failure_count": self._failure_counts.get(endpoint, 0),
            "success_count": self._success_counts.get(endpoint, 0),
            "last_failure": self._last_failure_time.get(endpoint),
        }

class FallbackManager:
    """Manages fallback endpoints for API resilience."""

    def __init__(self, config: FallbackConfig | None = None):
        self._config = config or FallbackConfig()
        self._endpoints: dict[str, dict[str, Any]] = {}
        self._current_primary_index: int = 0
        for url in self._config.fallback_endpoints:
            self._endpoints[url] = {"healthy": True, "consecutive_failures": 0, "metadata": {}}

    def add_endpoint(
        self, url: str, is_primary: bool = True, metadata: dict[str, Any] | None = None
    ) -> None:
        """Add an endpoint to the pool."""
        self._endpoints[url] = {
            "healthy": True,
            "consecutive_failures": 0,
            "metadata": metadata or {},
            "is_primary": is_primary,
        }

    def get_available_endpoint(self) -> str | None:
        """Get best available endpoint."""
        if not self._config.enabled:
            return None
        for url, data in self._endpoints.items():
            if data["healthy"]:
                return url
        return None

    def record_failure(self, endpoint: str) -> None:
        """Record failure for endpoint."""
        if endpoint in self._endpoints:
            self._endpoints[endpoint]["consecutive_failures"] += 1
            if self._endpoints[endpoint]["consecutive_failures"] >= 3:
                self._endpoints[endpoint]["healthy"] = False

    def record_success(self, endpoint: str) -> None:
        """Record success for endpoint."""
        if endpoint in self._endpoints:
            self._endpoints[endpoint]["consecutive_failures"] = 0
            self._endpoints[endpoint]["healthy"] = True

    def get_health_status(self) -> dict[str, Any]:
        """Get health status of all endpoints."""
        return {
            "endpoints": {
                url: {"healthy": d["healthy"], "failures": d["consecutive_failures"]}
                for url, d in self._endpoints.items()
            },
            "any_healthy": any(d["healthy"] for d in self._endpoints.values()),
        }

    def reset(self) -> None:
        """Reset all endpoints to healthy state."""
        for endpoint in self._endpoints:
            self._endpoints[endpoint]["healthy"] = True
            self._endpoints[endpoint]["consecutive_failures"] = 0

class ResilientAPIClient:
    """External API client with automatic retry, rate limiting, circuit breaker, and fallback support."""  # noqa: E501

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        retry_config: RetryConfig | None = None,
        rate_limit_config: RateLimitConfig | None = None,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        fallback_config: FallbackConfig | None = None,
        timeout_seconds: float = 30.0,
        zero_trust_enabled: bool = True,
    ):
        self._session = session
        self._retry_config = retry_config or RetryConfig()
        self._rate_limiter = RateLimitHandler(rate_limit_config)
        self._circuit_breaker = CircuitBreaker(circuit_breaker_config)
        self._fallback_manager = FallbackManager(fallback_config)
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._zero_trust_enabled = zero_trust_enabled
        self._total_requests: int = 0
        self._total_errors: int = 0
        self._total_rate_limits: int = 0
        self._total_circuit_breaks: int = 0
        self._total_fallbacks: int = 0

    async def request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
        retry_count: int = 0,
        request_id: str | None = None,
    ) -> ApiResponse:
        """Execute HTTP request with full resilience."""
        req_id = request_id or str(uuid.uuid4())
        can_exec, _circuit_state = self._circuit_breaker.can_execute(url)
        if not can_exec:
            self._total_circuit_breaks += 1
            return ApiResponse(
                success=False,
                status_code=0,
                error="Circuit breaker open",
                request_id=req_id,
                circuit_open=True,
            )
        await self._rate_limiter.wait_if_needed(url)
        start_time = datetime.now(UTC)
        try:
            if not self._session:
                self._session = aiohttp.ClientSession(timeout=self._timeout)
            async with self._session.request(
                method, url, headers=headers, params=params, json=json, data=data
            ) as response:
                latency = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                self._rate_limiter.record_response(url, response.status)
                if response.status == 429:
                    self._total_rate_limits += 1
                    retry_after_header = response.headers.get("Retry-After")
                    retry_after = int(retry_after_header) if retry_after_header else None
                    if retry_count < self._retry_config.max_retries:
                        backoff = self._calculate_backoff(
                            retry_count, retry_after * 1000 if retry_after else None
                        )
                        await asyncio.sleep(backoff)
                        return await self.request(
                            method, url, headers, params, json, data, retry_count + 1, req_id
                        )
                    return ApiResponse(
                        success=False,
                        status_code=429,
                        data=await response.text() if response.status else None,
                        headers=dict(response.headers),
                        latency_ms=latency,
                        request_id=req_id,
                        rate_limited=True,
                        total_retries=retry_count,
                    )
                if response.status >= 500:
                    self._circuit_breaker.record_failure(url, response.status)
                    if retry_count < self._retry_config.max_retries:
                        backoff = self._calculate_backoff(retry_count, None)
                        await asyncio.sleep(backoff)
                        return await self.request(
                            method, url, headers, params, json, data, retry_count + 1, req_id
                        )
                    return ApiResponse(
                        success=False,
                        status_code=response.status,
                        data=await response.text() if response.status else None,
                        headers=dict(response.headers),
                        latency_ms=latency,
                        request_id=req_id,
                        total_retries=retry_count,
                    )
                self._circuit_breaker.record_success(url)
                try:
                    response_data = await response.json()
                except Exception:
                    response_data = await response.text()
                return ApiResponse(
                    success=200 <= response.status < 300,
                    status_code=response.status,
                    data=response_data,
                    headers=dict(response.headers),
                    latency_ms=latency,
                    request_id=req_id,
                    total_retries=retry_count,
                )
        except aiohttp.ClientError as e:
            self._total_errors += 1
            self._circuit_breaker.record_failure(url)
            latency = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            fallback_url = self._fallback_manager.get_available_endpoint()
            if fallback_url and fallback_url != url:
                self._total_fallbacks += 1
                return await self.request(
                    method, fallback_url, headers, params, json, data, retry_count, req_id
                )
            if retry_count < self._retry_config.max_retries:
                backoff = self._calculate_backoff(retry_count, None)
                await asyncio.sleep(backoff)
                return await self.request(
                    method, url, headers, params, json, data, retry_count + 1, req_id
                )
            return ApiResponse(
                success=False,
                status_code=0,
                error=str(e),
                latency_ms=latency,
                request_id=req_id,
                total_retries=retry_count,
            )
        except Exception as e:
            self._total_errors += 1
            latency = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            return ApiResponse(
                success=False,
                status_code=0,
                error=str(e),
                latency_ms=latency,
                request_id=req_id,
            )

    def _should_retry(self, status_code: int, retry_count: int) -> bool:
        """Determine if request should be retried."""
        if retry_count >= self._retry_config.max_retries:
            return False
        return status_code in (429, 500, 502, 503, 504)

    def _calculate_backoff(self, retry_count: int, retry_after_ms: int | None = None) -> float:
        """Calculate backoff delay with jitter."""
        if self._retry_config.strategy == RetryStrategy.EXPONENTIAL:
            delay = self._retry_config.initial_delay_ms * (
                self._retry_config.backoff_multiplier**retry_count
            )
        elif self._retry_config.strategy == RetryStrategy.LINEAR:
            delay = self._retry_config.initial_delay_ms * (retry_count + 1)
        elif self._retry_config.strategy == RetryStrategy.FIBONACCI:
            fib_vals = [1, 1, 2, 3, 5, 8, 13, 21, 34]
            idx = min(retry_count, len(fib_vals) - 1)
            delay = self._retry_config.initial_delay_ms * fib_vals[idx]
        else:
            delay = self._retry_config.initial_delay_ms
        delay = min(delay, self._retry_config.max_delay_ms)
        if self._retry_config.jitter:
            jitter_range = delay * self._retry_config.jitter_factor
            delay += random.uniform(-jitter_range, jitter_range)  # noqa: S311
        if retry_after_ms:
            delay = max(delay, retry_after_ms)
        return delay / 1000.0

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> ApiResponse:
        """Execute GET request."""
        return await self.request("GET", url, headers, params)

    async def post(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
    ) -> ApiResponse:
        """Execute POST request."""
        return await self.request("POST", url, headers, json=json, data=data)

    async def put(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        json: Any = None,
        data: Any = None,
    ) -> ApiResponse:
        """Execute PUT request."""
        return await self.request("PUT", url, headers, json=json, data=data)

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> ApiResponse:
        """Execute DELETE request."""
        return await self.request("DELETE", url, headers)

    def get_metrics(self) -> dict[str, Any]:
        """Get aggregated client metrics."""
        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "total_rate_limits": self._total_rate_limits,
            "total_circuit_breaks": self._total_circuit_breaks,
            "total_fallbacks": self._total_fallbacks,
        }
