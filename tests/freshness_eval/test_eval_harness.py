"""Eval harness for freshness primitives (#38).

Measures:
- Detection rate: #37 correctly flags the stale_pyproject fixture
- False-positive rate: #37 stays silent on the good_pyproject fixture
- Freshness-index coverage: at least 4 of heretek's runtime deps have cache entries
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CACHE_DIR = Path("catalog/freshness")


def _run_hook_on_file(path: Path) -> dict:
    payload = json.dumps({
        "session_id": "test",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": str(path),
            "new_string": path.read_text(),
        },
    })
    result = subprocess.run(
        [sys.executable, "scripts/stale_dep_intercept.py"],
        input=payload, capture_output=True, text=True, timeout=5,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_eval_detection_rate_on_stale_fixture():
    """#38: hook must warn on at least 2 of the 3 stale pins."""
    stale = FIXTURES / "stale_pyproject.toml"
    output = _run_hook_on_file(stale)
    output_str = json.dumps(output)
    # Count distinct "is stale" warnings
    warnings = output_str.count("is stale")
    assert warnings >= 2, f"expected ≥2 stale warnings, got {warnings}: {output}"


def test_eval_false_positive_rate_on_good_fixture():
    """#38: hook must NOT warn when pins are >= latest."""
    import yaml

    # Build a good fixture dynamically from cache state
    libs = ["requests", "pyyaml", "ruff"]
    pins = []
    for lib in libs:
        cache_file = CACHE_DIR / f"{lib.replace('.', '-')}.yaml"
        if cache_file.exists():
            latest = yaml.safe_load(cache_file.read_text())["latest_version"]
            pins.append(f'"{lib}=={latest}"')

    good = FIXTURES / "good_pyproject.toml"
    dynamic = good.read_text().replace(
        "# dynamic substitution below",
        ",\n    ".join(pins) + ",\n",
    )
    dynamic_file = good.parent / "_dynamic_good_pyproject.toml"
    dynamic_file.write_text(dynamic)

    output = _run_hook_on_file(dynamic_file)
    assert "is stale" not in json.dumps(output), \
        f"false positive on fresh pins: {output}"

    dynamic_file.unlink()


def test_eval_freshness_index_coverage():
    """#38: at least 4 of heretek's runtime deps must have cache entries."""
    expected = {"pyyaml", "jsonschema", "requests", "ruamel-yaml", "pytest", "ruff"}
    actual = {p.stem for p in CACHE_DIR.glob("*.yaml") if p.stem != "__init__"}
    missing = expected - actual
    assert len(missing) <= 2, f"freshness index missing entries: {missing}"
