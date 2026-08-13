"""Binary table walkers for Unity IL2CPP ``global-metadata.dat``.

This module reads the **structured** data that lives alongside the
unprotected C# symbol table: the ``typeDefinitions``, ``methods``,
``fields``, ``parameters``, ``properties``, ``events``, and
``images`` record arrays. Each record's ``nameIndex`` /
``namespaceIndex`` is a ``uint32`` byte offset from the start of the
``string`` table (a packed run of NUL-terminated UTF-8 strings); we
resolve those to UTF-8 via ``_read_string_at``.

Format reverse-engineered from
[Il2CppDumper](https://github.com/Perfare/Il2CppDumper)'s
``Il2CppDumper/Il2Cpp/MetadataClass.cs``. Per-version struct sizes and
field layouts live in ``version_table.RECORD_FORMATS``.

Public API (consumed by ``metadata.py`` and ``server.py``):

    get_type_definitions(path, namespace="", limit=500)
    get_methods(path, class_fqn, limit=500)
    get_fields(path, class_fqn, limit=200)
    get_parameters(path, method_fqn, limit=50)
    get_properties(path, class_fqn, limit=200)
    get_events(path, class_fqn, limit=200)
    get_images(path)

Plus the lower-level helpers used by ``rva_resolver.py``:

    find_type_definition_by_fqn(path, fqn)
    find_method_by_name(path, class_fqn, method_name)
    _image_for_type(images, type_index)
"""

from __future__ import annotations

import mmap
import os
import struct
from functools import lru_cache
from typing import Any, Callable

from re_il2cpp._common import Il2CppMetadataError, _open_mmap, read_header
from re_il2cpp.version_table import (
    FIELDS,
    RECORD_FORMATS,
    detect_subversion,
    format_key,
)


# ── Header reading ─────────────────────────────────────────────────────


def _read_u32_pair_at(mm: mmap.mmap, header_offset: int) -> tuple[int, int]:
    """Read a little-endian ``(uint32 offset, uint32 count)`` pair.

    Used to slurp one entry of the global-metadata header.
    """
    a, b = struct.unpack_from("<II", mm, header_offset)
    return a, b


def _read_full_header(path: str) -> dict[str, Any]:
    """Read the full 22-field header into a dict.

    Validates magic + version via ``read_header`` first. Returns a dict
    keyed by the FIELDS name, plus the major/minor version and a
    computed ``format_key`` for the per-version struct table.

    Note: the second uint32 in each header pair is the **size in
    bytes** of the table's record array, not a count of records. The
    count is derived per-table as ``size_bytes // record_size``.
    """
    hdr = read_header(path)
    size, mm = _open_mmap(path)
    try:
        out: dict[str, Any] = {
            "magic": hdr["magic"],
            "version": hdr["version"],
            "size_bytes": hdr["size_bytes"],
        }
        for spec in FIELDS:
            offset, size_bytes = _read_u32_pair_at(mm, spec.header_offset)
            out[spec.name] = {"offset": offset, "size_bytes": size_bytes}
        # Sub-version detection (v24 only; v25+ returns 0)
        major = hdr["version"]
        minor = detect_subversion(mm, major)
        out["major"] = major
        out["minor"] = minor
        out["format_key"] = format_key(major, minor)
        return out
    finally:
        mm.close()


@lru_cache(maxsize=8)
def _read_full_header_cached(
    path: str, size: int, mtime_ns: int
) -> dict[str, Any]:
    """Cached full-header read.

    Cache key includes size + mtime so a re-read of the same file is
    free, and a re-read of a different file with the same path
    invalidates the cache. The cache is bounded at 8 entries.
    """
    return _read_full_header(path)


def get_header(path: str) -> dict[str, Any]:
    """Read the full header (cached). Caller must NOT mutate the result."""
    st = os.stat(path)
    return _read_full_header_cached(path, st.st_size, st.st_mtime_ns)


# ── String resolution ──────────────────────────────────────────────────


def _read_string_at(
    mm: mmap.mmap, string_offset: int, name_index: int
) -> str:
    """Resolve a nameIndex (uint32 byte offset from stringOffset) to a
    UTF-8 string.

    The ``string`` table at ``header.string.offset`` is a packed run of
    NUL-terminated UTF-8 strings. This is identical in shape to what
    Il2CppDumper's ``GetStringFromIndex`` does: find the next NUL past
    ``stringOffset + name_index`` and decode.
    """
    abs_pos = string_offset + name_index
    if abs_pos < 0 or abs_pos >= len(mm):
        return ""
    nul = mm.find(b"\x00", abs_pos)
    if nul < 0:
        return ""
    raw = mm[abs_pos:nul]
    try:
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


