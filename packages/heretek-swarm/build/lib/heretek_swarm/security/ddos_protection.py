"""
Enhanced Rate Limiting and DDoS Protection Module for Heretek Swarm (SH-3)

Implements comprehensive rate limiting and DDoS protection:
- Tiered Rate Limiting (4 tiers: anonymous, authenticated, premium, internal)
- Token Bucket Algorithm with configurable refill rates
- Distributed Rate Limiting with Redis backend
- DDoS Detection (request spikes, geographic anomalies, pattern attacks)
- Mitigation Strategies (temporary blocks, IP blocklist, geo-fencing)

Reference: EXPANSION_ROADMAP.md SH-3 Rate Limiting/DDoS
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class UserTier(StrEnum):
    """User tier for rate limiting."""

    ANONYMOUS = "anonymous"
    AUTHENTICATED = "authenticated"
    PREMIUM = "premium"
    INTERNAL = "internal"


class DDoSSeverity(StrEnum):
    """DDoS attack severity levels."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MitigationAction(StrEnum):
    """Mitigation actions for DDoS attacks."""

    NONE = "none"
    THROTTLE = "throttle"
    CHALLENGE = "challenge"  # CAPTCHA or similar
    TEMP_BLOCK = "temp_block"
    PERM_BLOCK = "perm_block"
    GEO_BLOCK = "geo_block"


# =============================================================================
# Configuration Classes
# =============================================================================


@dataclass
class TierConfig:
    """Rate limit configuration for a user tier."""

    requests_per_second: int
    requests_per_minute: int
    requests_per_hour: int
    burst_size: int  # Token bucket burst capacity

    @classmethod
    def anonymous(cls) -> "TierConfig":
        return cls(
            requests_per_second=10,
            requests_per_minute=100,
            requests_per_hour=1000,
            burst_size=20,
        )

    @classmethod
    def authenticated(cls) -> "TierConfig":
        return cls(
            requests_per_second=30,
            requests_per_minute=500,
            requests_per_hour=5000,
            burst_size=50,
        )

    @classmethod
    def premium(cls) -> "TierConfig":
        return cls(
            requests_per_second=100,
            requests_per_minute=2000,
            requests_per_hour=20000,
            burst_size=200,
        )

    @classmethod
    def internal(cls) -> "TierConfig":
        return cls(
            requests_per_second=500,
            requests_per_minute=10000,
            requests_per_hour=100000,
            burst_size=1000,
        )


@dataclass
class RateLimitConfig:
    """Overall rate limiting configuration."""

    tiers: dict[UserTier, TierConfig] = field(
        default_factory=lambda: {
            UserTier.ANONYMOUS: TierConfig.anonymous(),
            UserTier.AUTHENTICATED: TierConfig.authenticated(),
            UserTier.PREMIUM: TierConfig.premium(),
            UserTier.INTERNAL: TierConfig.internal(),
        }
    )
    enable_token_bucket: bool = True
    enable_sliding_window: bool = True
    enable_redis_backend: bool = True
    redis_url: str | None = None
    fallback_to_memory: bool = True
    key_prefix: str = "heretek_swarm:ratelimit:"


@dataclass
class DDoSDetectionConfig:
    """DDoS detection configuration."""

    enable_spike_detection: bool = True
    enable_geo_anomaly: bool = True
    enable_pattern_detection: bool = True
    enable_resource_monitoring: bool = True

    # Spike detection thresholds
    spike_multiplier: float = 10.0  # Alert if > 10x baseline
    spike_window_seconds: int = 30

    # Geographic anomaly thresholds
    max_countries: int = 50  # Alert if requests from > 50 countries

    # Pattern attack thresholds
    identical_request_threshold: int = 100  # Alert if > 100 identical requests/s

    # Resource exhaustion thresholds
    cpu_threshold_percent: float = 90.0
    memory_threshold_percent: float = 85.0

    # Detection window
    detection_window_seconds: int = 30


