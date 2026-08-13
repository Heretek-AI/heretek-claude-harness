"""Native library tools: list, parse, disassemble.

Exposes three MCP tools:

- :func:`list_native_libs` — enumerate ``lib/<abi>/*.so`` paths.
- :func:`analyze_elf` — LIEF-backed parse of a single library, returning
  format, architecture, and security features.
- :func:`disassemble_native` — capstone-backed disassembly of a single
  symbol or byte range.

These tools require a project that has already been opened via
``open_project``. The native libraries are read directly from the
APK ZIP, not from the apktool-decoded project.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import ProjectClosed, ProjectNotFound
from android_re_mcp_static.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register native-analysis tools."""

    @mcp.tool(
        name="list_native_libs",
        description=(
            "List every ``lib/<abi>/*.so`` shared library in the APK. "
            "Also reports the set of ABIs the APK ships native code for."
        ),
    )
    def list_native_libs(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        # Lazy import: NativeView imports LIEF.
        from android_re_core.native import NativeView

        view = NativeView.from_apk(project.apk)
        return {
            "project_id": project_id,
            "lib_count": view.lib_count(),
            "abis": view.abis(),
            "libs": view.list_libs(),
        }

    @mcp.tool(
        name="analyze_elf",
        description=(
            "Parse a single native library (LIEF) and return format, "
            "architecture, sections, imports, exports, and security "
            "features (NX, RELRO, PIE, stack canary, fortify, "
            "RPATH/RUNPATH, stripped)."
        ),
    )
    def analyze_elf(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[
            str,
            Field(description="Library path inside the APK, e.g. 'lib/arm64-v8a/libfoo.so'"),
        ],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.errors import APKError, APKInvalid
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {"project_id": project_id, "binary": info.to_dict()}

    @mcp.tool(
        name="disassemble_native",
        description=(
            "Disassemble bytes from a native library using capstone. "
            "Provide either a symbol name (e.g. 'Java_com_example_Foo_bar') "
            "or a byte offset + length. Returns up to ``max_instructions`` "
            "instructions with mnemonic + operand text."
        ),
    )
    def disassemble_native(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        symbol: Annotated[
            str | None,
            Field(description="Symbol name to disassemble; if set, offset+length are ignored"),
        ] = None,
        offset: Annotated[
            int,
            Field(ge=0, description="Byte offset into the file (only when symbol is not set)"),
        ] = 0,
        length: Annotated[
            int,
            Field(ge=1, le=65536, description="Number of bytes to disassemble"),
        ] = 256,
        max_instructions: Annotated[
            int,
            Field(ge=1, le=2000, description="Cap on returned instructions"),
        ] = 200,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        try:
            import capstone  # type: ignore[import-untyped]
        except ImportError as e:
            return {"error": {"code": "missing_dependency", "message": str(e)}}

        import zipfile

        try:
            with zipfile.ZipFile(str(project.apk.path), "r") as zf:
                data = zf.read(lib_name)
        except KeyError:
            return {"error": {"code": "lib_not_found", "message": lib_name}}

        # Resolve symbol -> offset+length if needed
        if symbol:
            from android_re_core.native import NativeView  # type: ignore[import-untyped]

            try:
                view = NativeView.from_apk(project.apk)
                hits = view.find_symbol(lib_name, symbol, limit=1)
            except Exception:
                hits = []
            if not hits:
                return {
                    "error": {
                        "code": "symbol_not_found",
                        "message": f"symbol matching {symbol!r} not found",
                    }
                }
            sym = hits[0]
            start = sym.value
            sz = sym.size or length
            data = data[start : start + sz]
        else:
            data = data[offset : offset + length]

        # Best-effort arch detection from the binary header
        import struct

        if data[:4] == b"\x7fELF":
            ei_data = data[5]  # 1 = little, 2 = big
            e_machine = struct.unpack("<H", data[18:20])[0]
        else:
            ei_data = 1
            e_machine = 0xB7  # AArch64 fallback

        arch_map = {
            0x03: (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
            0x3E: (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
            0x28: (capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM),
            0xB7: (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM),
        }
        cs_arch, cs_mode = arch_map.get(e_machine, (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM))
        if ei_data == 2:
            cs_mode |= capstone.CS_MODE_BIG_ENDIAN

        try:
            md = capstone.Cs(cs_arch, cs_mode)
        except Exception as e:
            return {"error": {"code": "capstone_init_failed", "message": str(e)}}

        out: list[dict[str, Any]] = []
        for ins in md.disasm(data, 0):
            out.append(
                {
                    "address": int(ins.address),
                    "mnemonic": ins.mnemonic,
                    "op_str": ins.op_str,
                    "bytes_hex": ins.bytes.hex(),
                }
            )
            if len(out) >= max_instructions:
                break

        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "symbol": symbol,
            "arch": {0x03: "x86", 0x3E: "x86_64", 0x28: "arm", 0xB7: "arm64"}.get(
                e_machine, "unknown"
            ),
            "instruction_count": len(out),
            "instructions": out,
        }
