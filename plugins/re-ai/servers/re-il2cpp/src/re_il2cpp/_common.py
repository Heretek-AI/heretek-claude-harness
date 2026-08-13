"""Shared low-level helpers for the re_il2cpp package.

Lives in its own module to avoid the circular import between
``metadata.py`` (string-table reader) and ``tables.py`` (binary-table
walker). Both modules import from here.
"""

from __future__ import annotations

import mmap
import os
import struct
from typing import Any


# Magic number (little-endian uint32 at file offset 0).
MAGIC = 0xFAB11BAF

# Supported metadata versions: 24-31 covering Unity 2019.4 LTS - Unity 6
# (Unity 6 ships as "6000.0.x" in the Editor version string).
#
# v2.9.1 (Gap 25 fix): bumped MAX_VERSION from 29 to 31. The
# v30/v31 on-disk layout is forward-compatible with v25plus
# per Il2CppDumper's Metadata.cs (v30 keeps the same header
# offsets through the published Unity 6 RC). The version_table
# ``format_key`` resolves major >= 30 to ``"v25plus"`` until
# field-size deltas are confirmed; if a future version surfaces
# a divergent layout, add a per-version format key on demand.
# The runtime warning in ``read_header`` (when version >= 30)
# surfaces the assumption so a future divergence is a parser
# error, not silent corruption.
MIN_VERSION = 24
MAX_VERSION = 31


class Il2CppMetadataError(Exception):
    """Raised when a file is not a valid global-metadata.dat."""


def _open_mmap(path: str) -> tuple[int, mmap.mmap]:
    """Open *path* read-only and return ``(file_size, mmap)``."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    size = os.path.getsize(path)
    if size < 8:
        raise Il2CppMetadataError(
            f"{path}: too small ({size} bytes) to be global-metadata.dat"
        )
    fd = os.open(path, os.O_RDONLY)
    try:
        mm = mmap.mmap(fd, 0, access=mmap.ACCESS_READ)
    finally:
        os.close(fd)
    return size, mm


def read_header(path: str) -> dict[str, Any]:
    """Read the magic and version, return them as a dict.

    Validates magic and the version range, so the user gets a clear
    error if they point us at a non-IL2CPP file. The full 22-field
    header is read by ``tables._read_full_header``; this is the cheap
    validation gate.
    """
    size, mm = _open_mmap(path)
    try:
        magic = struct.unpack_from("<I", mm, 0)[0]
        if magic != MAGIC:
            raise Il2CppMetadataError(
                f"{path}: bad magic 0x{magic:08X} (expected 0x{MAGIC:08X})"
            )
        version = struct.unpack_from("<i", mm, 4)[0]
        if not (MIN_VERSION <= version <= MAX_VERSION):
            raise Il2CppMetadataError(
                f"{path}: unsupported metadata version {version} "
                f"(supported: {MIN_VERSION}-{MAX_VERSION}, "
                f"i.e. Unity 2019.4 LTS - Unity 6)"
            )
        result = {
            "path": path,
            "size_bytes": size,
            "magic": f"0x{magic:08X}",
            "version": version,
            "version_supported": True,
            "note": (
                "Read the unprotected C# string table to recover the "
                "original C# class FQNs / method names / field names "
                "that IL2CPP stripped from GameAssembly.dll."
            ),
        }
        # v2.9.1 (Gap 25): runtime warning when version >= 30 to
        # surface the v30+ forward-compat assumption. If records
        # are malformed on a v30+ target, the analyst sees this
        # warning and knows to file a bug — not to trust silent
        # corruption.
        if version >= 30:
            result["v30plus_warning"] = (
                f"v{version} layout is forward-compatibility aliased "
                f"over v25plus; if records are malformed, file a bug"
            )
        return result
    finally:
        mm.close()
