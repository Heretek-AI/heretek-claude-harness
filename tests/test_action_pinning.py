"""D20: every `uses:` reference in every workflow must be pinned to a 40-char SHA."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WORKFLOW_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"
# Accept both bare `uses: ...` (named steps) and `- uses: ...` (list-form steps).
USES_RE = re.compile(r"^\s*-?\s*uses:\s*([\w./\-]+)@([^\s#]+)")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _iter_uses_lines() -> list[tuple[Path, str, str, str]]:
    """Return (workflow_path, owner_repo, ref, kind) for every uses: line."""
    results: list[tuple[Path, str, str, str]] = []
    for yml in sorted(WORKFLOW_DIR.glob("*.yml")):
        for line in yml.read_text().splitlines():
            m = USES_RE.match(line)
            if m:
                results.append((yml, m.group(1), m.group(2), "pinned"))
    return results


def test_workflow_dir_exists() -> None:
    assert WORKFLOW_DIR.is_dir(), f"missing {WORKFLOW_DIR}"


@pytest.mark.parametrize("workflow,action,ref,_", _iter_uses_lines())
def test_uses_is_pinned_to_commit_sha(workflow: Path, action: str, ref: str, _: str) -> None:
    assert SHA_RE.match(ref), (
        f"{workflow.name}: uses:{action}@{ref} is not a 40-char commit SHA "
        f"(D20 forbids tags, branches, and rolling aliases)"
    )
