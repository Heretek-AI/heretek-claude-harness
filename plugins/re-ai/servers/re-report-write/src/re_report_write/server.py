"""MCP server entry point for re-report-write.

Exposes report-write primitives to Claude Code via the
Model Context Protocol stdio transport.

The server is **pure Python** (no system deps). It is
scope-restricted: it refuses to write to a path containing
``..`` or under a system directory. The override
``allow_outside_run_dir`` is exposed for tests only; the
analyst should never set it in a production run.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_report_write import writer

logger = logging.getLogger("re_report_write")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-report-write")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_report_write() -> dict:
    """Return server status + version. Always ``status: OK`` —
    ``re-report-write`` has no external system dependencies.
    """
    return {
        "server": "re-report-write",
        "version": "0.1.0",
        "status": "OK",
        "deps": {"hashlib": "stdlib", "pathlib": "stdlib"},
        "scope_restricted": True,
        "notes": (
            "Refuses to write to a path containing `..` or "
            "under a system directory (e.g. /etc, /var, "
            "C:\\Windows). Pass a path under the run's "
            "working directory (Output/<run-id>/...) instead."
        ),
    }


# ── Free-text write ─────────────────────────────────────────────────────


@mcp.tool()
def write_report(
    path: str,
    content: str,
    overwrite: bool = False,
) -> dict:
    """Write *content* to *path* and return the SHA-256 of the result.

    The function is the foundational primitive the
    ``re-report`` skill uses to commit report fragments to
    ``Output/<run-id>/<file>.md``. The returned SHA-256
    is the integrity hash the run manifest records.

    Args:
        path: file to write (must not contain ``..`` or
            target a system directory)
        content: text content (typically Markdown)
        overwrite: if True, overwrite an existing file;
            if False, refuse to overwrite

    Returns::

        {
          "path": "...",
          "size": N,
          "sha256": "<64 hex chars>",
          "overwritten": bool,
        }
    """
    return writer.write_report(path, content, overwrite=overwrite)


# ── Structured table write ──────────────────────────────────────────────


@mcp.tool()
def write_table(
    path: str,
    headers: list[str],
    rows: list[list[str]],
    overwrite: bool = False,
) -> dict:
    """Render a Markdown table from *headers* + *rows* and write it to *path*.

    The table is rendered in GitHub-Flavored Markdown
    (GFM) style: a header row, a separator row, then one
    row per record. Column widths are computed from the
    longest value in each column.

    Args:
        path: file to write
        headers: column headers (one entry per column)
        rows: row data (one list per row)
        overwrite: if True, overwrite an existing file

    Returns::

        {
          "path": "...",
          "size": N,
          "sha256": "<64 hex chars>",
          "row_count": M,
          "column_count": K,
        }
    """
    return writer.write_table(
        path=path,
        headers=headers,
        rows=rows,
        overwrite=overwrite,
    )


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
