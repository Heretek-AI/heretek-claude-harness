"""Tests for plugins/hooks/hooks/hooks.json — Layer-1 manifest wiring."""

import json
import sys
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import validate  # noqa: E402


HOOKS_JSON = REPO_ROOT / "plugins" / "hooks" / "hooks" / "hooks.json"


def test_hooks_manifest_exists() -> None:
    assert HOOKS_JSON.is_file(), f"missing {HOOKS_JSON}"


def test_hooks_manifest_validates_against_schema(
    schemas_dir: Path,
) -> None:
    schema = json.loads((schemas_dir / "hooks.schema.json").read_text())
    instance = json.loads(HOOKS_JSON.read_text())
    jsonschema.validate(instance=instance, schema=schema)


def test_hooks_manifest_has_fast_gate_pre_tool_use() -> None:
    instance = json.loads(HOOKS_JSON.read_text())
    pre_tool = instance["hooks"]["PreToolUse"]
    # PreToolUse must contain a fast_gate entry on Edit|Write|MultiEdit
    # plus a telemetry_collector entry (v3.5 collector sprint invariant)
    fast_gate_entries = [e for e in pre_tool if e["matcher"] == "Edit|Write|MultiEdit"]
    assert len(fast_gate_entries) == 1, "expected exactly one fast_gate PreToolUse entry"
    hook = fast_gate_entries[0]["hooks"][0]
    assert hook["type"] == "command"
    assert "fast_gate.py" in hook["command"]
    assert hook["timeout"] == 1
    # Telemetry collector entry must also be wired in
    telemetry_entries = [e for e in pre_tool if "telemetry_collector" in str(e)]
    assert telemetry_entries, "expected telemetry_collector wired into PreToolUse"


def test_hooks_manifest_validates_full_tree(repo_root: Path, schemas_dir: Path) -> None:
    """The full validate.py run must accept plugins/hooks/hooks/hooks.json."""
    errors = validate.validate_all(repo_root, schemas_dir=schemas_dir)
    assert errors == [], f"validate_all flagged: {errors}"
