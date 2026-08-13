"""Shared helpers for the static MCP server's tools.

Lifted out of smali_tools.py so decompile_tools.py, dex_tools.py, and
future tool modules can share a single per-project workdir derivation.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["project_workdir"]


def project_workdir(project_id: str, suffix: str) -> Path:
    """Return a stable per-project workdir under ``/tmp/android-re/``.

    Args:
        project_id: The id returned by ``open_project``.
        suffix: A short tag describing what lives in the workdir
            (e.g. ``"jadx"``, ``"jadx-deobf-java"``, ``"apktool"``).
            Different suffixes give different dirs.

    Override the base directory with the ``ANDROID_RE_TMP_DIR`` env var.
    """
    base = (
        Path(os.environ.get("ANDROID_RE_TMP_DIR", "/tmp")) / "android-re" / f"{project_id}-{suffix}"
    )
    return base
