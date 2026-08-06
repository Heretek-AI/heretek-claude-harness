"""Tests for ast_grep_scanner.py (#43) — the synchronous D15 fast gate.

All tests are fully isolated: synthetic stdin payloads are injected via
`monkeypatch.setattr(sys, "stdin", ...)`, and stdout is captured via
`capsys`. No test ever touches the real catalog or filesystem state.
"""
import io
import json
import sys
import time
from pathlib import Path

import pytest

import scripts.scanners.ast_grep_scanner as hook

FIXTURES = Path(__file__).parent / "fixtures"


def _build_payload(file_path: str, content: str) -> dict:
    return {
        "session_id": "test",
        "hook_event_name": "PreToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": content},
    }


def _run_hook(monkeypatch, payload: dict) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def _capture_output(monkeypatch, payload: dict, capsys) -> dict:
    rc = _run_hook(monkeypatch, payload)
    captured = capsys.readouterr()
    assert rc == 0, f"hook should not error; stderr: {captured.err}"
    return json.loads(captured.out) if captured.out.strip() else {}


def test_ast_grep_scanner_blocks_error_severity_pattern(monkeypatch, capsys):
    """#43: scanner emits permissionDecision=ask on rust-todo-macro (severity=error)."""
    bad = FIXTURES / "bad_todo_macro.rs"
    payload = _build_payload(str(bad), bad.read_text())
    out = _capture_output(monkeypatch, payload, capsys)
    assert "hookSpecificOutput" in out, f"expected hook output, got: {out}"
    specific = out["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "ask", \
        f"expected permissionDecision=ask, got: {specific}"
    assert "rust-todo-macro" in specific["permissionDecisionReason"], \
        f"expected pattern ID in reason, got: {specific}"


def test_ast_grep_scanner_allows_clean_code(monkeypatch, capsys):
    """#43: scanner does NOT block clean subprocess.run usage."""
    good = FIXTURES / "good_subprocess_list.py"
    payload = _build_payload(str(good), good.read_text())
    out = _capture_output(monkeypatch, payload, capsys)
    assert out == {}, f"unexpected block on clean code: {out}"


def test_ast_grep_scanner_ignores_unsupported_languages(monkeypatch, capsys, tmp_path):
    """#43: scanner is a no-op for non-tracked file extensions."""
    fake = tmp_path / "config.txt"
    fake.write_text("this is just text\n")
    payload = _build_payload(str(fake), fake.read_text())
    out = _capture_output(monkeypatch, payload, capsys)
    assert out == {}, f"scanner should ignore .txt files: {out}"


def test_ast_grep_scanner_latency_under_100ms(monkeypatch, capsys):
    """#43: scanner p95 latency must be <100ms (D15 fast gate budget)."""
    good = FIXTURES / "good_subprocess_list.py"
    payload = _build_payload(str(good), good.read_text())
    samples = []
    for _ in range(20):
        start = time.time()
        _capture_output(monkeypatch, payload, capsys)
        samples.append((time.time() - start) * 1000)
    p95 = sorted(samples)[int(0.95 * len(samples))]
    assert p95 < 100, f"p95 latency {p95:.0f}ms exceeds 100ms budget (samples: {samples})"
