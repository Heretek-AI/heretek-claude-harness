"""SHA-256 over the harness hook files.

Produced at init time and consumed by the harness loader at agent startup.
Mismatch refuses to load the agent manifest.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_HOOK_FILES = [
    ".claude/hooks/PreToolUse/deny-destructive.sh",
    ".claude/hooks/PostToolUse/run-pre-commit.sh",
    ".claude/hooks/Stop/verify-lint.sh",
]


def compute_lockfile_hash(templates_dir: Path | None = None) -> str:
    base = templates_dir or (Path(__file__).parents[2] / "templates")
    h = hashlib.sha256()
    for rel in _HOOK_FILES:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update((base / rel).read_bytes())
    return h.hexdigest()


def verify_lockfile(expected: str, templates_dir: Path | None = None) -> bool:
    return compute_lockfile_hash(templates_dir) == expected
