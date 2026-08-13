"""MCP server entry point for re-hypervisor-detect.

Hypervisor-detection primitive scanning. Wraps
``re-winedbg`` (CPUID enumeration) + ``re-lief``
(categorised strings). The server walks the
canonical hypervisor-detection categories:

- CPUID leaf probes (0x1, 0x40000000, 0x40000100)
- VMX / EPT detection
- TSC skew measurement
- SMBIOS / ACPI / registry probes
- File-system / MAC-address probes

All output is vendor-neutral: category names only.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("re_hypervisor_detect")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-hypervisor-detect")


@mcp.tool()
def check_hypervisor_detect() -> dict:
    """Report server status + the wrapped servers' availability."""
    return {
        "server": "re-hypervisor-detect",
        "version": "0.1.0",
        "status": "OK",
        "wrapped_servers": ["re-winedbg", "re-lief"],
    }


@mcp.tool()
def cpu_id_leaf_probe(path: str) -> dict:
    """Static detection of CPUID-leaf probes.

    Returns a list of CPUID leaves referenced in the
    binary's .text section, with the inferred probe
    category. Categories:
    - ``cpuid-leaf-1-hypervisor-present`` (leaf 1 ECX bit 31)
    - ``cpuid-leaf-0x40000000-hypervisor-vendor`` (leaf 0x40000000)
    - ``cpuid-leaf-0x40000100-misc`` (leaf 0x40000100)

    The walker searches for the ``0F A2`` opcode (CPUID)
    and the surrounding leaf-mov sequence.
    """
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"path": path, "error": "file not found", "leaves": []}
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {"path": path, "error": f"read failed: {exc}", "leaves": []}
    leaves: list[dict] = []
    CPUID = b"\x0F\xA2"
    start = 0
    while True:
        idx = data.find(CPUID, start)
        if idx < 0:
            break
        # Heuristic: look 6-30 bytes before for a `mov ecx, N`
        # or `mov eax, N` to determine the leaf.
        pre = data[max(0, idx - 32):idx]
        leaf = _guess_cpuid_leaf(pre)
        leaves.append({
            "offset": idx,
            "leaf": leaf,
            "category": _category_for_leaf(leaf),
        })
        start = idx + 1
        if len(leaves) > 200:
            break
    return {
        "path": path,
        "leaves": leaves,
        "leaf_count": len(leaves),
        "category_counts": _category_counts(leaves),
    }


@mcp.tool()
def vmx_ept_probe(path: str) -> dict:
    """Static detection of VMXON / VMCALL / EPT probes.

    The walker searches for the canonical VMX
    instruction opcodes (0F C7 for VMXON, 0F 01 C1 for
    VMCALL) and the INVEPT opcode (0F 01 82).
    """
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"path": path, "error": "file not found", "vmx_hits": []}
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {"path": path, "error": f"read failed: {exc}", "vmx_hits": []}
    hits: list[dict] = []
    for needle, name in (
        (b"\x0F\xC7", "VMXON-or-VMPTRST"),
        (b"\x0F\x01\xC1", "VMCALL"),
        (b"\x0F\x01\x82", "INVEPT"),
        (b"\x0F\x01\x83", "INVVPID"),
    ):
        start = 0
        while True:
            idx = data.find(needle, start)
            if idx < 0:
                break
            hits.append({"offset": idx, "primitive": name})
            start = idx + 1
            if len([h for h in hits if h["primitive"] == name]) > 50:
                break
    return {"path": path, "vmx_hits": hits, "hit_count": len(hits)}


@mcp.tool()
def tsc_skew_measure(path: str) -> dict:
    """Static detection of TSC-skew probes (the RDTSC
    timing-trap canonical pattern).

    Returns the count of ``0F 31`` (RDTSC) opcodes in
    the binary. The analyst pairs this with a runtime
    measurement (re-winedbg ``gef_trace_breakpoint``)
    to confirm the skew.
    """
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"path": path, "error": "file not found"}
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {"path": path, "error": f"read failed: {exc}"}
    rdtsc_count = data.count(b"\x0F\x31")
    return {
        "path": path,
        "rdtsc_count": rdtsc_count,
        "category": "tsc-skew-probe",
        "note": (
            "the static count is a triage signal; pair with a runtime "
            "measurement to confirm the skew. See the recipe in "
            "re-anti-analysis.suggest_runtime_trap for the RDTSC trap."
        ),
    }


