"""Tests for the Layer-1 fast-gate dispatcher."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Import the dispatcher as a module.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "hooks" / "scripts"))
import fast_gate  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "fast_gate"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture(scope="module", autouse=True)
def create_samples() -> None:
    """Create the sample files referenced by the fixtures."""
    _write(FIXTURES / "good_sample.py", "def hello():\n    print('hello')\n")
    _write(FIXTURES / "bad_sample.py", "import os\ndef f( ):pass\n")
    # rustfmt 2021 requires the body on its own indented line.
    _write(FIXTURES / "good_sample.rs", "fn main() {\n    println!(\"hi\");\n}\n")
    _write(FIXTURES / "bad_sample.rs", "fn main(){println!(\"hi\");}\n")
    # biome requires double-quoted strings and a single trailing newline.
    _write(FIXTURES / "good_sample.js", "const message = \"hi\";\nconsole.log(message);\n")
    _write(FIXTURES / "bad_sample.js", "function hello(){console.log('hi')}\n")
    _write(FIXTURES / "sample.md", "# hello\n")


def test_parse_payload_extracts_file_path() -> None:
    payload = (FIXTURES / "good_python.json").read_text()
    parsed = fast_gate.parse_payload(payload)
    assert parsed["file_path"].endswith("good_sample.py")
    assert parsed["tool_name"] == "Edit"


def test_parse_payload_rejects_missing_file_path() -> None:
    with pytest.raises(ValueError, match="file_path"):
        fast_gate.parse_payload(json.dumps({"tool_name": "Edit", "tool_input": {}}))


def test_dispatch_unsupported_extension_returns_zero() -> None:
    code = fast_gate.dispatch(Path("tests/fixtures/fast_gate/sample.md"))
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "ruff"], capture_output=True).returncode != 0,
    reason="ruff not installed",
)
def test_dispatch_python_good_returns_zero() -> None:
    code = fast_gate.dispatch(FIXTURES / "good_sample.py")
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "ruff"], capture_output=True).returncode != 0,
    reason="ruff not installed",
)
def test_dispatch_python_bad_returns_two() -> None:
    code = fast_gate.dispatch(FIXTURES / "bad_sample.py")
    assert code == 2


@pytest.mark.skipif(
    subprocess.run(["which", "rustfmt"], capture_output=True).returncode != 0,
    reason="rustfmt not installed",
)
def test_dispatch_rust_good_returns_zero() -> None:
    code = fast_gate.dispatch(FIXTURES / "good_sample.rs")
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "rustfmt"], capture_output=True).returncode != 0,
    reason="rustfmt not installed",
)
def test_dispatch_rust_bad_returns_two() -> None:
    code = fast_gate.dispatch(FIXTURES / "bad_sample.rs")
    assert code == 2


@pytest.mark.skipif(
    subprocess.run(["which", "biome"], capture_output=True).returncode != 0
    and subprocess.run(["which", "npx"], capture_output=True).returncode != 0,
    reason="biome/npx not installed",
)
def test_dispatch_js_good_returns_zero() -> None:
    code = fast_gate.dispatch(FIXTURES / "good_sample.js")
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "biome"], capture_output=True).returncode != 0
    and subprocess.run(["which", "npx"], capture_output=True).returncode != 0,
    reason="biome/npx not installed",
)
def test_dispatch_js_bad_returns_two() -> None:
    code = fast_gate.dispatch(FIXTURES / "bad_sample.js")
    assert code == 2


def test_run_fails_open_on_time_budget() -> None:
    """When the dispatcher exceeds the time budget, exit 0 with a warning."""
    payload = (FIXTURES / "good_python.json").read_text()
    # Patch dispatch to simulate a slow linter.
    original_dispatch = fast_gate.dispatch
    try:
        def slow_dispatch(file_path):
            import time
            time.sleep(1.0)
            return 0
        fast_gate.dispatch = slow_dispatch  # type: ignore
        code = fast_gate.run(payload, time_budget_s=0.05)
    finally:
        fast_gate.dispatch = original_dispatch  # type: ignore
    assert code == 0  # fail-open
