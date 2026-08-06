"""Model profile loader (#44).

Loads per-model enforcement profiles from `catalog/model_profiles/<model-id>.yaml`
and applies them to pattern definitions (promote/demote severities).

Active model is resolved from env var HERETEK_ACTIVE_MODEL, defaulting to
'claude-opus-4' (the lightest enforcement profile).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROFILES_DIR = Path(__file__).resolve().parent.parent / "catalog" / "model_profiles"
DEFAULT_MODEL_ID = "claude-opus-4"


def list_known_profiles() -> list[str]:
    """Return IDs of all known model profiles."""
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def resolve_active_model_id() -> str:
    """Resolve the active model ID from env var HERETEK_ACTIVE_MODEL."""
    return os.environ.get("HERETEK_ACTIVE_MODEL", DEFAULT_MODEL_ID)


def load_profile(model_id: str) -> dict:
    """Load a profile by ID. Raises FileNotFoundError if unknown."""
    path = PROFILES_DIR / f"{model_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No profile for model {model_id!r}")
    return yaml.safe_load(path.read_text())


def apply_profile_to_pattern(pattern: dict, profile: dict) -> dict:
    """Apply a profile's enforcement rules to a single pattern definition.

    Promote/demote semantics:
      * Ids in ``profile.enforcement.promote_to_block`` are upgraded
        ``warn → error`` (errors remain errors).
      * Ids in ``profile.enforcement.demote_to_warn`` are downgraded
        ``error → warn`` (warns remain warns).
      * Ids in neither list are passed through unchanged.

    Collision guard: if a pattern ``id`` appears in BOTH
    ``promote_to_block`` and ``demote_to_warn`` for the same profile,
    the ordering is ambiguous, so this raises :class:`ValueError` rather
    than silently picking one. Resolve the collision in the profile YAML
    before applying.
    """
    pid = pattern["id"]
    severity = pattern["severity"]
    enforcement = profile.get("enforcement", {})

    promote = enforcement.get("promote_to_block", [])
    demote = enforcement.get("demote_to_warn", [])

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
