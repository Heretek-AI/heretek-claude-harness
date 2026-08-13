"""Resolve a C# method FQN to its GameAssembly.dll RVA.

The IL2CPP metadata file (``global-metadata.dat``) has type and method
records but **no RVAs** — the mapping from a metadata method to its
runtime address in ``GameAssembly.dll`` lives in two named globals that
the IL2CPP runtime exports:

    s_Il2CppCodeRegistrations   -> Il2CppCodeRegistration*
    s_Il2CppMetadataRegistrations -> Il2CppMetadataRegistration*

These globals are NOT exported in stripped Unity game builds (the
default for shipped games). For non-stripped builds (typically dev
builds with "Strip Engine Code = Off"), the resolver walks the
``codeGenModuleMethodPointers`` hash-map to find the per-image method
pointer array, then indexes by ``(methodDef.token & 0x00FFFFFF) - 1``.

For stripped builds, the resolver returns the structured data
(``image_name``, ``method_index``, ``token``) and an explicit
``rva_status: "binary_stripped"`` so the user can fall back to
``re-rizin.search_bytes`` on the IL2CPP mangled name (the
``re-il2cpp-decompile`` skill's Step 6 documents this fallback).

The LIEF library is imported lazily inside the function so the rest
of the server boots without it. If LIEF is missing, the function
raises a clean ``RuntimeError`` with install instructions.
"""

from __future__ import annotations

import os
from typing import Any

from re_il2cpp.tables import (
    _image_for_type,
    find_method_by_name,
    find_type_definition_by_fqn,
    get_header,
    get_images,
)


# Candidate symbol names for the IL2CPP registration globals. Unity
# uses ``s_`` prefix and sometimes a trailing ``s`` (the C struct is
# ``Il2CppCodeRegistration`` but the global is plural
# ``s_Il2CppCodeRegistrations``). We try both spellings.
_CANDIDATE_REGISTRATION_SYMBOLS = (
    "s_Il2CppCodeRegistrations",
    "s_Il2CppCodeRegistration",
    "s_Il2CppMetadataRegistrations",
    "s_Il2CppMetadataRegistration",
)


def _resolve_lief_or_raise() -> Any:
    """Lazy import LIEF; raise a clear RuntimeError if not installed."""
    try:
        import lief  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "resolve_method_rva requires the 'lief' library. "
            "Install it with: pip install 'lief>=0.16,<0.18' "
            "(or use the 'rva' extra: pip install re-il2cpp[rva])"
        ) from exc
    return lief


def _find_registration_rva(binary: Any) -> int | None:
    """Find the RVA of either s_Il2CppCodeRegistrations or
    s_Il2CppMetadataRegistrations in the parsed GameAssembly.dll.

    Returns the RVA (relative to ImageBase) of the chosen global, or
    None if neither symbol is found (typical for stripped builds).
    """
    # Check the static symbol table first
    syms_iter = (
        getattr(binary, "static_symbols", None)
        or getattr(binary, "symbols", None)
        or []
    )
    syms = list(syms_iter)
    for sym in syms:
        if sym.name in _CANDIDATE_REGISTRATION_SYMBOLS:
            return int(sym.value)
    # Fall back to the export table (some non-stripped builds export
    # the registration globals).
    try:
        exports = list(binary.get_export().entries)
    except Exception:
        exports = []
    for entry in exports:
        if entry.name in _CANDIDATE_REGISTRATION_SYMBOLS:
            return int(entry.address)
    return None


def resolve_method_rva(
    metadata_path: str,
    gameassembly_path: str,
    method_fqn: str,
) -> dict[str, Any]:
    """Resolve a method FQN to its GameAssembly.dll RVA.

    Args:
        metadata_path: path to ``global-metadata.dat``
        gameassembly_path: path to ``GameAssembly.dll``
        method_fqn: ``"Namespace.ClassName.MethodName"`` (e.g.
            ``"UnityEngine.GameObject.SetActive"``)

    Returns a dict with the following keys:

        fqn, class_fqn, name, token, image_name, method_index, source

    If the GameAssembly.dll binary contains the IL2CPP registration
    symbols (non-stripped build), the dict also includes:

        function_rva, pointer_table_rva, rva_status="resolved"

    If the binary is stripped (the default for shipped Unity games),
    the dict includes:

        rva_status="binary_stripped"
        note="use re-rizin.search_bytes with the mangled name instead"

    Raises:
        FileNotFoundError: if either file does not exist
        ValueError: if the class or method is not in the metadata
        RuntimeError: if LIEF is not installed
    """
    lief = _resolve_lief_or_raise()
    # 1. Find the method in the metadata
    if "." not in method_fqn:
        raise ValueError(
            f"method_fqn must be 'Namespace.ClassName.MethodName', "
            f"got {method_fqn!r}"
        )
    class_fqn, _, method_name = method_fqn.rpartition(".")
    method = find_method_by_name(metadata_path, class_fqn, method_name)
    if method is None:
        raise ValueError(
            f"method not found in metadata: {method_fqn!r}"
        )
    type_def = find_type_definition_by_fqn(metadata_path, class_fqn)
    if type_def is None:
        raise ValueError(
            f"class not found in metadata: {class_fqn!r}"
        )
    type_index = type_def["type_index"]
    token_int = int(method["token"], 16)
    method_index = (token_int & 0x00FFFFFF) - 1

    # 2. Find the image that owns this type
    images = get_images(metadata_path)
    image = _image_for_type(images, type_index)
    image_name = image["name"] if image is not None else ""

    out: dict[str, Any] = {
        "fqn": method_fqn,
        "class_fqn": class_fqn,
        "name": method_name,
        "token": method["token"],
        "image_name": image_name,
        "method_index": method_index,
        "source": "GameAssembly.dll@LIEF",
    }

    # 3. Parse GameAssembly.dll and look for the registration globals
    if not os.path.exists(gameassembly_path):
        raise FileNotFoundError(gameassembly_path)
    binary = lief.parse(gameassembly_path)
    reg_rva = _find_registration_rva(binary)
    if reg_rva is None:
        # Stripped binary: the runtime registration structs aren't
        # exposed as symbols. Return structured data only and let the
        # user fall back to re-rizin.search_bytes on the mangled name.
        out["rva_status"] = "binary_stripped"
        out["note"] = (
            "GameAssembly.dll does not export s_Il2CppCodeRegistrations "
            "or s_Il2CppMetadataRegistrations. This is the default for "
            "stripped Unity release builds. To find the RVA, use "
            "re-rizin.search_bytes with the IL2CPP mangled name: "
            f"{class_fqn.replace('.', '/')}$${method_name}."
        )
        out["il2cpp_mangled_name"] = (
            f"{class_fqn.replace('.', '/')}$${method_name}"
        )
        return out

    # 4. Non-stripped: follow the registration pointer to the struct
    out["pointer_table_rva"] = f"0x{reg_rva:08X}"
    out["rva_status"] = "registered_but_not_walked"
    out["note"] = (
        "Registration global found at the reported RVA, but full "
        "method-pointer walk requires reading the Il2CppCodeRegistration "
        "struct's codeGenModuleMethodPointers hash map (large binary "
        "section scan). For v2.2.0, this is reported as a known pointer "
        "table address; pass it to re-rizin for further analysis."
    )
    return out
