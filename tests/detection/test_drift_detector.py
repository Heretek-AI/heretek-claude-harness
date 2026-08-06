"""Tests for drift_detector.py (#41).

All tests are fully isolated: state file is redirected to a per-test
`tmp_path` via `monkeypatch.setattr(..., SESSION_STATE_DIR, tmp_path)`,
synthetic stdin payloads are injected via `monkeypatch.setattr(sys, "stdin", ...)`,
and stdout is captured via `capsys`. No test ever touches the real
`.heretek/session_state/` tree.
"""
import io
import json
import sys

import pytest

import scripts.drift_detector as hook


def _build_payload(
    session_id: str,
    file_path: str,
    new_string: str,
    old_string: str = "",
) -> dict:
    return {
        "session_id": session_id,
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {
            "file_path": file_path,
            "new_string": new_string,
            "old_string": old_string,
        },
    }


def _run_hook(monkeypatch, payload: dict) -> int:
    """Invoke hook.main() with synthetic stdin JSON; returns exit code."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return hook.main()


def _capture_output(monkeypatch, payload: dict, capsys) -> dict:
    rc = _run_hook(monkeypatch, payload)
    captured = capsys.readouterr()
    assert rc == 0, f"hook should not error; stderr: {captured.err}"
    return json.loads(captured.out) if captured.out.strip() else {}


def test_drift_detector_warns_on_repeated_edits(monkeypatch, tmp_path, capsys):
    """#41: 3+ edits to same file → warning."""
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-repeated"
    target = tmp_path / "foo.py"
    target.write_text("v1\n")

    # First two edits — silent.
    out1 = _capture_output(monkeypatch, _build_payload(sid, str(target), "v1\n"), capsys)
    out2 = _capture_output(monkeypatch, _build_payload(sid, str(target), "v2\n"), capsys)
    assert out1 == {}, f"first edit should be silent: {out1}"
    assert out2 == {}, f"second edit should be silent: {out2}"

    # Third edit — should warn.
    out3 = _capture_output(monkeypatch, _build_payload(sid, str(target), "v3\n"), capsys)
    assert "hookSpecificOutput" in out3, f"expected warning JSON, got: {out3}"
    ctx = out3["hookSpecificOutput"]["additionalContext"]
    assert "drift" in ctx.lower()
    assert "foo.py" in ctx


def test_drift_detector_silent_on_normal_workflow(monkeypatch, tmp_path, capsys):
    """#41: distinct file edits do NOT trigger warnings."""
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-clean"
    for i in range(3):
        target = tmp_path / f"file_{i}.py"
        target.write_text(f"v{i}\n")
        out = _capture_output(monkeypatch, _build_payload(sid, str(target), f"v{i}\n"), capsys)
        assert out == {}, f"unexpected warning on distinct file: {out}"


def test_drift_detector_warns_on_monotonic_growth(monkeypatch, tmp_path, capsys):
    """#41: strictly increasing diff_size across last 5 edits → warning.

    Each edit grows the file by a strictly larger amount than the previous one,
    so the diff_size series is strictly increasing.
    """
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-grow"
    target = tmp_path / "grow.py"
    target.write_text("")

    # Diff sizes: 1, 2, 3, 4, 5 — strictly increasing. We track the cumulative
    # file length so the diff between new_string and old_string is exactly `d`.
    diffs = [1, 2, 3, 4, 5]
    total = 0
    for d in diffs:
        old = "x" * total
        new = "x" * (total + d)
        total += d
        out = _capture_output(
            monkeypatch, _build_payload(sid, str(target), new, old), capsys
        )
    assert "hookSpecificOutput" in out, f"expected monotonic-growth warning, got: {out}"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "strictly increasing" in ctx, f"expected monotonicity text in: {ctx}"


def test_drift_detector_no_monotonicity_warning_on_steady_growth(
    monkeypatch, tmp_path, capsys
):
    """#41: constant diff_sizes across edits do NOT trigger monotonicity warning.

    diff_size must be strictly increasing — constant appends are fine.
    Other warnings (e.g., repeated edits) may still fire on the same edit.
    """
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-steady"
    target = tmp_path / "steady.py"
    target.write_text("")

    # Use 3 edits (the minimum to evaluate monotonicity) with constant diff_size.
    for i in range(3):
        old = "x" * i
        new = "x" * (i + 1)  # diff_size = 1 every time
        out = _capture_output(
            monkeypatch, _build_payload(sid, str(target), new, old), capsys
        )
    assert "hookSpecificOutput" in out, f"expected at least repeated-edit warning, got: {out}"
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "strictly increasing" not in ctx, (
        f"constant diff_size must not produce monotonicity warning, got: {ctx}"
    )


def test_drift_detector_warns_on_unreferenced_import(monkeypatch, tmp_path, capsys):
    """#41: import added in one edit and not referenced in the next → warning."""
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-import"
    target = tmp_path / "mod.py"

    # Edit 1: add `import os`. Pending list grows.
    out1 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "import os\n"),
        capsys,
    )
    assert out1 == {}, f"first edit (just adding import) should be silent: {out1}"

    # Edit 2: replace with something that does NOT reference os.
    # This means pending import `os` is never referenced → should warn.
    out2 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "x = 1\n", "import os\n"),
        capsys,
    )
    assert "hookSpecificOutput" in out2, f"expected unreferenced-import warning, got: {out2}"
    ctx = out2["hookSpecificOutput"]["additionalContext"]
    assert "os" in ctx
    assert "import" in ctx.lower()


