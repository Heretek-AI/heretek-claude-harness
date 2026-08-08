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
    code = fast_gate.dispatch(FIXTURES / "good_sample.py", time_budget_s=5.0)
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "ruff"], capture_output=True).returncode != 0,
    reason="ruff not installed",
)
def test_dispatch_python_bad_returns_two() -> None:
    code = fast_gate.dispatch(FIXTURES / "bad_sample.py", time_budget_s=5.0)
    assert code == 2


@pytest.mark.skipif(
    subprocess.run(["which", "rustfmt"], capture_output=True).returncode != 0,
    reason="rustfmt not installed",
)
def test_dispatch_rust_good_returns_zero() -> None:
    code = fast_gate.dispatch(FIXTURES / "good_sample.rs", time_budget_s=5.0)
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "rustfmt"], capture_output=True).returncode != 0,
    reason="rustfmt not installed",
)
def test_dispatch_rust_bad_returns_two() -> None:
    code = fast_gate.dispatch(FIXTURES / "bad_sample.rs", time_budget_s=5.0)
    assert code == 2


@pytest.mark.skipif(
    subprocess.run(["which", "biome"], capture_output=True).returncode != 0
    and subprocess.run(["which", "npx"], capture_output=True).returncode != 0,
    reason="biome/npx not installed",
)
def test_dispatch_js_good_returns_zero() -> None:
    code = fast_gate.dispatch(FIXTURES / "good_sample.js", time_budget_s=10.0)
    assert code == 0


@pytest.mark.skipif(
    subprocess.run(["which", "biome"], capture_output=True).returncode != 0
    and subprocess.run(["which", "npx"], capture_output=True).returncode != 0,
    reason="biome/npx not installed",
)
def test_dispatch_js_bad_returns_two() -> None:
    code = fast_gate.dispatch(FIXTURES / "bad_sample.js", time_budget_s=10.0)
    assert code == 2


def test_run_fails_open_on_time_budget() -> None:
    """When the linter exceeds the time budget, exit 0 with a warning.

    Verifies the timeout is actually enforced by patching ``subprocess.run``
    to raise ``TimeoutExpired`` (the same exception ``subprocess.run``
    raises when its ``timeout`` argument elapses), AND by asserting the
    wrapper passed our ``time_budget_s`` into the ``timeout=`` kwarg.

    Uses ``fast_gate._FORCE_BINARY`` so the test is independent of which
    linter binaries are installed on the host — the timeout-propagation
    contract is what we're verifying.
    """
    payload = (FIXTURES / "good_python.json").read_text()
    original_run = fast_gate.subprocess.run
    original_forced = dict(fast_gate._FORCE_BINARY)
    captured: dict = {}
    try:
        fast_gate._FORCE_BINARY["ruff"] = "/usr/bin/true"  # any resolvable path

        def hang(*_args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            raise subprocess.TimeoutExpired(
                cmd=_args[0] if _args else [], timeout=kwargs.get("timeout", 0)
            )

        fast_gate.subprocess.run = hang  # type: ignore
        code = fast_gate.run(payload, time_budget_s=0.05)
    finally:
        fast_gate.subprocess.run = original_run  # type: ignore
        fast_gate._FORCE_BINARY.clear()
        fast_gate._FORCE_BINARY.update(original_forced)
    assert code == 0  # fail-open
    # Verify the wrapper actually passed our budget into subprocess.run.
    assert captured["timeout"] == 0.05


def test_dispatch_fails_open_on_linter_internal_error() -> None:
    """Linter exit code >= 2 (internal error) must fail-open (#97)."""
    payload = (FIXTURES / "good_python.json").read_text()
    original_run = fast_gate.subprocess.run
    original_forced = dict(fast_gate._FORCE_BINARY)
    fake = subprocess.CompletedProcess(
        args=[], returncode=3, stderr="internal error: oops", stdout=""
    )
    try:
        fast_gate._FORCE_BINARY["ruff"] = "/usr/bin/true"
        fast_gate.subprocess.run = lambda *a, **kw: fake  # type: ignore
        code = fast_gate.run(payload, time_budget_s=0.05)
    finally:
        fast_gate.subprocess.run = original_run  # type: ignore
        fast_gate._FORCE_BINARY.clear()
        fast_gate._FORCE_BINARY.update(original_forced)
    assert code == 0, "returncode>=2 should fail-open, not block"


def test_dispatch_fails_open_on_stderr_internal_error_marker() -> None:
    """returncode==1 with stderr containing 'internal error' marker must fail-open (#97)."""
    payload = (FIXTURES / "good_python.json").read_text()
    original_run = fast_gate.subprocess.run
    original_forced = dict(fast_gate._FORCE_BINARY)
    fake = subprocess.CompletedProcess(
        args=[], returncode=1, stderr="internal error: parser crashed", stdout=""
    )
    try:
        fast_gate._FORCE_BINARY["ruff"] = "/usr/bin/true"
        fast_gate.subprocess.run = lambda *a, **kw: fake  # type: ignore
        code = fast_gate.run(payload, time_budget_s=0.05)
    finally:
        fast_gate.subprocess.run = original_run  # type: ignore
        fast_gate._FORCE_BINARY.clear()
        fast_gate._FORCE_BINARY.update(original_forced)
    assert code == 0, "stderr internal-error marker should fail-open"


def test_dispatch_still_blocks_on_normal_violation() -> None:
    """Regression: returncode==1 with normal violation stderr must still block."""
    payload = (FIXTURES / "good_python.json").read_text()
    original_run = fast_gate.subprocess.run
    original_forced = dict(fast_gate._FORCE_BINARY)
    fake = subprocess.CompletedProcess(
        args=[], returncode=1, stderr="E501 line too long", stdout=""
    )
    try:
        fast_gate._FORCE_BINARY["ruff"] = "/usr/bin/true"
        fast_gate.subprocess.run = lambda *a, **kw: fake  # type: ignore
        code = fast_gate.run(payload, time_budget_s=0.05)
    finally:
        fast_gate.subprocess.run = original_run  # type: ignore
        fast_gate._FORCE_BINARY.clear()
        fast_gate._FORCE_BINARY.update(original_forced)
    assert code == 2, "returncode==1 with normal violation must still block"
