"""Persistent state stores.

Phase 4 ships:

- :mod:`android_re_core.store.sqlite` — SQLite-backed triage state
  store for long-running multi-step analyses that need to survive
  server restarts.

The store API is intentionally small. It supports:

- open / close a triage
- add findings (typed)
- link findings to evidence (typed)
- checkpoint / resume
- history listing

The orchestrator MCP server (Phase 4) is the only consumer in v0.1.0.
"""

from __future__ import annotations

__all__ = ["paths", "sqlite"]


# Module-level path helpers (re-exported here for convenience).
def default_db_path() -> Path:  # type: ignore[name-defined]  # noqa: F821
    """Return the default SQLite DB path under ``~/.android-re/``."""
    import os
    from pathlib import Path

    base = Path(os.environ.get("ANDROID_RE_DATA_DIR", str(Path.home() / ".android-re")))
    base.mkdir(parents=True, exist_ok=True)
    return base / "triage.db"


def triage_dir() -> Path:  # type: ignore[name-defined]  # noqa: F821
    """Return the Output/ base directory.

    The legacy ``./.triage/`` directory at the repo root has been
    retired. Every per-triage workdir now lives under
    ``Output/<apk-basename>-<short-sha>/<triage_id>/`` (see
    :func:`android_re_core.paths.output_dir_for` and
    :func:`android_re_core.store.paths.triage_workdir`).
    """
    from android_re_core.paths import OUTPUT_DIR

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


# Avoid an import cycle: import paths only when used.
from android_re_core.store import (
    paths,
    sqlite,
)
