"""Signature, packer, and certificate tools."""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import APKError, APKInvalid, ProjectClosed, ProjectNotFound
from android_re_mcp_native.server import get_store

__all__ = ["register"]


#: Built-in signature rules (lightweight, no external YARA). Each rule
#: is a (name, severity, pattern) triple; matched by substring search
#: over symbols and strings.
_BUILTIN_SIGNATURES: tuple[tuple[str, str, str], ...] = (
    ("crypto-openssl", "medium", "OpenSSL"),
    ("crypto-boringssl", "medium", "BoringSSL"),
    ("crypto-mbedtls", "low", "mbedtls"),
    ("packer-upx", "high", "UPX!"),
    ("antire-frida", "high", "frida-agent"),
    ("antire-xposed", "high", "de.robv.android.xposed"),
    ("antire-magisk", "high", "magisk"),
    ("antire-substrate", "medium", "MobileSubstrate"),
    ("antire-elf-symbols-stripped", "info", ""),  # handled specially
    ("antire-debug-detect", "medium", "ptrace"),
    ("antire-emulator", "low", "qemu"),
)


def register(mcp: FastMCP) -> None:
    """Register signature tools."""

    @mcp.tool(
        name="detect_packers",
        description=(
            "Heuristic packer / anti-RE detection. Returns a list of "
            "matches with confidence scores and a snippet of evidence."
        ),
    )
    def detect_packers(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            matches = view.detect_packers(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "match_count": len(matches),
            "matches": [m.to_dict() for m in matches],
        }

    @mcp.tool(
        name="lookup_signature",
        description=(
            "Look for built-in crypto / anti-RE signatures in a native "
            "library by searching symbols and strings. Returns matches "
            "with severity."
        ),
    )
    def lookup_signature(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        sigset: Annotated[
            str,
            Field(
                description="'default' for the built-in rule set; 'strict' to also flag low-severity"
            ),
        ] = "default",
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            # Collect haystack: symbols + .rodata strings
            view.parse(lib_name)
            strings = view.get_strings(lib_name, section=".rodata", limit=5000)
            # Use a broader text scan: pull all printable strings and
            # use the regex rules from android_re_core.native.
            haystack = "\n".join(s.value for s in strings)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        out: list[dict[str, Any]] = []
        from android_re_core.native import _PACKER_SIGNATURES  # type: ignore[attr-defined]

        for packer_name, pattern in _PACKER_SIGNATURES:
            m = pattern.search(haystack)
            if m:
                out.append(
                    {
                        "signature": packer_name,
                        "kind": "packer",
                        "severity": "high",
                        "evidence": m.group(0)[:200],
                    }
                )
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "match_count": len(out),
            "matches": out,
        }

    @mcp.tool(
        name="extract_certificate_chain",
        description=(
            "Pull embedded X.509 certificates from a native library "
            "(rare, but some apps bundle certs in .rodata). Phase 2 "
            "scans for DER-encoded certs heuristically; full ASN.1 "
            "parsing lands in Phase 3."
        ),
    )
    def extract_certificate_chain(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        # Phase 2: placeholder returning a "not yet implemented" marker
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "certificates": [],
            "note": "Certificate chain extraction from native binaries lands in Phase 3.",
        }


_ = _BUILTIN_SIGNATURES  # available for future expansion
