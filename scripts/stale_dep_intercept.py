"""Stale-dep intercept hook (#37) — D15 PostToolUse hook for dep manifests.

Watches Edit events on requirements*.txt and pyproject.toml. If a pinned
dep is >1 minor behind the freshness cache, emits a warning via
additionalContext. Per spec §2 latency budget: blocking stays <100ms,
async checks ≤2s.

Usage: registered as a PostToolUse hook in plugins/hooks/hooks/hooks.json
(D15 — only the hooks plugin owns quality-gate hooks).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
DEP_FILE_PATTERNS = (
    re.compile(r"requirements.*\.txt$"),
    re.compile(r"pyproject\.toml$"),
)
# Match `name==X.Y.Z` or `name>=X.Y.Z` etc. (simple regex; semver is overkill for "is it stale")
PIN_RE = re.compile(r"^\s*([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*([0-9][^,;\s]*)", re.MULTILINE)


def _is_dep_file(path: str) -> bool:
    return any(p.search(path) for p in DEP_FILE_PATTERNS)


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse leading X.Y.Z into a tuple; ignore pre-release / build metadata."""
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts[:3])


def _is_stale(pinned: str, latest: str) -> bool:
    """A pin is stale if it's >1 minor behind latest."""
    try:
        p = _parse_version(pinned)
        l = _parse_version(latest)
    except (ValueError, IndexError):
        return False
    if len(p) < 2 or len(l) < 2:
        return False
    # Same major: stale if pinned minor is <= latest minor - 2
    if p[0] == l[0]:
        return p[1] <= l[1] - 2
    # Different major: only stale if pinned is older
    return p[0] < l[0]


def _check_content(file_path: str, new_content: str) -> list[str]:
    """Return list of stale-pin warnings."""
    warnings = []
    for match in PIN_RE.finditer(new_content):
        name, op, version = match.group(1), match.group(2), match.group(3)
        safe_name = name.lower().replace(".", "-")
        cache_file = CACHE_DIR / f"{safe_name}.yaml"
        if not cache_file.exists():
            continue
        try:
            import yaml
            cache = yaml.safe_load(cache_file.read_text())
        except Exception:
            continue
        latest = cache.get("latest_version")
        if not latest:
            continue
        if _is_stale(version, latest):
            warnings.append(
                f"{name}=={version} is stale (latest stable: {latest}). "
                f"Consider updating unless pinned for CVE/LTS reasons."
            )
    return warnings


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0  # Bad input — don't block the agent

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    new_content = tool_input.get("new_string", "")

    if not _is_dep_file(file_path):
        return 0

    warnings = _check_content(file_path, new_content)
    if not warnings:
        return 0

    # Async-with-warning per spec §2 (non-blocking, hooks adds context to next turn)
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(f"⚠️  {w}" for w in warnings),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())