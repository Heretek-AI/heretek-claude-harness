"""Tests for model_profile_loader.py and scanner integration."""
import pytest
from pathlib import Path

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


def test_apply_profile_demotes_pattern_severity():
    """#44: profile.demote_to_warn downgrades pattern severity from error → warn."""
    profile = load_profile("claude-opus-4")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "warn"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "warn"  # no change for already-warn


    profile = load_profile("claude-opus-4")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "error"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "warn"