"""Tests for model_profile_loader.py and scanner integration."""

import importlib
from pathlib import Path

import pytest

from scripts.model_profile_loader import (
    load_profile,
    list_known_profiles,
    resolve_active_model_id,
    apply_profile_to_pattern,
)


def test_load_known_profile():
    """#44: loader reads a known profile by ID."""
    profile = load_profile("qwen3.6-27b")
    assert profile["model_id"] == "qwen3.6-27b"
    assert "py-yaml-load-without-loader" in profile["enforcement"]["promote_to_block"]


def test_load_unknown_profile_raises():
    """#44: loader raises on unknown profile ID."""
    with pytest.raises(FileNotFoundError):
        load_profile("nonexistent-model-xyz")


def test_list_known_profiles_includes_all_four():
    """#44: list_known_profiles returns the 4 initial models."""
    profiles = list_known_profiles()
    assert {"qwen3.6-27b", "deepseek-v3", "claude-opus-4", "gemini-2.5"} <= set(profiles)


def test_resolve_active_model_from_env(monkeypatch):
    """#44: env var HERETEK_ACTIVE_MODEL resolves the active profile."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "deepseek-v3")
    assert resolve_active_model_id() == "deepseek-v3"


def test_resolve_active_model_default(monkeypatch):
    """#44: missing env var returns the 'claude-opus-4' default."""
    monkeypatch.delenv("HERETEK_ACTIVE_MODEL", raising=False)
    assert resolve_active_model_id() == "claude-opus-4"


def test_apply_profile_promotes_pattern_severity():
    """#44: profile.promote_to_block upgrades pattern severity from warn → error."""
    profile = load_profile("qwen3.6-27b")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "warn"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "error"


def test_apply_profile_passes_through_warn():
    """#44: pattern severity 'warn' stays 'warn' when not listed in promote_to_block."""
    profile = load_profile("claude-opus-4")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "warn"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "warn"


def test_apply_profile_demotes_error_to_warn():
    """#44: profile.demote_to_warn downgrades pattern severity from error → warn."""
    profile = load_profile("claude-opus-4")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "error"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "warn"


def test_apply_profile_raises_on_promote_demote_collision():
    """#44: a pattern ID listed in both promote_to_block and demote_to_warn is rejected."""
    profile = {
        "model_id": "test-collision",
        "enforcement": {
            "promote_to_block": ["py-yaml-load-without-loader"],
            "demote_to_warn": ["py-yaml-load-without-loader"],
        },
    }
    pattern = {"id": "py-yaml-load-without-loader", "severity": "warn"}
    with pytest.raises(ValueError, match="collision"):
        apply_profile_to_pattern(pattern, profile)


@pytest.mark.skipif(
    not Path("/home/linuxbrew/.linuxbrew/bin/ast-grep").exists()
    and __import__("shutil").which("ast-grep") is None,
    reason="ast-grep not installed",
)
def test_qwen_profile_emits_error_marker_for_py_yaml_load(monkeypatch):
    """#44 integration: HERETEK_ACTIVE_MODEL=qwen3.6-27b promotes py-yaml-load-without-loader to error → 🚫 marker."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "qwen3.6-27b")
    scanner_module = importlib.import_module("scripts.scanners.forbidden_pattern_scanner")
    importlib.reload(scanner_module)

    bad_py = "import yaml\nyaml.load(data)\n"
    warnings = scanner_module._scan("test.py", bad_py)
    assert any("🚫" in w for w in warnings), f"expected 🚫 marker, got: {warnings}"
    assert all(
        "⚠️" not in w.replace("⚠️  ", "") for w in warnings if "🚫" in w
    ), f"expected 🚫 (not ⚠️) on a qwen-promoted violation: {warnings}"


@pytest.mark.skipif(
    not Path("/home/linuxbrew/.linuxbrew/bin/ast-grep").exists()
    and __import__("shutil").which("ast-grep") is None,
    reason="ast-grep not installed",
)
def test_claude_opus_profile_emits_warn_marker_for_py_yaml_load(monkeypatch):
    """#44 integration: HERETEK_ACTIVE_MODEL=claude-opus-4 demotes py-yaml-load-without-loader to warn → ⚠️ marker."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "claude-opus-4")
    scanner_module = importlib.import_module("scripts.scanners.forbidden_pattern_scanner")
    importlib.reload(scanner_module)

    bad_py = "import yaml\nyaml.load(data)\n"
    warnings = scanner_module._scan("test.py", bad_py)
    assert any("⚠️" in w for w in warnings), f"expected ⚠️ marker, got: {warnings}"
    assert all(
        "🚫" not in w for w in warnings
    ), f"expected only ⚠️ marker (no 🚫) on a claude-opus-4-demoted violation: {warnings}"
