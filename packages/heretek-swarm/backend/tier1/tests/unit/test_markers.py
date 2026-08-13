"""Marker leak check: every test under tests/integration/ must be marked @pytest.mark.integration.

Without this check, an unmarked test would silently slip into PR CI and
slow it down (or hit the live API unexpectedly).
"""

from __future__ import annotations

from pathlib import Path

import pytest

INTEGRATION_DIR = Path(__file__).parent.parent / "integration"


@pytest.fixture(scope="module")
def integration_test_files() -> list[Path]:
    if not INTEGRATION_DIR.exists():
        return []
    return [p for p in INTEGRATION_DIR.rglob("test_*.py")]


def test_every_integration_test_is_marked(integration_test_files: list[Path]):
    """Every test_* function in tests/integration/ must have @pytest.mark.integration."""
    if not integration_test_files:
        pytest.skip(f"no integration tests found at {INTEGRATION_DIR}")
    unmarked: list[str] = []
    for path in integration_test_files:
        text = path.read_text(encoding="utf-8")
        # Naive AST-free scan: split into test definitions and check for marker.
        # We treat the test as "marked" if `pytest.mark.integration` appears
        # in the surrounding decorators above the `def test_` line.
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("def test_") or stripped.startswith("async def test_"):
                # Walk backwards to find decorators.
                preceding = "\n".join(lines[max(0, i - 12) : i])
                if "pytest.mark.integration" not in preceding:
                    unmarked.append(f"{path.name}:{i + 1}: {stripped}")
    assert not unmarked, "unmarked integration tests found:\n" + "\n".join(unmarked)
