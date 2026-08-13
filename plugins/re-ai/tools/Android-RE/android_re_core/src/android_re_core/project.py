"""Project lifecycle and in-memory state management.

A :class:`Project` represents an open APK plus all of the derived views
(:class:`~android_re_core.manifest.ManifestView`,
:class:`~android_re_core.dex.DexView`, :class:`~android_re_core.certs.CertsView`).
The :class:`ProjectStore` is a process-wide registry of projects keyed
by a stable ``project_id`` (derived from the APK's SHA-256).

MCP servers hold a reference to a single :class:`ProjectStore` and call
:meth:`ProjectStore.open` to register a new APK and
:meth:`ProjectStore.get` to look one up by id.

The store is intentionally in-memory and process-local. For long-running
multi-step triage that needs to survive server restarts, use
:mod:`android_re_core.store.sqlite` (Phase 4).
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

from .apk import DEFAULT_MAX_APK_SIZE, Apk, ApkSummary
from .certs import CertsView
from .dex import DexView
from .errors import APKAlreadyOpen, ProjectClosed, ProjectNotFound
from .manifest import ManifestView

__all__ = [
    "DEFAULT_PROJECT_ID_PREFIX",
    "Project",
    "ProjectStore",
]


#: Default prefix for synthetic project_ids (when the user doesn't supply one).
DEFAULT_PROJECT_ID_PREFIX: str = "apk"


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


@dataclass
class Project:
    """A single open APK plus its derived views.

    All views are computed lazily on first access and cached. The
    underlying :class:`Apk` file is held open until :meth:`close`.
    """

    project_id: str
    apk: Apk
    summary: ApkSummary
    _manifest: ManifestView | None = field(default=None, init=False, repr=False)
    _dex: DexView | None = field(default=None, init=False, repr=False)
    _certs: CertsView | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # Lazy views
    # ------------------------------------------------------------------

    @property
    def manifest(self) -> ManifestView:
        """Lazily compute the manifest view."""
        if self._closed:
            raise ProjectClosed(
                f"Project {self.project_id} is closed.",
                details={"project_id": self.project_id},
            )
        if self._manifest is None:
            self._manifest = ManifestView.from_apk(self.apk)
        return self._manifest

    @property
    def dex(self) -> DexView:
        """Lazily compute the DEX view."""
        if self._closed:
            raise ProjectClosed(
                f"Project {self.project_id} is closed.",
                details={"project_id": self.project_id},
            )
        if self._dex is None:
            self._dex = DexView.from_apk(self.apk)
        return self._dex

    @property
    def certs(self) -> CertsView:
        """Lazily compute the certs view."""
        if self._closed:
            raise ProjectClosed(
                f"Project {self.project_id} is closed.",
                details={"project_id": self.project_id},
            )
        if self._certs is None:
            self._certs = CertsView.from_apk(self.apk)
        return self._certs

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release all underlying resources. Idempotent."""
        if self._closed:
            return
        self._closed = True
        self.apk.close()
        # Drop view references so the GC can reclaim them.
        self._manifest = None
        self._dex = None
        self._certs = None

    @property
    def is_closed(self) -> bool:
        return self._closed

    def to_dict(self) -> dict[str, Any]:
        """Serialize a lightweight summary for tool responses."""
        return {
            "project_id": self.project_id,
            "is_closed": self._closed,
            **self.summary.to_dict(),
        }


# ---------------------------------------------------------------------------
# ProjectStore
# ---------------------------------------------------------------------------


def derive_project_id(sha256: str, user_id: str | None) -> str:
    """Derive a stable project_id from the APK's SHA-256.

    A short hash prefix keeps IDs readable in tool output. The user can
    supply a custom id via the MCP tool's ``project_id`` parameter.
    """
    if user_id:
        return user_id
    short = sha256[:12]
    return f"{DEFAULT_PROJECT_ID_PREFIX}-{short}"