# ── Generic table walker ──────────────────────────────────────────────


def _read_record_array(
    mm: mmap.mmap,
    header: dict[str, Any],
    field_name: str,
    formatter: Callable[[tuple, int], dict[str, Any]],
    *,
    start_index: int = 0,
    count_override: int | None = None,
) -> list[dict[str, Any]]:
    """Walk a binary table and return its records as a list of dicts.

    Args:
        mm: open mmap of the metadata file
        header: output of ``get_header`` (the full 22-field header)
        field_name: the FIELDS name whose ``(offset, size_bytes)``
            locates this table (e.g. ``"typeDefinitions"``)
        formatter: ``(unpacked_tuple, record_index) -> dict`` that maps
            the raw struct tuple to the user-facing dict
        start_index: skip this many records at the start of the table
            (used by ``get_methods`` etc. to scope to a class's range)
        count_override: override the table's full count (used together
            with ``start_index`` to read a sub-range)
    """
    table = header.get(field_name)
    if table is None or table["offset"] == 0 or table["size_bytes"] == 0:
        return []
    full_offset = table["offset"]
    full_size = table["size_bytes"]
    fmt_key = header["format_key"]
    fmt, record_size = RECORD_FORMATS[fmt_key][field_name]
    if full_size % record_size != 0:
        raise Il2CppMetadataError(
            f"{field_name} table size {full_size} is not a multiple of "
            f"record_size {record_size} — header may be corrupt or "
            f"version is misdetected"
        )
    full_count = full_size // record_size
    # Sanity: ensure the table fits in the file
    needed = full_offset + full_size
    if needed > len(mm):
        raise Il2CppMetadataError(
            f"{field_name} table at 0x{full_offset:X} size={full_size} "
            f"extends past EOF ({needed} > {len(mm)})"
        )
    # Sub-range bounds
    if start_index < 0 or start_index > full_count:
        return []
    end_index = (
        full_count
        if count_override is None
        else min(start_index + count_override, full_count)
    )
    if end_index <= start_index:
        return []
    unpack = struct.Struct(fmt).unpack_from
    out: list[dict[str, Any]] = []
    for i in range(start_index, end_index):
        raw = unpack(mm, full_offset + i * record_size)
        out.append(formatter(raw, i))
    return out


# ── Public helpers used by rva_resolver ───────────────────────────────


def find_type_definition_by_fqn(
    path: str, fqn: str
) -> dict[str, Any] | None:
    """Return the typeDef record for *fqn*, or None if not found.

    Walks the typeDefinitions table; expensive (linear scan, but bounded
    by the number of typeDefs in the file). Used by
    ``rva_resolver.resolve_method_rva`` to find a class's image and
    method/field range.
    """
    if "." not in fqn:
        return None
    target_ns, _, target_name = fqn.rpartition(".")
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]
        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (
                name_index,
                namespace_index,
                _byval,
                _declaring,
                parent_index,
                _element,
                _generic,
                _flags,
                field_start,
                method_start,
                event_start,
                property_start,
                _nested_start,
                _interfaces_start,
                _vtable_start,
                _interface_offsets_start,
                method_count,
                property_count,
                field_count,
                event_count,
                nested_type_count,
                _vtable_count,
                _interfaces_count,
                _interface_offsets_count,
                _bitfield,
                _token,
            ) = raw
            return {
                "type_index": i,
                "name": _read_string_at(mm, string_offset, name_index),
                "namespace": _read_string_at(mm, string_offset, namespace_index),
                "parent_index": parent_index,
                "field_start": field_start,
                "method_start": method_start,
                "event_start": event_start,
                "property_start": property_start,
                "method_count": method_count,
                "field_count": field_count,
                "property_count": property_count,
                "event_count": event_count,
                "nested_type_count": nested_type_count,
            }

        records = _read_record_array(mm, header, "typeDefinitions", _fmt)
        for rec in records:
            if rec["namespace"] == target_ns and rec["name"] == target_name:
                return rec
        return None
    finally:
        mm.close()


