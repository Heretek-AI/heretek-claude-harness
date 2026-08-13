"""IL2CPP metadata header field offsets for Unity 2019.4 - 2022.3 LTS.

The field order in the ``global-metadata.dat`` header is stable across
metadata versions 24, 25, 26, 27, 28, and 29 (covering Unity 2019.4,
2020.3, 2021.3, and 2022.3 LTS lines). Each field is a ``(offset, count)``
pair of ``uint32`` values, totalling 8 bytes. The field order is
reverse-engineered from the public ``MetadataLoader.cs`` shipped with
Il2CppDumper.

Header layout (all little-endian):

    0x00  uint32  magic          (always 0xFAB11BAF)
    0x04  int32   version        (24-29 for the supported range)
    0x08  (offset, count) stringLiteral
    0x10  (offset, count) stringLiteralData
    0x18  (offset, count) string
    0x20  (offset, count) events
    0x28  (offset, count) properties
    0x30  (offset, count) methods
    0x38  (offset, count) parameterDefaultValues
    0x40  (offset, count) fieldDefaultValues
    0x48  (offset, count) fieldAndParameterDefaultValueData
    0x50  (offset, count) fieldMarshaledSizes
    0x58  (offset, count) parameters
    0x60  (offset, count) fields
    0x68  (offset, count) genericParameters
    0x70  (offset, count) genericParameterConstraints
    0x78  (offset, count) genericContainers
    0x80  (offset, count) nestedTypes
    0x88  (offset, count) interfaces
    0x90  (offset, count) vtableMethods
    0x98  (offset, count) interfaceOffsets
    0xA0  (offset, count) typeDefinitions
    0xA8  (offset, count) images
    0xB0  (offset, count) assemblies

Total header size for v24-v29 = 0xB8 (184) bytes for the supported
fields above. v27 in practice extends to 0x110 (additional post-
assemblies fields like ``referencedAssemblies``); we don't read them
in the MVP — the string table is sufficient to recover the readable
C# class graph.
"""

from __future__ import annotations

import mmap
import struct
from typing import NamedTuple


class FieldSpec(NamedTuple):
    """One ``(offset, count)`` pair slot in the header."""

    name: str
    header_offset: int


# Field order in the header (after the 8-byte magic+version prefix).
# The header offset is the byte position of the ``offset`` uint32;
# the count uint32 immediately follows at +4.
FIELDS: list[FieldSpec] = [
    FieldSpec("stringLiteral", 0x08),
    FieldSpec("stringLiteralData", 0x10),
    FieldSpec("string", 0x18),
    FieldSpec("events", 0x20),
    FieldSpec("properties", 0x28),
    FieldSpec("methods", 0x30),
    FieldSpec("parameterDefaultValues", 0x38),
    FieldSpec("fieldDefaultValues", 0x40),
    FieldSpec("fieldAndParameterDefaultValueData", 0x48),
    FieldSpec("fieldMarshaledSizes", 0x50),
    FieldSpec("parameters", 0x58),
    FieldSpec("fields", 0x60),
    FieldSpec("genericParameters", 0x68),
    FieldSpec("genericParameterConstraints", 0x70),
    FieldSpec("genericContainers", 0x78),
    FieldSpec("nestedTypes", 0x80),
    FieldSpec("interfaces", 0x88),
    FieldSpec("vtableMethods", 0x90),
    FieldSpec("interfaceOffsets", 0x98),
    FieldSpec("typeDefinitions", 0xA0),
    FieldSpec("images", 0xA8),
    FieldSpec("assemblies", 0xB0),
]

