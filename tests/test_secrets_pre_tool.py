"""Tests for plugins/hooks/scripts/secrets_pre_tool.py.

Pure-stdlib regex sweep for AWS keys, GitHub PATs, JWT tokens, and
generic API key markers. Exit 2 = block, exit 0 = allow.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECRETS = REPO_ROOT / "plugins" / "hooks" / "scripts" / "secrets_pre_tool.py"


def _run(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SECRETS)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )


def _payload(file_path: str, new_string: str) -> dict:
    return {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "new_string": new_string,
            "old_string": "",
        },
    }


def test_blocks_aws_access_key() -> None:
    result = _run(_payload("config.py", 'AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'))
    assert (
        result.returncode == 2
    ), f"expected block (exit 2), got {result.returncode}; stderr: {result.stderr}"
    assert "AWS" in result.stderr


def test_blocks_github_pat() -> None:
    # 36-char suffix after ghp_
    pat = "ghp_" + "a" * 36
    result = _run(_payload("config.py", f'TOKEN = "{pat}"\n'))
    assert result.returncode == 2
    assert "GitHub" in result.stderr


def test_blocks_jwt() -> None:
    # Synthetic JWT (3 base64url segments with dots) — matches our regex,
    # not a real token. gitleaks:allow inline annotation suppresses the
    # heuristic that flags any 3-segment base64url string as a JWT.
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.testtesttesttesttesttesttesttest"  # gitleaks:allow
    result = _run(_payload("config.py", f'token = "{jwt}"\n'))
    assert result.returncode == 2


def test_blocks_generic_api_key() -> None:
    # Synthetic placeholder key — matches our regex (api_key=... with 20+ chars).
    # Uses repeating "X" + nonce to avoid gitleaks heuristic false positives on
    # the fixed jwt.io example we used previously.
    result = _run(
        _payload(
            "config.py",
            'api_key = "placeholderapikeyxxxxxxxxxxxxxxxxx"\n',
        )
    )
    assert result.returncode == 2


def test_allows_clean_python() -> None:
    result = _run(
        _payload(
            "src/example.py",
            'def hello():\n    return "world"\n',
        )
    )
    assert (
        result.returncode == 0
    ), f"expected allow (exit 0), got {result.returncode}; stderr: {result.stderr}"


def test_allows_unrelated_pin() -> None:
    """Pin patterns (e.g. `requests==2.34.0`) must NOT trigger."""
    result = _run(
        _payload(
            "requirements.txt",
            "requests==2.34.0\npyyaml==6.0.1\n",
        )
    )
    assert result.returncode == 0


def test_allows_empty_payload() -> None:
    result = subprocess.run(
        [sys.executable, str(SECRETS)],
        input="",
        capture_output=True,
        text=True,
        timeout=5.0,
        check=False,
    )
    assert result.returncode == 0
