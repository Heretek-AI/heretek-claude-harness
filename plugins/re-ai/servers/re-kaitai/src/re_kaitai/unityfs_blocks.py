"""UnityFS / Addressables block-decompression helper.

The ``data/ksy/unityfs.ksy`` and ``data/ksy/unity_addressables.ksy``
specs cover the on-disk file header + bundle header up to the
per-block size records. They do NOT cover the *decompressed*
first-block payload, which is where the actual directory
(asset path -> offset/size/type mapping) lives. The on-disk KSY
parse therefore cannot recover the directory by itself.

This module provides ``parse_unityfs_with_blocks``: a small
helper that

1. runs the on-disk KSY parse to get the bundle_header
   (flags, num_blocks, per-block uncompressed/compressed sizes),
2. reads each block's compressed payload from the file,
3. decompresses the block (LZ4 / LZMA / none per ``flags``),
4. re-parses the directory from the decompressed first block
   using the compiled ``Directory`` class.

The Python kaitai runtime does not support inline LZ4 / LZMA
``process:`` directives (the kaitai-struct-compiler 0.10 emits
runtime calls but Python's kaitaistruct library has no built-in
LZ4 / LZMA services), so the decompression must happen on the
Python side and the directory parse must be re-driven against
the decompressed bytes.

The vendor-neutral guarantee is preserved: this helper deals
with the UnityFS / Addressables on-disk format only, not with
any specific commercial product, publisher, or game title.
"""

from __future__ import annotations

import importlib
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from kaitaistruct import KaitaiStream


# Soft-imports for the optional compression deps. Mirror the
# pattern in ``servers/re-lief/src/re_lief/categorizers.py:33-41``:
# import the dep lazily so the MCP server can still load when
# lz4 / lzma are absent, and surface a useful error message at
# the call site.
def _require_lz4() -> Any:
    try:
        import lz4.block  # type: ignore[import-untyped]
        return lz4.block
    except ImportError as _exc:
        raise ImportError(
            "re_kaitai.parse_unityfs requires the lz4 package for "
            "UnityFS / Addressables block decompression. Re-run "
            "`./install.sh` (or `pip install lz4` in the re-kaitai "
            f"venv). Underlying error: {_exc}"
        ) from _exc


# ``lzma`` is a Python stdlib module (PEP 42) — always present.
import lzma  # noqa: E402


def _get_compiler() -> str:
    """Locate the kaitai-struct-compiler binary (PATH or env)."""
    import os
    return (
        os.environ.get("KAITAI_COMPILER")
        or shutil.which("kaitai-struct-compiler")
        or "kaitai-struct-compiler"
    )


