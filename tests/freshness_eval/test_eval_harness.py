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


FIXTURES = Path(__file__).parent / "fixtures"
CACHE_DIR = Path("catalog/freshness")


def _run_hook_on_file(path: Path) -> dict:
    payload = json.dumps(
        {
            "session_id": "test",
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {
                "file_path": str(path),
                "new_string": path.read_text(),
            },
        }
    )
    result = subprocess.run(
        [sys.executable, "plugins/hooks/scripts/stale_dep_intercept.py"],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
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


def test_eval_false_positive_rate_on_good_fixture(tmp_path):
    """#38: hook must NOT warn when pins are >= latest.

    Builds the pyproject content directly into tmp_path from the live cache
    state. Uses PEP 621 quoted-string format (matches the production format
    that PIN_RE now supports).
    """
    import yaml

    libs = ["requests", "pyyaml", "ruff"]
    pins = []
    for lib in libs:
        cache_file = CACHE_DIR / f"{lib.replace('.', '-')}.yaml"
        if cache_file.exists():
            latest = yaml.safe_load(cache_file.read_text())["latest_version"]
            pins.append(f'"{lib}=={latest}"')

    dynamic_file = tmp_path / "good_pyproject.toml"
    dynamic_file.write_text(
        "[project]\n"
        'name = "good-fixture"\n'
        'version = "0.1.0"\n'
        "dependencies = [\n" + ",\n".join(f"    {p}" for p in pins) + ",\n]\n"
    )

    output = _run_hook_on_file(dynamic_file)
    assert "is stale" not in json.dumps(output), f"false positive on fresh pins: {output}"


def test_eval_freshness_index_coverage():
    """#38: at least 4 of heretek's runtime deps must have cache entries."""
    expected = {"pyyaml", "jsonschema", "requests", "ruamel-yaml", "pytest", "ruff"}
    actual = {p.stem for p in CACHE_DIR.glob("*.yaml") if p.stem != "__init__"}
    missing = expected - actual
    assert len(missing) <= 2, f"freshness index missing entries: {missing}"