@dataclass
class MitigationConfig:
    """DDoS mitigation configuration."""

    enable_temp_blocks: bool = True
    enable_ip_blocklist: bool = True
    enable_geo_fencing: bool = False  # Disabled by default
    enable_emergency_throttle: bool = True

    # Block durations
    temp_block_duration_seconds: int = 300  # 5 minutes
    perm_block_requires_incidents: int = 3  # 3 temp blocks = perm block

    # Emergency throttle settings
    emergency_throttle_percent: int = 50  # Reduce to 50% capacity

    # False positive threshold
    max_false_positive_rate: float = 0.001  # < 0.1%


# =============================================================================
# Rate Limit Result
# =============================================================================


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    tier: UserTier
    remaining_tokens: int
    remaining_minute: int
    remaining_hour: int
    reset_seconds: int
    retry_after: int | None = None
    key: str | None = None

    def to_headers(self) -> dict[str, str]:
        """Convert to HTTP headers."""
        headers = {
            "X-RateLimit-Limit": str(self.tier.value),
            "X-RateLimit-Remaining": str(self.remaining_minute),
            "X-RateLimit-Reset": str(self.reset_seconds),
        }
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        return headers


@dataclass
class DDoSDetectionResult:
    """Result of DDoS detection analysis."""

    is_attack: bool
    severity: DDoSSeverity
    attack_type: list[str]
    affected_ips: list[str]
    confidence: float
    recommended_action: MitigationAction
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# =============================================================================
# Token Bucket Implementation
# =============================================================================


