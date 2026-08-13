"""android_re_core: shared Python library for Android reverse engineering.

This package is the internal core that every Python MCP server in the
android-re monorepo imports from. It centralizes:

- APK opening and zip-bomb guarding (:mod:`android_re_core.apk`)
- Manifest, DEX, and certificate views (:mod:`android_re_core.manifest`,
  :mod:`android_re_core.dex`, :mod:`android_re_core.certs`)
- The :class:`~android_re_core.project.ProjectStore` registry
- Typed errors (:mod:`android_re_core.errors`)
- Path resolution for vendored tools (:mod:`android_re_core.paths`)

Phase 1 ships: apk, manifest, dex, certs, project, errors, paths, version.
Phase 2 adds: native, smali, sources, secrets, reporting.
Phase 3 adds: frida, device.
Phase 4 adds: store/sqlite.
"""

from __future__ import annotations

from .apk import Apk, ApkSummary
from .certs import CertificateInfo, CertsView, SignatureInfo, SignerInfo
from .cleanup import CleanupReport, JadxCleanup
from .cleanup import cleanup as cleanup_workdir
from .dex import DexClass, DexField, DexMethod, DexView, Xref
from .errors import (
    AndroidReError,
    APKAlreadyOpen,
    APKError,
    APKInvalid,
    APKNotFound,
    APKTooLarge,
    APKZipBomb,
    DeviceError,
    FridaError,
    ProjectClosed,
    ProjectError,
    ProjectNotFound,
    ToolError,
    ToolFailed,
    ToolNotFound,
    ToolTimeout,
)
from .gradle import GradleProjectBuilder, GradleProjectReport, create_gradle_project
from .manifest import Component, ComponentType, ManifestView, Permission
from .paths import (
    OUTPUT_DIR,
    REPO_ROOT,
    TOOL_VERSION,
    TRIAGE_DIR,
    VENDOR_DIR,
    find_aapt2,
    find_adb,
    find_apksigner,
    find_apktool,
    find_bundletool,
    find_frida_server,
    find_jadx,
    find_tool,
    find_uber_apk_signer,
    output_dir_for,
)
from .project import (
    DEFAULT_PROJECT_ID_PREFIX,
    Project,
    ProjectStore,
    derive_project_id,
)
from .version import ANDROID_RE_VERSION, PYTHON_MIN_VERSION, __version__

__all__ = [
    "ANDROID_RE_VERSION",
    "DEFAULT_PROJECT_ID_PREFIX",
    "OUTPUT_DIR",
    "PYTHON_MIN_VERSION",
    "REPO_ROOT",
    "TOOL_VERSION",
    "TRIAGE_DIR",
    "VENDOR_DIR",
    "APKAlreadyOpen",
    "APKError",
    "APKInvalid",
    "APKNotFound",
    "APKTooLarge",
    "APKZipBomb",
    "AndroidReError",
    "Apk",
    "ApkSummary",
    "CertificateInfo",
    "CertsView",
    "CleanupReport",
    "Component",
    "ComponentType",
    "DeviceError",
    "DexClass",
    "DexField",
    "DexMethod",
    "DexView",
    "FridaError",
    "GradleProjectBuilder",
    "GradleProjectReport",
    "JadxCleanup",
    "ManifestView",
    "Permission",
    "Project",
    "ProjectClosed",
    "ProjectError",
    "ProjectNotFound",
    "ProjectStore",
    "SignatureInfo",
    "SignerInfo",
    "ToolError",
    "ToolFailed",
    "ToolNotFound",
    "ToolTimeout",
    "Xref",
    "__version__",
    "cleanup_workdir",
    "create_gradle_project",
    "derive_project_id",
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

__version_info__ = tuple(int(x) for x in __version__.split(".") if x.isdigit())
