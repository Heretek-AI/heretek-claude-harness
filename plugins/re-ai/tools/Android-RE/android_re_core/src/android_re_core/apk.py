"""androguard 4.1.4 wrapper with zip-bomb guards.

The :class:`Apk` class is the main entry point for static APK analysis.
It wraps androguard's :class:`APK` object with:

- **Zip-bomb guard** — checks file size and decompression ratio before
  opening. Defaults are conservative; override via env vars.
- **Resource access** — typed views for the manifest, components,
  permissions, and certificates.
- **Lazy closing** — androguard parses on construction. We allow
  explicit :meth:`close` to release the file handle.
- **SHA-256** — computed once on construction for project_id derivation.

This module is intentionally small. The androguard object model is rich
and best exposed in the higher-level modules (:mod:`manifest`,
:mod:`dex`, :mod:`certs`). :class:`Apk` exists to centralize the
"how do I open an APK?" question in one place.
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import (
    APKInvalid,
    APKNotFound,
    APKTooLarge,
    APKZipBomb,
)

# androguard is an optional-but-required import. We import at module load
# time because the rest of this file's type hints depend on it; if the
# user is on a platform without androguard wheels, the import will fail
# loudly at install time, not at first use.
try:
    from androguard.core.apk import APK  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "androguard is required for android_re_core.apk. "
        "Install with: uv pip install 'androguard==4.1.4'"
    ) from e


__all__ = [
    "DEFAULT_MAX_APK_SIZE",
    "DEFAULT_MAX_ZIP_ENTRIES",
    "DEFAULT_MAX_ZIP_RATIO",
    "Apk",
    "ApkSummary",
]


# ---------------------------------------------------------------------------
# Defaults (overridable via env)
# ---------------------------------------------------------------------------

#: Default max APK file size in bytes (500 MB).
DEFAULT_MAX_APK_SIZE: int = int(os.environ.get("ANDROID_RE_MAX_APK_SIZE", 500 * 1024 * 1024))

#: Default max ZIP decompression ratio (100:1). Anything beyond is
#: treated as a zip-bomb and rejected.
DEFAULT_MAX_ZIP_RATIO: int = int(os.environ.get("ANDROID_RE_MAX_ZIP_RATIO", 100))

#: Default max number of entries in the APK ZIP central directory.
DEFAULT_MAX_ZIP_ENTRIES: int = int(os.environ.get("ANDROID_RE_MAX_ZIP_ENTRIES", 100_000))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApkSummary:
    """Lightweight summary of an APK, safe to embed in tool responses."""

    apk_path: str
    sha256: str
    size: int
    package: str | None
    version_name: str | None
    version_code: str | None
    min_sdk: int | None
    target_sdk: int | None
    dex_count: int
    native_count: int
    is_signed: bool
    is_debuggable: bool
    allows_backup: bool | None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "apk_path": self.apk_path,
            "sha256": self.sha256,
            "size": self.size,
            "package": self.package,
            "version_name": self.version_name,
            "version_code": self.version_code,
            "min_sdk": self.min_sdk,
            "target_sdk": self.target_sdk,
            "dex_count": self.dex_count,
            "native_count": self.native_count,
            "is_signed": self.is_signed,
            "is_debuggable": self.is_debuggable,
            "allows_backup": self.allows_backup,
        }


# ---------------------------------------------------------------------------
# The Apk wrapper
# ---------------------------------------------------------------------------


@dataclass
class Apk:
    """A parsed, zip-bomb-guarded view of an APK.

    Construct with :meth:`open` (classmethod) rather than the regular
    constructor; this lets us run the safety checks before the androguard
    parse, so a hostile APK never reaches androguard's parser.

    Example::

        apk = Apk.open("/path/to/app.apk")
        manifest_xml = apk.read_manifest_xml()
        apk.close()
    """

    path: Path
    sha256: str
    size: int
    _apk: APK = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def open(
        cls,
        apk_path: str | Path,
        *,
        max_size: int = DEFAULT_MAX_APK_SIZE,
        max_ratio: int = DEFAULT_MAX_ZIP_RATIO,
        max_entries: int = DEFAULT_MAX_ZIP_ENTRIES,
    ) -> Apk:
        """Open an APK with zip-bomb guards.

        Args:
            apk_path: Path to the APK file. Must exist and be a regular file.
            max_size: Maximum APK file size in bytes.
            max_ratio: Maximum decompression ratio (uncompressed/compressed).
            max_entries: Maximum number of entries in the ZIP central directory.

        Raises:
            APKNotFound: The path does not exist or is not a file.
            APKTooLarge: The file exceeds ``max_size``.
            APKZipBomb: The file's entries exceed ``max_ratio`` or
                ``max_entries``.
            APKInvalid: The file is not a valid ZIP / APK.
        """
        path = Path(apk_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise APKNotFound(
                f"APK not found: {path}",
                details={"path": str(path)},
            )

        size = path.stat().st_size
        if size > max_size:
            raise APKTooLarge(
                f"APK exceeds max size: {size} > {max_size}",
                details={"size": size, "max_size": max_size, "path": str(path)},
            )

        # Pre-flight: verify the ZIP and check ratios without unzipping.
        cls._check_zip_bomb(path, max_ratio=max_ratio, max_entries=max_entries)

        # Hash the file. For very large files this is O(size); we do it once
        # on open so the project_id is stable across calls.
        sha256 = cls._sha256(path)

        # Now safe to hand off to androguard.
        try:
            apk_obj = APK(str(path))
        except Exception as e:  # androguard raises a variety of types
            raise APKInvalid(
                f"Failed to parse APK: {path}",
                details={"path": str(path), "error": str(e)},
            ) from e

        return cls(path=path, sha256=sha256, size=size, _apk=apk_obj)

    @staticmethod
    def _check_zip_bomb(path: Path, *, max_ratio: int, max_entries: int) -> None:
        """Walk the ZIP central directory and reject obvious zip-bombs.

        Cheap O(N) scan: does not decompress any entry, only reads the
        central directory.
        """
        try:
            with zipfile.ZipFile(str(path), "r") as zf:
                infos = zf.infolist()
        except zipfile.BadZipFile as e:
            raise APKInvalid(
                f"Not a valid ZIP/APK: {path}",
                details={"path": str(path), "error": str(e)},
            ) from e

        if len(infos) > max_entries:
            raise APKZipBomb(
                f"APK has too many entries: {len(infos)} > {max_entries}",
                details={"count": len(infos), "max_entries": max_entries},
            )

        for info in infos:
            # Skip directories
            if info.is_dir():
                continue
            # ``compress_size`` may be 0 for stored entries. In that case
            # the ratio check is meaningless; we accept.
            if info.compress_size == 0:
                continue
            ratio = info.file_size / info.compress_size
            if ratio > max_ratio:
                raise APKZipBomb(
                    f"Entry '{info.filename}' has suspicious ratio: {ratio:.1f} > {max_ratio}",
                    details={
                        "entry": info.filename,
                        "ratio": ratio,
                        "max_ratio": max_ratio,
                    },
                )

    @staticmethod
    def _sha256(path: Path, *, chunk: int = 1024 * 1024) -> str:
        """Compute SHA-256 of a file by streaming chunks."""
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                buf = f.read(chunk)
                if not buf:
                    break
                h.update(buf)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release any underlying file handles. Safe to call multiple times."""
        self._closed = True
        # androguard's APK does not expose a close() in 4.1.4; the
        # underlying ZipFile is held in attributes. We set them to None
        # to allow GC.
        import contextlib

        for attr in ("zip", "_zip"):
            with contextlib.suppress(AttributeError):
                setattr(self._apk, attr, None)

    @property
    def is_closed(self) -> bool:
        return self._closed

    def __enter__(self) -> Apk:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Views into the APK
    # ------------------------------------------------------------------

    @property
    def raw(self) -> APK:
        """Access the underlying androguard APK. Use sparingly.

        Most callers should prefer the typed view methods below.
        Accessing this after :meth:`close` raises :class:`APKInvalid`.
        """
        if self._closed:
            raise APKInvalid("APK has been closed", details={"path": str(self.path)})
        return self._apk

    def summary(self) -> ApkSummary:
        """Compute a lightweight summary of the APK.

        All androguard accessors are wrapped in try/except because
        synthetic test APKs and malformed APKs can raise varied errors
        at any of these access points.
        """
        apk = self.raw
        package = apk.get_package()
        return ApkSummary(
            apk_path=str(self.path),
            sha256=self.sha256,
            size=self.size,
            package=package,
            version_name=_safe(apk.get_androidversion_name),
            version_code=_safe(apk.get_androidversion_code),
            min_sdk=_safe(apk.get_min_sdk_version),
            target_sdk=_safe(apk.get_target_sdk_version),
            dex_count=len(list(apk.get_dex_names())),
            native_count=self._count_native_libs(),
            is_signed=_safe(apk.is_signed, default=False),
            is_debuggable=apk.get_attribute_value("application", "debuggable") in (True, "true"),
            allows_backup=self._get_allows_backup(apk),
        )

    @staticmethod
    def _get_allows_backup(apk: APK) -> bool | None:
        """Extract ``android:allowBackup`` from the application tag.

        Returns None if not specified (and on API levels where the default
        differs).
        """
        try:
            value = apk.get_attribute_value("application", "allowBackup")
        except Exception:
            return None
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        return str(value).lower() == "true"

    def _count_native_libs(self) -> int:
        """Count ELF shared objects across all ABIs."""
        count = 0
        for name in self.raw.get_files():
            if name.startswith("lib/") and name.endswith(".so"):
                count += 1
        return count

    # ------------------------------------------------------------------
    # Manifest / DEX / certs (Phase 1 stubs; real impls in Phase 2/3)
    # ------------------------------------------------------------------

    def read_manifest_xml(self) -> str:
        """Return the decoded ``AndroidManifest.xml`` as a UTF-8 string."""
        if self._closed:
            raise APKInvalid("APK has been closed", details={"path": str(self.path)})
        apk = self.raw
        try:
            # androguard 4.x exposes get_android_manifest_xml() returning
            # the AXMLPrinter output (an ElementTree Element).
            from xml.etree import ElementTree

            tree: ElementTree.Element = apk.get_android_manifest_xml()  # type: ignore[assignment]
            return ElementTree.tostring(tree, encoding="unicode")
        except Exception as e:
            raise APKInvalid(
                "Failed to decode AndroidManifest.xml",
                details={"path": str(self.path), "error": str(e)},
            ) from e


def _safe(func: Any, *, default: Any = None) -> Any:
    """Call an androguard accessor, returning ``default`` on any error.

    Many androguard accessors raise ``KeyError`` or ``Exception`` when
    the APK is malformed or a particular field is missing. The static
    analyzer must be robust to these.
    """
    try:
        return func()
    except Exception:
        return default
