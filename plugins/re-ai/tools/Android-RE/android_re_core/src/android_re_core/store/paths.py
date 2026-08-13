"""Path helpers for the triage store.

Centralized here so the orchestrator doesn't have to know about
``platformdirs`` or env-var conventions.

The per-triage workdir is now derived from the
:data:`android_re_core.paths.OUTPUT_DIR` base, keyed on the APK's
basename + short SHA. The legacy ``./.triage``-at-cwd behaviour is
no longer supported — callers must pass the APK path.
"""

from __future__ import annotations

import os
from pathlib import Path

from android_re_core.paths import output_dir_for

# Re-export for convenience from store.__init__.
__all__ = [
    "default_db_dir",
    "default_db_path",
    "triage_workdir",
]


def default_db_dir() -> Path:
    """Return the directory used for the SQLite DB.

    Order: $ANDROID_RE_DATA_DIR → ~/.android-re/ → a tmp dir.
    """
    if env := os.environ.get("ANDROID_RE_DATA_DIR"):
        return Path(env).expanduser()
    return Path.home() / ".android-re"


def default_db_path() -> Path:
    """Return the default SQLite DB path (``triage.db``)."""
    d = default_db_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d / "triage.db"


def triage_workdir(triage_id: str, apk_path: str | os.PathLike[str]) -> Path:
    """Return the per-triage workdir under the per-APK Output/ directory.

    The result is ``Output/<apk-basename>-<short-sha>/<triage_id>/``.
    The directory is created on first call.

    Args:
        triage_id: The triage id (UUID-ish string from ``start_triage``).
        apk_path: Path to the APK that the triage was opened against.
            Used to compute the per-APK subdir.

    Returns:
        The per-triage workdir, created on disk.
    """
    base = output_dir_for(apk_path) / triage_id
    base.mkdir(parents=True, exist_ok=True)
    return base
