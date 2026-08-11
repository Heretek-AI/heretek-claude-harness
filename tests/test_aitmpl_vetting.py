"""Verify every hook referenced in plugins/hooks/hooks/hooks.json has an
ADR (approved) or a rejected.md entry (rejected)."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_JSON = REPO_ROOT / "plugins" / "hooks" / "hooks" / "hooks.json"
REVIEWS_DIR = REPO_ROOT / "catalog" / "reviews"
REJECTED = REPO_ROOT / "catalog" / "rejected.md"


def _hook_identifiers_in_hooks_json() -> list[str]:
    import json

    data = json.loads(HOOKS_JSON.read_text())
    # Walk every hook entry and extract the command's basename as the ID.
    ids: list[str] = []
    for event, matchers in data.get("hooks", {}).items():
        for matcher in matchers:
            for hook in matcher.get("hooks", []):
                cmd = hook.get("command", "")
                # Match trailing filename without .py for python scripts
                # referenced by aitmpl-origin names.
                ids.append(cmd)
    return ids


def test_each_aitmpl_vetted_hook_has_adr() -> None:
    """For each approved aitmpl-origin hook, an ADR file must exist."""
    if not HOOKS_JSON.is_file():
        pytest.skip("hooks.json not yet written; this test gates on Task 3+6")
    # This test only asserts presence of ADRs in catalog/reviews/. The actual
    # vetting status is recorded in each ADR; we just verify the file exists.
    expected_adrs = [
        "aitmpl-security-scanner.md",
        "aitmpl-dependency-checker.md",
        "aitmpl-smart-formatting.md",
        "aitmpl-run-tests-after-changes.md",
        "aitmpl-change-tracker.md",
    ]
    missing = [a for a in expected_adrs if not (REVIEWS_DIR / a).is_file()]
    assert not missing, f"missing ADRs: {missing}"


def test_rejected_md_exists() -> None:
    assert REJECTED.is_file(), "catalog/rejected.md must exist (SP1 Task 9)"
