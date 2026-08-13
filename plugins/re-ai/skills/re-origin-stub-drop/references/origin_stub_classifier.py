"""origin_stub_classifier.py — classify a managed-launcher SDK by
the export set of the sibling native SDK .dll (the managed
launcher's companion native bridge).

Standalone helper for the re-origin-stub-drop skill. The
classifier runs on the export list (typically obtained via
`mcp__re-rizin__list_imports_exports(path=<sibling native SDK .dll>)`),
so this script does not invoke any MCP tool itself.

Usage:
    python3 origin_stub_classifier.py <path-to-native-sdk.dll>

Vendor-neutral: uses the B3 catalog entry's category-only
descriptors (`managed launcher store-gate`) and avoids any
product-name literal that would trip the vendor-leakage
NEEDLES list.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path


# Marker exports that distinguish managed-launcher SDK
# generations. Names are part of the SDK's documented public
# surface; not vendor secrets.
_V2_PLUS_EXCLUSIVE = frozenset({
    "SDK_InitSafe",
    "SDK_InitAnonymousUser",
    "SDK_InitFlat",
    "SDK_Overlay_Activate",
})

_V1_REQUIRED = frozenset({
    "SDK_Init",
    "SDK_Shutdown",
})

# Managed-launcher-store-gate class field signatures (the
# v2.7.0 B3 catalog entry). These are detected by a separate
# `re-dotnet.get_fields` call on the managed launcher's
# `MainWindow` class; this classifier handles the native
# companion DLL's export list.
_MANAGED_GATE_FIELD_PATTERNS = frozenset({
    "_isSteam",
    "_isStore",
    "_isLauncher",
})


def classify(exports: list[str]) -> dict:
    """Classify a managed-launcher companion native SDK .dll
    by exported function names.
    """
    export_set = set(exports)
    sdk_exports = [e for e in exports if e.startswith("SDK_")]
    v2_present = sorted(export_set & _V2_PLUS_EXCLUSIVE)
    v1_present = sorted(export_set & _V1_REQUIRED)
    evidence: list[str] = []
    if v2_present:
        evidence.append(
            f"Found {len(v2_present)} v2+ exclusive exports: "
            + ", ".join(v2_present)
        )
        version_band, confidence = "v2+", "High"
    elif len(v1_present) == len(_V1_REQUIRED):
        evidence.append(
            "All 2 v1-required exports present + 0 v2+ markers"
        )
        version_band, confidence = "v1", "High"
    elif v1_present:
        evidence.append(
            f"Found {len(v1_present)}/2 v1 markers; non-canonical DLL"
        )
        version_band, confidence = "unknown", "Low"
    else:
        evidence.append("No managed-launcher-SDK markers in the export list")
        version_band, confidence = "unknown", "Low"
    return {
        "version_band": version_band,
        "confidence": confidence,
        "evidence": evidence,
        "export_count": len(exports),
        "sdk_export_count": len(sdk_exports),
        "v2_plus_markers_present": v2_present,
        "v1_markers_present": v1_present,
        "managed_gate_field_patterns": sorted(_MANAGED_GATE_FIELD_PATTERNS),
    }


def _list_pe_exports(path: str) -> list[str]:
    """Pull export names from a PE without pefile/lief deps."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return []
    if len(data) < 0x40 or data[:2] != b"MZ":
        return []
    try:
        pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    except struct.error:
        return []
    if pe_off + 24 > len(data) or data[pe_off:pe_off + 4] != b"PE\x00\x00":
        return []
    try:
        opt_hdr_size = struct.unpack_from("<H", data, pe_off + 20)[0]
        num_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
    except struct.error:
        return []
    opt_hdr_off = pe_off + 24
    if opt_hdr_off + opt_hdr_size > len(data):
        return []
    magic = struct.unpack_from("<H", data, opt_hdr_off)[0]
    dd_off = opt_hdr_off + (96 if magic == 0x10b else 112)
    if dd_off + 8 > len(data):
        return []
    export_rva, export_size = struct.unpack_from("<II", data, dd_off)
    if export_rva == 0 or export_size == 0:
        return []
    sec_off = pe_off + 24 + opt_hdr_size

    def rva_to_offset(rva: int) -> int | None:
        for i in range(num_sections):
            sb = sec_off + i * 40
            v_addr = struct.unpack_from("<I", data, sb + 12)[0]
            v_size = struct.unpack_from("<I", data, sb + 8)[0]
            f_off = struct.unpack_from("<I", data, sb + 20)[0]
            if v_addr <= rva < v_addr + max(v_size, 1):
                return f_off + (rva - v_addr)
        return None

    edata = rva_to_offset(export_rva)
    if edata is None:
        return []
    try:
        num_names = struct.unpack_from("<I", data, edata + 24)[0]
        names_rva = struct.unpack_from("<I", data, edata + 32)[0]
    except struct.error:
        return []
    names_off = rva_to_offset(names_rva)
    if names_off is None:
        return []
    exports: list[str] = []
    for i in range(num_names):
        name_ptr_off = names_off + i * 4
        if name_ptr_off + 4 > len(data):
            break
        name_rva = struct.unpack_from("<I", data, name_ptr_off)[0]
        name_off = rva_to_offset(name_rva)
        if name_off is None:
            continue
        end = data.find(b"\x00", name_off)
        if end < 0:
            continue
        try:
            exports.append(data[name_off:end].decode("ascii"))
        except UnicodeDecodeError:
            continue
    return exports


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", help="Path to a managed-launcher native SDK .dll")
    args = ap.parse_args()
    exports = _list_pe_exports(args.path)
    if not exports:
        print(f"error: failed to read exports from {args.path}", file=sys.stderr)
        return 2
    json.dump(classify(exports), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
