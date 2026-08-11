"""Tests for plugins/hooks/.pre-commit-config.yaml.

These tests assert structural invariants from the mechanical-gates spec
(D30, D37, D38): config is plugin-internal, fail-fast at the root, every
repo SHA-pinned (40-hex), and every repo in the allowlist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PRECOMMIT_CONFIG = REPO_ROOT / "plugins" / "hooks" / ".pre-commit-config.yaml"

# Allowlist of repos approved for A0 (spec section 6 + D33):
# hygiene + ruff + local heretek-fast-gate + biome + shellcheck-py + gitleaks.
# doublify/pre-commit-rust is dropped from A0 (D7 last_commit fail — latest
# release v1.0 from 2020; the repo is unmaintained). Rust fmt/clippy will be
# moved to a maintained wrapper in slice A3.
A0_REPO_ALLOWLIST = frozenset(
    {
        "https://github.com/pre-commit/pre-commit-hooks",
        "https://github.com/astral-sh/ruff-pre-commit",
        "local",  # heretek-fast-gate
        "https://github.com/biomejs/pre-commit",
        "https://github.com/shellcheck-py/shellcheck-py",
        "https://github.com/gitleaks/gitleaks",
    }
)


def test_precommit_config_exists() -> None:
    assert (
        PRECOMMIT_CONFIG.is_file()
    ), f"{PRECOMMIT_CONFIG} must exist per spec D30 (plugin-internal config)"


def test_precommit_config_is_parsable_yaml() -> None:
    """Sanity: file parses as a YAML mapping (pre-commit accepts comments
    before the first key, so we cannot require `repos:` on the first line)."""
    import yaml

    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    assert isinstance(data, dict), "pre-commit config must be a YAML mapping at the top level"
    assert "repos" in data, "pre-commit config must declare a `repos:` key"


def test_precommit_config_fails_fast_at_root() -> None:
    """Spec D37: fail_fast: true at the root for local developer-time optimization."""
    import yaml

    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    assert isinstance(data, dict)
    assert data.get("fail_fast") is True, "root `fail_fast: true` required per spec D37"


def test_precommit_config_repos_sha_pinned() -> None:
    """Every non-local repo entry must pin a 40-char hex SHA per D20 spirit (hook immutability)."""
    import yaml

    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    sha_re = re.compile(r"^[0-9a-f]{40}$")
    repos = data.get("repos") or []
    assert repos, "config must declare at least one repo"
    for repo in repos:
        if repo.get("repo") == "local":
            continue  # local hooks have no `rev` (run system command)
        rev = repo.get("rev")
        assert rev, f"repo {repo.get('repo')} missing `rev`"
        assert sha_re.match(rev), f"repo {repo.get('repo')} rev={rev!r} is not a 40-char hex SHA"


def test_precommit_config_repos_in_allowlist() -> None:
    """Every repo must be in the A0 allowlist (no surprise additions)."""
    import yaml

    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    repos = data.get("repos") or []
    seen = {r.get("repo") for r in repos}
    extras = seen - A0_REPO_ALLOWLIST
    assert not extras, f"unexpected repos outside A0 allowlist: {extras}"


def test_precommit_validate_config_passes() -> None:
    """`pre-commit validate-config` must exit 0 (skip if CLI unavailable)."""
    import shutil
    import subprocess

    if not shutil.which("python3"):
        pytest.skip("python3 not installed")
    cli_check = subprocess.run(
        ["python3", "-m", "pre_commit", "--version"],
        capture_output=True,
    )
    if cli_check.returncode != 0:
        pytest.skip("pre-commit CLI not runnable (install with `pip install pre-commit`)")
    result = subprocess.run(
        ["python3", "-m", "pre_commit", "validate-config", str(PRECOMMIT_CONFIG)],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode == 0
    ), f"pre-commit validate-config failed: {result.stdout}\n{result.stderr}"