def _compile_and_import(ksy_path: str) -> tuple[Any, str, str]:
    """Compile a .ksy to Python and import it.

    Returns ``(module, top_level_class_name, compiled_dir)``.
    Mirrors the cache-invalidation flow in
    ``kaitai_runner.parse_with_format`` (lines 112-148).
    """
    src = Path(ksy_path)
    if not src.exists():
        raise FileNotFoundError(ksy_path)
    out_dir = src.parent / "_compiled"
    out_dir.mkdir(exist_ok=True)
    proc = subprocess.run(
        [_get_compiler(), "--target", "python", "--outdir", str(out_dir), str(src)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"kaitai-struct-compiler failed: {proc.stderr[:500]}"
        )
    module_name = src.stem
    sys.path.insert(0, str(out_dir))
    try:
        importlib.invalidate_caches()
        sys.modules.pop(module_name, None)
        mod = importlib.import_module(module_name)
        # Find the top-level class. Prefer the name derived from
        # `meta.id` in the KSY (e.g. `unity_addressables` ->
        # `UnityAddressables`); fall back to the first uppercase
        # class in the module that isn't the `KaitaiStruct` base
        # class (which the compiler imports into the module's
        # namespace but is not the parse target).
        meta_id_attr = (
            module_name.replace("_", " ")
            .title()
            .replace(" ", "")
        )
        cls_name = None
        if hasattr(mod, meta_id_attr) and isinstance(
            getattr(mod, meta_id_attr), type
        ):
            cls_name = meta_id_attr
        else:
            for k, v in vars(mod).items():
                if (
                    k[0].isupper()
                    and isinstance(v, type)
                    and v is not __import__(
                        "kaitaistruct", fromlist=["KaitaiStruct"]
                    ).KaitaiStruct
                ):
                    cls_name = k
                    break
        if cls_name is None:
            raise RuntimeError(
                f"no top-level class found in compiled {module_name}"
            )
        return mod, cls_name, str(out_dir)
    finally:
        sys.path.remove(str(out_dir))
        sys.modules.pop(module_name, None)


def _to_dict(obj: Any) -> dict[str, Any]:
    """Best-effort: convert a kaitai struct parse tree to a dict.

    Mirrors the same walk in ``kaitai_runner._to_dict`` (lines
    164-182), with one addition: ``bytes`` fields (e.g. the
    8-byte ``magic`` field) are preserved. The original
    ``kaitai_runner._to_dict`` drops bytes because they
    don't match the (int, float, str, bool, NoneType) tuple;
    the UnityFS / Addressables file-header has a binary
    ``magic`` field that we want to surface to the consumer
    so it can sanity-check the file. Kept private to this
    module so we don't add a cross-module dep on
    kaitai_runner for the directory parse.
    """
    out: dict[str, Any] = {}
    for attr in dir(obj):
        if attr.startswith("_"):
            continue
        try:
            val = getattr(obj, attr)
        except Exception:  # noqa: BLE001
            continue
        if callable(val):
            continue
        if isinstance(val, (int, float, str, bool, type(None), bytes)):
            out[attr] = val
        elif isinstance(val, list):
            out[attr] = [_to_dict(v) if hasattr(v, "__dict__") else v for v in val]
        elif hasattr(val, "__dict__"):
            out[attr] = _to_dict(val)
    return out


def _decompress_block(
    flags: int, data: bytes, uncompressed_size: int
) -> bytes:
    """Decompress one block per the bundle's ``flags`` value.

    ``flags`` is a 3-value enum per the KSY docstring:
      0 = none (raw bytes)
      1 = LZ4 (LZ4 *block* format — the bytes have a 4-byte
           uncompressed-size header that the ``lz4`` Python
           module reads; we do NOT pass an explicit
           ``uncompressed_size`` to ``lz4.block.decompress``)
      2 = LZMA

    The ``uncompressed_size`` parameter is the on-disk
    block-record value (4 bytes u4, read by the KSY parse);
    it is recorded in the response so the consumer can
    sanity-check the decompressed size but is not used in
    the decompress call.
    """
    if flags == 0:
        return data
    if flags == 1:
        lz4 = _require_lz4()
        # The LZ4 block format includes the uncompressed size
        # in its 8-byte header (when ``mode='default'``, which
        # is what ``lz4.block.compress`` uses by default). The
        # decompress call reads the size from the header; an
        # explicit ``uncompressed_size=`` argument conflicts
        # with the header and raises ``LZ4BlockError`` for any
        # compressible payload. We omit the argument and let
        # the header drive the buffer allocation.
        return lz4.decompress(data)
    if flags == 2:
        return lzma.decompress(data)
    raise ValueError(
        f"unsupported UnityFS / Addressables flags={flags}; "
        f"expected 0 (none), 1 (LZ4), or 2 (LZMA)"
    )


def parse_unityfs_with_blocks(
    path: str,
    ksy_path: str = "",
    decompress_block: int = 0,
) -> dict[str, Any]:
    """Parse a UnityFS / Addressables bundle, LZ4/LZMA-decompress
    block 0, and re-parse the directory from the decompressed
    stream.

    Args:
        path: file to parse
        ksy_path: path to the .ksy to compile (defaults to
            ``data/ksy/unity_addressables.ksy`` from the plugin
            root). Pass ``data/ksy/unityfs.ksy`` for the older
            ``bundle_header``-wrappered variant.
        decompress_block: index of the block whose decompressed
            bytes are returned in the ``decompressed_blocks[]``
            list AND re-parsed as the ``directory`` (default 0,
            which is the directory block in canonical UnityFS).
            Pass ``-1`` to skip the directory re-parse and only
            return the on-disk parse + raw decompressed bytes.

    Returns:
        A dict with the following shape::

            {
              "file_header": {magic, version, bundle_format_version,
                              unity_version, file_size},
              "bundle_header": {signature, version, unity_revision,
                                compressed_block_info: {flags, num_blocks,
                                blocks: [{uncompressed_size, compressed_size}, ...]}},
              "decompressed_blocks": [
                {"index": 0, "uncompressed_size": N, "decompressed_size": M,
                 "data_b64": "..."},
                ...
              ],
              "directory": {num_entries, entries: [...]} | None,
            }

    The ``data_b64`` field is base64-encoded because MCP
    responses are JSON and the decompressed bytes are arbitrary
    binary. The downstream consumer decodes it before
    re-processing.
    """
    if not ksy_path:
        # Default to the Addressables KSY (the v0.3 corrected
        # layout that the 2026-06-06-r01 stress test verified).
        plugin_root = Path(__file__).resolve().parents[4]
        default_ksy = plugin_root / "data" / "ksy" / "unity_addressables.ksy"
        if default_ksy.exists():
            ksy_path = str(default_ksy)
        else:
            raise FileNotFoundError(
                f"no ksy_path given and default not found: {default_ksy}"
            )

    mod, cls_name, _ = _compile_and_import(ksy_path)
    cls = getattr(mod, cls_name)

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    raw = p.read_bytes()
    bio = BytesIO(raw)

    # Step 1: on-disk parse (file_header + bundle_header +
    # compressed_block_info + per-block records).
    parsed = cls(KaitaiStream(bio))
    file_header = _to_dict(parsed)
    # The two KSY variants have different structures:
    #   - unityfs.ksy wraps the rest in a `bundle_header` sub-
    #     type (signature + version + unity_revision +
    #     compressed_block_info).
    #   - unity_addressables.ksy is flat: the top-level seq
    #     contains the compressed_block_info directly (no
    #     bundle_header wrapper).
    # Find the compressed_block_info in whichever level it
    # appears at.
    bundle_header = file_header.get("bundle_header", {}) or {}
    cbi = (
        file_header.get("compressed_block_info")
        or bundle_header.get("compressed_block_info")
        or {}
    )
    flags = int(cbi.get("flags", 0))
    num_blocks = int(cbi.get("num_blocks", 0))
    block_records = cbi.get("blocks", []) or []

    # Step 2: walk the per-block records, read each block's
    # compressed_size bytes from the file, decompress.
    import base64

    cursor = bio.tell()
    decompressed_blocks: list[dict[str, Any]] = []
    for i, blk in enumerate(block_records):
        comp_size = int(blk.get("compressed_size", 0))
        unc_size = int(blk.get("uncompressed_size", 0))
        compressed = raw[cursor : cursor + comp_size]
        cursor += comp_size
        try:
            decompressed = _decompress_block(flags, compressed, unc_size)
        except Exception as exc:  # noqa: BLE001
            decompressed_blocks.append({
                "index": i,
                "uncompressed_size": unc_size,
                "compressed_size": comp_size,
                "decompress_error": f"{type(exc).__name__}: {exc}",
            })
            continue
        decompressed_blocks.append({
            "index": i,
            "uncompressed_size": unc_size,
            "compressed_size": comp_size,
            "decompressed_size": len(decompressed),
            "data_b64": base64.b64encode(decompressed).decode("ascii"),
        })

    # Step 3: re-parse the directory from the decompressed
    # first block.
    directory: dict[str, Any] | None = None
    if (
        decompress_block >= 0
        and decompress_block < len(decompressed_blocks)
        and "data_b64" in decompressed_blocks[decompress_block]
    ):
        dec_bytes = base64.b64decode(
            decompressed_blocks[decompress_block]["data_b64"]
        )
        # Find the `Directory` class. The kaitai compiler
        # generates the inner-type classes as NESTED classes
        # of the top-level class (e.g.
        # ``UnityAddressables.Directory``); we walk the
        # module's namespace and any nested ``__dict__`` on
        # the top-level class to find it.
        from kaitaistruct import KaitaiStruct as _KS
        Directory = None
        TopClass = getattr(mod, cls_name)
        for v in vars(TopClass).values():
            if (
                isinstance(v, type)
                and v is not _KS
                and v.__name__ == "Directory"
            ):
                Directory = v
                break
        if Directory is None:
            # Fallback: scan the module namespace.
            for k, v in vars(mod).items():
                if (
                    k[0].isupper()
                    and isinstance(v, type)
                    and v is not _KS
                    and k.lower() == "directory"
                ):
                    Directory = v
                    break
        if Directory is not None:
            dir_obj = Directory(KaitaiStream(BytesIO(dec_bytes)))
            directory = _to_dict(dir_obj)

    return {
        "file_header": file_header,
        "bundle_header": bundle_header,
        "decompressed_blocks": decompressed_blocks,
        "directory": directory,
    }
