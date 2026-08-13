"""MCP server entry point for re-il2cpp.

Exposes Unity IL2CPP ``global-metadata.dat`` reading to Claude Code.
The server is pure-Python (no system tools required) and mmap-based
so even the 10+ MB metadata files parse in under a second.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_il2cpp import metadata, rva_resolver

logger = logging.getLogger("re_il2cpp")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-il2cpp")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_il2cpp(metadata_path: str = "") -> dict:
    """Read the metadata header and return version + per-table counts.

    Args:
        metadata_path: optional path to global-metadata.dat. If empty,
            returns the server's status (no path is OK).
    """
    if not metadata_path:
        return {
            "status": "OK",
            "server": "re-il2cpp",
            "note": "pass a metadata_path to read the header",
        }
    return metadata.read_header(metadata_path)


# ── String table ───────────────────────────────────────────────────────


@mcp.tool()
def list_strings(
    metadata_path: str, substring: str = "", limit: int = 500
) -> list[str]:
    """Return strings from the unprotected C# symbol table.

    Args:
        metadata_path: path to global-metadata.dat
        substring: if set, only return strings containing this
            case-sensitive substring
        limit: maximum number of results to return (default 500)
    """
    return metadata.list_strings(metadata_path, substring, limit)


@mcp.tool()
def search_strings(
    metadata_path: str, substring: str, limit: int = 50
) -> list[dict]:
    """Substring search of the C# symbol table.

    Returns ``[{index, string}]`` matches. Useful for finding asset
    paths, save keys, or specific gameplay terms in the metadata.

    Args:
        metadata_path: path to global-metadata.dat
        substring: case-sensitive substring to search for
        limit: maximum matches to return (default 50)
    """
    return metadata.search_strings(metadata_path, substring, limit)


# ── Class / namespace view ─────────────────────────────────────────────


@mcp.tool()
def list_namespaces(metadata_path: str, limit: int = 200) -> list[dict]:
    """Return a sorted list of namespaces with class counts.

    Scans the string table for class FQNs and buckets them by
    namespace. The class count is an upper bound (a FQN-shaped
    string might be a non-class entity, though rare).

    Args:
        metadata_path: path to global-metadata.dat
        limit: maximum namespaces to return (default 200)
    """
    return metadata.list_namespaces(metadata_path, limit)


@mcp.tool()
def list_classes(
    metadata_path: str, namespace: str = "", limit: int = 500
) -> list[dict]:
    """Return class FQNs from the string table.

    Args:
        metadata_path: path to global-metadata.dat
        namespace: if set, only return classes whose FQN starts with
            ``namespace + "."`` (e.g. ``"UnityEngine"``)
        limit: maximum classes to return (default 500)
    """
    return metadata.list_classes(metadata_path, namespace, limit)


# ── Binary tables (structured class graph) ─────────────────────────────


@mcp.tool()
def get_type_definitions(
    metadata_path: str, namespace: str = "", limit: int = 500
) -> list[dict]:
    """Walk the binary typeDefinitions table; return structured records.

    Unlike list_classes (which harvests the string table for FQNs), this
    reads the actual record array and returns parent, type_index,
    method_count, field_count, etc. for each class.

    Args:
        metadata_path: path to global-metadata.dat
        namespace: if set, only return typeDefs whose FQN starts with
            ``namespace + "."``
        limit: maximum results (default 500)
    """
    return metadata.get_type_definitions(metadata_path, namespace, limit)


@mcp.tool()
def get_methods(
    metadata_path: str, class_fqn: str, limit: int = 500
) -> list[dict]:
    """Return the methods of a class as a structured list.

    Use this instead of search_strings for typed method discovery.

    Args:
        metadata_path: path to global-metadata.dat
        class_fqn: fully qualified class name (e.g. "MyGame.PlayerController")
        limit: maximum methods to return (default 500)
    """
    return metadata.get_methods(metadata_path, class_fqn, limit)


@mcp.tool()
def get_fields(
    metadata_path: str, class_fqn: str, limit: int = 200
) -> list[dict]:
    """Return the fields of a class as a structured list.

    Args:
        metadata_path: path to global-metadata.dat
        class_fqn: fully qualified class name
        limit: maximum fields to return (default 200)
    """
    return metadata.get_fields(metadata_path, class_fqn, limit)


@mcp.tool()
def get_parameters(
    metadata_path: str, method_fqn: str, limit: int = 50
) -> list[dict]:
    """Return the parameters of a method (in declaration order).

    Args:
        metadata_path: path to global-metadata.dat
        method_fqn: ``"ClassName.MethodName"`` (e.g. "MyGame.PlayerController.TakeDamage")
        limit: maximum parameters to return (default 50)
    """
    return metadata.get_parameters(metadata_path, method_fqn, limit)


@mcp.tool()
def get_properties(
    metadata_path: str, class_fqn: str, limit: int = 200
) -> list[dict]:
    """Return the properties of a class.

    Args:
        metadata_path: path to global-metadata.dat
        class_fqn: fully qualified class name
        limit: maximum properties to return (default 200)
    """
    return metadata.get_properties(metadata_path, class_fqn, limit)


@mcp.tool()
def get_events(
    metadata_path: str, class_fqn: str, limit: int = 200
) -> list[dict]:
    """Return the events of a class.

    Args:
        metadata_path: path to global-metadata.dat
        class_fqn: fully qualified class name
        limit: maximum events to return (default 200)
    """
    return metadata.get_events(metadata_path, class_fqn, limit)


@mcp.tool()
def get_images(metadata_path: str) -> list[dict]:
    """Walk the binary images table; return assembly image records.

    Each image corresponds to one IL2CPP assembly (e.g.
    Assembly-CSharp.dll, UnityEngine.CoreModule.dll). The ``name`` field
    is the assembly file name; the ``type_count`` is the size of the
    typeDef range owned by this image.

    Args:
        metadata_path: path to global-metadata.dat
    """
    return metadata.get_images(metadata_path)


@mcp.tool()
def get_assembly_types(
    metadata_path: str, image_name: str, limit: int = 500
) -> list[dict]:
    """Enumerate every type in one IL2CPP assembly.

    Unlike :func:`list_classes` (which scans the string table and
    misses root-namespace types), this walks the typeDef range owned
    by a specific image — use it to enumerate the publisher's actual
    game code (``Assembly-CSharp.dll``) or a specific engine module
    (``UnityEngine.CoreModule.dll``).

    Each record: ``{fqn, namespace, name, type_index, method_count,
    field_count, property_count, event_count, nested_type_count,
    parent_index, token, flags}`` — same shape as
    :func:`get_type_definitions`.

    Args:
        metadata_path: path to global-metadata.dat
        image_name: assembly file name (e.g. ``"Assembly-CSharp.dll"``)
        limit: maximum results
    """
    return metadata.get_assembly_types(metadata_path, image_name, limit)


# ── RVA cross-reference (requires `pip install lief`) ──────────────────


@mcp.tool()
def resolve_method_rva(
    metadata_path: str, gameassembly_path: str, method_fqn: str
) -> dict:
    """Resolve a method FQN to its GameAssembly.dll RVA.

    Walks the global-metadata.dat typeDef/method tables to find the
    method, then parses GameAssembly.dll to look for the
    ``s_Il2CppCodeRegistrations`` global. If the binary is non-stripped
    and contains the registration symbols, the pointer table's RVA is
    reported. If the binary is stripped (the default for shipped Unity
    games), the function returns ``rva_status="binary_stripped"`` plus
    the IL2CPP mangled name to use with ``re-rizin.search_bytes``.

    Requires ``pip install lief`` (an optional dep — install via
    ``pip install re-il2cpp[rva]``).

    Args:
        metadata_path: path to global-metadata.dat
        gameassembly_path: path to GameAssembly.dll
        method_fqn: ``"Namespace.ClassName.MethodName"``
    """
    return rva_resolver.resolve_method_rva(
        metadata_path, gameassembly_path, method_fqn
    )


# ── Entrypoint ──────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