def find_method_by_name(
    path: str, class_fqn: str, method_name: str
) -> dict[str, Any] | None:
    """Return the methodDef record for *class_fqn.method_name*, or None.

    Scans the class's method range (typeDef.methodStart .. +methodCount).
    """
    type_def = find_type_definition_by_fqn(path, class_fqn)
    if type_def is None:
        return None
    method_start = type_def["method_start"]
    method_count = type_def["method_count"]
    if method_count <= 0 or method_start < 0:
        return None
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (
                name_index,
                declaring_type,
                return_type,
                parameter_start,
                generic_container_index,
                token,
                flags,
                iflags,
                slot,
                parameter_count,
            ) = raw
            return {
                "method_index": method_start + i,
                "name": _read_string_at(mm, string_offset, name_index),
                "declaring_type": declaring_type,
                "return_type_index": return_type,
                "parameter_start": parameter_start,
                "generic_container_index": generic_container_index,
                "token": f"0x{token:08X}",
                "flags": flags,
                "iflags": iflags,
                "slot": slot,
                "parameter_count": parameter_count,
            }

        records = _read_record_array(
            mm,
            header,
            "methods",
            _fmt,
            start_index=method_start,
            count_override=method_count,
        )
        for rec in records:
            if rec["name"] == method_name:
                return rec
        return None
    finally:
        mm.close()


def _image_for_type(
    images: list[dict[str, Any]], type_index: int
) -> dict[str, Any] | None:
    """Find the image record that owns a given type_index.

    An image owns types in the range ``[type_start, type_start + type_count)``.
    """
    for img in images:
        ts = img.get("type_start", -1)
        tc = img.get("type_count", 0)
        if ts >= 0 and tc > 0 and ts <= type_index < ts + tc:
            return img
    return None


# ── 7 table walker functions ───────────────────────────────────────────


def get_type_definitions(
    path: str, namespace: str = "", limit: int = 500
) -> list[dict[str, Any]]:
    """Walk the ``typeDefinitions`` table; return structured records.

    Each record: ``{fqn, namespace, parent, type_index, method_count,
    field_count, property_count, event_count, nested_type_count,
    flags, token}``.

    *namespace*, if non-empty, filters results to typeDefs whose FQN
    starts with ``namespace + "."``.
    """
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]
        prefix = f"{namespace}." if namespace else ""

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (
                name_index,
                namespace_index,
                _byval,
                _declaring,
                parent_index,
                _element,
                _generic,
                flags,
                field_start,
                method_start,
                event_start,
                property_start,
                _nested_start,
                _interfaces_start,
                _vtable_start,
                _interface_offsets_start,
                method_count,
                property_count,
                field_count,
                event_count,
                nested_type_count,
                _vtable_count,
                _interfaces_count,
                _interface_offsets_count,
                _bitfield,
                token,
            ) = raw
            ns_name = _read_string_at(mm, string_offset, namespace_index)
            type_name = _read_string_at(mm, string_offset, name_index)
            fqn = f"{ns_name}.{type_name}" if ns_name else type_name
            return {
                "fqn": fqn,
                "namespace": ns_name,
                "name": type_name,
                "parent_index": parent_index,
                "type_index": i,
                "method_count": method_count,
                "field_count": field_count,
                "property_count": property_count,
                "event_count": event_count,
                "nested_type_count": nested_type_count,
                "field_start": field_start,
                "method_start": method_start,
                "event_start": event_start,
                "property_start": property_start,
                "flags": f"0x{flags:08X}",
                "token": f"0x{token:08X}",
            }

        all_records = _read_record_array(mm, header, "typeDefinitions", _fmt)
        if prefix:
            return [r for r in all_records if r["fqn"].startswith(prefix)][:limit]
        return all_records[:limit]
    finally:
        mm.close()


