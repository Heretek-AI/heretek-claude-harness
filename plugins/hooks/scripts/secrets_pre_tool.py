"""Secrets pre-tool hook — D15 PreToolUse gate for Edit/Write/MultiEdit.

Pure-stdlib regex sweep for high-confidence secret patterns:
- AWS access keys (`AKIA...`)
- GitHub personal access tokens (`ghp_...`)
- JWT tokens (`eyJ...eyJ...`)
- Generic API key markers (`api_key=...`, `token=...`, `secret=...`)

On match: exit 2 (Claude Code treats exit-2 as deny) with file_path +
matched line to stderr. Otherwise exit 0.

<200ms budget — fail-open on timeout. Runs before fast_gate so secrets
are caught even when the linter passes.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# High-confidence patterns only. False-positive tolerance: medium.
PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub PAT", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")),
    (
        "Generic api_key",
        re.compile(r"(?i)\b(api_key|apikey|token|secret)\s*[=:]\s*['\"]?[A-Za-z0-9+/]{20,}"),
    ),
)

# File extensions we scan. Skip binary / non-text.
SCAN_EXTS: frozenset[str] = frozenset(
    {
        ".py",
        ".sh",
        ".yaml",
        ".yml",
        ".json",
        ".env",
        ".toml",
        ".cfg",
        ".ini",
        ".md",
        ".txt",
    }
)

# Per-extension budget (seconds). Reads single regex sweep over new_string;
# 200ms is generous.
TIMEOUT_S = 0.2


def _read_payload() -> dict:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _scan_text(file_path: str, new_string: str) -> list[tuple[str, int]]:
    """Return [(pattern_name, line_no)] for every match in new_string.

    Line numbers are 1-indexed for human-readable stderr output.
    """
    if not new_string:
        return []
    ext = Path(file_path).suffix.lower()
    if ext and ext not in SCAN_EXTS:
        return []
    hits: list[tuple[str, int]] = []
    for line_no, line in enumerate(new_string.splitlines(), start=1):
        for name, pattern in PATTERNS:
            if pattern.search(line):
                hits.append((name, line_no))
    return hits


def main() -> int:  # nosonar — egress point; exit 0/2 per pattern
    payload = _read_payload()
    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path", ""))
    new_string = str(tool_input.get("new_string", ""))
    old_string = str(tool_input.get("old_string", ""))
    if not file_path:
        return 0

    # Scan both old_string (catches pre-existing secrets being preserved)
    # and new_string (catches fresh injections).
    hits = _scan_text(file_path, new_string)
    if not hits and old_string:
        # Old-string hits are advisory; only block on new-string matches.
        old_hits = _scan_text(file_path, old_string)
        if old_hits:
            print(
                f"secrets_pre_tool: {file_path} contains pre-existing secret(s) — review before commit",
                file=sys.stderr,
            )

    if hits:
        for name, line_no in hits:
            print(
                f"secrets_pre_tool: BLOCKED {file_path}:{line_no} — {name} pattern matched",
                file=sys.stderr,
            )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