class ProjectStore:
    """A process-wide registry of open :class:`Project` instances.

    Thread-safe: all mutations are guarded by an internal lock. The
    store is not designed for cross-process sharing; for that, use
    :mod:`android_re_core.store.sqlite`.

    Usage::

        store = ProjectStore()
        project = store.open("/path/to/app.apk")
        manifest = project.manifest
        store.close(project.project_id)
    """

    def __init__(self) -> None:
        self._projects: dict[str, Project] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Open / close
    # ------------------------------------------------------------------

    def open(
        self,
        apk_path: str,
        *,
        project_id: str | None = None,
        max_size: int | None = None,
    ) -> Project:
        """Open a new APK and register a :class:`Project`.

        Args:
            apk_path: Path to the APK file.
            project_id: Optional explicit id. If omitted, one is derived
                from the APK's SHA-256.
            max_size: Optional override for the per-APK size cap, in bytes.
                Defaults to ``DEFAULT_MAX_APK_SIZE`` (which is itself
                sourced from the ``ANDROID_RE_MAX_APK_SIZE`` env var at
                import time). Pass a larger value to analyze large APKs
                without restarting the host process.

        Raises:
            APKAlreadyOpen: If a project with the same id is already open
                on a different file.
            APKTooLarge: If the APK exceeds the effective size cap.
        """
        effective_max = max_size if max_size is not None else DEFAULT_MAX_APK_SIZE
        with self._lock:
            apk = Apk.open(apk_path, max_size=effective_max)
            new_id = derive_project_id(apk.sha256, project_id)
            existing = self._projects.get(new_id)
            if existing is not None and not existing.is_closed:
                if existing.summary.sha256 == apk.sha256:
                    # Re-opening the same APK returns the existing project.
                    apk.close()
                    return existing
                raise APKAlreadyOpen(
                    f"Project {new_id!r} is already open with a different APK.",
                    details={
                        "project_id": new_id,
                        "existing_sha256": existing.summary.sha256,
                        "new_sha256": apk.sha256,
                    },
                )
            summary = apk.summary()
            project = Project(project_id=new_id, apk=apk, summary=summary)
            self._projects[new_id] = project
            return project

    def close(self, project_id: str) -> None:
        """Close and remove a project. Idempotent."""
        with self._lock:
            project = self._projects.get(project_id)
            if project is None:
                return
            project.close()
            del self._projects[project_id]

    def get(self, project_id: str) -> Project:
        """Return the project with the given id, or raise :class:`ProjectNotFound`."""
        with self._lock:
            project = self._projects.get(project_id)
            if project is None or project.is_closed:
                raise ProjectNotFound(
                    f"Project {project_id!r} is not open.",
                    details={"project_id": project_id},
                )
            return project

    def try_get(self, project_id: str) -> Project | None:
        """Return the project, or ``None`` if not found / closed."""
        try:
            return self.get(project_id)
        except ProjectNotFound:
            return None

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list(self) -> list[Project]:
        """Return all open projects, in insertion order."""
        with self._lock:
            return [p for p in self._projects.values() if not p.is_closed]

    def list_summaries(self) -> list[dict[str, Any]]:
        """Return JSON-serializable summaries of all open projects."""
        return [p.to_dict() for p in self.list()]

    def __iter__(self) -> Iterator[Project]:
        return iter(self.list())

    def __len__(self) -> int:
        with self._lock:
            return sum(1 for p in self._projects.values() if not p.is_closed)

    def __contains__(self, project_id: object) -> bool:
        if not isinstance(project_id, str):
            return False
        return self.try_get(project_id) is not None

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return a diagnostic snapshot of the store."""
        with self._lock:
            open_count = sum(1 for p in self._projects.values() if not p.is_closed)
            total_count = len(self._projects)
            total_size = sum(p.summary.size for p in self._projects.values() if not p.is_closed)
        return {
            "open_projects": open_count,
            "total_projects": total_count,
            "total_size_bytes": total_size,
            "store_sha256": hashlib.sha256(
                "|".join(sorted(self._projects.keys())).encode()
            ).hexdigest()[:16],
        }
