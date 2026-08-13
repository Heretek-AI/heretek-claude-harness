"""Tests for the :mod:`android_re_core.native` module."""

from __future__ import annotations

import struct

import pytest

from android_re_core.errors import APKError, APKInvalid
from android_re_core.native import (
    NativeView,
    PackerMatch,
    SecurityFeatures,
    parse_binary_bytes,
)


def test_native_view_lists_libs(make_apk):
    """NativeView.from_apk enumerates ``lib/<abi>/*.so`` paths."""
    from android_re_core import Apk

    apk = make_apk(include_lib64=True, include_libv7=True, include_libx86_64=True)
    ap = Apk.open(apk)
    try:
        view = NativeView.from_apk(ap)
        libs = view.list_libs()
        assert len(libs) == 3
        assert "lib/arm64-v8a/libfoo.so" in libs
        assert "lib/armeabi-v7a/libfoo.so" in libs
        assert "lib/x86_64/libfoo.so" in libs
    finally:
        ap.close()


def test_native_view_reports_abis(make_apk):
    """abis() returns the unique ABI set across all libraries."""
    from android_re_core import Apk

    apk = make_apk(include_lib64=True, include_libv7=True, include_libx86_64=True)
    ap = Apk.open(apk)
    try:
        view = NativeView.from_apk(ap)
        assert sorted(view.abis()) == ["arm64-v8a", "armeabi-v7a", "x86_64"]
    finally:
        ap.close()


def test_native_view_empty_apk(make_apk):
    """An APK with no native libs returns an empty view."""
    from android_re_core import Apk

    apk = make_apk()
    ap = Apk.open(apk)
    try:
        view = NativeView.from_apk(ap)
        assert view.list_libs() == []
        assert view.abis() == []
        assert view.lib_count() == 0
    finally:
        ap.close()


def test_parse_binary_bytes_minimal_arm64():
    """parse_binary_bytes handles a minimal AArch64 ELF."""
    # Build a tiny ELF64 (just the header + null section)
    data = _make_minimal_elf(arch="arm64")
    info = parse_binary_bytes(data, name="libtest.so")
    assert info.format == "ELF"
    assert info.architecture == "arm64"
    assert info.bits == 64
    assert info.endianness == "little"
    assert info.name == "libtest.so"


def test_parse_binary_bytes_minimal_x86_64():
    """parse_binary_bytes handles a minimal x86_64 ELF."""
    data = _make_minimal_elf(arch="x86_64")
    info = parse_binary_bytes(data, name="libtest.so")
    assert info.architecture == "x86_64"
    assert info.bits == 64


def test_parse_binary_bytes_minimal_arm():
    """parse_binary_bytes handles a minimal 32-bit ARM ELF."""
    data = _make_minimal_elf(arch="arm")
    info = parse_binary_bytes(data, name="libtest.so")
    assert info.architecture == "arm"
    assert info.bits == 32


def test_native_view_parse_unknown_lib_raises(make_apk):
    """Parsing a library not in the APK raises APKError."""
    from android_re_core import Apk

    apk = make_apk(include_lib64=True)
    ap = Apk.open(apk)
    try:
        view = NativeView.from_apk(ap)
        with pytest.raises(APKError):
            view.parse("lib/nope.so")
    finally:
        ap.close()


def test_security_features_dataclass():
    """SecurityFeatures serializes to a JSON-friendly dict."""
    sec = SecurityFeatures(
        nx=True,
        relro="full",
        stack_canary=True,
        pie=True,
        fortify=False,
        rpath=None,
        runpath=None,
        symbols_stripped=True,
    )
    d = sec.to_dict()
    assert d == {
        "nx": True,
        "relro": "full",
        "stack_canary": True,
        "pie": True,
        "fortify": False,
        "rpath": None,
        "runpath": None,
        "symbols_stripped": True,
    }


def test_packer_match_dataclass():
    """PackerMatch serializes to a JSON-friendly dict."""
    p = PackerMatch(packer="UPX", confidence=0.9, evidence="UPX! header")
    assert p.to_dict() == {
        "packer": "UPX",
        "confidence": 0.9,
        "evidence": "UPX! header",
    }


def test_native_view_closed_apk_raises(make_apk):
    """NativeView.from_apk on a closed Apk raises APKInvalid."""
    from android_re_core import Apk

    apk = make_apk(include_lib64=True)
    ap = Apk.open(apk)
    ap.close()
    with pytest.raises(APKInvalid):
        NativeView.from_apk(ap)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_elf(*, arch: str) -> bytes:
    """Same as the conftest version; duplicated here for unit test isolation."""
    if arch == "arm64":
        ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
        header = struct.pack(
            "<HHIQQQIHHHHHH",
            1,
            0xB7,
            1,
            0,
            0,
            64,
            0,
            64,
            0,
            0,
            64,
            1,
            0,
        )
        shstrtab = struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        return ident + header + shstrtab
    if arch == "x86_64":
        ident = b"\x7fELF" + bytes([2, 1, 1, 0]) + b"\x00" * 8
        header = struct.pack(
            "<HHIQQQIHHHHHH",
            1,
            0x3E,
            1,
            0,
            0,
            64,
            0,
            64,
            0,
            0,
            64,
            1,
            0,
        )
        shstrtab = struct.pack("<IIQQQQIIQQ", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        return ident + header + shstrtab
    if arch == "arm":
        ident = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\x00" * 8
        header = struct.pack(
            "<HHIIIIIHHHHHH",
            1,
            0x28,
            1,
            0,
            0,
            52,
            0,
            52,
            0,
            0,
            40,
            1,
            0,
        )
        shstrtab = struct.pack("<IIIIIIIIII", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        return ident + header + shstrtab
    raise ValueError(arch)
