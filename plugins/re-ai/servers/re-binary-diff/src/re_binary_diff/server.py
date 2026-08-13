"""MCP server entry point for re-binary-diff.

Exposes read-only binary diff + section fingerprint tools to
Claude Code via the Model Context Protocol stdio transport.

The server is **pure Python** (no system deps). It is
**dry-run only** — it never writes a byte to disk.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_binary_diff import differ

logger = logging.getLogger("re_binary_diff")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-binary-diff")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_binary_diff() -> dict:
    """Return server status + version. Always ``status: OK`` —
    ``re-binary-diff`` has no external system dependencies.
    """
    return {
        "server": "re-binary-diff",
        "version": "0.1.0",
        "status": "OK",
        "deps": {"difflib": "stdlib", "hashlib": "stdlib"},
        "writable": False,
        "notes": (
            "Dry-run only. Computes a diff or fingerprint "
            "between two files; never writes a byte to disk. "
            "Pairs with the `re-patch` server's on-disk patch "
            "primitive — diff the original vs. the patched "
            "copy to see the net effect of a patch."
        ),
    }


# ── Diff ────────────────────────────────────────────────────────────────


@mcp.tool()
def unified_diff(path_a: str, path_b: str) -> dict:
    """Compute a unified-style diff between *path_a* and *path_b*.

    For small files (<= 8 MiB per side) the function runs
    ``difflib.unified_diff`` over the byte streams (decoded
    as latin-1). For large files it falls back to a
    per-chunk SHA-256 diff.

    Args:
        path_a: first file (the "before" or "original")
        path_b: second file (the "after" or "patched")

    Returns::

        {
          "path_a": "...",
          "path_b": "...",
          "size_a": N,
          "size_b": N,
          "mode": "sha256_equal" | "inline_unified_diff" | "chunk_sha256_diff",
          "equal": bool,
          "diff_lines": ["...", ...],   (inline mode)
          "chunk_diff": [{...}, ...],   (chunk mode)
        }

    The function is **read-only**. The "patched" copy at
    *path_b* is not modified.
    """
    return differ.unified_diff(path_a, path_b)


# ── Fingerprint ─────────────────────────────────────────────────────────


@mcp.tool()
def fingerprint_sections(path: str, chunk_size: int = 1048576, max_chunks: int = 0) -> dict:
    """Return a per-chunk SHA-256 + offset + size fingerprint of *path*.

    Useful for finding the structural delta between two
    versions of a binary without loading either into
    memory. Pair with ``unified_diff`` (chunk mode) for
    large files.

    Args:
        path: file to fingerprint
        chunk_size: bytes per chunk (default 1 MiB)
        max_chunks: 0 = no cap; > 0 = return at most N chunks

    Returns::

        {
          "path": "...",
          "size": N,
          "chunk_size": N,
          "truncated": bool,
          "chunks": [
            {"index": 0, "offset": 0, "size": 1048576, "sha256": "..."},
            ...
          ],
        }
    """
    return differ.fingerprint_sections(
        path=path,
        chunk_size=chunk_size,
        max_chunks=max_chunks,
    )


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
