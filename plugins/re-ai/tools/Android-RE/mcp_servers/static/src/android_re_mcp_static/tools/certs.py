"""Signing-scheme and certificate tools.

Two tools:

- :func:`verify_signature` — summary of which APK signature schemes are
  present (v1, v2, v3) and the per-signer digest algorithms.
- :func:`get_certificate_info` — full X.509 details for a single signer.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import ProjectClosed, ProjectNotFound
from android_re_mcp_static.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register certificate tools."""

    @mcp.tool(
        name="verify_signature",
        description=(
            "Return a summary of the APK's signature state: is it signed, "
            "which schemes are present (v1/v2/v3), and the per-signer "
            "digest algorithms."
        ),
    )
    def verify_signature(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        sig = project.certs.signature
        return {
            "project_id": project_id,
            **sig.to_dict(),
        }

    @mcp.tool(
        name="get_certificate_info",
        description=(
            "Return X.509 details for the certificate chain of a single "
            "signer: subject, issuer, validity window, public key, "
            "fingerprint_sha256, and self-signed / expired / not-yet-valid flags."
        ),
    )
    def get_certificate_info(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        signer_index: Annotated[
            int,
            Field(ge=0, description="Zero-based index of the signer in the signature block"),
        ] = 0,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        all_certs = project.certs.certificates
        # Group by signer: we don't have an explicit per-signer grouping in
        # Phase 1 (Phase 2 will refine this), so we return the cert chain
        # in order and let the caller identify the leaf vs. CA.
        return {
            "project_id": project_id,
            "signer_index": signer_index,
            "count": len(all_certs),
            "certificates": [c.to_dict() for c in all_certs],
        }
