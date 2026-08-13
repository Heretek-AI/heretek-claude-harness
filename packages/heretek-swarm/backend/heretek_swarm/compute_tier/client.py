"""
Typed HTTP client for the compute tier service.

Used by the Sentinel's AnomalyMonitor to query the host's compute
capacity before responding to anomalies.  The client is deliberately
conservative: any failure (timeout, non-200, bad JSON) falls back to
Tier 1 so the anomaly pipeline is never blocked by a tier query.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger("compute_tier.client")

FALLBACK_RESULT = (1, 1, 0.0, False)

# Keep default timeout tight — tier queries are background enrichment,
# not gating calls; the anomaly pipeline must never stall on them.
DEFAULT_TIMEOUT = 0.5


@dataclass
class ComputeTierResult:
    """Immutable result from a compute tier query.

    Attributes:
        tier: Classified tier (1 = low, 2 = medium, 3 = high).
        cpu_count: Logical CPU count reported by the tier service.
        total_ram_gb: Total physical RAM in GiB.
        gpu_available: Whether a CUDA-capable GPU was detected.
    """

    tier: int
    cpu_count: int
    total_ram_gb: float
    gpu_available: bool


class ComputeTierClient:
    """Async client that queries ``GET /api/compute/tier``.

    Parameters:
        base_url: Root URL of the swarm API (default ``http://localhost:8000``).
        timeout: HTTP request timeout in seconds (default 0.5 s).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._endpoint = f"{self._base_url}/api/compute/tier"

    async def get_tier(self) -> ComputeTierResult:
        """Query the compute tier service and return a typed result.

        On *any* failure the client logs two structured events and
        returns a Tier-1 fallback so callers never need a try/except
        around this method.

        Returns:
            ``ComputeTierResult`` from the live service, or a Tier-1
            fallback when the service is unreachable.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(self._endpoint)
        except httpx.TimeoutException:
            return self._fallback("timeout")
        except httpx.ConnectError:
            return self._fallback("connection refused")
        except httpx.RequestError:
            return self._fallback("request error")
        except Exception:
            return self._fallback("unexpected error")

        if resp.status_code != 200:
            return self._fallback(f"HTTP {resp.status_code}")

        try:
            data = resp.json()
        except Exception:
            return self._fallback("invalid JSON response")

        try:
            result = ComputeTierResult(
                tier=int(data["tier"]),
                cpu_count=int(data["details"]["cpu_count"]),
                total_ram_gb=float(data["details"]["total_ram_gb"]),
                gpu_available=bool(data["details"]["gpu_available"]),
            )
        except (KeyError, TypeError, ValueError):
            return self._fallback("malformed response payload")

        logger.info(
            "compute_tier_queried",
            tier=result.tier,
            cpu_count=result.cpu_count,
            total_ram_gb=result.total_ram_gb,
            gpu_available=result.gpu_available,
        )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fallback(self, reason: str) -> ComputeTierResult:
        logger.warning(
            "compute_tier_service_unreachable",
            reason=reason,
        )
        logger.warning(
            "compute_tier_fallback_tier_1",
            reason=reason,
        )
        return ComputeTierResult(*FALLBACK_RESULT)
