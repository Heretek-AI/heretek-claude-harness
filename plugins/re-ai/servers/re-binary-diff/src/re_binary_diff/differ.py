"""Read-only binary diff + section fingerprinting primitives.

Pure stdlib Python. No third-party deps. The functions in
this module are the heavy lifting the ``re-binary-diff`` MCP
server wraps.

The diff strategy is:

  - If both files are <= ``MAX_INLINE_DIFF_BYTES`` (default
    8 MiB), run ``difflib.unified_diff`` over the byte
    streams (decoded as latin-1 to avoid UnicodeError on
    arbitrary binary) and return the resulting hunks.
  - If either file is larger, fall back to a chunked
    SHA-256 diff: walk both files in fixed-size chunks
    (``CHUNK_SIZE`` = 1 MiB), report which chunks differ.

The fingerprint strategy is: walk *path* in fixed-size
chunks, return per-chunk SHA-256 + offset + size. Useful
for finding the structural delta between an original
binary and a patched copy without loading either into
memory.
"""

from __future__ import annotations

import difflib
import hashlib
from pathlib import Path
from typing import Any

MAX_INLINE_DIFF_BYTES = 8 * 1024 * 1024  # 8 MiB
CHUNK_SIZE = 1 * 1024 * 1024             # 1 MiB
HUNK_CONTEXT = 3                         # unified-diff context lines


def unified_diff(
    path_a: str,
    path_b: str,
    max_inline_bytes: int = MAX_INLINE_DIFF_BYTES,
) -> dict[str, Any]:
    """Compute a unified-style diff between *path_a* and *path_b*.

    For files larger than *max_inline_bytes* per side, fall
    back to a per-chunk SHA-256 diff (still dry-run; no
    writes).

    Args:
        path_a: first file (the "before" or "original")
        path_b: second file (the "after" or "patched")
        max_inline_bytes: per-file byte threshold; above
            this the function falls back to chunk hashing

    Returns::

        {
          "path_a": "...",
          "path_b": "...",
          "size_a": N,
          "size_b": N,
          "mode": "inline_unified_diff" | "chunk_sha256_diff",
          "equal": bool,
          "diff_lines": ["...", ...]    (inline mode)
          "chunk_diff": [{...}, ...]    (chunk mode)
        }
    """
    a = Path(path_a)
    b = Path(path_b)
    if not a.is_file():
        raise FileNotFoundError(f"path_a not found: {path_a}")
    if not b.is_file():
        raise FileNotFoundError(f"path_b not found: {path_b}")

    size_a = a.stat().st_size
    size_b = b.stat().st_size

    # Fast-path: file sizes are equal AND the SHA-256s match → no diff
    if size_a == size_b:
        a_hash = hashlib.sha256(a.read_bytes()).hexdigest()
        b_hash = hashlib.sha256(b.read_bytes()).hexdigest()
        if a_hash == b_hash:
            return {
                "path_a": str(a),
                "path_b": str(b),
                "size_a": size_a,
                "size_b": size_b,
                "mode": "sha256_equal",
                "equal": True,
                "diff_lines": [],
                "chunk_diff": [],
                "sha256_a": a_hash,
                "sha256_b": b_hash,
            }

    if size_a <= max_inline_bytes and size_b <= max_inline_bytes:
        return _inline_unified_diff(a, b, size_a, size_b)
    return _chunk_sha256_diff(a, b, size_a, size_b)


def _inline_unified_diff(
    a: Path, b: Path, size_a: int, size_b: int
) -> dict[str, Any]:
    """Run difflib.unified_diff over the byte streams."""
    a_bytes = a.read_bytes()
    b_bytes = b.read_bytes()
    a_lines = a_bytes.decode("latin-1").splitlines(keepends=True)
    b_lines = b_bytes.decode("latin-1").splitlines(keepends=True)
    diff = list(
        difflib.unified_diff(
            a_lines, b_lines, fromfile=str(a), tofile=str(b),
            n=HUNK_CONTEXT,
        )
    )
    return {
        "path_a": str(a),
        "path_b": str(b),
        "size_a": size_a,
        "size_b": size_b,
        "mode": "inline_unified_diff",
        "equal": not diff,
        "diff_lines": diff,
        "chunk_diff": [],
    }


