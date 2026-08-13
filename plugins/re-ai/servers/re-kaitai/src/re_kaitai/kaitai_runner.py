"""Subprocess + import glue for the kaitai-struct-compiler.

The compiler is a system binary; the runtime is the `kaitaistruct`
Python library. We compile .ksy → Python at runtime with subprocess,
then import the generated module and parse the target binary.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Any

from kaitaistruct import KaitaiStream


def get_compiler() -> str:
    return os.environ.get("KAITAI_COMPILER") or shutil.which("kaitai-struct-compiler") or "kaitai-struct-compiler"


def check_compiler() -> dict[str, Any]:
    """Return kaitai-struct-compiler version (or 'NOT FOUND')."""
    info: dict[str, Any] = {"status": "OK"}
    try:
        proc = subprocess.run(
            [get_compiler(), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            info["version"] = (proc.stdout or "").strip().splitlines()[0]
        else:
            info["version"] = "ERROR"
            info["status"] = "WARN"
    except FileNotFoundError as exc:
        info["version"] = f"NOT FOUND: {exc}"
        info["status"] = "WARN"
    return info


def list_known_formats() -> list[dict[str, str]]:
    """Return the list of bundled .ksy formats in kaitaistruct.

    Note: kaitaistruct ships a small built-in catalog; the full
    gallery is at https://formats.kaitai.io/ and can be downloaded
    on demand with `download_format`.

    Implemented by globbing the kaitaistruct package directory for
    ``*.py`` modules (excluding ``__init__`` and the package itself)
    rather than a hard-coded tuple of names — the hard-coded list
    drifted out of sync with what kaitaistruct actually ships.
    """
    import kaitaistruct

    pkg_dir = Path(kaitaistruct.__file__).parent
    formats: list[dict[str, str]] = []
    for f in sorted(pkg_dir.glob("*.py")):
        if f.stem in ("__init__", "kaitaistruct"):
            continue
        formats.append({
            "name": f.stem,
            "module": f"kaitaistruct.{f.stem}",
            "source": "bundled",
        })
    return formats


def download_format(name: str, target_dir: str = "") -> dict[str, str]:
    """Download a .ksy spec from the kaitai-formats gallery."""
    target = Path(target_dir) if target_dir else Path(tempfile.gettempdir()) / "kaitai-formats"
    target.mkdir(parents=True, exist_ok=True)
    url = f"https://raw.githubusercontent.com/kaitai-io/kaitai_struct_formats/master/{name}/{name}.ksy"
    out = target / f"{name}.ksy"
    import requests
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    out.write_bytes(r.content)
    return {"name": name, "ksy_path": str(out), "downloaded": "yes"}


def compile_format(ksy_path: str, target: str = "python") -> dict[str, str]:
    """Compile a .ksy file to a Python module. Returns the path."""
    src = Path(ksy_path)
    if not src.exists():
        raise FileNotFoundError(ksy_path)
    out_dir = src.parent / "_compiled"
    out_dir.mkdir(exist_ok=True)
    args = [get_compiler(), "--target", target, "--outdir", str(out_dir), str(src)]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"kaitai-struct-compiler failed: {proc.stderr[:500]}")
    return {"ksy_path": str(src), "compiled_dir": str(out_dir)}


def parse_with_format(
    path: str,
    format_module: str = "",
    ksy_path: str = "",
) -> dict[str, Any]:
    """Parse a binary using either a precompiled module or a fresh .ksy."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)
    if ksy_path:
        compiled = compile_format(ksy_path)
        # Cycle 2 fix: stale `sys.modules` cache. The prior
        # implementation called `importlib.import_module(stem)`
        # which returned the previously-cached module from
        # `sys.modules` on a second call with the same `ksy_path` —
        # so the freshly-compiled module was ignored and the user
        # saw stale results.
        #
        # The new flow:
        # 1. Use the ksy stem as the module name (kaitai-struct-compiler
        #    names the output file `<stem>.py`, so the module must be
        #    importable as `<stem>`).
        # 2. Pop the cached entry from `sys.modules` before re-importing.
        # 3. Call `importlib.invalidate_caches()` so the import
        #    machinery re-reads `sys.path`.
        module_name = Path(ksy_path).stem
        sys.path.insert(0, compiled["compiled_dir"])
        try:
            importlib.invalidate_caches()
            sys.modules.pop(module_name, None)
            mod = importlib.import_module(module_name)
            cls = getattr(mod, module_name.title().replace("_", ""), None) or next(
                (v for k, v in vars(mod).items() if k[0].isupper() and isinstance(v, type)),
                None,
            )
            if cls is None:
                raise RuntimeError(f"no top-level class found in compiled {module_name}")
            with p.open("rb") as f:
                obj = cls(KaitaiStream(BytesIO(f.read())))
            return _to_dict(obj)
        finally:
            sys.path.remove(compiled["compiled_dir"])
            # Best-effort: drop the freshly-imported module so a
            # subsequent recompile of the same .ksy (with new
            # mtime) actually re-imports.
            sys.modules.pop(module_name, None)
    elif format_module:
        mod = importlib.import_module(format_module)
        cls = next(
            (v for k, v in vars(mod).items() if k[0].isupper() and isinstance(v, type)),
            None,
        )
        if cls is None:
            raise RuntimeError(f"no top-level class in {format_module}")
        with p.open("rb") as f:
            obj = cls(KaitaiStream(BytesIO(f.read())))
        return _to_dict(obj)
    else:
        raise ValueError("either format_module or ksy_path is required")


def _to_dict(obj: Any) -> dict[str, Any]:
    """Best-effort: convert a kaitai struct parse tree to a dict."""
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
        if isinstance(val, (int, float, str, bool, type(None))):
            out[attr] = val
        elif isinstance(val, list):
            out[attr] = [_to_dict(v) if hasattr(v, "__dict__") else v for v in val]
        elif hasattr(val, "__dict__"):
            out[attr] = _to_dict(val)
    return out


def diff_parses(
    path_a: str,
    path_b: str,
    format_module: str = "",
    ksy_path: str = "",
) -> dict[str, Any]:
    """Parse two files with the same format and return a structural diff."""
    a = parse_with_format(path_a, format_module=format_module, ksy_path=ksy_path)
    b = parse_with_format(path_b, format_module=format_module, ksy_path=ksy_path)
    return {
        "a": a,
        "b": b,
        "differences": _diff(a, b),
    }


def _diff(a: Any, b: Any, path: str = "") -> list[dict[str, str]]:
    """Recursively compute field-level differences."""
    out: list[dict[str, str]] = []
    if type(a) != type(b):
        out.append({"path": path, "a_type": str(type(a)), "b_type": str(type(b))})
        return out
    if isinstance(a, dict):
        keys = set(a.keys()) | set(b.keys())
        for k in keys:
            out.extend(_diff(a.get(k), b.get(k), f"{path}.{k}"))
    elif a != b:
        out.append({"path": path, "a": str(a)[:120], "b": str(b)[:120]})
    return out