def get_assembly_types(
    path: str, image_name: str, limit: int = 500
) -> list[dict[str, Any]]:
    """Walk the typeDef range owned by a single IL2CPP image.

    Unlike :func:`get_type_definitions` (which scans the full table and
    filters by namespace), this scopes to the slice of typeDefinitions
    that belongs to one assembly — e.g. the publisher's
    ``Assembly-CSharp.dll`` or the engine's ``UnityEngine.CoreModule.dll``.

    The string-table scan in :func:`list_classes` cannot surface
    root-namespace classes (the publisher's game code is typically in
    the root namespace of ``Assembly-CSharp.dll``), so this is the
    recommended entry point for getting the actual game class graph.

    Each record: ``{fqn, namespace, name, type_index, method_count,
    field_count, property_count, event_count, nested_type_count,
    parent_index, token, flags}`` — same shape as
    :func:`get_type_definitions`.

    Args:
        path: path to global-metadata.dat
        image_name: assembly file name, e.g. ``"Assembly-CSharp.dll"``
        limit: maximum results
    """
    if not image_name:
        raise ValueError("image_name is required")
    images = get_images(path)
    target = next((img for img in images if img["name"] == image_name), None)
    if target is None:
        return []
    type_start = target["type_start"]
    type_count = target["type_count"]
    if type_count == 0:
        return []
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (
                name_index,
                namespace_index,
                _byval,
                _declaring,
                parent_index,
                _element,
                _generic,
                flags,
                field_start,
                method_start,
                event_start,
                property_start,
                _nested_start,
                _interfaces_start,
                _vtable_start,
                _interface_offsets_start,
                method_count,
                property_count,
                field_count,
                event_count,
                nested_type_count,
                _vtable_count,
                _interfaces_count,
                _interface_offsets_count,
                _bitfield,
                token,
            ) = raw
            ns_name = _read_string_at(mm, string_offset, namespace_index)
            type_name = _read_string_at(mm, string_offset, name_index)
            fqn = f"{ns_name}.{type_name}" if ns_name else type_name
            return {
                "fqn": fqn,
                "namespace": ns_name,
                "name": type_name,
                "parent_index": parent_index,
                "type_index": i,
                "method_count": method_count,
                "field_count": field_count,
                "property_count": property_count,
                "event_count": event_count,
                "nested_type_count": nested_type_count,
                "field_start": field_start,
                "method_start": method_start,
                "event_start": event_start,
                "property_start": property_start,
                "flags": f"0x{flags:08X}",
                "token": f"0x{token:08X}",
            }

        return _read_record_array(
            mm,
            header,
            "typeDefinitions",
            _fmt,
            start_index=type_start,
            count_override=type_count,
        )[:limit]
    finally:
        mm.close()


def get_methods(
    path: str, class_fqn: str, limit: int = 500
) -> list[dict[str, Any]]:
    """Return the methods of *class_fqn* as a structured list.

    Each record: ``{name, method_index, token, return_type_index,
    parameter_start, parameter_count, slot, flags, iflags,
    generic_container_index}``.

    The declaring class is implied by *class_fqn*; it is not repeated
    in each record.
    """
    type_def = find_type_definition_by_fqn(path, class_fqn)
    if type_def is None:
        raise ValueError(f"class not found in metadata: {class_fqn!r}")
    method_start = type_def["method_start"]
    method_count = type_def["method_count"]
    if method_count <= 0 or method_start < 0:
        return []
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (
                name_index,
                declaring_type,
                return_type,
                parameter_start,
                generic_container_index,
                token,
                flags,
                iflags,
                slot,
                parameter_count,
            ) = raw
            return {
                "name": _read_string_at(mm, string_offset, name_index),
                "method_index": method_start + i,
                "declaring_type": declaring_type,
                "return_type_index": return_type,
                "parameter_start": parameter_start,
                "generic_container_index": generic_container_index,
                "token": f"0x{token:08X}",
                "flags": f"0x{flags:04X}",
                "iflags": f"0x{iflags:04X}",
                "slot": slot,
                "parameter_count": parameter_count,
            }

        return _read_record_array(
            mm,
            header,
            "methods",
            _fmt,
            start_index=method_start,
            count_override=min(method_count, limit),
        )
    finally:
        mm.close()


def get_fields(
    path: str, class_fqn: str, limit: int = 200
) -> list[dict[str, Any]]:
    """Return the fields of *class_fqn* as a structured list.

    Each record: ``{name, field_index, type_index, token}``.
    """
    type_def = find_type_definition_by_fqn(path, class_fqn)
    if type_def is None:
        raise ValueError(f"class not found in metadata: {class_fqn!r}")
    field_start = type_def["field_start"]
    field_count = type_def["field_count"]
    if field_count <= 0 or field_start < 0:
        return []
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (name_index, type_index, token) = raw
            return {
                "name": _read_string_at(mm, string_offset, name_index),
                "field_index": field_start + i,
                "type_index": type_index,
                "token": f"0x{token:08X}",
            }

        return _read_record_array(
            mm,
            header,
            "fields",
            _fmt,
            start_index=field_start,
            count_override=min(field_count, limit),
        )
    finally:
        mm.close()


