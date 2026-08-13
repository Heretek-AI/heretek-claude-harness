"""Disassembly tools: disassemble_function, disassemble_bytes."""

from __future__ import annotations

import struct
import zipfile
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import APKError, APKInvalid, ProjectClosed, ProjectNotFound
from android_re_mcp_native.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register disassembly tools."""

    @mcp.tool(
        name="disassemble_function",
        description=(
            "Disassemble a single exported/imported function in a "
            "native library, identified by symbol name. Uses capstone."
        ),
    )
    def disassemble_function(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        symbol: Annotated[str, Field(description="Symbol name to disassemble")],
        max_instructions: Annotated[int, Field(ge=1, le=2000)] = 200,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            hits = view.find_symbol(lib_name, symbol, limit=1)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        if not hits:
            return {"error": {"code": "symbol_not_found", "message": symbol}}
        sym = hits[0]
        # Pull raw bytes from the APK
        with zipfile.ZipFile(str(project.apk.path), "r") as zf:
            data = zf.read(lib_name)
        chunk = data[sym.value : sym.value + (sym.size or 1024)]
        return _disasm_payload(
            chunk, arch_hint=_arch_from_elf_header(data), max_instructions=max_instructions
        )

    @mcp.tool(
        name="disassemble_bytes",
        description=(
            "Disassemble a byte range inside a native library. The "
            "range is specified by file offset and length."
        ),
    )
    def disassemble_bytes(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        offset: Annotated[int, Field(ge=0, description="File offset")],
        length: Annotated[int, Field(ge=1, le=65536)],
        max_instructions: Annotated[int, Field(ge=1, le=2000)] = 200,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        with zipfile.ZipFile(str(project.apk.path), "r") as zf:
            data = zf.read(lib_name)
        chunk = data[offset : offset + length]
        return _disasm_payload(
            chunk,
            arch_hint=_arch_from_elf_header(data),
            offset=offset,
            max_instructions=max_instructions,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _arch_from_elf_header(data: bytes) -> int:
    """Extract the e_machine field from an ELF header. Returns 0xB7 (AArch64) as fallback."""
    if data[:4] != b"\x7fELF" or len(data) < 20:
        return 0xB7
    return struct.unpack("<H", data[18:20])[0]


def _disasm_payload(
    data: bytes,
    *,
    arch_hint: int,
    offset: int = 0,
    max_instructions: int = 200,
) -> dict[str, Any]:
    """Disassemble a byte buffer with capstone and return a JSON-friendly dict."""
    try:
        import capstone  # type: ignore[import-untyped]
    except ImportError as e:
        return {"error": {"code": "missing_dependency", "message": str(e)}}

    arch_map = {
        0x03: (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
        0x3E: (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
        0x28: (capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM),
        0xB7: (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM),
    }
    cs_arch, cs_mode = arch_map.get(arch_hint, (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM))
    try:
        md = capstone.Cs(cs_arch, cs_mode)
    except Exception as e:
        return {"error": {"code": "capstone_init_failed", "message": str(e)}}

    instructions: list[dict[str, Any]] = []
    for ins in md.disasm(data, offset):
        instructions.append(
            {
                "address": int(ins.address),
                "mnemonic": ins.mnemonic,
                "op_str": ins.op_str,
                "bytes_hex": ins.bytes.hex(),
            }
        )
        if len(instructions) >= max_instructions:
            break

    return {
        "instruction_count": len(instructions),
        "instructions": instructions,
    }
