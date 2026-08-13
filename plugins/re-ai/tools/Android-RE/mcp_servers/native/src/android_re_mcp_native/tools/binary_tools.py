"""Binary metadata tools: list, parse, sections, symbols, imports, exports, security."""

from __future__ import annotations

import re
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_core.errors import APKError, APKInvalid, ProjectClosed, ProjectNotFound
from android_re_mcp_native.server import get_store

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register binary-metadata tools."""

    @mcp.tool(
        name="list_binaries",
        description=(
            "List every native binary in the project: ``.so`` files in "
            "any ABI, plus OAT / VDEX / ART images. Returns the list of "
            "paths and the set of ABIs the APK ships code for."
        ),
    )
    def list_binaries(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        view = NativeView.from_apk(project.apk)
        return {
            "project_id": project_id,
            "binary_count": view.lib_count(),
            "abis": view.abis(),
            "binaries": view.list_libs(),
        }

    @mcp.tool(
        name="parse_binary",
        description=(
            "Parse a single native library (LIEF) and return format, "
            "architecture, bits, endianness, entrypoint, base address, "
            "PIE, stripped status, security features, and counts of "
            "sections / imports / exports."
        ),
    )
    def parse_binary(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[
            str, Field(description="Library path inside the APK, e.g. 'lib/arm64-v8a/libfoo.so'")
        ],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "binary": info.to_dict(),
            "sections": [s.to_dict() for s in info.sections],
            "imports": [i.to_dict() for i in info.imports],
            "exports": [e.to_dict() for e in info.exports],
        }

    @mcp.tool(
        name="get_sections",
        description="Return the section table for a native library.",
    )
    def get_sections(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "count": len(info.sections),
            "sections": [s.to_dict() for s in info.sections],
        }

    @mcp.tool(
        name="get_symbols",
        description=(
            "Return symbols from a native library, filterable by name "
            "substring. Use ``kind='export'`` or ``kind='import'`` to "
            "restrict to exported or imported symbols."
        ),
    )
    def get_symbols(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
        filter: Annotated[
            str | None,
            Field(description="Substring filter on symbol name"),
        ] = None,
        kind: Annotated[
            str,
            Field(description="'all' (default), 'export', or 'import'"),
        ] = "all",
        limit: Annotated[int, Field(ge=1, le=10000)] = 500,
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            if filter:
                syms = view.find_symbol(lib_name, filter, limit=limit)
            else:
                info = view.parse(lib_name)
                syms = [
                    _sym_to_dict(s)  # type: ignore[arg-type]
                    for s in (
                        # We don't have a direct way to enumerate; use a no-op
                        # pattern to return the cached exports as Symbols.
                        _export_to_symbol(e)
                        for e in info.exports
                    )
                ]
                if kind in ("all", "export"):
                    out = syms
                # Phase 2: imports not in the symbol list, so this is partial
                if kind == "import":
                    out = [_imp_to_dict(i) for i in info.imports]
                return {
                    "project_id": project_id,
                    "lib_name": lib_name,
                    "count": len(out),
                    "symbols": out[:limit],
                }
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}

        # Apply kind filter
        if kind == "export":
            syms = [s for s in syms if s.is_external]
        elif kind == "import":
            syms = []  # Phase 2 placeholder; full impl in Phase 3

        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "count": len(syms),
            "symbols": [s.to_dict() for s in syms],
        }

    @mcp.tool(
        name="get_relocations",
        description=(
            "Return the relocation table for a native library. Phase 2 "
            "returns a summary count; the full table lands in Phase 3 "
            "once LIEF's relocation API is verified against "
            "androguard-style data."
        ),
    )
    def get_relocations(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "note": "Relocation table is summary-only in Phase 2.",
            "info": {
                "format": info.format,
                "is_pie": info.is_pie,
                "base_address": info.base_address,
            },
        }

    @mcp.tool(
        name="get_imports",
        description="Return the import table for a native library.",
    )
    def get_imports(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "count": len(info.imports),
            "imports": [i.to_dict() for i in info.imports],
        }

    @mcp.tool(
        name="get_exports",
        description="Return the export table for a native library.",
    )
    def get_exports(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "count": len(info.exports),
            "exports": [e.to_dict() for e in info.exports],
        }

    @mcp.tool(
        name="get_security_features",
        description=(
            "Return the security features of a native library: NX, "
            "RELRO, stack canary, PIE, fortify, RPATH/RUNPATH, "
            "stripped status."
        ),
    )
    def get_security_features(
        project_id: Annotated[str, Field(description="Project id returned by open_project")],
        lib_name: Annotated[str, Field(description="Library path inside the APK")],
    ) -> dict[str, Any]:
        try:
            project = get_store().get(project_id)
        except (ProjectNotFound, ProjectClosed) as e:
            return {"error": e.to_dict()}
        from android_re_core.native import NativeView

        try:
            view = NativeView.from_apk(project.apk)
            info = view.parse(lib_name)
        except (APKError, APKInvalid) as e:
            return {"error": e.to_dict()}
        return {
            "project_id": project_id,
            "lib_name": lib_name,
            "security": info.security.to_dict(),
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sym_to_dict(s: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    return s.to_dict()


def _export_to_symbol(e: Any) -> Any:  # type: ignore[no-untyped-def]
    """Wrap an ExportEntry in a Symbol-shaped object so get_symbols returns uniform dicts."""
    from android_re_core.native import Symbol

    return Symbol(
        name=e.name,
        value=e.address,
        size=e.size,
        binding="GLOBAL",
        type="FUNC",
        visibility="DEFAULT",
        section_name=None,
        is_external=True,
    )


def _imp_to_dict(i: Any) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Format an ImportEntry as a dict resembling a symbol."""
    return {
        "name": i.name,
        "value": 0,
        "size": 0,
        "binding": "GLOBAL",
        "type": "FUNC",
        "visibility": "DEFAULT",
        "section_name": None,
        "is_external": False,
        "library": i.library,
        "address": i.address,
    }


# Suppress unused imports.
_ = re
