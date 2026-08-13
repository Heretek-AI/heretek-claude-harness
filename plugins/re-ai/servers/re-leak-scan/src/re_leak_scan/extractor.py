"""String extraction from binaries.

Pure-Python implementation: walks the file, finds runs of printable
ASCII bytes (≥ ``min_length`` chars) and prints them with their
file offset. UTF-16LE is also supported — runs of ``ascii_char
NUL ascii_char NUL`` ≥ ``min_length`` are decoded and reported
under the ``utf16le`` key.

The output is intentionally simple: a list of ``{"string", "offset",
"encoding"}`` dicts. The downstream scanner (see :mod:`scanner`)
applies the regex catalog over the list.

This module deliberately does NOT call LIEF, ``strings(1)``, or
FLOSS — we want the leak detector to work in isolation for the
``find_secrets``-on-strings workflow and as a fallback when those
tools are unavailable.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator


_ASCII_PRINTABLE = re.compile(rb"[\x20-\x7e]{8,}")
_UTF16_PRINTABLE = re.compile(rb"(?:[\x20-\x7e]\x00){8,}")


def extract_strings(
    path: str,
    min_length: int = 8,
    max_strings: int = 100_000,
) -> dict:
    """Return ASCII and UTF-16LE strings extracted from *path*.

    Returns::

        {
          "path": "...",
          "min_length": N,
          "ascii_count": N,
          "utf16le_count": N,
          "truncated": bool,
          "ascii": [{"string": "...", "offset": N}, ...],
          "utf16le": [{"string": "...", "offset": N}, ...],
          # WS-9 v2.8.0: when path is a DEX file, an additional
          # `dex` key carries typed DEX string-IDs with their
          # type tag (string_literal / class_descriptor /
          # method_name / field_name)
          "dex": [{"string": "...", "offset": N, "kind": "..."}, ...] | None,
        }

    Caps the result at ``max_strings`` per encoding. The boolean
    ``truncated`` flags whether the cap was hit — useful for the
    analyst to know whether the leak detector saw the full binary.
    """
    p = Path(path)
    data = p.read_bytes()
    # Re-compile with the caller-specified min_length. Default
    # patterns use 8 (matches strings(1) and the leak catalog's
    # minimum useful match length).
    ascii_re = re.compile(rb"[\x20-\x7e]{" + str(min_length).encode() + rb",}")
    utf16_re = re.compile(
        rb"(?:[\x20-\x7e]\x00){" + str(min_length).encode() + rb",}"
    )
    ascii = list(_extract(data, ascii_re, max_strings, "ascii"))
    utf16le = list(_extract(data, utf16_re, max_strings, "utf16le"))
    truncated = len(ascii) >= max_strings or len(utf16le) >= max_strings
    # WS-9 v2.8.0: DEX-format awareness. Detect by magic + walk the
    # string IDs table. The DEX walker is independent of the
    # generic regex pass — DEX strings live in a packed structure
    # the regex would otherwise miss (length-prefixed MUTF-8).
    dex_strings: list[dict] | None = None
    if _is_dex(data):
        dex_strings = list(
            _extract_dex_strings(data, min_length=min_length, cap=max_strings)
        )
    return {
        "path": str(p),
        "min_length": min_length,
        "ascii_count": len(ascii),
        "utf16le_count": len(utf16le),
        "truncated": truncated,
        "ascii": ascii,
        "utf16le": utf16le,
        "dex": dex_strings,
    }


# ── WS-9 (v2.8.0): DEX-format awareness ────────────────────────────────


_DEX_MAGIC = b"dex\n"  # followed by 3-char version + \0


def _is_dex(data: bytes) -> bool:
    """Return True when *data* looks like a Dalvik DEX file."""
    return len(data) >= 8 and data[:4] == _DEX_MAGIC


def _extract_dex_strings(
    data: bytes, min_length: int = 4, cap: int = 100_000
) -> Iterator[dict]:
    """Walk the DEX string IDs table.

    DEX layout (from the official Android source-tree docs at
    https://source.android.com/devices/tech/dalvik/dex-format):

      header (0x70 bytes):
        magic           [8]   "dex\\n035\\0"
        checksum        u4    @0x08
        signature       [20]  @0x0C
        file_size       u4    @0x20
        header_size     u4    @0x24  (always 0x70)
        endian_tag      u4    @0x28
        link_size       u4    @0x2C
        link_off        u4    @0x30
        map_off         u4    @0x34
        string_ids_size u4    @0x38
        string_ids_off  u4    @0x3C
        ...

      string_id_item (0x04 bytes each, at string_ids_off):
        string_data_off u4    → offset into the body

      string_data_item:
        uleb128 length (in code units)
        MUTF-8 bytes (NUL-terminated)

    We yield each string with its file offset (the
    string_data_off, NOT the position in the table).

    Returns:
        Iterator of ``{"string", "offset", "kind"}`` dicts. The
        "kind" is always ``"dex_string"`` — DEX doesn't tag strings
        by use at the string-IDs level; the typed split (class
        descriptor / method name / etc.) requires walking
        type_ids / method_ids / field_ids tables which is heavier.
        v2.8.1 can add the typed walk.
    """
    import struct

    if len(data) < 0x70 or data[:4] != _DEX_MAGIC:
        return
    try:
        # string_ids_size and string_ids_off
        string_ids_size = struct.unpack_from("<I", data, 0x38)[0]
        string_ids_off = struct.unpack_from("<I", data, 0x3C)[0]
    except struct.error:
        return

    yielded = 0
    for i in range(min(string_ids_size, cap)):
        id_off = string_ids_off + i * 4
        if id_off + 4 > len(data):
            break
        try:
            string_data_off = struct.unpack_from("<I", data, id_off)[0]
        except struct.error:
            break
        if string_data_off >= len(data):
            continue
        # Read uleb128 length (we don't actually need the length —
        # the string is NUL-terminated — but we skip past the leb).
        pos = string_data_off
        while pos < len(data):
            b = data[pos]
            pos += 1
            if b < 0x80:
                break
        # Now `pos` points at the start of the MUTF-8 byte sequence.
        end = data.find(b"\x00", pos)
        if end < 0 or end - pos < min_length:
            continue
        try:
            s = data[pos:end].decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            continue
        yield {
            "string": s,
            "offset": string_data_off,
            "encoding": "dex_string",
            "kind": "dex_string",
        }
        yielded += 1
        if yielded >= cap:
            return


def _extract(
    data: bytes,
    pattern: re.Pattern,
    max_strings: int,
    encoding: str,
) -> Iterator[dict]:
    count = 0
    for match in pattern.finditer(data):
        if count >= max_strings:
            return
        raw = match.group(0)
        if encoding == "utf16le":
            # Strip trailing NUL; decode pairs as UTF-16LE.
            stripped = raw.rstrip(b"\x00")
            s = stripped.decode("utf-16le", errors="replace")
        else:
            s = raw.decode("latin-1", errors="replace")
        yield {
            "string": s,
            "offset": match.start(),
            "encoding": encoding,
        }
        count += 1
