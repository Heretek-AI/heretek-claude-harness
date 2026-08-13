"""
ProviderProbe Protocol — Phase 3.3 of PLAN.md (§1.4 god-class
extraction).

The audit's exit criterion for the config_api package
includes a ``ProviderProbe`` Protocol that gates LLM and
embedding provider validation through a common surface.
Today the wizard has ad-hoc provider-validation HTTP calls
inlined in the route handlers; this module ships the
Protocol that the new validators implement.

The Protocol is intentionally minimal: ``probe(provider_config)``
returns a :class:`ProbeResult` with a status, message, and
optional latency. Implementations can do an HTTP GET to the
provider's ``/models`` endpoint, a DNS lookup, a static
metadata check, or any combination.

This commit ships the Protocol and two reference
implementations:

* :class:`HttpProbe` — does a real HTTP ``GET /models`` call
  to the provider's base URL with a short timeout. Used
  in production for cloud providers.
* :class:`StaticProbe` — checks that the provider
  configuration is well-formed (URL is set, name is
  non-empty, model is non-empty). Used in dev and CI where
  real network calls are undesirable.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class ProbeStatus(str, Enum):
    """Outcome of a provider probe."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ProbeResult:
    """The output of a :class:`ProviderProbe.probe` call.

    Attributes
    ----------
    status:
        Overall status (healthy / degraded / unhealthy).
    message:
        Human-readable explanation (e.g. "GET /models → 200",
        "missing api_key", "timeout after 5s").
    latency_ms:
        Wall-clock duration of the probe call. ``0`` for
        static probes.
    details:
        Provider-specific additional information (e.g.
        model list from /models response).
    """

    status: ProbeStatus
    message: str
    latency_ms: float = 0.0
    details: dict[str, Any] | None = None


@runtime_checkable
class ProviderProbe(Protocol):
    """The minimum surface every provider probe must expose.

    Implementations:

    * :class:`HttpProbe` — real HTTP ``GET /models`` call.
    * :class:`StaticProbe` — configuration-only check
      (no network).
    * Custom probes can do DNS lookups, paid-API pings,
      test completions, etc.
    """

    async def probe(self, provider_config: dict[str, Any]) -> ProbeResult:
        """Probe the provider described by ``provider_config``.

        Args:
            provider_config: Provider metadata. Recognized keys:
                ``base_url`` (str), ``api_key`` (str | None),
                ``name`` (str), ``model`` (str), ``timeout``
                (float, default 5.0).

        Returns:
            A :class:`ProbeResult` describing the outcome.
        """
        ...


class HttpProbe:
    """Real HTTP probe — GET ``{base_url}/models`` with timeout."""

    def __init__(self, default_timeout: float = 5.0) -> None:
        self._default_timeout = default_timeout

    async def probe(self, provider_config: dict[str, Any]) -> ProbeResult:
        base_url = provider_config.get("base_url")
        if not base_url:
            return ProbeResult(
                status=ProbeStatus.UNHEALTHY,
                message="missing base_url",
            )
        timeout = float(provider_config.get("timeout", self._default_timeout))
        start = time.perf_counter()
        try:
            import httpx

            headers = {}
            api_key = provider_config.get("api_key")
            if api_key:
                # OpenAI-compatible auth header for most providers;
                # the per-provider adapter can override.
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{base_url.rstrip('/')}/models",
                    headers=headers,
                )
            duration_ms = (time.perf_counter() - start) * 1000.0

            if response.status_code == 200:
                return ProbeResult(
                    status=ProbeStatus.HEALTHY,
                    message=f"GET /models → 200 in {duration_ms:.0f}ms",
                    latency_ms=duration_ms,
                    details=(
                        response.json() if response.headers.get(
                            "content-type", ""
                        ).startswith("application/json") else None
                    ),
                )
            if response.status_code in (401, 403):
                return ProbeResult(
                    status=ProbeStatus.UNHEALTHY,
                    message=f"auth failed: {response.status_code}",
                    latency_ms=duration_ms,
                )
            if 400 <= response.status_code < 500:
                return ProbeResult(
                    status=ProbeStatus.DEGRADED,
                    message=f"client error: {response.status_code}",
                    latency_ms=duration_ms,
                )
            return ProbeResult(
                status=ProbeStatus.UNHEALTHY,
                message=f"server error: {response.status_code}",
                latency_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return ProbeResult(
                status=ProbeStatus.UNHEALTHY,
                message=f"{type(exc).__name__}: {exc}",
                latency_ms=duration_ms,
            )


class StaticProbe:
    """Configuration-only probe — no network."""

    REQUIRED_KEYS = ("name", "base_url", "model")

    async def probe(self, provider_config: dict[str, Any]) -> ProbeResult:
        missing = [k for k in self.REQUIRED_KEYS if not provider_config.get(k)]
        if missing:
            return ProbeResult(
                status=ProbeStatus.UNHEALTHY,
                message=f"missing required keys: {', '.join(missing)}",
            )
        return ProbeResult(
            status=ProbeStatus.HEALTHY,
            message="configuration valid",
            latency_ms=0.0,
            details={
                "name": provider_config["name"],
                "model": provider_config["model"],
            },
        )


# Default probe selection: HTTP when the host is reachable,
# static otherwise. The wizard / config CLI can override.
_default_probe: ProviderProbe | None = None


def get_default_probe() -> ProviderProbe:
    """Return the process-wide :class:`ProviderProbe`.

    Honors ``HERETEK_PROVIDER_PROBE`` env var:
    - ``http`` (default) — real HTTP probe
    - ``static`` — static probe (no network)
    """
    global _default_probe
    if _default_probe is None:
        kind = os.getenv("HERETEK_PROVIDER_PROBE", "http").lower()
        if kind == "static":
            _default_probe = StaticProbe()
        else:
            _default_probe = HttpProbe()
    return _default_probe


__all__ = [
    "ProviderProbe",
    "ProbeStatus",
    "ProbeResult",
    "HttpProbe",
    "StaticProbe",
    "get_default_probe",
]
