"""APK protection classification (v2.7.0).

The :func:`classify_apk` walker implements the
``re-apktool.classify_apk_protection`` MCP tool. It opens
the APK as a zipfile, walks every ``classes*.dex`` and
``lib/*.so``, and matches the extracted content against
the vendored ``data/apkid-signatures.json`` catalog.

The walker is pure-Python (no apktool / androguard
required) so it works in degraded mode when the
:class:`re_apktool.parser` is missing optional deps. The
dex parser is a tiny subset — enough to extract the
``string_ids`` and ``class_defs`` tables; the full Smali
dump is out of scope (use ``apktool d`` for that).

All output is vendor-neutral: category names describe
observable patterns. The vendored catalog never names a
specific commercial obfuscator / packager / product.
"""

from __future__ import annotations

import json
import re
import struct
import zipfile
from pathlib import Path
from typing import Any

# Try to import the apktool parser for richer metadata;
# the classify walker only needs it for the manifest
# decoding, which we do ourselves as a fallback.
try:
    from re_apktool import parser as _parser  # type: ignore
except ImportError:  # pragma: no cover
    _parser = None


# ── Catalog loader ────────────────────────────────────────────────────


def _load_catalog() -> dict:
    """Load the vendored apkid-signatures.json catalog.

    The plugin-root is `servers/re-apktool/src/re_apktool/classify.py`
    — we walk up 4 parents to reach the data/ directory.
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "data" / "apkid-signatures.json",
        here.parents[3] / "data" / "apkid-signatures.json",
        here.parents[2] / "data" / "apkid-signatures.json",
    ]
    for p in candidates:
        if p.is_file():
            return json.loads(p.read_text())
    return {"entries": []}


# ── DEX subset parser ─────────────────────────────────────────────────


def _parse_dex_strings(data: bytes) -> list[dict[str, Any]]:
    """Best-effort parse of a DEX file's string_ids table.

    The DEX format is documented in
    https://source.android.com/devices/tech/dalvik/dex-format.
    We only need the string pool + the type-defs to support
    the catalog's ``class_name`` + ``method_signature``
    + ``string_literal`` evidence kinds.

    Returns a list of ``{"string": "...", "offset": N}`` records.
    """
    out: list[dict[str, Any]] = []
    if len(data) < 0x70:
        return out
    try:
        string_ids_size = struct.unpack_from("<I", data, 0x38)[0]
        string_ids_off = struct.unpack_from("<I", data, 0x3C)[0]
    except struct.error:
        return out
    for i in range(string_ids_size):
        try:
            str_data_off = struct.unpack_from(
                "<I", data, string_ids_off + i * 4
            )[0]
        except struct.error:
            break
        if str_data_off >= len(data):
            continue
        # ULEB128 length prefix
        try:
            length, _ = _read_uleb128(data, str_data_off)
        except (ValueError, IndexError):
            continue
        start = str_data_off + _uleb128_size(length) if False else str_data_off
        # The actual ULEB size is 1+ bytes; for our purposes
        # we read the prefix byte and skip it.
        if start >= len(data):
            continue
        # Simpler: read the ULEB prefix and offset by it.
        prefix_size = _uleb128_size(_peek_uleb128_size(data, str_data_off))
        body_off = str_data_off + prefix_size
        # DEX MUTF-8 strings end with a 0 byte; we read up
        # to length bytes.
        try:
            raw = data[body_off:body_off + length]
        except (IndexError, ValueError):
            continue
        s = raw.decode("utf-8", errors="replace").rstrip("\x00")
        if s:
            out.append({"string": s, "offset": str_data_off})
    return out


def _peek_uleb128_size(data: bytes, off: int) -> int:
    """Read the ULEB128 value at *off* and return it."""
    val = 0
    for i in range(5):
        if off + i >= len(data):
            return val
        b = data[off + i]
        val = (val << 7) | (b & 0x7F)
        if (b & 0x80) == 0:
            return val
    return val


def _read_uleb128(data: bytes, off: int) -> tuple[int, int]:
    """Read a ULEB128 from *data* at *off*; return (value, bytes_consumed)."""
    val = 0
    shift = 0
    i = 0
    while True:
        if off + i >= len(data):
            return val, i
        b = data[off + i]
        val |= (b & 0x7F) << shift
        i += 1
        if (b & 0x80) == 0:
            break
        shift += 7
    return val, i


def _uleb128_size(val: int) -> int:
    """Number of bytes to encode *val* as ULEB128."""
    if val == 0:
        return 1
    bits = val.bit_length()
    return (bits + 6) // 7


# ── The classifier ────────────────────────────────────────────────────


# Heuristic regexes for the class_name + method_signature + native_section
# evidence kinds. These are vendored into the catalog as
# ``match_pattern`` strings; the walker applies them.
_CLASS_NAME_PATTERN = re.compile(r"^[a-z]{1,2}$")
_DECRYPT_STUB_PATTERN = re.compile(
    r"public\s+static\s+string\s+[a-zA-Z0-9_]+\s*\(\s*string\s+", re.MULTILINE
)
_CERT_PINNER_PATTERN = re.compile(r"CertificatePinner", re.IGNORECASE)
_OKHTTP_PATTERN = re.compile(r"\bOkHttp\b", re.IGNORECASE)
_NATIVE_VM_PATTERN = re.compile(
    r"^\\.(text|data|bss)$", re.IGNORECASE  # the canonical .text/.data/.bss set
)
_SECTION_NAME_PATTERN = re.compile(r"\.text|\.data|\.bss")


def classify_apk(path: str, max_per_category: int = 50) -> dict:
    """Walk the APK and emit protection-category matches.

    Args:
        path: path to the APK
        max_per_category: per-category cap

    Returns the dict shape documented on
    ``re-apktool.classify_apk_protection``.
    """
    catalog = _load_catalog()
    entries = catalog.get("entries", [])
    p = Path(path)
    if not p.is_file():
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": "file not found",
        }
    matches: list[dict[str, Any]] = []
    by_category: dict[str, int] = {}
    per_category_count: dict[str, int] = {}
    truncated_per_category = False
    try:
        with zipfile.ZipFile(p, "r") as zf:
            dex_files = [n for n in zf.namelist() if n.startswith("classes") and n.endswith(".dex")]
            native_files = [n for n in zf.namelist() if n.startswith("lib/") and n.endswith(".so")]
            manifest_data = None
            try:
                manifest_data = zf.read("AndroidManifest.xml")
            except KeyError:
                pass

            for dex_name in dex_files:
                try:
                    dex_data = zf.read(dex_name)
                except (KeyError, OSError):
                    continue
                strings = _parse_dex_strings(dex_data)
                _apply_catalog_to_dex_strings(
                    entries, strings, dex_name, matches, by_category,
                    per_category_count, max_per_category,
                )
            for native_name in native_files:
                try:
                    native_data = zf.read(native_name)
                except (KeyError, OSError):
                    continue
                # Lightweight native scan: look for the section
                # names + the obfuscation string patterns.
                _apply_catalog_to_native(
                    entries, native_data, native_name, matches, by_category,
                    per_category_count, max_per_category,
                )
            if manifest_data is not None:
                _apply_catalog_to_manifest(
                    entries, manifest_data, matches, by_category,
                    per_category_count, max_per_category,
                )
    except zipfile.BadZipFile:
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": "not a valid ZIP/APK file",
        }
    except OSError as exc:
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": f"failed to read APK: {exc}",
        }
    truncated_per_category = any(
        per_category_count.get(c, 0) >= max_per_category for c in by_category
    )
    return {
        "path": path,
        "matches": matches,
        "by_category": dict(sorted(by_category.items())),
        "truncated": {"per_category": truncated_per_category},
    }


def _apply_catalog_to_dex_strings(
    entries, strings, dex_name, matches, by_category, per_category_count,
    max_per_category,
) -> None:
    for entry in entries:
        cat = entry.get("category")
        ev = entry.get("evidence_kind")
        if ev not in ("class_name", "method_signature", "string_literal"):
            continue
        if per_category_count.get(cat, 0) >= max_per_category:
            continue
        pattern = entry.get("match_pattern", "")
        # class_name heuristic: 1-2 letter class names
        if ev == "class_name":
            for s in strings:
                txt = s.get("string", "")
                # The DEX string table holds type descriptors
                # like "Lcom/foo/Bar;". Strip L/; to get the FQN.
                fqn = txt.strip("L;")
                short = fqn.rsplit("/", 1)[-1]
                if _CLASS_NAME_PATTERN.match(short):
                    _add_match(matches, by_category, per_category_count,
                               cat, pattern, entry["id"], dex_name, s.get("offset", 0),
                               max_per_category, evidence_detail=short)
        elif ev == "method_signature":
            for s in strings:
                txt = s.get("string", "")
                if _DECRYPT_STUB_PATTERN.search(txt) or "static string" in txt:
                    _add_match(matches, by_category, per_category_count,
                               cat, pattern, entry["id"], dex_name, s.get("offset", 0),
                               max_per_category, evidence_detail=txt[:80])
        elif ev == "string_literal":
            pat = entry.get("match_pattern", "").lower()
            for s in strings:
                txt = s.get("string", "")
                if pat and pat in txt.lower():
                    _add_match(matches, by_category, per_category_count,
                               cat, pattern, entry["id"], dex_name, s.get("offset", 0),
                               max_per_category, evidence_detail=txt[:80])


def _apply_catalog_to_native(
    entries, native_data, native_name, matches, by_category, per_category_count,
    max_per_category,
) -> None:
    # Section names: walk the ELF/PE header quickly. For ELF
    # the section header table is at e_shoff; for PE the
    # section table is at the COFF header offset. We do a
    # best-effort: scan for any substring that matches a
    # catalog pattern.
    try:
        strings = _scan_native_strings(native_data)
    except Exception:
        strings = []
    for entry in entries:
        cat = entry.get("category")
        ev = entry.get("evidence_kind")
        if ev not in ("string_literal", "native_section"):
            continue
        if per_category_count.get(cat, 0) >= max_per_category:
            continue
        pattern = entry.get("match_pattern", "")
        if ev == "string_literal":
            pat = pattern.lower()
            for s in strings:
                txt = s.get("string", "")
                if pat and pat in txt.lower():
                    _add_match(matches, by_category, per_category_count,
                               cat, pattern, entry["id"], native_name, s.get("offset", 0),
                               max_per_category, evidence_detail=txt[:80])


def _apply_catalog_to_manifest(
    entries, manifest_data, matches, by_category, per_category_count,
    max_per_category,
) -> None:
    try:
        # The AndroidManifest.xml inside the APK is the binary
        # AXML format; decoding it properly requires androguard
        # or apktool. We do a best-effort ASCII scan for the
        # string patterns the catalog cares about (most
        # `manifest_meta` patterns are the packager meta-data
        # tag name which is a short ASCII token).
        text = manifest_data.decode("utf-8", errors="replace")
    except Exception:
        return
    for entry in entries:
        cat = entry.get("category")
        if entry.get("evidence_kind") != "manifest_meta":
            continue
        if per_category_count.get(cat, 0) >= max_per_category:
            continue
        pat = entry.get("match_pattern", "").lower()
        if pat and pat in text.lower():
            _add_match(matches, by_category, per_category_count,
                       cat, entry.get("match_pattern", ""), entry["id"],
                       "AndroidManifest.xml", 0,
                       max_per_category, evidence_detail=pat)


def _add_match(
    matches, by_category, per_category_count, cat, evidence, entry_id,
    evidence_file, evidence_offset, max_per_category,
    evidence_detail: str | None = None,
) -> None:
    matches.append({
        "category": cat,
        "evidence": evidence,
        "evidence_offset": evidence_offset,
        "evidence_file": evidence_file,
        "id": entry_id,
        "match_pattern": evidence,
        "match_detail": evidence_detail,
    })
    by_category[cat] = by_category.get(cat, 0) + 1
    per_category_count[cat] = per_category_count.get(cat, 0) + 1


def _scan_native_strings(data: bytes) -> list[dict[str, Any]]:
    """Walk a native .so and extract printable ASCII strings.

    Lightweight re-implementation of the re-leak-scan extractor
    for the .so subset. The real extractor is in
    ``re_leak_scan.extractor``; we duplicate the small
    function here so the classify walker is standalone.
    """
    out: list[dict[str, Any]] = []
    min_length = 6
    cur: list[bytes] = []
    cur_start = 0
    for i, b in enumerate(data):
        if 0x20 <= b < 0x7F:
            if not cur:
                cur_start = i
            cur.append(b)
        else:
            if len(cur) >= min_length:
                out.append({
                    "string": b"".join(cur).decode("latin-1", errors="replace"),
                    "offset": cur_start,
                })
            cur = []
    if len(cur) >= min_length:
        out.append({
            "string": b"".join(cur).decode("latin-1", errors="replace"),
            "offset": cur_start,
        })
    return out