def get_parameters(
    path: str, method_fqn: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Return the parameters of a method (in declaration order).

    *method_fqn* is ``"ClassName.MethodName"``. If multiple methods
    share a name, the first match (by table order) is used.

    Each record: ``{name, parameter_index, type_index, token}``.
    """
    if "." not in method_fqn:
        raise ValueError(
            f"method_fqn must be 'ClassName.MethodName', got {method_fqn!r}"
        )
    class_fqn, _, method_name = method_fqn.rpartition(".")
    method = find_method_by_name(path, class_fqn, method_name)
    if method is None:
        raise ValueError(
            f"method not found in metadata: {method_fqn!r}"
        )
    parameter_start = method["parameter_start"]
    parameter_count = method["parameter_count"]
    if parameter_count <= 0 or parameter_start < 0:
        return []
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (name_index, token, type_index) = raw
            return {
                "name": _read_string_at(mm, string_offset, name_index),
                "parameter_index": parameter_start + i,
                "type_index": type_index,
                "token": f"0x{token:08X}",
            }

        return _read_record_array(
            mm,
            header,
            "parameters",
            _fmt,
            start_index=parameter_start,
            count_override=min(parameter_count, limit),
        )
    finally:
        mm.close()


def get_properties(
    path: str, class_fqn: str, limit: int = 200
) -> list[dict[str, Any]]:
    """Return the properties of *class_fqn*.

    Each record: ``{name, has_getter, has_setter, attrs, token}``.
    """
    type_def = find_type_definition_by_fqn(path, class_fqn)
    if type_def is None:
        raise ValueError(f"class not found in metadata: {class_fqn!r}")
    property_start = type_def["property_start"]
    property_count = type_def["property_count"]
    if property_count <= 0 or property_start < 0:
        return []
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (name_index, get_idx, set_idx, attrs, token) = raw
            return {
                "name": _read_string_at(mm, string_offset, name_index),
                "has_getter": get_idx >= 0,
                "has_setter": set_idx >= 0,
                "attrs": f"0x{attrs:08X}",
                "token": f"0x{token:08X}",
            }

        return _read_record_array(
            mm,
            header,
            "properties",
            _fmt,
            start_index=property_start,
            count_override=min(property_count, limit),
        )
    finally:
        mm.close()


def get_events(
    path: str, class_fqn: str, limit: int = 200
) -> list[dict[str, Any]]:
    """Return the events of *class_fqn*.

    Each record: ``{name, type_index, has_add, has_remove, has_raise,
    token}``.
    """
    type_def = find_type_definition_by_fqn(path, class_fqn)
    if type_def is None:
        raise ValueError(f"class not found in metadata: {class_fqn!r}")
    event_start = type_def["event_start"]
    event_count = type_def["event_count"]
    if event_count <= 0 or event_start < 0:
        return []
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (name_index, type_index, add_idx, remove_idx, raise_idx, token) = raw
            return {
                "name": _read_string_at(mm, string_offset, name_index),
                "type_index": type_index,
                "has_add": add_idx >= 0,
                "has_remove": remove_idx >= 0,
                "has_raise": raise_idx >= 0,
                "token": f"0x{token:08X}",
            }

        return _read_record_array(
            mm,
            header,
            "events",
            _fmt,
            start_index=event_start,
            count_override=min(event_count, limit),
        )
    finally:
        mm.close()


def get_images(path: str) -> list[dict[str, Any]]:
    """Walk the ``images`` table; return assembly image records.

    Each record: ``{name, assembly_index, type_start, type_count,
    exported_type_start, exported_type_count, entry_point_index,
    token}``.

    ``name`` is the assembly file name (e.g. ``"Assembly-CSharp.dll"``,
    ``"UnityEngine.CoreModule.dll"``) — this is the key into
    GameAssembly.dll's ``codeGenModuleMethodPointers[const char*]``
    hash map (see ``rva_resolver.py``).
    """
    header = get_header(path)
    mm_size, mm = _open_mmap(path)
    try:
        string_offset = header["string"]["offset"]

        def _fmt(raw: tuple, i: int) -> dict[str, Any]:
            (
                name_index,
                assembly_index,
                type_start,
                type_count,
                exported_type_start,
                exported_type_count,
                entry_point_index,
                token,
                _custom_attr_start,
                _custom_attr_count,
            ) = raw
            return {
                "name": _read_string_at(mm, string_offset, name_index),
                "image_index": i,
                "assembly_index": assembly_index,
                "type_start": type_start,
                "type_count": type_count,
                "exported_type_start": exported_type_start,
                "exported_type_count": exported_type_count,
                "entry_point_index": entry_point_index,
                "token": f"0x{token:08X}",
            }

        return _read_record_array(mm, header, "images", _fmt)
    finally:
        mm.close()
