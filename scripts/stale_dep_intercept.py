"""Stale-dep intercept hook (#37) — D15 PostToolUse hook for dep manifests.

Watches Edit/Write/MultiEdit events on requirements*.txt and pyproject.toml.
If a pinned dep is >1 minor behind the freshness cache, emits a warning via
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
# Match `name==X.Y.Z` or `name>=X.Y.Z` etc. (simple regex; semver is overkill for "is it stale").
# Tolerates optional single or double quotes around the package name so PEP 621 quoted
# strings (e.g. `"requests==2.20.0"` inside `dependencies = [...]`) parse correctly.
PIN_RE = re.compile(
    r"^\s*[\"']?([a-zA-Z0-9_.+-]+)[\"']?\s*([=<>~!]=)\s*(\d[^,;\s]*)",
    re.MULTILINE,
)


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


def _check_content(new_content: str) -> list[str]:
    """Return list of stale-pin warnings."""
    warnings = []
    for match in PIN_RE.finditer(new_content):
        name, _op, version = match.group(1), match.group(2), match.group(3)
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


def _extract_content_candidates(tool_name: str, tool_input: dict) -> list[str]:
    """Return the list of new_content strings to scan, based on tool event shape.

    Edit → tool_input.new_string
    Write → tool_input.content
    MultiEdit → each tool_input.edits[*].new_string
    """
    if tool_name == "Edit":
        return [tool_input.get("new_string", "")]
    if tool_name == "Write":
        return [tool_input.get("content", "")]
    if tool_name == "MultiEdit":
        edits = tool_input.get("edits") or []
        return [e.get("new_string", "") for e in edits]
    # Unknown / future tool name — defensively try common fields.
    return [
        tool_input.get("new_string", ""),
        tool_input.get("content", ""),
    ]


def main() -> int:  # nosonar — false positive: hook-script entrypoint always returns 0
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0  # Bad input — don't block the agent

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    tool_name = payload.get("tool_name", "")

    if not _is_dep_file(file_path):
        return 0

    warnings: list[str] = []
    for content in _extract_content_candidates(tool_name, tool_input):
        if content:
            warnings.extend(_check_content(content))
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