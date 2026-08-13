"""conftest for the native MCP server tests.

Pytest auto-discovers conftest.py only along the ancestor chain, so
we mirror the synthetic-APK fixture from ``android_re_core/tests``
here. ``android_re_core/tests`` has no ``__init__.py`` (it's not a
package — just a directory of test files), so we can't import
across.
"""

from __future__ import annotations

import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

# Make ``android_re_core`` importable for the test modules without
# requiring an editable install.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CORE_SRC = _REPO_ROOT / "android_re_core" / "src"
if str(_CORE_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_SRC))


@pytest.fixture
def make_apk(tmp_path: Path) -> Callable[..., Path]:
    """Synthetic APK factory (mirror of android_re_core's conftest)."""

    def _make(
        *,
        include_native: bool = False,
        include_lib64: bool = False,
        include_libv7: bool = False,
        include_libx86_64: bool = False,
        package: str = "com.example",
    ) -> Path:
        apk = tmp_path / f"{package}.apk"
        with zipfile.ZipFile(apk, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("AndroidManifest.xml", b"")
            zf.writestr("classes.dex", b"\x00" * 16)
            if include_native:
                zf.writestr("lib/arm64-v8a/libexample.so", b"\x7fELF" + b"\x00" * 60)
            if include_lib64:
                zf.writestr("lib/arm64-v8a/libfoo.so", b"\x7fELF" + b"\x00" * 60)
            if include_libv7:
                zf.writestr("lib/armeabi-v7a/libfoo.so", b"\x7fELF" + b"\x00" * 60)
            if include_libx86_64:
                zf.writestr("lib/x86_64/libfoo.so", b"\x7fELF" + b"\x00" * 60)
        return apk

    return _make
