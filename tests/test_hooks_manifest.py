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
    # PreToolUse has the original entry + the telemetry_collector entry (Task 3)
    assert len(pre_tool) == 2
    matcher_entry = pre_tool[0]
    assert matcher_entry["matcher"] == "Edit|Write|MultiEdit"
    hook = matcher_entry["hooks"][0]
    assert hook["type"] == "command"
    assert "fast_gate.py" in hook["command"]
    assert hook["timeout"] == 1


def test_hooks_manifest_validates_full_tree(repo_root: Path, schemas_dir: Path) -> None:
    """The full validate.py run must accept plugins/hooks/hooks/hooks.json."""
    errors = validate.validate_all(repo_root, schemas_dir=schemas_dir)
    assert errors == [], f"validate_all flagged: {errors}"
