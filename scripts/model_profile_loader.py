"""Model profile loader (#44)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, cast

import yaml

PROFILES_DIR = Path(__file__).resolve().parent.parent / "catalog" / "model_profiles"
DEFAULT_MODEL_ID = "claude-opus-4"


def list_known_profiles() -> list[str]:
    """Return IDs of all known model profiles."""
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def resolve_active_model_id() -> str:
    """Resolve the active model ID from env var HERETEK_ACTIVE_MODEL."""
    return os.environ.get("HERETEK_ACTIVE_MODEL", DEFAULT_MODEL_ID)


def load_profile(model_id: str) -> dict[str, Any]:
    """Load a profile by ID. Raises FileNotFoundError if unknown."""
    path = PROFILES_DIR / f"{model_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No profile for model {model_id!r}")
    loaded: Any = yaml.safe_load(path.read_text())
    if not isinstance(loaded, dict):
        raise ValueError(f"profile in {path} must be a dict")
    return cast(dict[str, Any], loaded)


def apply_profile_to_pattern(pattern: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Apply a profile's enforcement rules to a single pattern definition."""
    pid = cast(str, pattern["id"])
    severity = cast(str, pattern["severity"])
    enforcement = cast(dict[str, Any], profile.get("enforcement", {}))

    promote = cast(list[str], enforcement.get("promote_to_block", []))
    demote = cast(list[str], enforcement.get("demote_to_warn", []))

    if pid in promote and pid in demote:
        raise ValueError(
            f"profile collision for id {pid!r}: appears in both "
            f"promote_to_block and demote_to_warn"
        )

    if pid in promote and severity == "warn":
        severity = "error"
    if pid in demote and severity == "error":
        severity = "warn"

    return {**pattern, "severity": severity}