# Unity version -> metadata header version.
# v24 = Unity 2019.4, v25-v26 = Unity 2020.x, v27 = Unity 2020.3+,
# v28 = Unity 2021.3+, v29 = Unity 2022.3+.
# v2.9.1 (Gap 25 fix): extend to v30/v31 (Unity 2023.x / Unity 6).
# Unity 6 ships as "6000.0.x" in the Editor version string.
UNITY_TO_HEADER_VERSION: dict[str, int] = {
    "2019.4": 24,
    "2020.1": 24,
    "2020.2": 26,
    "2020.3": 27,
    "2021.1": 27,
    "2021.2": 27,
    "2021.3": 28,
    "2022.1": 28,
    "2022.2": 29,
    "2022.3": 29,
    # v2.9.1 additions — forward-compat aliases over v25plus
    # record format. See ``read_header`` runtime warning when
    # version >= 30.
    "2023.1": 30,
    "2023.2": 30,
    "2023.3": 30,
    "6.0": 31,
    "6000.0": 31,
    "6000.1": 31,
}

MIN_SUPPORTED_VERSION = 24
MAX_SUPPORTED_VERSION = 31
MAGIC = 0xFAB11BAF


def is_supported(version: int) -> bool:
    return MIN_SUPPORTED_VERSION <= version <= MAX_SUPPORTED_VERSION


# ── Sub-version detection (v24.x only) ──────────────────────────────────
#
# The v24 metadata format has 5 documented sub-versions (24.0, 24.1, 24.2,
# 24.4, 24.5) with slightly different struct layouts. v25+ uses a single
# stable layout per record. The detection tree below replicates the logic
# in Il2CppDumper's `Metadata.cs:67-83`.


def _read_u32_pair(mm: mmap.mmap, offset: int) -> tuple[int, int]:
    """Read two little-endian uint32 values starting at *offset*.

    Returns (offset_value, count_value). Helper for reading a header
    ``(offset, count)`` pair.
    """
    a, b = struct.unpack_from("<II", mm, offset)
    return a, b


def detect_subversion(mm: mmap.mmap, major_version: int) -> int:
    """Return the minor sub-version (0 for v25+; 0-5 for v24).

    Replicates Il2CppDumper/Il2Cpp/Metadata.cs:67-83. The tree is:
      - v25+ → 0 (no sub-version)
      - v24 with stringLiteralOffset == 264 → 2
      - v24 with imageDefs[0].token != 0 → 1
      - v24 otherwise → 4 (best-effort default)

    The imageDef record size for v24.1 is 40 bytes; the ``token`` field is
    at offset 0x20 within the record. We only need to check the FIRST
    image — if any image's token is non-zero, this is v24.1.
    """
    if major_version != 24:
        return 0
    # v24.2 detection: stringLiteralOffset == 264
    string_literal_offset, _ = _read_u32_pair(mm, 0x08)
    if string_literal_offset == 264:
        return 2
    # v24.1 detection: imageDefs[0].token != 0
    images_offset, images_count = _read_u32_pair(mm, 0xA8)
    if images_count > 0 and images_offset + 0x24 <= len(mm):
        first_image_token = struct.unpack_from("<I", mm, images_offset + 0x20)[0]
        if first_image_token != 0:
            return 1
    # Default for v24 with no positive signal — best-effort v24.4
    return 4


def format_key(major_version: int, minor_version: int) -> str:
    """Return the RECORD_FORMATS key for a given (major, minor) version.

    v25+ all use ``"v25plus"``. v24.1 uses ``"v24.1"`` (the only v24
    sub-version we currently support with a distinct format; v24.0/24.2/
    24.4/24.5 fall back to ``"v25plus"`` with a runtime warning if the
    layout differs).
    """
    if major_version >= 25:
        return "v25plus"
    if minor_version == 1:
        return "v24.1"
    # v24.0/24.2/24.4/24.5 fall back to v25plus formats
    return "v25plus"


# ── Per-version struct formats ──────────────────────────────────────────
#
# Each entry maps record name -> (struct_format_string, size_in_bytes).
# The format strings are little-endian ('<') and use:
#   I = uint32, i = int32, H = uint16, h = int16
#
# Sizes are computed by `struct.calcsize(fmt)`. The values below are
# reverse-engineered from Il2CppDumper's `MetadataClass.cs` source. v25+
# is the stable layout used by Unity 2020.3+ through Unity 2022.3 LTS.
# v24.1 has a few extra ints in methodDef (methodIndex, invokerIndex,
# delegateWrapperIndex, rgctxStartIndex, rgctxCount) and the typeDef
# token field is present (it was absent in v24.0).


