"""MCP server entry point for re-kaitai."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_kaitai import kaitai_runner
from re_kaitai import unityfs_blocks

logger = logging.getLogger("re_kaitai")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-kaitai")


@mcp.tool()
def check_compiler() -> dict:
    """Return kaitai-struct-compiler version."""
    return kaitai_runner.check_compiler()


@mcp.tool()
def list_known_formats() -> list[dict]:
    """Return the list of bundled .ksy formats."""
    return kaitai_runner.list_known_formats()


@mcp.tool()
def download_format(name: str, target_dir: str = "") -> dict:
    """Download a .ksy spec from the kaitai-formats gallery."""
    return kaitai_runner.download_format(name, target_dir)


@mcp.tool()
def compile_format(ksy_path: str, target: str = "python") -> dict:
    """Compile a .ksy file to a Python module."""
    return kaitai_runner.compile_format(ksy_path, target)


@mcp.tool()
def parse_with_format(
    path: str,
    format_module: str = "",
    ksy_path: str = "",
) -> dict:
    """Parse a binary using either a precompiled module or a fresh .ksy.

    Args:
        path: file to parse
        format_module: precompiled module (e.g. "kaitaistruct.gif")
        ksy_path: path to a .ksy file (will be compiled on the fly)
    """
    return kaitai_runner.parse_with_format(path, format_module=format_module, ksy_path=ksy_path)


@mcp.tool()
def visualize(
    path: str,
    format_module: str = "",
    ksy_path: str = "",
) -> dict:
    """Return a tree-shaped dict suitable for visualization.

    Same as parse_with_format but explicitly named for the "show me
    the structure of this file" intent.
    """
    return kaitai_runner.parse_with_format(path, format_module=format_module, ksy_path=ksy_path)


@mcp.tool()
def parse_unityfs(
    path: str,
    ksy_path: str = "",
    decompress_block: int = 0,
) -> dict:
    """Parse a UnityFS / Addressables bundle, LZ4/LZMA-decompress
    the first block, and re-parse the directory from the
    decompressed stream.

    The on-disk KSY parse covers the file header + bundle header
    + per-block size records; the directory actually lives
    inside the *decompressed* first block (the on-disk format
    stores compressed block payloads after the per-block size
    records, and the directory + asset bodies are in those
    compressed bytes). This helper LZ4 / LZMA-decompresses the
    requested block and re-parses the ``Directory`` sub-type
    from the decompressed stream.

    Args:
        path: file to parse.
        ksy_path: optional path to a .ksy to compile on the
            fly. Defaults to the bundled
            ``data/ksy/unity_addressables.ksy`` (the v0.3
            corrected layout). Pass
            ``data/ksy/unityfs.ksy`` for the older
            ``bundle_header``-wrappered variant.
        decompress_block: index of the block to re-parse the
            directory from (default 0, the canonical directory
            block). Pass ``-1`` to skip the directory re-parse.

    Returns:
        A dict with ``file_header``, ``bundle_header``,
        ``decompressed_blocks[]`` (each with
        ``uncompressed_size`` / ``compressed_size`` /
        ``decompressed_size`` / ``data_b64``), and
        ``directory`` (or ``None`` if
        ``decompress_block=-1``).
    """
    return unityfs_blocks.parse_unityfs_with_blocks(
        path, ksy_path=ksy_path, decompress_block=decompress_block
    )


@mcp.tool()
def diff_parses(
    path_a: str,
    path_b: str,
    format_module: str = "",
    ksy_path: str = "",
) -> dict:
    """Parse two files with the same format and return a structural diff."""
    return kaitai_runner.diff_parses(path_a, path_b, format_module=format_module, ksy_path=ksy_path)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
