"""Tests for freshness_index.py (#36).

All tests are fully isolated: PyPI HTTP responses are mocked via
`unittest.mock.patch` and the on-disk cache directory is redirected to a
per-test `tmp_path` via `monkeypatch`. No test ever touches the real
catalog/freshness/ tree or makes a network call.
"""
from unittest.mock import MagicMock, patch

import yaml

from scripts.freshness_index import main


def _fake_pypi_response(version: str = "6.0.3", upload_time: str = "2025-09-25T21:31:46"):
    """Build a mock matching PyPI's /pypi/<lib>/json schema."""
    mock = MagicMock()
    mock.json.return_value = {
        "info": {"version": version},
        "releases": {version: [{"upload_time": upload_time}]},
    }
    mock.raise_for_status.return_value = None
    return mock


def test_freshness_index_writes_yaml_for_known_lib(monkeypatch, tmp_path):
    """#36: freshness_index --lib pyyaml produces catalog/freshness/pyyaml.yaml."""
    # Isolate on-disk cache from the real catalog/freshness/ tree.
    monkeypatch.setattr("scripts.freshness_index.CACHE_DIR", tmp_path)

    # Block the real PyPI HTTP call.
    with patch("requests.get", return_value=_fake_pypi_response()):
        assert main(["--lib", "pyyaml"]) == 0

    cache_file = tmp_path / "pyyaml.yaml"
    assert cache_file.exists(), f"expected {cache_file} to exist after run"

    # Parse-assert schema check (stronger than substring assertions).
    data = yaml.safe_load(cache_file.read_text())
    assert data["latest_version"] == "6.0.3"
    assert data["latest_release_date"] == "2025-09-25T21:31:46"
    assert data["eol_date"] is None
    assert data["cve_count_critical"] == 0


def test_freshness_index_is_idempotent(monkeypatch, tmp_path):
    """#36: re-running freshness_index yields identical output for unchanged registry."""
    monkeypatch.setattr("scripts.freshness_index.CACHE_DIR", tmp_path)

    with patch("requests.get", return_value=_fake_pypi_response()):
        assert main(["--lib", "pyyaml"]) == 0
        before = (tmp_path / "pyyaml.yaml").read_text()

        assert main(["--lib", "pyyaml"]) == 0
        after = (tmp_path / "pyyaml.yaml").read_text()

    assert before == after, "freshness_index output is not idempotent"


def test_freshness_index_dry_run_does_not_write(monkeypatch, tmp_path):
    """#36: --dry-run mode must not write to the cache directory."""
    monkeypatch.setattr("scripts.freshness_index.CACHE_DIR", tmp_path)

    with patch("requests.get", return_value=_fake_pypi_response()):
        assert main(["--lib", "pyyaml", "--dry-run"]) == 0

    assert not (tmp_path / "pyyaml.yaml").exists(), "dry-run wrote a file"