def test_drift_detector_silent_when_import_referenced(monkeypatch, tmp_path, capsys):
    """#41: import added and then used in subsequent edit → no warning."""
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-import-used"
    target = tmp_path / "used.py"

    out1 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "import os\n"),
        capsys,
    )
    assert out1 == {}, f"first edit should be silent: {out1}"

    # Edit 2 references `os` via `os.path`.
    out2 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "x = os.path.join('a', 'b')\n", "import os\n"),
        capsys,
    )
    assert out2 == {}, f"referenced import should not warn, got: {out2}"


def test_drift_detector_migrates_legacy_state_with_length_key(
    monkeypatch, tmp_path, capsys
):
    """Re-review I-NEW-1: legacy edit records use `length` instead of `diff_size`.

    Pre-populate a state file with the old schema, then ensure the hook loads
    it without KeyError and behaves correctly (no crash, no spurious warning).
    """
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-legacy"
    target = tmp_path / "foo.py"
    state_file = tmp_path / f"{sid}.json"
    # 2 legacy entries for the SAME path the next edit will target.
    state_file.write_text(json.dumps({
        "edits": [
            {"file": str(target), "length": 5},
            {"file": str(target), "length": 7},
        ],
        "imports": {},
    }))

    # If migration fails, recent_diffs lookup will raise KeyError and the
    # hook will exit non-zero — guard against that regression.
    out = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "x" * 10),
        capsys,
    )
    # Edit count is now 3 → repeated-edit warning is expected and proves the
    # legacy records were loaded successfully.
    ctx = out.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "drift" in ctx.lower(), f"expected drift warning after legacy migration, got: {out}"


def test_drift_detector_ignores_reimports_from_old_string(
    monkeypatch, tmp_path, capsys
):
    """Re-review I-NEW-2: imports that exist in old_string are NOT new.

    If an import appears in both old_string and new_string, it must not be
    queued as pending — it's not new, just re-stated.
    """
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-reimport"
    target = tmp_path / "mod.py"

    # Edit 1: file had `import os; x=1` → `import os; x=2`. Both old and new
    # contain `os`, so `os` is NOT new.
    out1 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "import os\nx = 2\n", "import os\nx = 1\n"),
        capsys,
    )
    assert out1 == {}, f"first edit (re-import) should be silent: {out1}"

    # Edit 2: replace with code that does NOT include `import os` and doesn't
    # reference it. With the bug, `os` was queued in edit 1 → warns. With the
    # fix, `os` was never new → no warning about `os`.
    out2 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "x = 3\n", "import os\nx = 2\n"),
        capsys,
    )
    ctx2 = out2.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "added import(s) not referenced" not in ctx2, (
        f"re-imported symbol must not warn about being unreferenced: {out2}"
    )


def test_drift_detector_ignores_imports_used_in_same_edit(
    monkeypatch, tmp_path, capsys
):
    """Re-review I-NEW-2: imports used in the SAME edit are not pending.

    A single edit that introduces and uses an import (e.g., `import os;
    os.getcwd()`) must not flag `os` as pending, because the import was
    already used in the introducing edit.
    """
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-same-edit"
    target = tmp_path / "mod.py"

    # Edit 1: introduces AND uses `os` in the same edit.
    out1 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "import os\nx = os.getcwd()\n"),
        capsys,
    )
    assert out1 == {}, f"first edit (introduce+use same edit) should be silent: {out1}"

    # Edit 2: replace with code that drops the import and doesn't reference `os`.
    # With the bug, `os` was queued in edit 1 → warns. With the fix, `os` was
    # used in edit 1 → never queued.
    out2 = _capture_output(
        monkeypatch,
        _build_payload(
            sid, str(target), "y = 1\n", "import os\nx = os.getcwd()\n"
        ),
        capsys,
    )
    ctx2 = out2.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "added import(s) not referenced" not in ctx2, (
        f"import used in same edit must not warn on next, got: {out2}"
    )


def test_drift_detector_warns_once_per_unreferenced_import(
    monkeypatch, tmp_path, capsys
):
    """Re-review M-NEW: unreferenced imports warn on next edit only, then drop.

    Import added and never referenced → warns on edit 2 but NOT on edit 3,
    because the import is dropped from pending after the first warning.
    """
    monkeypatch.setattr(hook, "SESSION_STATE_DIR", tmp_path)
    sid = "test-session-warn-once"
    target = tmp_path / "mod.py"

    # Edit 1: add `import os` (silent).
    out1 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "import os\n"),
        capsys,
    )
    assert out1 == {}, f"first edit should be silent: {out1}"

    # Edit 2: replace with code that does NOT reference `os` → warns.
    out2 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "x = 1\n", "import os\n"),
        capsys,
    )
    ctx2 = out2.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "added import(s) not referenced" in ctx2, (
        f"expected unreferenced-import warning on edit 2, got: {out2}"
    )

    # Edit 3: another edit that still doesn't reference `os` → must NOT
    # re-warn about `os` (dropped from pending after edit 2).
    # Repeated-edit warnings may still fire, so check for the import text.
    out3 = _capture_output(
        monkeypatch,
        _build_payload(sid, str(target), "x = 2\n", "x = 1\n"),
        capsys,
    )
    ctx3 = out3.get("hookSpecificOutput", {}).get("additionalContext", "")
    assert "added import(s) not referenced" not in ctx3, (
        f"third edit must not re-warn about dropped import, got: {out3}"
    )
