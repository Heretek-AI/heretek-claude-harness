"""Counterfactual diffs spike (#47) — prototype.

Given a unified diff touching dep pins, emits a side-by-side annotation
showing "what would change if you bumped to latest stable."

This is research code. Production integration is a follow-up issue if
the prototype proves out.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
# Match `name==X.Y.Z` etc.
PIN_RE = re.compile(r"^([+-])([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*(\d[^,;\s]*)", re.MULTILINE)


def _latest_for(lib: str) -> str | None:
    cache_file = CACHE_DIR / f"{lib.lower().replace('.', '-')}.yaml"
    if not cache_file.exists():
        return None
    try:
        data = yaml.safe_load(cache_file.read_text())
    except yaml.YAMLError:
        return None
    return data.get("latest_version")


def annotate_diff(diff: str) -> str:
    """Annotate a diff with counterfactual "bump to latest" hints."""
    today = datetime.now(timezone.utc).date().isoformat()
    trailing_newline = "\n" if diff.endswith("\n") else ""
    annotated_lines = []

    for line in diff.splitlines():
        match = PIN_RE.match(line)
        if not match:
            annotated_lines.append(line)
            continue

        sign, name, op, version = match.groups()
        latest = _latest_for(name)

        if not latest or latest == version:
            annotated_lines.append(line)
            continue

        annotated_lines.append(line)
        if sign == "-":
            annotated_lines.append(
                f"+# counterfactual: {name}=={latest} is also stable as of {today} "
                f"({_major_minor_diff(version, latest)} behind)"
            )

    return "\n".join(annotated_lines) + trailing_newline


def _major_minor_diff(pinned: str, latest: str) -> str:
    """Render 'N minor' or 'N major' diff between pinned and latest."""
    try:
        p = tuple(int(x) for x in pinned.split(".")[:2])
        l = tuple(int(x) for x in latest.split(".")[:2])
    except ValueError:
        return "version diff"
    if len(p) < 2 or len(l) < 2:
        return "version diff"
    if p[0] != l[0]:
        return f"{l[0] - p[0]} major"
    return f"{l[1] - p[1]} minor"


if __name__ == "__main__":
    import sys
    print(annotate_diff(sys.stdin.read()))