def _chunk_sha256_diff(
    a: Path, b: Path, size_a: int, size_b: int
) -> dict[str, Any]:
    """Walk both files in fixed-size chunks; report per-chunk SHA-256 + size."""
    a_chunks = list(_iter_chunks(a))
    b_chunks = list(_iter_chunks(b))
    out: list[dict[str, Any]] = []
    n = max(len(a_chunks), len(b_chunks))
    for i in range(n):
        a_chunk = a_chunks[i] if i < len(a_chunks) else None
        b_chunk = b_chunks[i] if i < len(b_chunks) else None
        if a_chunk is None:
            out.append({
                "index": i,
                "offset": None,
                "size_a": 0,
                "size_b": b_chunk["size"],
                "sha256_a": None,
                "sha256_b": b_chunk["sha256"],
                "status": "added",
            })
            continue
        if b_chunk is None:
            out.append({
                "index": i,
                "offset": a_chunk["offset"],
                "size_a": a_chunk["size"],
                "size_b": 0,
                "sha256_a": a_chunk["sha256"],
                "sha256_b": None,
                "status": "removed",
            })
            continue
        if a_chunk["sha256"] == b_chunk["sha256"] and a_chunk["size"] == b_chunk["size"]:
            out.append({
                "index": i,
                "offset": a_chunk["offset"],
                "size_a": a_chunk["size"],
                "size_b": b_chunk["size"],
                "sha256_a": a_chunk["sha256"],
                "sha256_b": b_chunk["sha256"],
                "status": "equal",
            })
        else:
            out.append({
                "index": i,
                "offset": a_chunk["offset"],
                "size_a": a_chunk["size"],
                "size_b": b_chunk["size"],
                "sha256_a": a_chunk["sha256"],
                "sha256_b": b_chunk["sha256"],
                "status": "differs",
            })
    equal = all(c["status"] in ("equal",) for c in out)
    return {
        "path_a": str(a),
        "path_b": str(b),
        "size_a": size_a,
        "size_b": size_b,
        "mode": "chunk_sha256_diff",
        "equal": equal,
        "diff_lines": [],
        "chunk_diff": out,
    }


def _iter_chunks(path: Path):
    """Yield (offset, size, sha256) for each 1 MiB chunk of *path*."""
    offset = 0
    with path.open("rb") as f:
        while True:
            buf = f.read(CHUNK_SIZE)
            if not buf:
                return
            h = hashlib.sha256(buf).hexdigest()
            yield {"offset": offset, "size": len(buf), "sha256": h}
            offset += len(buf)


def fingerprint_sections(
    path: str,
    chunk_size: int = CHUNK_SIZE,
    max_chunks: int = 0,
) -> dict[str, Any]:
    """Return a per-chunk SHA-256 + offset + size fingerprint of *path*.

    Args:
        path: file to fingerprint
        chunk_size: bytes per chunk (default 1 MiB)
        max_chunks: 0 = no cap; > 0 = return at most N chunks
            (truncates the output with a `truncated: true` flag)

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
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"path not found: {path}")
    size = p.stat().st_size
    chunks: list[dict[str, Any]] = []
    truncated = False
    index = 0
    with p.open("rb") as f:
        offset = 0
        while True:
            buf = f.read(chunk_size)
            if not buf:
                break
            h = hashlib.sha256(buf).hexdigest()
            chunk = {
                "index": index,
                "offset": offset,
                "size": len(buf),
                "sha256": h,
            }
            if max_chunks and index >= max_chunks:
                truncated = True
                break
            chunks.append(chunk)
            offset += len(buf)
            index += 1
    return {
        "path": str(p),
        "size": size,
        "chunk_size": chunk_size,
        "truncated": truncated,
        "chunks": chunks,
    }
