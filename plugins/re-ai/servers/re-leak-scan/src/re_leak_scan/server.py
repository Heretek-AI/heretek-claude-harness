"""MCP server entry point for re-leak-scan.

Exposes publisher telemetry pipeline leak detection tools to Claude
Code via the Model Context Protocol stdio transport.

All output is vendor-neutral: pattern categories describe
observable string content (Sentry DSN, Logstash URL, Confluence
wiki link, Google Drive document URL) without naming any
specific publisher or product.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from re_leak_scan import extractor, patterns, scanner

logger = logging.getLogger("re_leak_scan")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-leak-scan")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_leak_scan() -> dict:
    """Return pattern-catalog summary + dependency availability.

    Always returns ``status: OK`` (this server has no external
    system-tool dependencies — pure Python).

    The optional ``[verify]`` extra adds ``httpx`` for live
    verification of Sentry / Confluence endpoints. When missing,
    :func:`verify_sentry_dsn` and :func:`verify_confluence_url`
    return ``{"verified": False, "reason": "httpx not installed"}``
    — the leak detection itself is unaffected.
    """
    import importlib.util

    httpx_ok = importlib.util.find_spec("httpx") is not None
    return {
        "server": "re-leak-scan",
        "version": "0.1.0",
        "status": "OK",
        "pattern_count": len(patterns.PATTERNS),
        "patterns_by_risk": patterns.get_patterns_by_risk(),
        "httpx_available": httpx_ok,
    }


# ── Core detection ──────────────────────────────────────────────────────


@mcp.tool()
def extract_strings(path: str, min_length: int = 8, max_strings: int = 50_000) -> dict:
    """Extract printable ASCII and UTF-16LE strings from *path*.

    Args:
        path: file to scan
        min_length: minimum string length (default 8)
        max_strings: per-encoding cap (default 50,000)

    Returns a dict with ``ascii`` and ``utf16le`` arrays of
    ``{"string", "offset", "encoding"}``. This is the raw
    string extraction — pass the result to :func:`find_secrets`
    for the leak-detection pass.

    On a 500+ MB GameAssembly.dll, prefer the section-aware
    :func:`re-lief.categorize_strings` instead; this implementation
    walks the file linearly and may be slow.
    """
    out = extractor.extract_strings(path, min_length=min_length, max_strings=max_strings)
    # Count fields for the analyst
    out["ascii_count"] = len(out["ascii"])
    out["utf16le_count"] = len(out["utf16le"])
    return out


@mcp.tool()
def find_secrets(
    path: str,
    detector_set: str = "sentry-dsn,logstash-url,confluence-url,google-drive-url,aws-access-key,slack-token",
    min_length: int = 8,
    max_per_category: int = 200,
) -> dict:
    """Run the regex leak catalog over *path*'s string table.

    Args:
        path: file to scan
        detector_set: comma-separated list of pattern names to apply
            (default: all categories except the noisy ``generic-hex-secret``).
            Use ``detector_set="all"`` for the full catalog.
        min_length: minimum string length passed to :func:`extract_strings`
        max_per_category: per-category match cap (default 200)

    Returns::

        {
          "path": "...",
          "totals": {"strings_seen": N, "matches": N},
          "truncated": bool,
          "categories_run": ["sentry-dsn", ...],
          "by_category": {
            "sentry-dsn": {"count": N, "risk": "HIGH", "description": "...",
                           "matches": [{"string": "...", "offset": N, ...}]},
            ...
          },
        }
    """
    if detector_set.lower() == "all":
        cats = patterns.get_pattern_names()
    else:
        cats = [c.strip() for c in detector_set.split(",") if c.strip()]
    strings = extractor.extract_strings(path, min_length=min_length, max_strings=50_000)
    all_strings = strings["ascii"] + strings["utf16le"]
    result = scanner.scan_strings(all_strings, categories=cats, max_per_category=max_per_category)
    return {
        "path": path,
        "totals": result["totals"],
        "truncated": strings["truncated"],
        "categories_run": cats,
        "by_category": result["by_category"],
    }


@mcp.tool()
def scan(path: str, max_per_category: int = 200) -> dict:
    """Full pipeline: extract strings → apply all detectors → return findings.

    Convenience wrapper for the typical workflow. Equivalent to
    ``find_secrets(path, detector_set="all", max_per_category=...)``.

    Returns the same shape as :func:`find_secrets`.
    """
    return find_secrets(
        path=path,
        detector_set="all",
        min_length=8,
        max_per_category=max_per_category,
    )


# ── Active verification (optional, requires httpx) ─────────────────────


@mcp.tool()
def verify_sentry_dsn(dsn: str) -> dict:
    """Parse a Sentry DSN and (if ``httpx`` is available) probe the
    Sentry host to confirm reachability.

    Args:
        dsn: a single Sentry DSN string (the full URL, including
            the ``https://key@host/project_id`` form)

    Returns::

        {"dsn": "...", "parsed": {"host": "...", "project_id": N,
                                   "public_key": "..."},
         "verified": bool, "http_status": N | None, "reason": "..."}

    The probe hits ``<host>/api/0/projects/<org>/<project>/`` with
    the public key. A 200/401/403/404 means the endpoint is
    reachable (the specific status tells you whether the key has
    project access). A connection error or timeout means the
    host is unreachable from the analyst's network.
    """
    import re
    parsed = _parse_sentry_dsn(dsn)
    if parsed is None:
        return {"dsn": dsn, "parsed": None, "verified": False, "reason": "could not parse DSN"}
    try:
        import httpx
    except ImportError:
        return {
            "dsn": dsn,
            "parsed": parsed,
            "verified": False,
            "reason": "httpx not installed (pip install re-leak-scan[verify])",
        }
    url = f"https://{parsed['host']}/api/0/projects/{parsed['public_key']}/{parsed['project_id']}/"
    try:
        resp = httpx.get(url, timeout=5, follow_redirects=False)
        return {
            "dsn": dsn,
            "parsed": parsed,
            "verified": True,
            "http_status": resp.status_code,
            "reason": (
                "endpoint reachable" if resp.status_code < 500
                else "endpoint reachable but server error"
            ),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "dsn": dsn,
            "parsed": parsed,
            "verified": False,
            "http_status": None,
            "reason": f"connection failed: {exc}",
        }


@mcp.tool()
def verify_confluence_url(url: str) -> dict:
    """Probe a Confluence URL to confirm reachability + anon-access.

    Returns::

        {"url": "...", "verified": bool, "http_status": N | None,
         "anon_accessible": bool, "reason": "..."}

    A 200 means the page is publicly readable (anon-accessible).
    A 401/403 means it's behind auth (still reachable). A
    connection error means unreachable.

    Note: this only checks the URL — the actual content of the
    Confluence page is the analyst's responsibility.
    """
    try:
        import httpx
    except ImportError:
        return {
            "url": url,
            "verified": False,
            "reason": "httpx not installed (pip install re-leak-scan[verify])",
        }
    try:
        resp = httpx.get(url, timeout=5, follow_redirects=True)
        anon = resp.status_code == 200
        return {
            "url": url,
            "verified": True,
            "http_status": resp.status_code,
            "anon_accessible": anon,
            "reason": "OK" if anon else "behind auth (401/403/redirect)",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "url": url,
            "verified": False,
            "http_status": None,
            "anon_accessible": False,
            "reason": f"connection failed: {exc}",
        }


# ── Helpers ────────────────────────────────────────────────────────────


_SENTRY_DSN_RE = re.compile(
    r"^https?://(?P<key>[a-f0-9]{20,})@(?P<host>[a-z0-9.\-]+)/(?P<project>\d+)/?$",
    re.IGNORECASE,
)


def _parse_sentry_dsn(dsn: str) -> dict | None:
    m = _SENTRY_DSN_RE.match(dsn.strip())
    if not m:
        return None
    return {
        "public_key": m.group("key"),
        "host": m.group("host"),
        "project_id": int(m.group("project")),
    }


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
