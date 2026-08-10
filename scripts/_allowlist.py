"""Centralized allowlist patterns for catalog-controlled strings (issues #93, #94).

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

# item id — used as branch-name component. Letters, digits, dot, underscore, dash.
# No slashes (would create nested refs), no `..`.
ID_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# 40-char lowercase hex SHA.
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

# Session id — opaque token from stdin JSON. Letters, digits, underscore, dash.
# Bounded length so a multi-MB payload can't blow up the filesystem.
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def require_upstream(value: str) -> None:
    if not UPSTREAM_RE.match(value):
        raise ValueError(f"upstream {value!r} failed owner/repo allowlist")


def require_ref_segment(label: str, value: str) -> None:
    if not value or ".." in value:
        raise ValueError(f"{label} {value!r} contains path-traversal or is empty")
    if not REF_SEGMENT_RE.match(value):
        raise ValueError(f"{label} {value!r} failed ref-segment allowlist")


def require_id_segment(label: str, value: str) -> None:
    if not value or ".." in value:
        raise ValueError(f"{label} {value!r} contains path-traversal or is empty")
    if not ID_SEGMENT_RE.match(value):
        raise ValueError(f"{label} {value!r} failed id-segment allowlist")


def require_sha(value: str) -> None:
    if not SHA_RE.match(value or ""):
        raise ValueError(f"sha {value!r} failed 40-hex allowlist")


def require_session_id(value: str) -> None:
    if not SESSION_ID_RE.match(value or ""):
        raise ValueError(f"session_id {value!r} failed allowlist")
