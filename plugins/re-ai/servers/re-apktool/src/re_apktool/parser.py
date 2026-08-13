"""APK parsing helpers.

The MCP wrappers in :mod:`re_apktool.server` call into this
module. The module supports two backends:

* **androguard** — pure-Python, always available. Used for the
  header summary, DEX class enumeration, and manifest decoding.
* **apktool** — Java CLI, used for high-fidelity Smali dumps and
  full manifest decoding (androguard's manifest parser is
  good-enough for the component lists, but apktool's output is
  closer to the canonical AOSP form).

The backend choice is transparent to the MCP layer: callers ask
for a result shape, and this module picks whichever backend can
deliver.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("re_apktool")
logger.setLevel(logging.INFO)


# ── availability ────────────────────────────────────────────────────────


def check_apktool() -> dict:
    """Return apktool / androguard / java availability."""
    import importlib.util

    apkt = shutil.which("apktool") or shutil.which("apktool.bat")
    java_ok = shutil.which("java") is not None
    ag_spec = importlib.util.find_spec("androguard")
    ag_ok = ag_spec is not None
    # Determine the active backend: apktool wins when both are
    # present, androguard is always the fallback.
    if apkt and java_ok:
        backend = "apktool"
        status = "OK"
    elif ag_ok:
        backend = "androguard"
        status = "OK"
    else:
        backend = "none"
        status = "WARN"
    return {
        "server": "re-apktool",
        "version": "0.1.0",
        "status": status,
        "apktool_path": apkt,
        "java_path": shutil.which("java"),
        "androguard_available": ag_ok,
        "active_backend": backend,
        "install_hint": (
            "pip install androguard (required); "
            "apktool is optional (apt-get install apktool)"
        ),
    }


# ── header / summary ────────────────────────────────────────────────────


def parse_apk(path: str) -> dict:
    """Return a structural summary of *path*.

    Uses androguard's APK analysis when available; falls back to
    a pure-zipfile + manifest-parse pass when it isn't. The
    output is always JSON-safe (no androguard object types leak
    through).
    """
    p = Path(path)
    if not p.is_file():
        return {"status": "ERROR", "path": path, "error": f"not a file: {path}"}
    if not zipfile.is_zipfile(p):
        return {"status": "ERROR", "path": path, "error": "not a zip / APK file"}

    out: dict[str, Any] = {
        "status": "OK",
        "path": path,
        "size": p.stat().st_size,
    }

    # Try androguard first — its APK object gives a richer
    # header (package, version, min/target SDK, perms, sig
    # scheme, etc.) than the zipfile-only fallback.
    try:
        from androguard.core.apk import APK  # type: ignore[import-untyped]
    except (ImportError, Exception):  # noqa: BLE001
        APK = None  # type: ignore[assignment]

    if APK is not None:
        try:
            apk = APK(path)
            out["backend"] = "androguard"
            out["package"] = apk.get_package()
            out["app_name"] = apk.get_app_name()
            out["version_name"] = apk.get_androidversion_name()
            out["version_code"] = apk.get_androidversion_code()
            out["min_sdk"] = apk.get_min_sdk_version()
            out["target_sdk"] = apk.get_target_sdk_version()
            out["compile_sdk"] = apk.get_max_sdk_version()
            out["permissions"] = sorted(apk.get_permissions() or [])
            out["activities"] = sorted(apk.get_activities() or [])
            out["services"] = sorted(apk.get_services() or [])
            out["receivers"] = sorted(apk.get_receivers() or [])
            out["providers"] = sorted(apk.get_providers() or [])
            out["signature_names"] = sorted(apk.get_signature_names() or [])
            out["is_signed"] = bool(apk.is_signed())
            out["is_signed_v1"] = bool(apk.is_signed_v1())
            out["is_signed_v2"] = bool(apk.is_signed_v2())
            out["is_signed_v3"] = bool(apk.is_signed_v3())
            out["is_debuggable"] = bool(apk.get_attribute_value("application", "debuggable"))
            out["is_backup_allowed"] = (
                str(apk.get_attribute_value("application", "allowBackup")).lower() == "true"
            )
        except Exception as exc:  # noqa: BLE001
            out["backend_error"] = f"{type(exc).__name__}: {exc}"
            out["backend"] = "zipfile-fallback"
    else:
        out["backend"] = "zipfile-fallback"

    # Always-on zipfile walk — gives the per-file entry list and
    # the dex-file inventory regardless of which backend parsed
    # the manifest.
    out["entries"] = []
    out["dex_files"] = []
    out["native_libs"] = []
    out["assets_count"] = 0
    out["resources_arsc_present"] = False
    out["manifest_present"] = False
    with zipfile.ZipFile(p) as zf:
        for info in zf.infolist():
            out["entries"].append({
                "name": info.filename,
                "size": info.file_size,
                "compressed": info.compress_size,
            })
            base = info.filename.rsplit("/", 1)[-1]
            if info.filename.startswith("classes") and base.endswith(".dex"):
                out["dex_files"].append(info.filename)
            elif info.filename.startswith("lib/") and base.endswith(".so"):
                out["native_libs"].append(info.filename)
            elif info.filename.startswith("assets/"):
                out["assets_count"] += 1
            elif info.filename == "resources.arsc":
                out["resources_arsc_present"] = True
            elif info.filename == "AndroidManifest.xml":
                out["manifest_present"] = True
    return out


# ── DEX class enumeration ───────────────────────────────────────────────


def list_dex_classes(path: str) -> dict:
    """Enumerate every class in every ``classes*.dex`` in the APK."""
    p = Path(path)
    if not p.is_file():
        return {"status": "ERROR", "path": path, "error": f"not a file: {path}"}

    try:
        from androguard.core.dex import DEX  # type: ignore[import-untyped]
    except (ImportError, Exception):  # noqa: BLE001
        return {
            "status": "ERROR",
            "path": path,
            "error": "androguard is required for list_dex_classes",
        }

    out: dict[str, Any] = {
        "status": "OK",
        "path": path,
        "dex_files": [],
        "class_count": 0,
        "classes": [],
    }
    with zipfile.ZipFile(p) as zf:
        for info in zf.infolist():
            base = info.filename.rsplit("/", 1)[-1]
            if not (info.filename.startswith("classes") and base.endswith(".dex")):
                continue
            with zf.open(info) as f:
                dex_bytes = f.read()
            try:
                dex = DEX(dex_bytes)
            except Exception as exc:  # noqa: BLE001
                out["dex_files"].append({
                    "name": info.filename,
                    "size": info.file_size,
                    "error": f"{type(exc).__name__}: {exc}",
                })
                continue
            dex_classes: list[dict] = []
            for cls in dex.get_classes():
                # cls.get_name() returns "Lcom/foo/Bar;" — strip
                # the L/; for a Java-style FQN.
                raw = cls.get_name() or ""
                fqn = raw.lstrip("L").rstrip(";")
                access = cls.get_access_flags_string() or ""
                dex_classes.append({
                    "fqn": fqn,
                    "access": access,
                    "method_count": len(list(cls.get_methods())),
                })
            out["dex_files"].append({
                "name": info.filename,
                "size": info.file_size,
                "class_count": len(dex_classes),
            })
            out["classes"].extend(dex_classes)
    out["class_count"] = len(out["classes"])
    return out


# ── manifest decoding ───────────────────────────────────────────────────


def decode_manifest(path: str) -> dict:
    """Decode the APK's AndroidManifest.xml.

    Returns the manifest as text (androguard's AXMLPrinter) plus
    the parsed component / permission lists (same shape as
    :func:`parse_apk`'s output for the components the manifest
    declares).
    """
    p = Path(path)
    if not p.is_file():
        return {"status": "ERROR", "path": path, "error": f"not a file: {path}"}

    try:
        from androguard.core.apk import APK  # type: ignore[import-untyped]
    except (ImportError, Exception):  # noqa: BLE001
        return {
            "status": "ERROR",
            "path": path,
            "error": "androguard is required for decode_manifest",
        }

    try:
        apk = APK(path)
        manifest_text = apk.get_android_manifest_axml().get_xml() or ""
        # ``apk.get_android_manifest_xml()`` returns an
        # AXMLPrinter on success; the get_xml() call serialises
        # it. If androguard refuses (encrypted manifest), the
        # text is empty — the analyst falls back to apktool
        # for that case.
        return {
            "status": "OK",
            "path": path,
            "backend": "androguard",
            "manifest_xml": manifest_text,
            "package": apk.get_package(),
            "version_name": apk.get_androidversion_name(),
            "version_code": apk.get_androidversion_code(),
            "min_sdk": apk.get_min_sdk_version(),
            "target_sdk": apk.get_target_sdk_version(),
            "permissions": sorted(apk.get_permissions() or []),
            "activities": sorted(apk.get_activities() or []),
            "services": sorted(apk.get_services() or []),
            "receivers": sorted(apk.get_receivers() or []),
            "providers": sorted(apk.get_providers() or []),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "path": path,
            "error": f"manifest decode failed: {type(exc).__name__}: {exc}",
        }
