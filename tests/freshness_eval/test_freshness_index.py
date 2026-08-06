"""Tests for freshness_index.py (#36)."""
import subprocess
import sys
from pathlib import Path

import pytest

CACHE_DIR = Path("catalog/freshness")


def test_freshness_index_writes_yaml_for_known_lib():
    """#36: freshness_index --lib pyyaml produces catalog/freshness/pyyaml.yaml."""
    cache_file = CACHE_DIR / "pyyaml.yaml"
    if cache_file.exists():
        cache_file.unlink()

    result = subprocess.run(
        [sys.executable, "-m", "scripts.freshness_index", "--lib", "pyyaml"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert cache_file.exists(), f"expected {cache_file} to exist after run"

    content = cache_file.read_text()
    # Schema check
    assert "latest_version:" in content
    assert "latest_release_date:" in content
    assert "eol_date:" in content
    assert "cve_count_critical:" in content


def test_freshness_index_is_idempotent():
    """#36: re-running freshness_index does not change output for unchanged registry."""
    cache_file = CACHE_DIR / "pyyaml.yaml"
    if not cache_file.exists():
        pytest.skip("cache file does not exist; run test_freshness_index_writes_yaml_for_known_lib first")

    before = cache_file.read_text()
    result = subprocess.run(
        [sys.executable, "-m", "scripts.freshness_index", "--lib", "pyyaml"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0
    after = cache_file.read_text()
    assert before == after, "freshness_index output is not idempotent"


def test_freshness_index_dry_run_does_not_write():
    """#36: --dry-run mode must not write to catalog/freshness/."""
    cache_file = CACHE_DIR / "pyyaml.yaml"
    expected = cache_file.read_text() if cache_file.exists() else None

    result = subprocess.run(
        [sys.executable, "-m", "scripts.freshness_index", "--lib", "pyyaml", "--dry-run"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0

    if expected is None:
        assert not cache_file.exists(), "dry-run wrote a file"
    else:
        assert cache_file.read_text() == expected, "dry-run modified file"
