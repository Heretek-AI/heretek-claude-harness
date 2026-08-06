"""Freshness tokens system (#46).

Renders a token block summarizing the freshness state of all tracked
libraries. The block is injected into agent prompts at session start
(via the hooks plugin install path), giving the agent a snapshot of
"what's current" so it doesn't fall back on training-time memory.

Token format:
    # Freshness tokens (auto-injected by heretek hooks)
    # Model: <model_id> · TTL: <hours>h · Refreshed: <iso8601>
    - <lib>==<version> (fetched <iso8601>; refresh if ><ttl>h old)

The TTL is read from the active model's profile; default 24h.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from scripts.model_profile_loader import (
    load_profile,
    resolve_active_model_id,
)

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
DEFAULT_TTL_HOURS = 24


def _format_token_line(lib: str, version: str, fetched_at: datetime, ttl_hours: int) -> str:
    return (
        f"- {lib}=={version} "
        f"(fetched {fetched_at.date().isoformat()}; "
        f"refresh if >{ttl_hours}h old)"
    )


def _tracked_libs_for(model_id: str) -> list[str]:
    try:
        profile = load_profile(model_id)
        return profile.get("mandatory_lookup", [])
    except FileNotFoundError:
        return []


def render(model_id: str | None = None) -> str:
    """Render the freshness-token block for the given (or active) model."""
    model_id = model_id or resolve_active_model_id()

    try:
        profile = load_profile(model_id)
        ttl = profile.get("freshness_token_ttl_hours", DEFAULT_TTL_HOURS)
    except FileNotFoundError:
        profile = None
        ttl = DEFAULT_TTL_HOURS

    now = datetime.now(timezone.utc)
    tracked = _tracked_libs_for(model_id)

    lines = [
        "# Freshness tokens (auto-injected by heretek hooks)",
        f"# Model: {model_id} · TTL: {ttl}h · Refreshed: {now.isoformat()}",
    ]

    for lib in tracked:
        cache_file = CACHE_DIR / f"{lib.replace('.', '-')}.yaml"
        if not cache_file.exists():
            continue
        try:
            data = yaml.safe_load(cache_file.read_text())
        except yaml.YAMLError:
            continue
        version = data.get("latest_version")
        if not version:
            continue
        # Use the file's mtime as fetched_at (best available signal)
        fetched_at = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
        lines.append(_format_token_line(lib, version, fetched_at, ttl))

    if not lines[2:]:
        lines.append(f"# (no tracked libs found for {model_id}; default TTL: {ttl}h)")

    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
