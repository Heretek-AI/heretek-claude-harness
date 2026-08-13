"""Binary reader for Unity IL2CPP ``global-metadata.dat``.

This module recovers the **readable C# symbol table** that the IL2CPP
compiler dropped into the unprotected ``global-metadata.dat`` file next
to a Unity game's ``GameAssembly.dll``. The data is the original C#
class FQNs, method names, field names, namespace names, etc. — all
plain UTF-8, null-terminated, packed contiguously.

What it does NOT do (future work): resolve a C# method's RVA in
``GameAssembly.dll``. The structured record arrays (``typeDefinitions``,
``methods``, ``fields``, ``parameters``, ``properties``, ``events``,
``images``) are walked by the ``tables`` submodule (re-exported below).

Format reverse-engineered from the public ``MetadataLoader.cs`` and
``MetadataClass.cs`` shipped with
[Il2CppDumper](https://github.com/Perfare/Il2CppDumper). The full
binary table layout is version-sensitive (24-29 across Unity
2019.4 - 2022.3 LTS) and is handled by the per-version struct format
table in ``version_table.RECORD_FORMATS``.
"""

from __future__ import annotations

import mmap
import os
import re
import struct
from typing import Any

# Shared low-level helpers (moved here to break a circular import
# between metadata.py and tables.py).
from re_il2cpp._common import (  # noqa: E402,F401
    Il2CppMetadataError,
    MAGIC,
    MAX_VERSION,
    MIN_VERSION,
    _open_mmap,
    read_header,
)

# Re-exports from tables.py — keep the public API surface as
# ``from re_il2cpp import metadata`` (so server.py doesn't need new
# imports) while keeping the implementation in a separate module.
from re_il2cpp.tables import (  # noqa: E402,F401
    find_method_by_name,
    find_type_definition_by_fqn,
    get_assembly_types,
    get_events,
    get_fields,
    get_images,
    get_methods,
    get_parameters,
    get_properties,
    get_type_definitions,
)


# A C# identifier is a letter/underscore followed by alphanumerics/underscores.
# A class FQN is one or more dotted identifiers, optionally followed by `<` (generic)
# or `/` (nested-type marker in IL2CPP mangling).
_CLASS_FQN_RE = re.compile(
    rb"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)"
    rb"(?:[<`/].*)?$"
)

# A C# identifier-shaped string (used to harvest the string table).
_IDENT_RE = re.compile(rb"^[A-Za-z_][A-Za-z0-9_]*$")


# ── String table scan ───────────────────────────────────────────────────
#
# The string table in global-metadata.dat is a packed sequence of
# null-terminated UTF-8 strings. We scan the whole file (typically
# 5-15 MB) and harvest strings that look like C# identifiers or FQNs.
# This is a *scan*, not a table walk — slightly slower than a direct
# offset read, but version-agnostic and works on every supported
# Unity LTS line.

# Cap on the number of strings to harvest from one file. Real Unity
# games have ~1-2 M strings in the C# symbol table; we cap at 5 M
# to bound memory if a file turns out to be larger than expected.
_MAX_STRINGS = 5_000_000

# Cap on the length of a single harvested string. C# identifiers
# are <200 chars in practice; longer strings are usually assembly
# manifest blobs, not C# symbols.
_MAX_STRING_LEN = 512


def _harvest_strings(mm: mmap.mmap) -> list[str]:
    """Walk the mmap, harvest null-terminated strings, return as a list.

    Filters: only emit strings that match a C# identifier pattern
    (a plain identifier or a dotted FQN optionally followed by `<`/`/`).
    """
    out: list[str] = []
    pos = 0
    end = len(mm)
    # We find the next null, then check the chunk before it.
    while pos < end and len(out) < _MAX_STRINGS:
        nul = mm.find(b"\x00", pos)
        if nul < 0:
            break
        if nul - pos > 0 and nul - pos <= _MAX_STRING_LEN:
            chunk = mm[pos:nul]
            # Skip 1- and 2-character "strings" — they're usually
            # noise from the assembly metadata blob (single-letter
            # flags, single-char type codes) rather than C# symbols.
            if len(chunk) < 3:
                pos = nul + 1
                continue
            # Cheap prefilter: a C# identifier or FQN must contain
            # all printable ASCII or valid UTF-8 with no control bytes.
            if b"\n" not in chunk and b"\r" not in chunk and b"\t" not in chunk:
                if _IDENT_RE.match(chunk) or _CLASS_FQN_RE.match(chunk):
                    try:
                        s = chunk.decode("utf-8")
                    except UnicodeDecodeError:
                        pass
                    else:
                        out.append(s)
        pos = nul + 1
    return out


