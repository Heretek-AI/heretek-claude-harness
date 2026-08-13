"""
NATS mTLS / SSL context helpers — extracted from
``gateway/nats_event_mesh.py`` as part of Phase 2.5 of
PLAN.md (§1.4 god-class extraction; the audit's exit
criterion for Phase 2 is "largest file < 1,000 LOC" and
``nats_event_mesh.py`` is 1,804 LOC).

This module owns the cert-loading and SSL-context-building
concerns. The function ``build_mtls_ssl_context()`` is a
free function that takes the cert paths (or the agent
identity) and returns an ``ssl.SSLContext``. The temp-file
lifecycle is captured in the ``MTLSContextHandle`` context
manager so the tempfiles are cleaned up automatically.

Backwards compatibility: the legacy method
``NATSEventMesh._build_ssl_context`` is preserved as a
thin delegate to ``build_mtls_ssl_context`` so existing
call sites work unchanged.
"""

from __future__ import annotations

import logging
import os
import ssl
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("heretek_swarm.gateway.nats_tls")


@contextmanager
def _temp_pem_files(
    ca_cert_str: str,
    cert_str: str,
    key_str: str,
    prefix: str,
) -> Iterator[tuple[str, str, str]]:
    """Write three PEM strings to tempfiles and yield the paths.

    Cleanup is automatic via the context-manager. Used by
    :func:`build_mtls_ssl_context` to materialize the cert
    data the ``ssl`` module needs.
    """
    paths: list[str] = []

    def _write(data: str, name: str) -> str:
        fd, path = tempfile.mkstemp(suffix=".pem", prefix=prefix + name + "_")
        with os.fdopen(fd, "w") as f:
            f.write(data)
        paths.append(path)
        return path

    try:
        yield (
            _write(ca_cert_str, "ca"),
            _write(cert_str, "cert"),
            _write(key_str, "key"),
        )
    finally:
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass


def _load_agent_certs(agent_id: str) -> tuple[str, str, str]:
    """Load (ca_cert, agent_cert, agent_key) PEM strings from
    ``secrets/certs.yaml`` via :class:`CertificateAuthority`."""
    from heretek_swarm.infrastructure.nats.ca import CertificateAuthority

    ca = CertificateAuthority()
    agent_result = ca.issue_agent_cert(agent_id)
    return ca.ca_cert_pem, agent_result["cert"], agent_result["key"]


def build_mtls_ssl_context(
    *,
    tls_ca_file: str | None = None,
    tls_cert_file: str | None = None,
    tls_key_file: str | None = None,
    client_name: str | None = None,
) -> ssl.SSLContext:
    """Build an :class:`ssl.SSLContext` for mTLS connections
    to the NATS server.

    Resolution order for the cert data:
    1. If all three of ``tls_ca_file``, ``tls_cert_file``,
       ``tls_key_file`` are set, read the PEM files from
       disk.
    2. Otherwise fall back to
       :class:`CertificateAuthority.issue_agent_cert` using
       ``client_name`` (or 'heretek-swarm' if unset) as the
       agent id.

    The dev/prod verification mode is picked from the
    ``ENVIRONMENT`` env var (default ``development``):
    - ``development`` → :func:`ssl._create_unverified_context`
      (uvloop's nats-py doesn't propagate verify_flags
      correctly for self-signed CAs)
    - any other value → :class:`ssl.SSLContext` with
      ``verify_mode = ssl.CERT_REQUIRED`` and the CA loaded

    ``HERETEK_TLS_SKIP_HOSTNAME_VERIFY=1`` disables hostname
    checking (do not use in production).

    The returned context has
    ``minimum_version = TLSv1_2``.
    """
    if tls_ca_file and tls_cert_file and tls_key_file:
        ca_cert_str = Path(tls_ca_file).read_text(encoding="utf-8")
        cert_str = Path(tls_cert_file).read_text(encoding="utf-8")
        key_str = Path(tls_key_file).read_text(encoding="utf-8")
    else:
        ca_cert_str, cert_str, key_str = _load_agent_certs(
            client_name or "heretek-swarm"
        )

    with _temp_pem_files(
        ca_cert_str, cert_str, key_str, prefix="heretek_mesh_"
    ) as (ca_cert_path, cert_path, key_path):
        env = os.getenv("ENVIRONMENT", "development")
        if env == "development":
            ssl_ctx: ssl.SSLContext = ssl._create_unverified_context()
        else:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_ctx.verify_mode = ssl.CERT_REQUIRED
            ssl_ctx.load_verify_locations(cafile=ca_cert_path)
        ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        skip_verify = os.getenv(
            "HERETEK_TLS_SKIP_HOSTNAME_VERIFY", ""
        ).lower() in ("1", "true", "yes")
        ssl_ctx.check_hostname = not skip_verify

        logger.debug(
            "ssl_context_built_for_mtls",
            ca_cert_path=ca_cert_path,
            cert_path=cert_path,
            key_path=key_path,
            verify_mode=str(ssl_ctx.verify_mode),
        )
        if ssl_ctx.verify_mode == ssl.CERT_NONE:
            logger.warning(
                "nats_tls_dev_mode_unverified_cert",
                message=(
                    "mTLS enabled with self-signed dev CA (verify_mode=CERT_NONE). "
                    "Production must use a real CA and cannot use "
                    "_create_unverified_context."
                ),
            )
        return ssl_ctx


__all__ = [
    "build_mtls_ssl_context",
]
