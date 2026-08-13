"""Safety net: detect leaked credentials in committed vcrpy cassettes.

A leaked live API key in git is a security incident. This test fails
loudly if any cassette file contains a recognizable live key pattern.

Live key patterns covered:
- OpenAI-style: `sk-` followed by 20+ alphanumeric chars (also MiniMax)
- Anthropic-style: `sk-ant-` followed by 20+ chars
- Bearer header with non-REDACTED value
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CASSETTE_DIR = Path(__file__).parent.parent / "integration" / "behavior" / "cassettes"

# Live credential patterns (case-sensitive).
LIVE_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

# Bearer header that is NOT the safe "REDACTED" placeholder.
BEARER_LIVE = re.compile(
    r"[Aa]uthorization:\s*Bearer\s+(?!REDACTED\s*$)[A-Za-z0-9_\-\.]{8,}",
    re.MULTILINE,
)


@pytest.fixture(scope="module")
def cassette_files() -> list[Path]:
    if not CASSETTE_DIR.exists():
        return []
    return list(CASSETTE_DIR.glob("*.yaml"))


def test_no_live_keys_in_cassettes(cassette_files: list[Path]):
    """No cassette file should contain a recognizable live API key."""
    if not cassette_files:
        pytest.skip(f"no cassettes found at {CASSETTE_DIR}")
    violations: list[str] = []
    for path in cassette_files:
        text = path.read_text(encoding="utf-8")
        for pat in LIVE_KEY_PATTERNS:
            for match in pat.finditer(text):
                violations.append(f"{path.name}: live key pattern matched: {match.group(0)[:12]}…")
    assert not violations, "leaked credentials detected:\n" + "\n".join(violations)


def test_no_live_bearer_headers(cassette_files: list[Path]):
    """No cassette file should contain a Bearer header with a non-REDACTED token."""
    if not cassette_files:
        pytest.skip(f"no cassettes found at {CASSETTE_DIR}")
    violations: list[str] = []
    for path in cassette_files:
        text = path.read_text(encoding="utf-8")
        for match in BEARER_LIVE.finditer(text):
            violations.append(f"{path.name}: live bearer header: {match.group(0)[:30]}…")
    assert not violations, "leaked bearer headers detected:\n" + "\n".join(violations)