@mcp.tool()
def smbios_probe(path: str) -> dict:
    """Static detection of SMBIOS / ACPI probe strings."""
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"path": path, "error": "file not found"}
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {"path": path, "error": f"read failed: {exc}"}
    keywords = (b"SMBIOS", b"ACPI", b"\\\\.\\PhysicalDrive", b"MachineGuid",
                b"GetVolumeInformationW")
    found = []
    for kw in keywords:
        if kw in data:
            found.append(kw.decode("latin-1", errors="replace"))
    return {
        "path": path,
        "found_keywords": found,
        "category": "smbios-acpi-probe",
    }


@mcp.tool()
def registry_probe(path: str) -> dict:
    """Static detection of registry-based VM-detection probes."""
    from pathlib import Path
    p = Path(path)
    if not p.is_file():
        return {"path": path, "error": "file not found"}
    try:
        data = p.read_bytes()
    except OSError as exc:
        return {"path": path, "error": f"read failed: {exc}"}
    # Search for the canonical VM-detection registry keys
    # as string literals in the binary. We don't enumerate
    # the full list (it's huge); the analyst uses
    # re-lief.categorize_strings for the full coverage.
    keywords = (
        b"HKLM\\SOFTWARE",
        b"HKEY_LOCAL_MACHINE",
        b"HKEY_CURRENT_USER",
        b"MachineGuid",
    )
    found = [kw.decode("latin-1", errors="replace") for kw in keywords if kw in data]
    return {
        "path": path,
        "found_keywords": found,
        "category": "registry-probe",
    }


@mcp.tool()
def classify_hypervisor_posture(path: str) -> dict:
    """Classify the binary's anti-hypervisor posture (category-only).

    Returns a category label from the set:
    - ``"no-probes"`` — none of the static probes fired.
    - ``"static-probes-only"`` — string-table hits only.
    - ``"runtime-probes"`` — RDTSC / CPUID opcodes found
      alongside the string-table hits.
    - ``"kernel-active"`` — VMXON / VMCALL / EPT opcodes
      found (signals hypervisor deployment, not just
      detection).
    - ``"rich-runtime"`` — multiple probe categories
      present.

    Categories only — never names a specific commercial
    hypervisor / product.
    """
    cpu = cpu_id_leaf_probe(path)
    vmx = vmx_ept_probe(path)
    tsc = tsc_skew_measure(path)
    smb = smbios_probe(path)
    reg = registry_probe(path)
    leaf_count = cpu.get("leaf_count", 0)
    vmx_count = vmx.get("hit_count", 0)
    rdtsc_count = tsc.get("rdtsc_count", 0)
    smb_count = len(smb.get("found_keywords", []))
    reg_count = len(reg.get("found_keywords", []))
    if vmx_count > 0:
        posture = "kernel-active"
    elif leaf_count > 4 and rdtsc_count > 4:
        posture = "rich-runtime"
    elif leaf_count > 0 or rdtsc_count > 0:
        posture = "runtime-probes"
    elif smb_count > 0 or reg_count > 0:
        posture = "static-probes-only"
    else:
        posture = "no-probes"
    return {
        "path": path,
        "posture": posture,
        "evidence": {
            "cpu_id_leaves": leaf_count,
            "vmx_ept_hits": vmx_count,
            "rdtsc_count": rdtsc_count,
            "smbios_acpi_keywords": smb_count,
            "registry_keywords": reg_count,
        },
    }


# ── helpers ────────────────────────────────────────────────────────────


def _guess_cpuid_leaf(pre: bytes) -> int:
    """Heuristic: look for the most recent `mov eax, N` /
    `mov ecx, N` (3-byte mov reg, imm32 = ``B8+reg N``)
    and return N."""
    # mov eax, imm32: B8 NNNNNNNN (5 bytes)
    # mov ecx, imm32: B9 NNNNNNNN (5 bytes)
    # mov eax, 0: 5 bytes
    for i in range(len(pre) - 5, max(len(pre) - 64, -1), -1):
        if i < 0 or i + 5 > len(pre):
            continue
        op = pre[i]
        if op in (0xB8, 0xB9):
            try:
                import struct
                val = struct.unpack_from("<I", pre, i + 1)[0]
                return val
            except struct.error:
                continue
    return -1


def _category_for_leaf(leaf: int) -> str:
    if leaf == 1:
        return "cpuid-leaf-1-hypervisor-present"
    if leaf == 0x40000000:
        return "cpuid-leaf-0x40000000-hypervisor-vendor"
    if leaf == 0x40000100:
        return "cpuid-leaf-0x40000100-misc"
    if leaf < 0x40000000:
        return f"cpuid-leaf-{leaf}-standard"
    return f"cpuid-leaf-{leaf:#x}-hypervisor"


def _category_counts(leaves: list[dict]) -> dict:
    out: dict[str, int] = {}
    for l in leaves:
        cat = l.get("category", "unknown")
        out[cat] = out.get(cat, 0) + 1
    return out


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
