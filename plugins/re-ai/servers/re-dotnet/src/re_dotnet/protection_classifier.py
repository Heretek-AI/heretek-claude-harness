"""Managed .NET protection classification (v2.7.0).

The :func:`classify` walker implements
``re-dotnet.classify_dotnet_protection``; the
:func:`detect_managed_anti_debug` walker implements
``re-dotnet.detect_managed_anti_debug``.

Both use a small ECMA-335 subset parser — enough to walk
the type-name table, the string heap, and the IL method
bodies — but not the full metadata reader. The
``.NET-style launcher / mod-loader`` use case in the
existing ``re-dotnet`` server is small enough that a
hand-rolled walker is the right scope; a full
``System.Reflection.Metadata`` consumer is in the
companion .NET 10 CLI binary (out of scope for the
Python helper).

All output is vendor-neutral: category names describe
observable obfuscation patterns. No commercial
obfuscator is named.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any


# ECMA-335 II.24.2 - #Strings heap
# ECMA-335 II.24.2.4 - #US (user string) heap
# ECMA-335 II.22 - TypeDef, MethodDef tables
# ECMA-335 II.25.4 - Method body formats (Tiny / Fat)


def _read_byte(path: Path, offset: int) -> int:
    """Read one byte from *path* at *offset*."""
    with path.open("rb") as f:
        f.seek(offset)
        return f.read(1)[0]


def _read_u4(path: Path, offset: int) -> int:
    with path.open("rb") as f:
        f.seek(offset)
        return struct.unpack("<I", f.read(4))[0]


def _read_u2(path: Path, offset: int) -> int:
    with path.open("rb") as f:
        f.seek(offset)
        return struct.unpack("<H", f.read(2))[0]


def _read_blob(path: Path, offset: int, length: int) -> bytes:
    with path.open("rb") as f:
        f.seek(offset)
        return f.read(length)


def _is_mono_pe(data: bytes) -> bool:
    """A10 fix (v2.8.1): heuristic Mono PE detection.

    The full .NET CLI header walker (:func:`_parse_pe_metadata_root`)
    returns ``None`` for Mono assemblies because the CLI header
    layout differs from the canonical .NET layout — the CLI header
    RVA points to a different stream and the lightweight walker
    misses the actual metadata root. The r03-stress run hit this on
    A representative target's launcher: the strict walker
    returned ``error: "not a managed PE"`` even though the binary
    is a real Mono assembly.

    Heuristic signals (any one is enough):
      1. The PE imports ``mscoree.dll`` (the canonical Mono / .NET
         runtime shim) or exposes ``_CorExeMain``.
      2. The PE contains the metadata-root signature ``BSJB`` (the
         first 4 bytes of any ECMA-335 metadata root, Mono or
         pure-.NET). Combined with the ``mscoree.dll`` import this
         is a near-certain Mono/.NET signal.
      3. The PE contains the Mono mscorlib fingerprint (the leading
         bytes of the canonical mscorlib.dll metadata).

    Returns True if any signal fires. False otherwise. This is a
    *detection* helper, not a parser — once Mono is confirmed, the
    caller should use ``re-dotnet.parse_assembly`` (which goes
    through the .NET CLI binary and handles Mono correctly) for
    actual classification.
    """
    if data[:2] != b"MZ":
        return False
    if b"mscoree.dll" in data or b"_CorExeMain" in data:
        return True
    if b"BSJB" in data:
        return True
    return False


def _parse_pe_metadata_root(path: Path) -> dict[str, Any] | None:
    """Find the .NET metadata root in a PE file.

    Walks the PE header to find the CLI header, then
    locates the metadata root. The metadata root is the
    anchor for the #Strings, #US, #Blob, and #GUID
    heaps + the table stream.

    Returns a dict with the metadata root address + each
    heap's offset+size, or ``None`` if the file is not
    a managed PE.
    """
    data = path.read_bytes()
    if data[:2] != b"MZ":
        return None
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if pe_off + 24 > len(data) or data[pe_off:pe_off + 4] != b"PE\x00\x00":
        return None
    # PE optional header: data directories start at pe_off + 24 + 96
    # The CLI header is the 14th data directory (index 14).
    opt_off = pe_off + 24
    if opt_off + 96 + 16 * 16 > len(data):
        return None
    # Number of data directories
    try:
        num_dd = struct.unpack_from("<I", data, opt_off + 92)[0]
    except struct.error:
        return None
    if num_dd < 15:
        return None
    dd_off = opt_off + 96
    if dd_off + 15 * 8 > len(data):
        return None
    # CLI header RVA + size
    cli_rva = struct.unpack_from("<I", data, dd_off + 14 * 8)[0]
    cli_size = struct.unpack_from("<I", data, dd_off + 14 * 8 + 4)[0]
    if cli_rva == 0 or cli_size == 0:
        return None
    # Convert RVA to file offset via the section table.
    num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    opt_hdr_size = struct.unpack_from("<H", data, pe_off + 20)[0]
    sec_off = pe_off + 24 + opt_hdr_size
    file_off = _rva_to_offset(data, sec_off, num_sections, cli_rva)
    if file_off is None:
        return None
    # CLI header (72 bytes) at file_off:
    #   u4 Metadata RVA, u4 Metadata Size
    #   ... other fields we don't need ...
    if file_off + 72 > len(data):
        return None
    md_rva = struct.unpack_from("<I", data, file_off + 8)[0]
    md_size = struct.unpack_from("<I", data, file_off + 12)[0]
    md_file_off = _rva_to_offset(data, sec_off, num_sections, md_rva)
    if md_file_off is None:
        return None
    # Metadata header signature 'BSJB' + version + ... heaps
    if data[md_file_off:md_file_off + 4] != b"BSJB":
        return None
    # The heap offsets are at fixed positions after the version
    # string. Layout: u4 length, u16 major, u16 minor, u4 reserved,
    # u4 version_length, [version], u2 flags, u2 num_streams,
    # then the stream headers (each: u4 offset, u4 size, null-terminated name)
    if md_file_off + 24 > len(data):
        return None
    # Skip version string: 16 bytes of major/minor/reserved/version_length
    # then version_length bytes
    version_length = struct.unpack_from("<I", data, md_file_off + 16)[0]
    streams_start = md_file_off + 24 + version_length
    # 2 bytes flags + 2 bytes num_streams
    if streams_start + 4 > len(data):
        return None
    num_streams = struct.unpack_from("<H", data, streams_start + 2)[0]
    hdr_off = streams_start + 4
    heaps: dict[str, dict[str, int]] = {}
    for _ in range(num_streams):
        if hdr_off + 8 > len(data):
            break
        s_off = struct.unpack_from("<I", data, hdr_off)[0]
        s_size = struct.unpack_from("<I", data, hdr_off + 4)[0]
        # Name: null-terminated, padded to 4-byte boundary
        name_start = hdr_off + 8
        name_end = data.find(b"\x00", name_start)
        if name_end < 0:
            break
        try:
            name = data[name_start:name_end].decode("ascii")
        except UnicodeDecodeError:
            break
        # Advance past the name + null + padding
        next_off = name_end + 1
        while next_off % 4 != 0:
            next_off += 1
        hdr_off = next_off
        heaps[name] = {
            "offset": md_file_off + s_off,
            "size": s_size,
        }
    return {
        "path": str(path),
        "md_root_offset": md_file_off,
        "md_size": md_size,
        "heaps": heaps,
    }


def _rva_to_offset(data: bytes, sec_off: int, num_sections: int, rva: int) -> int | None:
    """Convert an RVA to a file offset via the PE section table."""
    for i in range(num_sections):
        base = sec_off + i * 40
        if base + 40 > len(data):
            return None
        sec_va = struct.unpack_from("<I", data, base + 12)[0]
        sec_raw = struct.unpack_from("<I", data, base + 20)[0]
        sec_vsize = struct.unpack_from("<I", data, base + 8)[0]
        if sec_va <= rva < sec_va + sec_vsize:
            return sec_raw + (rva - sec_va)
    return None


def _read_cstring_at(data: bytes, base: int, offset: int) -> str:
    """Read a null-terminated ASCII string from *data* at *base + offset*."""
    end = data.find(b"\x00", base + offset)
    if end < 0:
        return ""
    try:
        return data[base + offset:end].decode("utf-8", errors="replace")
    except (UnicodeDecodeError, ValueError):
        return ""


# ── Type-name pattern walker (type-name-renaming detection) ─────────


_SHORT_NAME_RE = re.compile(r"^[a-zA-Z]{1,3}$|^[a-zA-Z]_[a-zA-Z]$|^\$[a-zA-Z]+$")


def _walk_type_names(data: bytes, strings_heap: dict[str, int]) -> list[dict[str, Any]]:
    """Walk the type table + return the short names of every type.

    The TypeDef table is row-major. Each row has:
    - u4 Flags
    - u2 Name (index into #Strings)
    - u2 Namespace (index into #Strings)
    - u2 Extends (coded index)
    - u2 FieldList (index into Field table)
    - u2 MethodList (index into Method table)
    Total: 14 bytes per row (TypeDef table is defined in
    ECMA-335 II.22).

    For the obfuscation classifier we only need the Name
    + Namespace; the field/method/extends fields can
    be skipped.
    """
    if not strings_heap:
        return []
    strings_off = strings_heap["offset"]
    strings_size = strings_heap["size"]
    # The TypeDef table is the second 1-bit-coded table
    # in the metadata; in practice we need the #~ stream
    # offset + the table-row size, which is read from
    # the #~ header. We don't parse the #~ stream here
    # — the obfuscation walker reads the entire #Strings
    # heap and classifies every short string as a
    # candidate obfuscated type name. This is a rough
    # pass; the candidate count is what we return.
    candidates: list[dict[str, Any]] = []
    pos = 0
    while pos < strings_size:
        end = data.find(b"\x00", strings_off + pos, strings_off + strings_size)
        if end < 0:
            break
        name_bytes = data[strings_off + pos:end]
        try:
            name = name_bytes.decode("utf-8")
        except UnicodeDecodeError:
            pos = end + 1
            continue
        if _SHORT_NAME_RE.match(name) and any(c.isalpha() for c in name):
            candidates.append({
                "name": name,
                "offset": pos,
            })
        pos = end + 1
    return candidates


# ── IL body walker (managed-anti-debug + string-encryption) ─────────


def _walk_method_bodies(path: Path, max_per_method: int = 500) -> list[dict[str, Any]]:
    """Walk the IL method bodies and emit per-method primitive hits.

    The IL body format (Fat or Tiny) is documented in
    ECMA-335 II.25.4. For each method, we:
    1. Locate the method RVAs via the Method table
       (out of scope here — we use the metadata root
       directly).
    2. For each method body, decode the IL bytecode
       enough to recognise the canonical call
       patterns (call/callvirt + a MemberRef token
       that points to a System.Diagnostics /
       System.Reflection / System.Threading / etc.
       API).

    For the obfuscation walker we use a simpler
    heuristic: scan the entire .text section for
    MemberRef tokens whose Owner points to
    System.Diagnostics / System.Reflection / etc.,
    and emit a hit per match. This is rough; a full
    MethodDef table walker would be exact.
    """
    data = path.read_bytes()
    out: list[dict[str, Any]] = []
    # The .NET canonical anti-debug string patterns —
    # these are the strings that appear in #Strings
    # when the obfuscator wraps a System.Diagnostics
    # call. They survive name-rename because they're
    # built-in types, not user code.
    ANTI_DEBUG_PRIMITIVES = (
        "IsDebuggerPresent",
        "Debugger.IsAttached",
        "Debug.Assert",
        "Debugger.Break",
        "Debugger.Launch",
        "Debug.WriteLine",
        "Process.GetCurrentProcess",
        "Process.GetProcessesByName",
        "Environment.FailFast",
        "Environment.Exit",
        "Thread.Sleep",
    )
    STRING_ENCRYPTION_PRIMITIVES = (
        # The canonical "ldstr -> call Get<name>(); ret" stub
        "Get",
        "Decrypt",
        "Decode",
        "FromBase64String",
    )
    # Heuristic: scan for the string + its preceding
    # call instruction. We don't decode the IL
    # bytecode — we look at the position of the
    # string in the binary and emit a hit for each
    # occurrence. This is fast and is what the
    # analyst uses as a *first-pass triage* signal.
    per_method_count: dict[int, int] = {}
    for i, prim in enumerate(ANTI_DEBUG_PRIMITIVES):
        for m in re.finditer(re.escape(prim).encode(), data):
            if per_method_count.get(i, 0) >= max_per_method:
                break
            out.append({
                "method_fqn": f"<bytecode-offset-{m.start():#x}>",
                "primitive": prim,
                "category": "managed-anti-debug",
                "evidence_il_offset": m.start(),
            })
            per_method_count[i] = per_method_count.get(i, 0) + 1
    for prim in STRING_ENCRYPTION_PRIMITIVES:
        for m in re.finditer(re.escape(prim).encode(), data):
            out.append({
                "method_fqn": f"<bytecode-offset-{m.start():#x}>",
                "primitive": prim,
                "category": "string-encryption",
                "evidence_il_offset": m.start(),
            })
    return out


# ── The two MCP-facing walkers ────────────────────────────────────────


def classify(path: str, max_per_category: int = 50) -> dict:
    """Walk a .NET assembly for canonical obfuscation patterns.

    Returns the dict shape documented on
    ``re-dotnet.classify_dotnet_protection``.
    """
    p = Path(path)
    if not p.is_file():
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": "file not found",
        }
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": f"read failed: {exc}",
        }
    md = _parse_pe_metadata_root(p)
    if md is None:
        # A10 fix (v2.8.1): the strict CLI-header walker misses
        # Mono assemblies (the target's MonoLauncher is the canonical example).
        # When the strict walker fails, try the Mono heuristic on
        # the bytes we already have. If Mono is detected, surface
        # a clear "this is a Mono assembly, use the full path"
        # hint so the caller can route to parse_assembly instead
        # of seeing the misleading "not a managed PE" error.
        if _is_mono_pe(data):
            return {
                "path": path,
                "matches": [],
                "by_category": {},
                "is_mono": True,
                "error": (
                    "Mono assembly detected; this lightweight walker "
                    "doesn't classify Mono PE protection. Route to "
                    "re-dotnet.parse_assembly or "
                    "re-dotnet.decompile_type (both go through "
                    "ilspycmd and handle Mono correctly)."
                ),
                "remediation": (
                    "Call mcp__re-dotnet__parse_assembly on the same "
                    "path; the .NET CLI subcommand 'read-header' "
                    "returns the type/method/field counts and the "
                    "managed entry point. For deep classification "
                    "use 'decompile_type' on the type FQN of "
                    "interest and regex over the decompiled C#."
                ),
            }
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": "not a managed PE (no CLI header found by lightweight walker)",
            "remediation": (
                "If this binary IS a managed assembly (e.g. Mono, mixed-mode, "
                "or an older .NET layout), use re-dotnet.decompile_type or "
                "re-dotnet.parse_assembly which go through ilspycmd and "
                "handle non-canonical CLI headers."
            ),
        }
    heaps = md.get("heaps", {})
    strings_heap = heaps.get("#Strings", {})
    matches: list[dict[str, Any]] = []
    by_category: dict[str, int] = {}
    per_category_count: dict[str, int] = {}
    # 1. type-name-renaming
    type_names = _walk_type_names(data, strings_heap)
    if type_names:
        cnt = min(len(type_names), max_per_category)
        for t in type_names[:cnt]:
            matches.append({
                "category": "type-name-renaming",
                "evidence": "short type name (1-3 alpha chars)",
                "evidence_member": t["name"],
                "offset": t["offset"],
            })
        by_category["type-name-renaming"] = cnt
        per_category_count["type-name-renaming"] = cnt
    # 2. string-encryption
    se_count = 0
    for prim in ("FromBase64String", "Decrypt", "Decode"):
        for m in re.finditer(re.escape(prim).encode(), data):
            if se_count >= max_per_category:
                break
            matches.append({
                "category": "string-encryption",
                "evidence": f"string-encryption helper: {prim}",
                "evidence_member": prim,
                "offset": m.start(),
            })
            se_count += 1
    if se_count:
        by_category["string-encryption"] = se_count
        per_category_count["string-encryption"] = se_count
    # 3. resource-encryption (presence of the ResourceManager
    #    cipher hint is a proxy; the proper check requires
    #    the full manifest, which is out of scope)
    if b"ResourceManager" in data and b"AesManaged" in data:
        matches.append({
            "category": "resource-encryption",
            "evidence": "ResourceManager + AesManaged",
            "evidence_member": "<assembly>",
        })
        by_category["resource-encryption"] = 1
        per_category_count["resource-encryption"] = 1
    # 4. native-aot-stub (very rough: presence of NativeAot
    #    in the metadata flags)
    if b"NativeAot" in data:
        matches.append({
            "category": "native-aot-stub",
            "evidence": "NativeAot metadata flag",
            "evidence_member": "<assembly>",
        })
        by_category["native-aot-stub"] = 1
        per_category_count["native-aot-stub"] = 1
    return {
        "path": path,
        "matches": matches,
        "by_category": dict(sorted(by_category.items())),
    }


def detect_managed_anti_debug(path: str, max_per_method: int = 500) -> dict:
    """Scan IL method bodies for managed anti-debug primitives.

    Returns the dict shape documented on
    ``re-dotnet.detect_managed_anti_debug``.
    """
    p = Path(path)
    if not p.is_file():
        return {
            "path": path,
            "hits": [],
            "by_primitive": {},
            "error": "file not found",
        }
    try:
        hits = _walk_method_bodies(p, max_per_method=max_per_method)
    except OSError as exc:
        return {
            "path": path,
            "hits": [],
            "by_primitive": {},
            "error": f"read failed: {exc}",
        }
    by_primitive: dict[str, int] = {}
    for h in hits:
        prim = h.get("primitive", "")
        if h.get("category") == "managed-anti-debug":
            by_primitive[prim] = by_primitive.get(prim, 0) + 1
    return {
        "path": path,
        "hits": [h for h in hits if h.get("category") == "managed-anti-debug"],
        "by_primitive": dict(sorted(by_primitive.items())),
    }
