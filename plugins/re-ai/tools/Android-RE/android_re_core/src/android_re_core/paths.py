"""Path resolution for vendored tools and the per-APK Output/ directory.

Centralizing path logic here means MCP servers and skills never have to
hard-code `vendor/jadx/bin/jadx` or `$ANDROID_HOME/platform-tools/adb`.
Every tool is resolved in a single place and can be overridden by an
environment variable.

Resolution order for every tool:

1. Explicit environment variable (e.g., ``APKTOOL_JAR``).
2. ``vendor/<tool>/<version>/...`` in the monorepo (populated by
   :file:`bin/pull-tools.sh`).
3. ``$PATH`` lookup.

For adb, we additionally check ``$ANDROID_HOME/platform-tools/adb`` and
``$ANDROID_SDK_ROOT/platform-tools/adb`` (common Android SDK locations).

The Output/ directory convention
--------------------------------

Every Android-RE run produces a directory tree under
``Output/<apk-basename>-<short-sha>/<subdir>/<file>``. The base path
``Output/`` lives at the monorepo root by default; override with the
``ANDROID_RE_OUTPUT_DIR`` environment variable. The env var is read
once at import time, so set it BEFORE importing :mod:`android_re_core`
in tests or alternative entry points.

The ``.triage/`` directory at the repo root has been retired — the
per-triage workdir now lives under ``Output/``. ``TRIAGE_DIR`` is
preserved as a backwards-compatible alias for ``OUTPUT_DIR`` and will
be removed in a future release.
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .errors import APKNotFound, ToolNotFound
from .version import __version__

__all__ = [
    "OUTPUT_DIR",
    "REPO_ROOT",
    "TOOL_VERSION",
    "TRIAGE_DIR",
    "VENDOR_DIR",
    "ToolPaths",
    "find_aapt2",
    "find_adb",
    "find_apksigner",
    "find_apktool",
    "find_bundletool",
    "find_frida_server",
    "find_jadx",
    "find_tool",
    "find_uber_apk_signer",
    "output_dir_for",
]


# ---------------------------------------------------------------------------
# Layout constants
# ---------------------------------------------------------------------------

#: Absolute path to the monorepo root. This is the directory containing
#: :file:`pyproject.toml`. Computed once at import time.
REPO_ROOT: Path = Path(__file__).resolve().parents[3]

#: Vendored tools directory. Populated by :file:`bin/pull-tools.sh`.
VENDOR_DIR: Path = REPO_ROOT / "vendor"

#: Base directory for every Android-RE deliverable. Each APK's artifacts
#: live in :func:`output_dir_for`. Resolved at import time from the
#: ``ANDROID_RE_OUTPUT_DIR`` env var if set, else ``REPO_ROOT / "Output"``.
OUTPUT_DIR: Path = (
    Path(os.environ.get("ANDROID_RE_OUTPUT_DIR", str(REPO_ROOT / "Output"))).expanduser().resolve()
)

#: Backwards-compatible alias for :data:`OUTPUT_DIR`. Retired; the
#: per-triage workdir now lives under ``Output/`` instead of a dedicated
#: ``.triage/`` directory. Will be removed in a future release.
TRIAGE_DIR: Path = OUTPUT_DIR

#: Default version of every vendored binary. Override with the
#: ``ANDROID_RE_VENDOR_VERSION`` env var.
TOOL_VERSION: str = os.environ.get("ANDROID_RE_VENDOR_VERSION", __version__)


# ---------------------------------------------------------------------------
# Per-APK output directory
# ---------------------------------------------------------------------------


def _short_sha(apk_path: Path, *, chunk_size: int = 1 << 20) -> str:
    """Return the first 8 hex chars of the APK's SHA-256.

    Reads in 1 MB chunks to keep memory bounded on large APKs
    (the input APK in ``Input/`` is 853 MB).
    """
    h = hashlib.sha256()
    with apk_path.open("rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            h.update(block)
    return h.hexdigest()[:8]


def output_dir_for(apk_path: str | os.PathLike[str]) -> Path:
    """Return the per-APK output directory.

    Convention: ``Output/<apk-basename>-<short-sha>/``. The short SHA is
    the first 8 hex chars of the APK's SHA-256; the directory name is
    therefore stable across runs of the same APK and distinct across
    different APKs (even if they share a basename).

    The directory is **not** created by this function — callers (the
    tool that writes the file) should ``mkdir(parents=True, exist_ok=True)``
    before writing. Tests and the ``Write`` tool can call this without
    a follow-up ``mkdir`` if they only inspect the path.

    Args:
        apk_path: Path to the APK. Must exist on disk; ``APKNotFound``
            is raised otherwise.

    Returns:
        The per-APK output directory (not yet created).
    """
    p = Path(apk_path).expanduser()
    if not p.exists():
        raise APKNotFound(str(p))
    return OUTPUT_DIR / f"{p.stem}-{_short_sha(p)}"


# ---------------------------------------------------------------------------
# Tool resolution
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolPaths:
    """Resolved paths for a single vendored tool."""

    name: str
    version: str
    root: Path
    primary: Path
    fallback: tuple[Path, ...] = ()

    def exists(self) -> bool:
        """Return True if the primary path exists and is executable."""
        return self.primary.exists()


def _which_or_422(name: str, *extra: Path) -> Path:
    """Resolve a tool on PATH, then the given extra directories."""
    found = shutil.which(name)
    if found:
        return Path(found)
    for p in extra:
        if p.exists():
            return p
    raise ToolNotFound(
        f"Could not locate '{name}' on PATH or in any extra search path.",
        details={"name": name, "extra": [str(p) for p in extra]},
    )


def _resolve(
    name: str,
    *,
    env_var: str | None,
    versioned_subpath: tuple[str, ...],
    fallback_exe: str | None = None,
    fallback_search: tuple[Path, ...] = (),
) -> ToolPaths:
    """Resolve a tool through the standard precedence order."""
    candidates: list[Path] = []

    if env_var and (env := os.environ.get(env_var)):
        candidates.append(Path(env))

    versioned_root = VENDOR_DIR.joinpath(name, *versioned_subpath)

    # The primary file is typically the executable inside the versioned root.
    exe_name = fallback_exe or name
    primary_file = versioned_root / exe_name

    return ToolPaths(
        name=name,
        version=TOOL_VERSION,
        root=versioned_root,
        primary=primary_file,
        fallback=fallback_search,
    )


def find_tool(name: str, env_var: str | None = None) -> Path:
    """Generic tool resolver. Returns the first existing path.

    Resolution order: env_var → ``$PATH`` → ``ToolPaths.primary``.
    """
    if env_var and (env := os.environ.get(env_var)):
        return Path(env)
    on_path = shutil.which(name)
    if on_path:
        return Path(on_path)
    # Fall back to vendor dir
    candidate = VENDOR_DIR / name / "bin" / name
    if candidate.exists():
        return candidate
    raise ToolNotFound(
        f"Could not locate '{name}' on PATH or in vendor/.",
        details={"name": name, "vendor_dir": str(VENDOR_DIR)},
    )


# ---------------------------------------------------------------------------
# Per-tool resolvers
# ---------------------------------------------------------------------------


def find_jadx() -> Path:
    """Locate the jadx executable."""
    if env := os.environ.get("JADX"):
        return Path(env)
    on_path = shutil.which("jadx")
    if on_path:
        return Path(on_path)
    vendor = VENDOR_DIR / "jadx" / TOOL_VERSION / "bin" / "jadx"
    if vendor.exists():
        return vendor
    raise ToolNotFound("jadx", details={"vendor_dir": str(VENDOR_DIR)})


def find_java() -> Path:
    """Locate the java executable (env, then ``$JAVA_HOME/bin/java``, then PATH)."""
    if env := os.environ.get("JAVA"):
        p = Path(env).expanduser()
        if p.exists():
            return p
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.exists():
            return candidate
    on_path = shutil.which("java")
    if on_path:
        return Path(on_path)
    raise ToolNotFound(
        "java",
        details={"hint": "Install Java 17+ or set JAVA_HOME or JAVA."},
    )


def find_apktool() -> Path:
    """Locate the apktool jar."""
    if env := os.environ.get("APKTOOL_JAR"):
        return Path(env)
    on_path = shutil.which("apktool")
    if on_path:
        return Path(on_path)
    vendor = VENDOR_DIR / "apktool" / TOOL_VERSION / "apktool.jar"
    if vendor.exists():
        return vendor
    raise ToolNotFound("apktool", details={"vendor_dir": str(VENDOR_DIR)})


def find_uber_apk_signer() -> Path:
    """Locate the uber-apk-signer jar."""
    if env := os.environ.get("UBER_APK_SIGNER_JAR"):
        return Path(env)
    on_path = shutil.which("uber-apk-signer")
    if on_path:
        return Path(on_path)
    vendor = VENDOR_DIR / "uber-apk-signer" / TOOL_VERSION / "uber-apk-signer.jar"
    if vendor.exists():
        return vendor
    raise ToolNotFound("uber-apk-signer", details={"vendor_dir": str(VENDOR_DIR)})


def find_apksigner() -> Path:
    """Locate the Android ``apksigner`` script.

    ``apksigner`` ships in ``$ANDROID_HOME/build-tools/<ver>/apksigner``.
    We look up the highest available build-tools version.
    """
    if env := os.environ.get("APKSIGNER"):
        return Path(env)
    on_path = shutil.which("apksigner")
    if on_path:
        return Path(on_path)
    for sdk_root in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(sdk_root)
        if not root:
            continue
        build_tools = Path(root) / "build-tools"
        if not build_tools.is_dir():
            continue
        versions = sorted(
            (p for p in build_tools.iterdir() if p.is_dir()),
            key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in p.name.split(".")),
            reverse=True,
        )
        for v in versions:
            apksigner = v / "apksigner"
            if apksigner.exists():
                return apksigner
    raise ToolNotFound(
        "apksigner", details={"hint": "Install Android build-tools or set APKSIGNER."}
    )


def find_bundletool() -> Path:
    """Locate the bundletool jar."""
    if env := os.environ.get("BUNDLETOOL_JAR"):
        return Path(env)
    on_path = shutil.which("bundletool")
    if on_path:
        return Path(on_path)
    vendor = VENDOR_DIR / "bundletool" / TOOL_VERSION / "bundletool.jar"
    if vendor.exists():
        return vendor
    raise ToolNotFound("bundletool", details={"vendor_dir": str(VENDOR_DIR)})


def find_aapt2() -> Path:
    """Locate the ``aapt2`` binary (Android build-tools)."""
    if env := os.environ.get("AAPT2"):
        return Path(env)
    on_path = shutil.which("aapt2")
    if on_path:
        return Path(on_path)
    for sdk_root in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(sdk_root)
        if not root:
            continue
        build_tools = Path(root) / "build-tools"
        if not build_tools.is_dir():
            continue
        versions = sorted(
            (p for p in build_tools.iterdir() if p.is_dir()),
            key=lambda p: tuple(int(x) if x.isdigit() else 0 for x in p.name.split(".")),
            reverse=True,
        )
        for v in versions:
            for candidate in (v / "aapt2", v / ("aapt2.exe" if os.name == "nt" else "aapt2")):
                if candidate.exists():
                    return candidate
    raise ToolNotFound("aapt2", details={"hint": "Install Android build-tools or set AAPT2."})


def find_adb() -> Path:
    """Locate the ``adb`` binary."""
    if env := os.environ.get("ADB"):
        return Path(env)
    on_path = shutil.which("adb")
    if on_path:
        return Path(on_path)
    for sdk_root in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        root = os.environ.get(sdk_root)
        if not root:
            continue
        candidate = Path(root) / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")
        if candidate.exists():
            return candidate
    raise ToolNotFound("adb", details={"hint": "Install Android Platform Tools or set ADB."})


def find_frida_server(arch: str) -> Path:
    """Locate the ``frida-server`` binary for the given architecture.

    Args:
        arch: One of ``"arm"``, ``"arm64"``, ``"x86"``, ``"x86_64"``.

    Returns:
        Path to the unpacked ``frida-server-<arch>`` binary.
    """
    if arch not in ("arm", "arm64", "x86", "x86_64"):
        raise ValueError(f"Unsupported frida-server arch: {arch!r}")
    suffix = ".exe" if os.name == "nt" else ""
    vendor = VENDOR_DIR / "frida-server" / TOOL_VERSION / f"frida-server-{arch}{suffix}"
    if vendor.exists():
        return vendor
    raise ToolNotFound(
        f"frida-server-{arch}",
        details={
            "hint": "Run ./bin/pull-tools.sh to vendor frida-server, or set FRIDA_SERVER_<ARCH>.",
            "arch": arch,
            "vendor_dir": str(VENDOR_DIR),
        },
    )
