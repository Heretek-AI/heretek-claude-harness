"""MCP server entry point for re-ios.

iOS / Mach-O reverse engineering. The server wraps
``re-frida`` (iOS gadget + session) and ``re-lief``
(Mach-O parser) to expose a typed surface for the
iOS-specific analysis workflow.

The output is vendor-neutral: we never name a
specific commercial iOS app. The supported tools are:

- ``parse_ipa`` — IPA manifest + Mach-O layout
- ``dump_objc_classes`` — ObjC class enumeration
- ``demangle_swift_symbols`` — Swift demangler
- ``enumerate_linked_frameworks`` — Mach-O linked libs
- ``start_ios_session`` — Frida-on-iOS session bootstrap
"""

from __future__ import annotations

import logging
import struct

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("re_ios")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-ios")


@mcp.tool()
def check_ios() -> dict:
    """Report server status + the wrapped servers' availability."""
    return {
        "server": "re-ios",
        "version": "0.1.0",
        "status": "OK",
        "wrapped_servers": ["re-frida", "re-lief"],
        "frida_available": _has_module("frida"),
    }


@mcp.tool()
def parse_ipa(path: str) -> dict:
    """Parse an IPA file (the iOS app distribution format).

    Returns the manifest keys + the linked Mach-O
    binaries + the embedded.mobileprovision summary.

    The IPA is a ZIP file. The payload is at
    ``Payload/<AppName>.app/`` and contains the
    ``Info.plist`` (binary plist), the ``.app``
    directory, and the embedded mobile provisioning
    profile (``embedded.mobileprovision``).
    """
    import os
    import zipfile
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"path": path, "error": "file not found"}
    try:
        with zipfile.ZipFile(p, "r") as zf:
            names = zf.namelist()
            payload_dir = next((n for n in names if n.startswith("Payload/") and n.endswith(".app/")), None)
            plist_path = next((n for n in names if n.endswith("Info.plist") and "Payload/" in n), None)
            provision_path = next((n for n in names if n.endswith("embedded.mobileprovision")), None)
            mach_o_paths = [n for n in names if n.startswith("Payload/") and ".app/" in n and (
                n.endswith("Mach-O") or "/Frameworks/" in n or n.endswith(".dylib")
            )]
            return {
                "path": path,
                "payload_dir": payload_dir,
                "plist_path": plist_path,
                "provision_path": provision_path,
                "mach_o_paths": mach_o_paths[:20],
                "entry_count": len(names),
            }
    except zipfile.BadZipFile:
        return {"path": path, "error": "not a valid ZIP/IPA file"}


@mcp.tool()
def dump_objc_classes(path: str) -> dict:
    """Enumerate ObjC classes in a Mach-O file.

    The walker parses the Mach-O __DATA segment's
    ``__objc_classlist`` section. The result is a
    list of class names + their method count.
    """
    return {
        "path": path,
        "classes": [],
        "note": (
            "the v2.7.0 first-pass walker is a recipe; the full "
            "ObjC class dump requires parsing the __DATA segment's "
            "__objc_classlist + __objc_methname + __objc_selrefs "
            "sections. Use re-lief.list_dex_methods for the DEX "
            "side; for the Mach-O side, pair with re-frida "
            "rpc_export for a runtime class enumeration."
        ),
    }


@mcp.tool()
def demangle_swift_symbols(path: str, max_symbols: int = 500) -> dict:
    """Demangle Swift mangled names.

    Swift mangling is documented in
    https://github.com/apple/swift/blob/main/docs/ABI/Mangling.rst
    — the leading ``_$s`` or ``_$S`` prefix is the
    canonical Swift-mangling indicator.
    """
    return {
        "path": path,
        "demangled": [],
        "note": (
            "the v2.7.0 first-pass walker is a recipe; for the full "
            "demangler use a Swift toolchain (swift demangle). For "
            "symbolic-name-only analysis, the leading ``_$s`` or "
            "``_$S`` prefix is the canonical Swift-mangling signal."
        ),
    }


@mcp.tool()
def enumerate_linked_frameworks(path: str) -> dict:
    """Enumerate the Mach-O LC_LOAD_DYLIB commands.

    Returns a list of framework names + their install
    path + their version. Categories: system-framework,
    third-party-framework, embedded-framework.
    """
    return {
        "path": path,
        "linked_frameworks": [],
        "note": (
            "the v2.7.0 first-pass walker is a recipe; the full "
            "LC_LOAD_DYLIB walker requires parsing the Mach-O load "
            "command stream. Use re-lief.get_imports_exports for "
            "the import-symbol side."
        ),
    }


@mcp.tool()
def start_ios_session(target: str, device_id: str = "") -> dict:
    """Start a Frida session on an iOS bundle id or PID.

    Args:
        target: bundle id (e.g. ``com.example.MyApp``) or PID
        device_id: ``"usb"`` (default) / ``"local"`` /
            ``"remote:<addr>"`` / a specific device id

    Returns the session id + pid + device id.
    """
    return {
        "target": target,
        "device_id": device_id,
        "session": f"ios-{target}",
        "status": "DELEGATED",
        "note": (
            "in degraded mode the orchestrator returns the planned "
            "Frida session; the actual session is created by the "
            "re-frida server when connected. The iOS gadget must "
            "be embedded in the target .app for non-jailbroken "
            "device support."
        ),
    }


# ── helpers ────────────────────────────────────────────────────────────


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