def list_strings(
    path: str, substring: str = "", limit: int = 500
) -> list[str]:
    """Return C#-identifier-shaped strings harvested from the file.

    Args:
        path: path to global-metadata.dat
        substring: if set, only return strings containing this
            case-sensitive substring
        limit: maximum results (default 500)
    """
    read_header(path)  # validate magic + version
    _, mm = _open_mmap(path)
    try:
        strings = _harvest_strings(mm)
    finally:
        mm.close()
    if substring:
        out = [s for s in strings if substring in s]
    else:
        out = strings
    return out[:limit]


# ── Class / namespace extraction ────────────────────────────────────────


def _is_class_fqn(s: str) -> bool:
    """Return True if *s* looks like a C# class FQN (dotted)."""
    return bool(_CLASS_FQN_RE.match(s.encode("utf-8")))


def _namespace_of(s: str) -> str:
    """Return the namespace (everything before the last dot) of a
    class FQN. Returns "" for top-level types.
    """
    # Class name may be followed by `<` (generic), `/` (nested), or
    # `\` (rare). Find the last '.' before any of these markers.
    for sep in ("<", "/", "`"):
        i = s.find(sep)
        if i >= 0:
            s = s[:i]
            break
    if "." in s:
        return s.rsplit(".", 1)[0]
    return ""


def list_namespaces(path: str, limit: int = 200) -> list[dict[str, Any]]:
    """Return a sorted list of namespaces with class counts.

    Scans the C# string table for class FQNs and buckets them by
    namespace.
    """
    read_header(path)  # validate
    _, mm = _open_mmap(path)
    try:
        strings = _harvest_strings(mm)
    finally:
        mm.close()
    buckets: dict[str, int] = {}
    for s in strings:
        if not _is_class_fqn(s):
            continue
        ns = _namespace_of(s)
        buckets[ns] = buckets.get(ns, 0) + 1
    return [
        {"namespace": ns, "class_count": n}
        for ns, n in sorted(buckets.items())
    ][:limit]


def list_classes(
    path: str, namespace: str = "", limit: int = 500
) -> list[dict[str, str]]:
    """Return class FQNs harvested from the C# string table.

    Args:
        path: path to global-metadata.dat
        namespace: if set, only return classes whose FQN starts with
            ``namespace + "."`` (e.g. ``"UnityEngine"``)
        limit: maximum results
    """
    read_header(path)  # validate
    _, mm = _open_mmap(path)
    try:
        strings = _harvest_strings(mm)
    finally:
        mm.close()
    prefix = f"{namespace}." if namespace else ""
    out: list[dict[str, str]] = []
    for s in strings:
        if not _is_class_fqn(s):
            continue
        if prefix and not s.startswith(prefix):
            continue
        out.append({"fqn": s, "namespace": _namespace_of(s)})
        if len(out) >= limit:
            break
    return out


def search_strings(
    path: str, substring: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Substring search of the C# symbol table.

    Returns ``[{index, string}]`` matches. Useful for finding asset
    paths, save keys, or specific gameplay terms in the metadata.
    """
    if not substring:
        return []
    read_header(path)  # validate
    _, mm = _open_mmap(path)
    try:
        strings = _harvest_strings(mm)
    finally:
        mm.close()
    out: list[dict[str, Any]] = []
    for i, s in enumerate(strings):
        if substring in s:
            out.append({"index": i, "string": s})
            if len(out) >= limit:
                break
    return out