class TokenBucket:
    """
    Token bucket algorithm implementation.

    Allows burst traffic up to bucket capacity while maintaining
    average rate limit through token refill.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,  # tokens per second
    ):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._tokens: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_refill)
        self._lock = asyncio.Lock()

    async def consume(
        self,
        key: str,
        tokens: int = 1,
    ) -> tuple[bool, int]:
        """
        Try to consume tokens from the bucket.

        Args:
            key: Unique identifier for the bucket
            tokens: Number of tokens to consume

        Returns:
            (success, remaining_tokens)
        """
        async with self._lock:
            now = time.time()

            # Get or create bucket
            if key not in self._tokens:
                self._tokens[key] = (float(self.capacity), now)

            current_tokens, last_refill = self._tokens[key]

            # Refill tokens
            elapsed = now - last_refill
            new_tokens = current_tokens + (elapsed * self.refill_rate)
            current_tokens = min(new_tokens, float(self.capacity))

            # Try to consume
            if current_tokens >= tokens:
                current_tokens -= tokens
                self._tokens[key] = (current_tokens, now)
                return True, int(current_tokens)
            self._tokens[key] = (current_tokens, now)
            return False, int(current_tokens)

    def get_tokens(self, key: str) -> int:
        """Get current token count for a key."""
        if key not in self._tokens:
            return self.capacity

        now = time.time()
        current_tokens, last_refill = self._tokens[key]
        elapsed = now - last_refill
        new_tokens = current_tokens + (elapsed * self.refill_rate)
        return int(min(new_tokens, float(self.capacity)))


# =============================================================================
# Rate Limiter Implementation
# =============================================================================


class RateLimiter:
    """
    Comprehensive rate limiter with tiered limits and token bucket.

    Features:
    - 4-tier rate limiting (anonymous, authenticated, premium, internal)
    - Token bucket algorithm for burst handling
    - Sliding window for minute/hour limits
    - Redis backend for distributed rate limiting
    - Graceful fallback to in-memory

    Target Performance:
    - Rate limit check latency < 10ms p95
    - Support > 10,000 requests/second
    - No impact on legitimate traffic
    """

    def __init__(
        self,
        config: RateLimitConfig | None = None,
        redis_client: Any | None = None,
    ):
        self.config = config or RateLimitConfig()
        self._redis = redis_client
        self._redis_available = False

        # In-memory fallback storage
        self._request_counts: dict[str, list[float]] = defaultdict(list)
        self._token_buckets: dict[UserTier, TokenBucket] = {}

        # Initialize token buckets for each tier
        for tier, tier_config in self.config.tiers.items():
            self._token_buckets[tier] = TokenBucket(
                capacity=tier_config.burst_size,
                refill_rate=float(tier_config.requests_per_second),
            )

        # Metrics
        self._check_count = 0
        self._total_latency_ms = 0.0
        self._blocked_count = 0

        # Try to connect to Redis if enabled
        if self.config.enable_redis_backend and self._redis is None:
            self._init_redis()

    def _init_redis(self):
        """Initialize Redis connection."""
        try:
            import redis.asyncio  # noqa: F401

            # Will be initialized on first use
            self._redis = None  # Lazy init
            self._redis_available = True
        except ImportError:
            logger.warning("redis not installed - using in-memory rate limiting")
            self._redis_available = False

    async def check_rate_limit(
        self,
        identifier: str,
        tier: UserTier = UserTier.ANONYMOUS,
        endpoint: str | None = None,
    ) -> RateLimitResult:
        """
        Check if request is allowed under rate limits.

        Args:
            identifier: Unique identifier (IP, user ID, etc.)
            tier: User tier for rate limit
            endpoint: Optional endpoint for per-endpoint limits

        Returns:
            RateLimitResult with allow status and remaining limits
        """
        start_time = time.time()
        tier_config = self.config.tiers[tier]

        # Build key
        key_parts = [self.config.key_prefix, tier.value, identifier]
        if endpoint:
            key_parts.append(endpoint)
        key = ":".join(key_parts)

        # Check token bucket (for burst control)
        if self.config.enable_token_bucket:
            bucket = self._token_buckets[tier]
            allowed, remaining_tokens = await bucket.consume(key)
        else:
            allowed, remaining_tokens = True, tier_config.burst_size

        # Check sliding window limits
        minute_key = f"{key}:minute"
        hour_key = f"{key}:hour"

        minute_allowed, minute_remaining, minute_reset = await self._check_sliding_window(
            minute_key,
            tier_config.requests_per_minute,
            60,
        )

        hour_allowed, hour_remaining, hour_reset = await self._check_sliding_window(
            hour_key,
            tier_config.requests_per_hour,
            3600,
        )

        # Determine overall allow
        overall_allowed = allowed and minute_allowed and hour_allowed

        # Calculate retry-after
        retry_after = None
        if not overall_allowed:
            retry_after = max(
                minute_reset if not minute_allowed else 0,
                hour_reset if not hour_allowed else 0,
            )

        # Update metrics
        latency_ms = (time.time() - start_time) * 1000
        self._check_count += 1
        self._total_latency_ms += latency_ms
        if not overall_allowed:
            self._blocked_count += 1

        return RateLimitResult(
            allowed=overall_allowed,
            tier=tier,
            remaining_tokens=remaining_tokens,
            remaining_minute=minute_remaining,
            remaining_hour=hour_remaining,
            reset_seconds=max(minute_reset, hour_reset),
            retry_after=retry_after,
            key=key,
        )

    async def _check_sliding_window(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check sliding window rate limit.

        Returns:
            (allowed, remaining, reset_seconds)
        """
        now = time.time()
        window_start = now - window_seconds

        # Clean old requests
        self._request_counts[key] = [t for t in self._request_counts[key] if t > window_start]

        current_count = len(self._request_counts[key])

        if current_count >= limit:
            # Calculate reset time
            oldest = min(self._request_counts[key]) if self._request_counts[key] else now
            reset_in = int(oldest + window_seconds - now)
            return False, 0, max(0, reset_in)

        # Record request
        self._request_counts[key].append(now)
        remaining = limit - len(self._request_counts[key])
        reset_in = window_seconds

        return True, remaining, reset_in

    async def reset(self, identifier: str, tier: UserTier = UserTier.ANONYMOUS):
        """Reset rate limits for an identifier."""
        key = f"{self.config.key_prefix}:{tier.value}:{identifier}"

        # Clear sliding windows
        self._request_counts.pop(f"{key}:minute", None)
        self._request_counts.pop(f"{key}:hour", None)

        # Reset token bucket
        bucket = self._token_buckets[tier]
        async with bucket._lock:  # noqa: SLF001
            bucket._tokens.pop(key, None)  # noqa: SLF001

    def get_metrics(self) -> dict[str, Any]:
        """Get rate limiter metrics."""
        avg_latency = self._total_latency_ms / self._check_count if self._check_count > 0 else 0

        return {
            "total_checks": self._check_count,
            "blocked_requests": self._blocked_count,
            "block_rate": (self._blocked_count / self._check_count if self._check_count > 0 else 0),
            "avg_latency_ms": avg_latency,
            "active_keys": len(self._request_counts),
        }


