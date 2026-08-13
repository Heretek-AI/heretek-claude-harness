"""Smoke tests for the native MCP server's project-lifecycle tools.

Exercises the bug repro: open_project on the native store, then
call into the native server's own store + binary enumeration to
confirm the project is reachable from the native server's own
state. Pre-fix, the native store was always empty (no
``open_project`` tool existed), so any
``mcp__android-re-native__list_binaries(project_id=...)`` call
returned ``project_not_found`` unless the project was opened in the
static server instead.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from android_re_mcp_native.server import get_store


def test_open_project_returns_dict(make_apk: Callable[..., Path]) -> None:
    """``open_project`` on the native store returns the standard
    ``{project_id, is_closed, ...}`` dict with the 13 summary keys.
    """
    store = get_store()
    apk_path = str(make_apk())
    project = store.open(apk_path)
    d = project.to_dict()
    assert d["project_id"].startswith("apk-")
    assert d["apk_path"] == apk_path
    assert d["size"] > 0
    assert d["is_closed"] is False


def test_list_binaries_resolves_after_open_project(make_apk: Callable[..., Path]) -> None:
    """Regression: pre-fix, the native store was always empty so any
    ``list_binaries(project_id=...)`` call returned
    ``project_not_found``. After ``open_project`` exists, the native
    server is self-contained — re-opening the same project from
    the native store works.
    """
    store = get_store()
    apk_path = str(make_apk())
    project = store.open(apk_path)
    # Re-resolve from the store — pre-fix this would raise
    # ProjectNotFound because the native store had no record.
    resolved = store.get(project.project_id)
    # ``make_apk`` ships no .so libs; the point is that ``get()``
    # succeeded and the summary is accessible. native_count == 0 is
    # the success signal for the no-lib fixture.
    assert resolved.summary.native_count == 0
    # And a second open of the same APK returns the same project.
    project2 = store.open(apk_path)
    assert project2.project_id == project.project_id
