"""Tests for forbidden_pattern_scanner.py (#40)."""

import json
import subprocess
import sys
from pathlib import Path


FIXTURES = Path(__file__).parent / "fixtures"
SCANNER = Path("scripts/scanners/forbidden_pattern_scanner.py")


def _run_scanner(file_path: str, content: str) -> dict:
    payload = json.dumps(
        {
            "session_id": "test",
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path, "new_string": content},
        }
    )
    result = subprocess.run(
        [sys.executable, str(SCANNER)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_scanner_flags_forbidden_pattern():
    """#40: scanner flags yaml.load() without Loader=."""
    bad = FIXTURES / "bad_yaml_load.py"
    output = _run_scanner(str(bad), bad.read_text())
    output_str = json.dumps(output)
    assert (
        "py-yaml-load-without-loader" in output_str
    ), f"expected forbidden pattern warning, got: {output}"


def test_scanner_silent_on_clean_code():
    """#40: scanner stays silent when no forbidden patterns match."""
    good = FIXTURES / "good_yaml_safe_load.py"
    output = _run_scanner(str(good), good.read_text())
    assert output == {}, f"unexpected warning on clean code: {output}"


def test_scanner_ignores_unsupported_languages():
    """#40: scanner does nothing for non-tracked file extensions."""
    fake = FIXTURES / "config.txt"
    fake.write_text("this is just text\n")
    try:
        output = _run_scanner(str(fake), fake.read_text())
        assert output == {}, f"scanner should ignore .txt files: {output}"
    finally:
        fake.unlink()