# =============================================================================
# DDoS Detector Implementation
# =============================================================================


class DDoSDetector:
    """
    DDoS attack detection system.

    Detects:
    - Request spikes (> 10x baseline)
    - Geographic anomalies (> 50 countries)
    - Pattern attacks (> 100 identical requests/s)
    - Resource exhaustion (CPU > 90%)

    Target Performance:
    - Detection within 30 seconds
    - False positive rate < 0.1%
    """

    def __init__(
        self,
        config: DDoSDetectionConfig | None = None,
    ):
        self.config = config or DDoSDetectionConfig()

        # Baseline tracking
        self._request_history: list[tuple[float, str, str]] = []  # (time, ip, request_hash)
        self._baseline_rps: float = 0.0
        self._current_rps: float = 0.0

        # Geographic tracking
        self._country_counts: dict[str, int] = defaultdict(int)

        # Pattern tracking
        self._request_patterns: dict[str, int] = defaultdict(int)

        # Metrics
        self._detection_count = 0
        self._attack_count = 0

    def record_request(
        self,
        ip: str,
        request_hash: str,
        country: str | None = None,
    ):
        """Record a request for DDoS analysis."""
        now = time.time()

        # Record request
        self._request_history.append((now, ip, request_hash))

        # Update pattern count
        self._request_patterns[request_hash] += 1

        # Update country count
        if country:
            self._country_counts[country] += 1

        # Clean old requests (outside detection window)
        cutoff = now - self.config.detection_window_seconds
        while self._request_history and self._request_history[0][0] < cutoff:
            _old_time, _old_ip, old_hash = self._request_history.pop(0)
            self._request_patterns[old_hash] -= 1
            if self._request_patterns[old_hash] <= 0:
                del self._request_patterns[old_hash]

        # Update RPS
        window_requests = len(self._request_history)
        self._current_rps = window_requests / self.config.detection_window_seconds

        # Update baseline (exponential moving average)
        if self._baseline_rps == 0:
            self._baseline_rps = self._current_rps
        else:
            alpha = 0.01  # Slow baseline update
            self._baseline_rps = alpha * self._current_rps + (1 - alpha) * self._baseline_rps

    def detect(self) -> DDoSDetectionResult:
        """
        Analyze current traffic for DDoS attacks.

        Returns:
            DDoSDetectionResult with attack status and details
        """
        self._detection_count += 1
        attack_indicators = []
        affected_ips: set[str] = set()
        details: dict[str, Any] = {}

        # Check for request spike
        if self.config.enable_spike_detection and self._baseline_rps > 0:
            spike_ratio = self._current_rps / max(self._baseline_rps, 0.1)
            if spike_ratio > self.config.spike_multiplier:
                attack_indicators.append("request_spike")
                details["spike_ratio"] = spike_ratio
                details["current_rps"] = self._current_rps
                details["baseline_rps"] = self._baseline_rps

        # Check for geographic anomaly
        if self.config.enable_geo_anomaly:
            unique_countries = len(self._country_counts)
            if unique_countries > self.config.max_countries:
                attack_indicators.append("geo_anomaly")
                details["unique_countries"] = unique_countries

        # Check for pattern attack
        if self.config.enable_pattern_detection:
            for count in self._request_patterns.values():
                if count > self.config.identical_request_threshold:
                    attack_indicators.append("pattern_attack")
                    details["max_pattern_count"] = count
                    break

        # Determine severity and action
        is_attack = len(attack_indicators) > 0

        if is_attack:
            self._attack_count += 1
            severity = self._calculate_severity(len(attack_indicators))
            action = self._determine_action(severity)
        else:
            severity = DDoSSeverity.NONE
            action = MitigationAction.NONE

        # Get affected IPs from recent requests
        cutoff = time.time() - self.config.detection_window_seconds
        for req_time, ip, _ in self._request_history:
            if req_time >= cutoff:
                affected_ips.add(ip)

        return DDoSDetectionResult(
            is_attack=is_attack,
            severity=severity,
            attack_type=attack_indicators,
            affected_ips=list(affected_ips),
            confidence=min(len(attack_indicators) * 0.4, 1.0),
            recommended_action=action,
            details=details,
        )

    def _calculate_severity(self, indicator_count: int) -> DDoSSeverity:
        """Calculate attack severity from indicator count."""
        if indicator_count >= 3:
            return DDoSSeverity.CRITICAL
        if indicator_count == 2:
            return DDoSSeverity.HIGH
        if indicator_count == 1:
            return DDoSSeverity.MEDIUM
        return DDoSSeverity.LOW

    def _determine_action(self, severity: DDoSSeverity) -> MitigationAction:
        """Determine mitigation action from severity."""
        if severity == DDoSSeverity.CRITICAL:
            return MitigationAction.PERM_BLOCK
        if severity == DDoSSeverity.HIGH:
            return MitigationAction.TEMP_BLOCK
        if severity == DDoSSeverity.MEDIUM:
            return MitigationAction.THROTTLE
        if severity == DDoSSeverity.LOW:
            return MitigationAction.CHALLENGE
        return MitigationAction.NONE

    def get_metrics(self) -> dict[str, Any]:
        """Get detector metrics."""
        return {
            "total_detections": self._detection_count,
            "attacks_detected": self._attack_count,
            "current_rps": self._current_rps,
            "baseline_rps": self._baseline_rps,
            "active_patterns": len(self._request_patterns),
            "unique_countries": len(self._country_counts),
        }


