"""Regression inventory for catalog/freshness/.

Added when 3 freshness/staleness tests failed because the cache only
contained pyyaml.yaml. Guards against silent removal of any required
entry by a future PR. Validates shape (top-level mapping with
`latest_version: str`) so the cache files remain parseable by
`scripts/stale_dep_intercept.py` and `scripts/staleness_metric_spike.py`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

CACHE_DIR = Path("catalog/freshness")
REQUIRED = {"pyyaml", "jsonschema", "requests", "ruamel-yaml", "pytest", "ruff"}


def test_freshness_cache_has_all_runtime_dep_entries():
    actual = {p.stem for p in CACHE_DIR.glob("*.yaml") if p.stem != "__init__"}
    missing = REQUIRED - actual
    assert not missing, f"freshness cache missing entries: {sorted(missing)}"


def test_freshness_cache_entries_have_latest_version_field():
    for stem in sorted(REQUIRED):
        path = CACHE_DIR / f"{stem}.yaml"
        assert path.exists(), f"{path} missing"
        data = yaml.safe_load(path.read_text())
        assert isinstance(data, dict), f"{path}: top-level must be a mapping"
        assert "latest_version" in data, f"{path}: missing 'latest_version'"
        assert isinstance(
            data["latest_version"], str
        ), f"{path}: latest_version must be a string, got {type(data['latest_version'])}"
