"""
NATS connection management — extracted from
``gateway/nats_event_mesh.py`` as part of Phase 2.5 of
PLAN.md (§1.4 god-class extraction; the audit's exit
criterion for Phase 2 is "largest file < 1,000 LOC" and
``nats_event_mesh.py`` is 1,804 LOC).

This module owns the connection concerns: connect-with-
retry, build-connect-kwargs, log-success / log-failure,
peer-cert extraction. They are mostly pure (no agent
state) and trivially testable in isolation.

Backwards compatibility: the legacy methods
``NATSEventMesh._connect_to_server``,
``_build_connect_kwargs``, ``_log_connection_success``, and
``_extract_peer_cert_subject`` are preserved as thin
delegates to the free functions in this module.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
from typing import Any, Callable

logger = logging.getLogger("heretek_swarm.gateway.nats_connection")


def build_connect_kwargs(
    *,
    client_name: str,
    reconnect_time_wait: float,
    ping_interval: float,
    max_outstanding_pings: int,
) -> dict[str, Any]:
    """Build the kwargs dict for ``nats.connect()``.

    The nats-py client manages reconnects on its own, so
    we cap ``max_reconnect_attempts=1`` here and own the
    retry loop in :func:`connect_with_retry`.
    """
    return {
        "name": client_name,
        "reconnect_time_wait": reconnect_time_wait,
        "ping_interval": ping_interval,
        "max_outstanding_pings": max_outstanding_pings,
        "max_reconnect_attempts": 1,
    }


def extract_peer_cert_subject(nc: Any) -> str:
    """Extract the peer certificate's commonName from a NATS
    connection's transport."""
    try:
        transport = getattr(nc, "_io_reader", None) or getattr(nc, "_transport", None)
        if transport is not None:
            sock = getattr(transport, "get_extra_info", None)
            if sock is not None:
                peer_cert = sock("peercert")
                if peer_cert is not None:
                    subject_attrs = peer_cert.get("subject", [])
                    cn = next(
                        (v for t, v in subject_attrs if t == "commonName"),
                        "unknown",
                    )
                    return cn
    except Exception:
        logger.debug("Could not extract peer certificate subject")
    return "unknown"


def log_connection_success(
    *,
    nc: Any,
    server_display: str,
    tls_enabled: bool,
    peer_cert_subject: str | None = None,
) -> None:
    """Log a successful connection. When TLS is enabled,
    includes the peer cert commonName for operator
    visibility."""
    if tls_enabled:
        logger.info(
            "nats_tls_connection_established",
            server=server_display,
            peer_cert_subject=peer_cert_subject,
        )
    else:
        logger.info("Connected to %s", server_display)


def log_connection_failure(
    *,
    server: str,
    error: Exception,
    attempt: int,
    tls_enabled: bool,
) -> None:
    """Log a connection failure. When TLS is enabled,
    uses the ``nats_tls_failed`` event key so the dev-mode
    warning is emitted by the existing alert surface."""
    if tls_enabled:
        logger.error("nats_tls_failed", server=server, error=str(error))
    logger.warning(
        "Failed to connect to %s",
        server,
        error=str(error),
        attempt=attempt + 1,
    )


async def connect_with_retry(
    *,
    servers: list[str],
    max_attempts: int,
    reconnect_time_wait: float,
    build_kwargs: Callable[[], dict[str, Any]],
    tls_context: ssl.SSLContext | None = None,
) -> Any:
    """Try each NATS server in turn, with ``max_attempts``
    retries per server, sleeping ``reconnect_time_wait``
    seconds between attempts. Returns the first successful
    connection or raises the last error.

    When ``tls_context`` is provided, the URL scheme is
    rewritten from ``nats://`` to ``tls://`` for that
    attempt so the nats client knows to use TLS.
    """
    import nats

    last_error: Exception | None = None

    for server in servers:
        for attempt in range(max_attempts):
            try:
                server_display = server
                logger.debug(
                    "Connecting to %s (attempt %d)", server, attempt + 1
                )

                kwargs = build_kwargs()
                if tls_context is not None:
                    kwargs["tls"] = tls_context
                    if server.startswith("nats://"):
                        server = server.replace("nats://", "tls://", 1)
                        server_display = server
                        logger.debug(
                            "mTLS enabled — using tls:// URL", server=server
                        )

                nc = await nats.connect(server, **kwargs)
                return nc

            except Exception as exc:
                last_error = exc
                log_connection_failure(
                    server=server_display,
                    error=exc,
                    attempt=attempt,
                    tls_enabled=tls_context is not None,
                )
                await asyncio.sleep(reconnect_time_wait)

    raise last_error or Exception("No servers available")


__all__ = [
    "build_connect_kwargs",
    "connect_with_retry",
    "extract_peer_cert_subject",
    "log_connection_failure",
    "log_connection_success",
]