# =============================================================================
# DDoS Mitigator Implementation
# =============================================================================


class DDoSMitigator:
    """
    DDoS attack mitigation system.

    Features:
    - Temporary IP blocks
    - IP blocklist management
    - Geo-fencing capability
    - Emergency throttling
    - False positive rate < 0.1%
    """

    def __init__(
        self,
        config: MitigationConfig | None = None,
    ):
        self.config = config or MitigationConfig()

        # Block lists
        self._temp_blocks: dict[str, float] = {}  # IP -> expiry time
        self._perm_blocks: set[str] = set()
        self._blocked_countries: set[str] = set()

        # Incident tracking
        self._incident_count: dict[str, int] = defaultdict(int)

        # Emergency throttle state
        self._emergency_throttle_active = False
        self._throttle_factor = 1.0

        # Metrics
        self._blocks_applied = 0
        self._blocks_expired = 0

    def is_blocked(self, ip: str, country: str | None = None) -> tuple[bool, str]:
        """
        Check if an IP is blocked.

        Returns:
            (is_blocked, reason)
        """
        # Check permanent block
        if ip in self._perm_blocks:
            return True, "permanent_block"

        # Check temporary block
        if ip in self._temp_blocks:
            if time.time() < self._temp_blocks[ip]:
                return True, "temporary_block"
            # Expired
            del self._temp_blocks[ip]
            self._blocks_expired += 1

        # Check geo-fencing
        if country and country in self._blocked_countries:
            return True, "geo_block"

        return False, ""

    def apply_mitigation(
        self,
        detection_result: DDoSDetectionResult,
        config: MitigationConfig | None = None,
    ) -> dict[str, Any]:
        """
        Apply mitigation based on detection result.

        Returns:
            Mitigation action summary
        """
        config = config or self.config
        action = detection_result.recommended_action
        actions_taken = []

        if action == MitigationAction.NONE:
            return {"action": "none", "actions_taken": []}

        for ip in detection_result.affected_ips:
            if action == MitigationAction.TEMP_BLOCK:
                if config.enable_temp_blocks:
                    self._temp_blocks[ip] = time.time() + config.temp_block_duration_seconds
                    self._incident_count[ip] += 1
                    actions_taken.append(f"temp_block:{ip}")
                    self._blocks_applied += 1

                    # Check for permanent block threshold
                    if self._incident_count[ip] >= config.perm_block_requires_incidents:
                        self._perm_blocks.add(ip)
                        actions_taken.append(f"perm_block:{ip}")

            elif action == MitigationAction.PERM_BLOCK and config.enable_ip_blocklist:
                self._perm_blocks.add(ip)
                actions_taken.append(f"perm_block:{ip}")
                self._blocks_applied += 1

        if action == MitigationAction.GEO_BLOCK and config.enable_geo_fencing:
            # Block countries with high traffic
            for country, count in detection_result.details.get("country_counts", {}).items():
                if count > 100:  # Threshold
                    self._blocked_countries.add(country)
                    actions_taken.append(f"geo_block:{country}")

        if action == MitigationAction.THROTTLE and config.enable_emergency_throttle:
            self._emergency_throttle_active = True
            self._throttle_factor = config.emergency_throttle_percent / 100.0
            actions_taken.append("emergency_throttle")

        return {
            "action": action.value,
            "actions_taken": actions_taken,
            "affected_count": len(detection_result.affected_ips),
        }

    def unblock(self, ip: str):
        """Remove all blocks for an IP."""
        self._temp_blocks.pop(ip, None)
        self._perm_blocks.discard(ip)
        self._incident_count.pop(ip, None)

    def get_throttle_factor(self) -> float:
        """Get current throttle factor (1.0 = no throttle)."""
        return self._throttle_factor

    def clear_emergency_throttle(self):
        """Clear emergency throttle state."""
        self._emergency_throttle_active = False
        self._throttle_factor = 1.0

    def cleanup_expired(self):
        """Clean up expired temporary blocks."""
        now = time.time()
        expired = [ip for ip, expiry in self._temp_blocks.items() if now >= expiry]
        for ip in expired:
            del self._temp_blocks[ip]
            self._blocks_expired += 1

    def get_metrics(self) -> dict[str, Any]:
        """Get mitigator metrics."""
        return {
            "temp_blocks_active": len(self._temp_blocks),
            "perm_blocks_active": len(self._perm_blocks),
            "blocked_countries": len(self._blocked_countries),
            "total_blocks_applied": self._blocks_applied,
            "total_blocks_expired": self._blocks_expired,
            "emergency_throttle_active": self._emergency_throttle_active,
            "throttle_factor": self._throttle_factor,
        }


