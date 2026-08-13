"""MCP server entry point for re-apktool.

Exposes Android APK triage tools to Claude Code via the Model
Context Protocol stdio transport.

The MCP wrappers are thin — every tool delegates to
:mod:`re_apktool.parser`. The parser chooses the active
backend (apktool when present, androguard otherwise) and
surfaces errors in a JSON-safe shape.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_apktool import parser

mcp = FastMCP("re-apktool")

logger = logging.getLogger("re_apktool")
logger.setLevel(logging.INFO)


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_apktool() -> dict:
    """Return apktool / androguard / java availability.

    Active backend is one of ``"apktool"`` (apktool jar on PATH
    and a JRE), ``"androguard"`` (pure-Python fallback), or
    ``"none"`` (server can't analyse anything).

    The MCP layer prefers apktool when both are present because
    apktool's Smali output is closer to the canonical AOSP
    form. androguard is the always-on fallback for the header
    + class enumeration + manifest-decoding tools.
    """
    return parser.check_apktool()


# ── Analysis ────────────────────────────────────────────────────────────


@mcp.tool()
def parse_apk(path: str) -> dict:
    """Return a structural summary of the APK at *path*.

    Output includes:

    - package / version / min+target SDK
    - activities, services, receivers, providers
    - permissions list
    - signature scheme (v1 / v2 / v3)
    - debuggable + allowBackup flags
    - per-file entry inventory + DEX / native lib / asset counts

    Uses androguard for the manifest-backed fields, falls back
    to a zipfile-only walk for the entry list when androguard
    is missing.
    """
    return parser.parse_apk(path)


@mcp.tool()
def list_dex_classes(path: str) -> dict:
    """Enumerate every class in every ``classes*.dex`` in the APK.

    Returns one record per class::

        {
          "fqn": "com.foo.Bar",
          "access": "public",
          "method_count": N
        }

    plus a per-dex summary. Use this for the
    "what's actually compiled into this APK" view — class names
    are the structural fact, not the implementation. Apktool
    would give a Smali dump; the MCP surface sticks to the
    typed class graph so the analyst can ask Claude "what
    classes are in this APK" without dragging the full
    bytecode into context.
    """
    return parser.list_dex_classes(path)


@mcp.tool()
def decode_manifest(path: str) -> dict:
    """Decode the APK's AndroidManifest.xml.

    Returns the manifest as text (androguard's AXMLPrinter
    output) plus the parsed activity / service / receiver /
    provider / permission lists.

    When the manifest is binary-only (some closed-source
    protectors encrypt it) androguard fails — the analyst
    falls back to ``apktool d`` directly. The MCP layer
    surfaces the error in the response rather than silently
    returning a half-decoded manifest.
    """
    return parser.decode_manifest(path)


# ── APK protection classification (v2.7.0) ────────────────────────────


@mcp.tool()
def classify_apk_protection(path: str, max_per_category: int = 50) -> dict:
    """Walk the APK + every classes*.dex for known protection patterns.

    Uses the vendored ``data/apkid-signatures.json`` catalog.
    Returns a list of ``{category, evidence, evidence_offset,
    evidence_file}`` records with **category-only** labels
    (``"apk_packager"``, ``"dex_obfuscator"``, ``"ssl_pinning"``,
    etc.). The category names describe observable patterns;
    no specific commercial product is named.

    Args:
        path: path to the APK
        max_per_category: per-category match cap (default 50)

    Returns::

        {
          "path": "...",
          "matches": [{"category": "...", "evidence": "...",
                       "evidence_offset": N, "evidence_file": "...",
                       "match_pattern": "...", "id": "..."}, ...],
          "by_category": {"dex-obfuscator": 12, "ssl_pinning": 2, ...},
          "truncated": {"per_category": bool}
        }

    The signature table is matched against:
    - ``classes.dex`` string table (DEX class names + method
      signatures + string literals);
    - every ``lib/*.so`` for the native-section + string-literal
      categories;
    - the manifest's ``application`` / ``meta-data`` elements.

    The implementation lives in
    ``servers/re-apktool/src/re_apktool/classify.py``.
    """
    try:
        from re_apktool import classify as classify_mod
    except ImportError as exc:
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": f"re_apktool.classify module not available: {exc}",
        }
    return classify_mod.classify_apk(path, max_per_category=max_per_category)


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
