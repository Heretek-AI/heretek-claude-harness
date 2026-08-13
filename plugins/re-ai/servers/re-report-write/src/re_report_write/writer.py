"""Report-write primitives.

Pure stdlib Python. The functions in this module are the
heavy lifting the ``re-report-write`` MCP server wraps.

The default policy is **scope-restricted**: the server
refuses to write to a path whose string contains a
path-traversal segment (e.g. ``..``) and refuses to write
to a path under ``/etc`` or ``/var`` (or ``C:\\Windows``
on Windows). The caller can override this with
``allow_outside_run_dir=True`` for tests, but the analyst
should never do that in a production run.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any, Sequence

# Path-traversal + system-dir protection
_FORBIDDEN_PATH_SUBSTRINGS: tuple[str, ...] = (
    "..",
    "/etc/",
    "/var/",
    "/usr/",
    "/bin/",
    "/sbin/",
    "\\Windows\\",
    "\\System32\\",
)


def _check_path(path: str) -> Path:
    """Validate *path* against the write-scope policy.

    Raises:
        ValueError: if *path* looks like a path-traversal
            attempt or targets a system directory.
    """
    p = Path(path)
    s = str(p)
    for bad in _FORBIDDEN_PATH_SUBSTRINGS:
        if bad in s:
            raise ValueError(
                f"refusing to write to {path!r}: contains forbidden "
                f"segment {bad!r}. Pass a path under the run's working "
                f"directory (e.g. Output/<run-id>/...) instead."
            )
    return p


def write_report(
    path: str,
    content: str,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Write *content* to *path* and return the SHA-256 of the result.

    Args:
        path: file to write
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

    Raises:
        ValueError: if *path* violates the write-scope policy
        FileExistsError: if the file exists and *overwrite* is False
    """
    p = _check_path(path)
    if p.exists() and not overwrite:
        raise FileExistsError(
            f"file already exists: {path} (pass overwrite=True to replace)"
        )
    p.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    p.write_bytes(data)
    h = hashlib.sha256(data).hexdigest()
    return {
        "path": str(p),
        "size": len(data),
        "sha256": h,
        "overwritten": bool(overwrite and p.exists()),
    }


def write_table(
    path: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Render a Markdown table from *headers* + *rows* and write it to *path*.

    The table is rendered in GitHub-Flavored Markdown
    (GFM) style: a header row, a separator row, then one
    row per record. Cell values are stringified via ``str()``
    and the column widths are computed from the longest
    value in each column (so the separator matches).

    Args:
        path: file to write
        headers: column headers (one entry per column)
        rows: row data (one list per row, one entry per column)
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
    if not headers:
        raise ValueError("headers must be non-empty")
    n_cols = len(headers)
    rows_list: list[list[str]] = []
    for r in rows:
        if len(r) != n_cols:
            raise ValueError(
                f"row has {len(r)} columns, expected {n_cols}: {r!r}"
            )
        rows_list.append([str(c) for c in r])

    # Compute column widths
    widths = [len(h) for h in headers]
    for r in rows_list:
        for i, cell in enumerate(r):
            if len(cell) > widths[i]:
                widths[i] = len(cell)

    def _pad(row: Sequence[str]) -> str:
        return "| " + " | ".join(
            c.ljust(widths[i]) for i, c in enumerate(row)
        ) + " |"

    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    lines = [
        _pad(headers),
        sep,
    ]
    for r in rows_list:
        lines.append(_pad(r))
    content = "\n".join(lines) + "\n"

    result = write_report(path, content, overwrite=overwrite)
    result["row_count"] = len(rows_list)
    result["column_count"] = n_cols
    return result
