"""End-to-end test: same Edit, different profiles, different outcomes."""

import json
import os
import subprocess
import sys
from pathlib import Path

FIXTURES = Path("tests/detection/fixtures")
SCANNER = Path("plugins/hooks/scripts/forbidden_pattern_scanner.py")


def _scan_as(model_id: str, content: str) -> dict:
    payload = json.dumps(
        {
            "session_id": "test-e2e",
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(FIXTURES / "bad_yaml_load.py"), "new_string": content},
        }
    )
    env = {"HERETEK_ACTIVE_MODEL": model_id, "PATH": os.environ["PATH"]}
    result = subprocess.run(
        [sys.executable, str(SCANNER)],
        input=payload,
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_qwen_strict_profile_flags_yaml_load_as_block():
    """Qwen profile promotes py-yaml-load-without-loader to error."""
    bad = (FIXTURES / "bad_yaml_load.py").read_text()
    output = _scan_as("qwen3.6-27b", bad)
    output_str = json.dumps(output, ensure_ascii=False)
    assert (
        "🚫" in output_str or "block" in output_str.lower()
    ), f"Qwen strict profile should flag as block, got: {output}"


def test_claude_lax_profile_demotes_yaml_load_to_warn():
    """Claude profile demotes py-yaml-load-without-loader; it must not block."""
    bad = (FIXTURES / "bad_yaml_load.py").read_text()
    output = _scan_as("claude-opus-4", bad)
    output_str = json.dumps(output, ensure_ascii=False)
    assert (
        "warn" in output_str.lower() or "⚠️" in output_str
    ), f"Claude profile should warn, got: {output}"
    assert "🚫" not in output_str, "Claude profile should not emit block emoji at demoted severity"
    assert "block" not in output_str.lower(), "Claude profile should not block at demoted severity"


def test_deepseek_moderate_profile_warns_only():
    """deepseek profile keeps default warn severity."""
    bad = (FIXTURES / "bad_yaml_load.py").read_text()
    output = _scan_as("deepseek-v3", bad)
    output_str = json.dumps(output, ensure_ascii=False)
    assert (
        "⚠️" in output_str or "warn" in output_str.lower()
    ), f"deepseek should warn only, got: {output}"
    assert "🚫" not in output_str, "deepseek should not block at default severity"