RECORD_FORMATS: dict[str, dict[str, tuple[str, int]]] = {
    "v25plus": {
        # 16 x (int|uint) = 64, 8 x uint16 = 16, 2 x uint = 8 -> 88 bytes
        "typeDefinitions": ("<IIIIIIIIIIIIIIIIHHHHHHHHII", 88),
        # nameIndex, declaringType, returnType, parameterStart,
        # genericContainerIndex, token, flags, iflags, slot, parameterCount
        # -> 6 x 4 + 4 x 2 = 32 bytes
        "methods": ("<IIIIIIHHHH", 32),
        # nameIndex, typeIndex, token -> 12 bytes
        "fields": ("<III", 12),
        # nameIndex, token, typeIndex -> 12 bytes
        "parameters": ("<III", 12),
        # nameIndex, get, set, attrs, token -> 20 bytes
        "properties": ("<IIIII", 20),
        # nameIndex, typeIndex, add, remove, raise, token -> 24 bytes
        "events": ("<IIIIII", 24),
        # 10 x 4-byte fields = 40 bytes
        "images": ("<IIIIIIIIII", 40),
    },
    "v24.1": {
        # Same typeDef as v25plus (token field is present)
        "typeDefinitions": ("<IIIIIIIIIIIIIIIIHHHHHHHHII", 88),
        # v24.1 methodDef has 5 extra ints (methodIndex, invokerIndex,
        # delegateWrapperIndex, rgctxStartIndex, rgctxCount) inserted
        # between genericContainerIndex and token. Total: 10 ints +
        # 4 uint16 = 40 + 8 = 48 bytes
        "methods": ("<IIIIIIIIIHHHHH", 48),
        # Same as v25plus for these smaller records
        "fields": ("<III", 12),
        "parameters": ("<III", 12),
        "properties": ("<IIIII", 20),
        "events": ("<IIIIII", 24),
        "images": ("<IIIIIIIIII", 40),
    },
}


# ── Il2CppCodeRegistration field offsets ─────────────────────────────────
#
# When parsing GameAssembly.dll to resolve a method's RVA, we need the
# offset of the `codeGenModuleMethodPointers` field within the
# Il2CppCodeRegistration C struct. The offset depends on the Unity
# major version (different fields are present in different versions).
#
# These offsets are best-effort. The Day 3 validation step is to
# cross-reference a returned RVA against `re-rizin.disassemble_function`
# output to confirm the right offset was used.
#
# Source: Il2CppDumper/Il2Cpp/Il2CppCodeRegistration.cs (per major version).


CODE_REGISTRATION_FIELDS: dict[int, dict[str, int]] = {
    24: {
        "codeGenModuleMethodPointers": 0x60,
        "codeGenModuleMethodPointersWithMetadata": 0x68,
    },
    25: {
        "codeGenModuleMethodPointers": 0x70,
        "codeGenModuleMethodPointersWithMetadata": 0x78,
    },
    27: {
        "codeGenModuleMethodPointers": 0x80,
        "codeGenModuleMethodPointersWithMetadata": 0x88,
    },
    29: {
        "codeGenModuleMethodPointers": 0x88,
        "codeGenModuleMethodPointersWithMetadata": 0x90,
    },
}


def code_registration_field_offset(major_version: int, field: str) -> int:
    """Return the field offset of *field* in the Il2CppCodeRegistration struct.

    Falls back to the v27 offset if the version is not in the table (v25
    is close enough to v27 that this is usually safe; v26 and v28 also
    fall through here).
    """
    if major_version in CODE_REGISTRATION_FIELDS:
        return CODE_REGISTRATION_FIELDS[major_version][field]
    # Fallback: use the most-recent known version's offsets
    return CODE_REGISTRATION_FIELDS[27][field]
