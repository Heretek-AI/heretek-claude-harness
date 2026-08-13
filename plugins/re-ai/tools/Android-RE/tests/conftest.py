"""Shared pytest fixtures for the android-re test suite (Phase 2 update)."""

from __future__ import annotations

import struct
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

#: Absolute path to the monorepo root.
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the monorepo root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Directory for real-APK fixtures (DIVA, MASTG CrackMe, DVA)."""
    d = REPO_ROOT / "tests" / "fixtures"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def native_fixtures_dir() -> Path:
    """Directory for cross-arch native binary fixtures."""
    d = REPO_ROOT / "tests" / "fixtures" / "native"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture(scope="session")
def crackme_apk(fixtures_dir: Path) -> Path | None:
    """Path to the OWASP MASTG CrackMe Level 1 APK, if present."""
    candidate = fixtures_dir / "owasp-mastg-crackme-level1.apk"
    return candidate if candidate.exists() else None


requires_real_apk = pytest.mark.skipif(
    "crackme_apk is None",
    reason="Real APK fixture not present (run bin/pull-fixtures.sh to fetch).",
)


# ---------------------------------------------------------------------------
# Synthetic APK factory
# ---------------------------------------------------------------------------


@pytest.fixture
def make_apk(tmp_path: Path) -> Callable[..., Path]:
    """Return a factory that synthesizes a minimal valid APK with optional native libs."""

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
                # Pick any default ABI for include_native=True
                zf.writestr("lib/arm64-v8a/libexample.so", b"\x7fELF" + b"\x00" * 60)
            if include_lib64:
                zf.writestr("lib/arm64-v8a/libfoo.so", b"\x7fELF" + b"\x00" * 60)
            if include_libv7:
                zf.writestr("lib/armeabi-v7a/libfoo.so", b"\x7fELF" + b"\x00" * 60)
            if include_libx86_64:
                zf.writestr("lib/x86_64/libfoo.so", b"\x7fELF" + b"\x00" * 60)
        return apk

    return _make


# ---------------------------------------------------------------------------
# Synthetic ELF factory (used by native tests)
# ---------------------------------------------------------------------------


def _make_minimal_elf(arch: str = "arm64") -> bytes:
    """Create a minimal valid ELF file of the given architecture.

    The output is parseable by LIEF but has no actual code. Sufficient
    for testing the parse path; not for execution.
    """
    if arch == "arm64":
        e_class = 2  # ELF64
        e_machine = 0xB7  # AArch64
        e_ident_data = 1  # little-endian
        # ELF64 header: 64 bytes
        ident = b"\x7fELF" + bytes([e_class, e_ident_data, 1, 0]) + b"\x00" * 8
        header = struct.pack(
            "<HHIQQQIHHHHHH",
            1,  # ET_REL (relocatable)
            e_machine,
            1,  # EV_CURRENT
            0,  # e_entry
            0,  # e_phoff
            64,  # e_shoff (section headers right after)
            0,  # e_flags
            64,  # e_ehsize
            0,  # e_phentsize
            0,  # e_phnum
            64,  # e_shentsize
            1,  # e_shnum (null section)
            0,  # e_shstrndx
        )
        # Null section header
        shstrtab = struct.pack(
            "<IIQQQQIIQQ",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
        )
        return ident + header + shstrtab
    elif arch == "arm":
        e_class = 1
        e_machine = 0x28
        e_ident_data = 1
        ident = b"\x7fELF" + bytes([e_class, e_ident_data, 1, 0]) + b"\x00" * 8
        # ELF32 header: 52 bytes
        header = struct.pack(
            "<HHIIIIIHHHHHH",
            1,
            e_machine,
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
    elif arch == "x86_64":
        e_class = 2
        e_machine = 0x3E
        e_ident_data = 1
        ident = b"\x7fELF" + bytes([e_class, e_ident_data, 1, 0]) + b"\x00" * 8
        header = struct.pack(
            "<HHIQQQIHHHHHH",
            1,
            e_machine,
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
    else:
        raise ValueError(f"Unsupported arch: {arch}")


@pytest.fixture
def make_elf(native_fixtures_dir: Path) -> Callable[..., Path]:
    """Return a factory that writes a minimal ELF to a per-arch path."""

    def _make(arch: str = "arm64", name: str = "libexample.so") -> Path:
        out = native_fixtures_dir / arch / name
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(_make_minimal_elf(arch))
        return out

    return _make


# ---------------------------------------------------------------------------
# Vendor dir guard
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _ensure_clean_vendor() -> None:
    """Warn (but don't fail) if the vendored tools dir is missing."""
    vendor = REPO_ROOT / "vendor"
    if not vendor.exists():
        import warnings

        warnings.warn(
            f"vendor/ directory missing at {vendor}; some Phase 2+ tests will skip.",
            stacklevel=1,
        )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-mark tests based on naming convention."""
    for item in items:
        path = Path(item.fspath).as_posix()
        if "/device/" in path or "test_device_" in path or item.get_closest_marker("device"):
            item.add_marker(pytest.mark.device)
        elif "test_unit_" in path or "test_smoke_" in path:
            item.add_marker(pytest.mark.unit)


def pytest_report_header(config: pytest.Config) -> list[str]:
    """Add a header to the test report."""
    return [
        "android-re test suite",
        f"  repo root: {REPO_ROOT}",
        f"  vendor/: {'present' if (REPO_ROOT / 'vendor').exists() else 'missing (Phase 2+ tests will skip)'}",
    ]
