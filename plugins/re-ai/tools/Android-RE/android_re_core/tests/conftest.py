"""conftest for the android_re_core test package.

Adds the package's ``src/`` directory to ``sys.path`` so the inner test
modules can ``import android_re_core`` without an editable install.
Also re-exports the ``make_apk`` and ``make_elf`` fixtures from the
top-level ``tests/conftest.py``.
"""

from __future__ import annotations

import sys
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture
def make_apk(tmp_path: Path) -> Callable[..., Path]:
    """Synthetic APK factory (mirror of the top-level fixture)."""

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
