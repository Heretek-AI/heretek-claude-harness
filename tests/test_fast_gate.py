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
    _write(FIXTURES / "bad_sample.py", "def f():pass\nundefined_var_xyz\n")
    # rustfmt 2021 requires the body on its own indented line.
    _write(FIXTURES / "good_sample.rs", 'fn main() {\n    println!("hi");\n}\n')
    _write(FIXTURES / "bad_sample.rs", 'fn main(){println!("hi");}\n')
    # biome requires double-quoted strings and a single trailing newline.
    _write(FIXTURES / "good_sample.js", 'const message = "hi";\nconsole.log(message);\n')
    _write(FIXTURES / "bad_sample.js", "function hello(){console.log('hi')}\n")
    _write(FIXTURES / "sample.md", "# hello\n")


def test_parse_payload_extracts_file_path() -> None:
    payload = (FIXTURES / "good_python.json").read_text()
    parsed = fast_gate.parse_payload(payload)
    assert parsed["file_path"].endswith("good_sample.py")
    assert parsed["tool_name"] == "Edit"


def test_parse_payload_rejects_missing_file_path() -> None:
    with pytest.raises(ValueError, match="file_path"):
        # Single invocation under test — no need to wrap in a helper.
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


def test_run_fails_open_on_time_budget(monkeypatch: pytest.MonkeyPatch) -> None:
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
    captured: dict = {}

    def hang(*_args, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        raise subprocess.TimeoutExpired(
            cmd=_args[0] if _args else [], timeout=kwargs.get("timeout", 0)
        )

    monkeypatch.setitem(fast_gate._FORCE_BINARY, "ruff", "/usr/bin/true")
    monkeypatch.setattr(fast_gate.subprocess, "run", hang)
    code = fast_gate.run(payload, time_budget_s=0.05)
    assert code == 0  # fail-open
    # Verify the wrapper actually passed our budget into subprocess.run.
    assert captured["timeout"] == 0.05


def test_dispatch_fails_open_on_linter_internal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Linter exit code >= 2 (internal error) must fail-open (#97)."""
    payload = (FIXTURES / "good_python.json").read_text()
    fake = subprocess.CompletedProcess(
        args=[], returncode=3, stderr="internal error: oops", stdout=""
    )
    monkeypatch.setitem(fast_gate._FORCE_BINARY, "ruff", "/usr/bin/true")
    monkeypatch.setattr(fast_gate.subprocess, "run", lambda *a, **kw: fake)
    code = fast_gate.run(payload, time_budget_s=0.05)
    assert code == 0, "returncode>=2 should fail-open, not block"


def test_dispatch_fails_open_on_stderr_internal_error_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """returncode==1 with stderr containing 'internal error' marker must fail-open (#97)."""
    payload = (FIXTURES / "good_python.json").read_text()
    fake = subprocess.CompletedProcess(
        args=[], returncode=1, stderr="internal error: parser crashed", stdout=""
    )
    monkeypatch.setitem(fast_gate._FORCE_BINARY, "ruff", "/usr/bin/true")
    monkeypatch.setattr(fast_gate.subprocess, "run", lambda *a, **kw: fake)
    code = fast_gate.run(payload, time_budget_s=0.05)
    assert code == 0, "stderr internal-error marker should fail-open"


def test_dispatch_still_blocks_on_normal_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: returncode==1 with normal violation stderr must still block."""
    payload = (FIXTURES / "good_python.json").read_text()
    fake = subprocess.CompletedProcess(
        args=[], returncode=1, stderr="E501 line too long", stdout=""
    )
    monkeypatch.setitem(fast_gate._FORCE_BINARY, "ruff", "/usr/bin/true")
    monkeypatch.setattr(fast_gate.subprocess, "run", lambda *a, **kw: fake)
    code = fast_gate.run(payload, time_budget_s=0.05)
    assert code == 2, "returncode==1 with normal violation must still block"


def test_dispatch_fails_open_on_path_traversal(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture,
) -> None:
    """Regression (#162): file_path that escapes REPO_ROOT must fail-open.

    A hostile payload (e.g. '../../etc/passwd.py') must NOT be passed to
    a linter subprocess. The wrapper writes a stderr message and exits 0.
    """
    payload = json.dumps(
        {
            "tool_name": "Edit",
            "tool_input": {
                "file_path": "../../etc/passwd.py",
                "old_string": "",
                "new_string": "",
            },
        }
    )
    invoked = []

    def fail_if_called(*_args, **_kwargs):
        invoked.append(_args)
        raise AssertionError("subprocess.run must not be called for escape")

    monkeypatch.setitem(fast_gate._FORCE_BINARY, "ruff", "/usr/bin/true")
    monkeypatch.setattr(fast_gate.subprocess, "run", fail_if_called)
    code = fast_gate.run(payload, time_budget_s=0.05)
    assert code == 0
    assert invoked == [], "linter subprocess must not be invoked on escape"
    err = capsys.readouterr().err
    assert "escapes REPO_ROOT" in err
    assert "failing open" in err
