"""Cumulative codebase-staleness metric spike (#49) — prototype.

Walks git history, computes per-commit staleness score based on
dep-pin-vs-latest-version distance.

This is research code. Production integration is a follow-up issue if
the prototype proves out.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
PIN_RE = re.compile(r"^\s*([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*(\d[^,;\s]*)", re.MULTILINE)


def _latest_for(lib: str) -> str | None:
    cache_file = CACHE_DIR / f"{lib.lower().replace('.', '-')}.yaml"
    if not cache_file.exists():
        return None
    try:
        return yaml.safe_load(cache_file.read_text()).get("latest_version")
    except yaml.YAMLError:
        return None


def _version_distance(pinned: str, latest: str) -> int:
    """Compute approximate major+minor distance between pinned and latest."""
    try:
        p = tuple(int(x) for x in pinned.split(".")[:2])
        l = tuple(int(x) for x in latest.split(".")[:2])
    except ValueError:
        return 0
    if len(p) < 2 or len(l) < 2:
        return 0
    return max(0, (l[0] - p[0]) * 100 + (l[1] - p[1]))


def score_for_pins(pins: dict[str, str]) -> float:
    """Compute staleness score for a dict of {lib: pinned_version}.

    Returns a sum of distance scores. Lower is fresher.
    """
    total = 0.0
    for lib, pinned in pins.items():
        latest = _latest_for(lib)
        if not latest:
            continue
        total += _version_distance(pinned, latest)
    return total


def parse_pins_from_diff(diff_text: str) -> dict[str, str]:
    """Extract dep pins from a unified diff (added lines only)."""
    pins = {}
    for match in PIN_RE.finditer(diff_text):
        # Only consider added lines (+ prefix)
        # Find the line's leading char
        start = match.start()
        # The line starts at the previous \n (or 0)
        line_start = diff_text.rfind("\n", 0, start) + 1
        if line_start < start and diff_text[line_start] == "+":
            lib, _, version = match.group(1), match.group(2), match.group(3)
            pins[lib] = version
    return pins


def compute_history_scores(repo_dir: str = ".") -> list[tuple[str, float]]:
    """Walk git history, return list of (commit_sha, staleness_score)."""
    result = subprocess.run(
        ["git", "log", "--pretty=format:%H", "--", "requirements.txt", "pyproject.toml"],
        cwd=repo_dir, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return []

    scores = []
    for sha in result.stdout.strip().splitlines():
        diff_result = subprocess.run(
            ["git", "show", sha, "--", "requirements.txt", "pyproject.toml"],
            cwd=repo_dir, capture_output=True, text=True, timeout=30,
        )
        if diff_result.returncode != 0:
            continue
        pins = parse_pins_from_diff(diff_result.stdout)
        scores.append((sha, score_for_pins(pins)))

    return scores


if __name__ == "__main__":
    import csv
    import sys

    scores = compute_history_scores()
    writer = csv.writer(sys.stdout)
    writer.writerow(["commit_sha", "staleness_score"])
    for sha, score in scores:
        writer.writerow([sha, score])
