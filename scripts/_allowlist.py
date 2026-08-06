"""Centralized allowlist patterns for catalog-controlled strings (issue #93).

Catalog entries flow into URL paths, branch names, and session-state filenames.
Validate against these regexes before any interpolation. Grow this module as
new call sites need new patterns; do not invent one-off regexes at the call site.
"""
from __future__ import annotations

import re

# owner/repo — GitHub upstream path segment.
UPSTREAM_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Git ref segment (branch / tag / SHA prefix). Letters, digits, dot, underscore,
# slash, dash. No shell metacharacters.
REF_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def require_upstream(value: str) -> None:
    if not UPSTREAM_RE.match(value):
        raise ValueError(f"upstream {value!r} failed owner/repo allowlist")


def require_ref_segment(label: str, value: str) -> None:
    if not value or ".." in value:
        raise ValueError(f"{label} {value!r} contains path-traversal or is empty")
    if not REF_SEGMENT_RE.match(value):
        raise ValueError(f"{label} {value!r} failed ref-segment allowlist")