# =============================================================================
# Unified DDoS Protection System
# =============================================================================


class DDoSProtection:
    """
    Unified DDoS protection system combining rate limiting, detection, and mitigation.

    Features:
    - Tiered rate limiting with token bucket
    - Real-time DDoS detection
    - Automatic mitigation
    - Comprehensive metrics
    """

    def __init__(
        self,
        rate_limit_config: RateLimitConfig | None = None,
        detection_config: DDoSDetectionConfig | None = None,
        mitigation_config: MitigationConfig | None = None,
    ):
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.detector = DDoSDetector(detection_config)
        self.mitigator = DDoSMitigator(mitigation_config)

    async def check_request(
        self,
        ip: str,
        tier: UserTier = UserTier.ANONYMOUS,
        endpoint: str | None = None,
        country: str | None = None,
        request_hash: str | None = None,
    ) -> tuple[RateLimitResult, DDoSDetectionResult | None]:
        """
        Check a request against rate limits and DDoS protection.

        Args:
            ip: Client IP address
            tier: User tier
            endpoint: Request endpoint
            country: Client country (for geo-fencing)
            request_hash: Hash of request for pattern detection

        Returns:
            (rate_limit_result, ddos_detection_result)
        """
        # Check if blocked
        is_blocked, _block_reason = self.mitigator.is_blocked(ip, country)
        if is_blocked:
            return RateLimitResult(
                allowed=False,
                tier=tier,
                remaining_tokens=0,
                remaining_minute=0,
                remaining_hour=0,
                reset_seconds=300,
                retry_after=300,
            ), None

        # Check rate limit
        rate_result = await self.rate_limiter.check_rate_limit(ip, tier, endpoint)

        # Record for DDoS analysis
        if request_hash:
            self.detector.record_request(ip, request_hash, country)

        # Run DDoS detection periodically
        ddos_result = None
        if self.detector._detection_count % 100 == 0:  # Every 100 requests  # noqa: SLF001
            ddos_result = self.detector.detect()
            if ddos_result.is_attack:
                self.mitigator.apply_mitigation(ddos_result)
                logger.warning(
                    "ddos_attack_detected",
                    severity=ddos_result.severity.value,
                    attack_type=ddos_result.attack_type,
                    affected_ips=len(ddos_result.affected_ips),
                )

        # Apply throttle factor if active
        # NOTE: random for emergency throttle decision - not security-critical (rate limit, not crypto)  # noqa: E501
        if self.mitigator._emergency_throttle_active:  # noqa: SLF001
            import random

            if random.random() > self.mitigator.get_throttle_factor():  # noqa: S311
                return RateLimitResult(
                    allowed=False,
                    tier=tier,
                    remaining_tokens=0,
                    remaining_minute=0,
                    remaining_hour=0,
                    reset_seconds=60,
                    retry_after=60,
                ), ddos_result

        return rate_result, ddos_result

    def get_all_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics from all components."""
        return {
            "rate_limiter": self.rate_limiter.get_metrics(),
            "detector": self.detector.get_metrics(),
            "mitigator": self.mitigator.get_metrics(),
        }


# =============================================================================
# Convenience Functions
# =============================================================================


def create_default_protection() -> DDoSProtection:
    """Create DDoS protection with default configuration."""
    return DDoSProtection(
        rate_limit_config=RateLimitConfig(),
        detection_config=DDoSDetectionConfig(),
        mitigation_config=MitigationConfig(),
    )


def create_strict_protection() -> DDoSProtection:
    """Create DDoS protection with strict configuration."""
    return DDoSProtection(
        rate_limit_config=RateLimitConfig(
            tiers={
                UserTier.ANONYMOUS: TierConfig(
                    requests_per_second=5,
                    requests_per_minute=30,
                    requests_per_hour=300,
                    burst_size=10,
                ),
                UserTier.AUTHENTICATED: TierConfig.authenticated(),
                UserTier.PREMIUM: TierConfig.premium(),
                UserTier.INTERNAL: TierConfig.internal(),
            }
        ),
        detection_config=DDoSDetectionConfig(
            spike_multiplier=5.0,  # More sensitive
            identical_request_threshold=50,
        ),
        mitigation_config=MitigationConfig(
            temp_block_duration_seconds=600,  # 10 minutes
            enable_geo_fencing=True,
        ),
    )
