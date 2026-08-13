"""Backward-compatibility shim for ``heretek_swarm.swarm_logging``.

Canonical implementation lives in
``heretek_swarm_core.swarm_logging``. This shim re-exports
the public surface and forwards submodule imports
(``import heretek_swarm.swarm_logging.config``) to the
canonical home during the migration. Remove once all
callers are updated.

Lazy access via ``__getattr__`` avoids eager evaluation of
``heretek_swarm_core`` at package import time.
"""

from __future__ import annotations

from pathlib import Path as _Path

# Forward submodule resolution to the canonical package directory.
_canonical_pkg = (
    _Path(__file__).resolve().parent.parent.parent.parent
    / "packages"
    / "core"
    / "src"
    / "heretek_swarm_core"
    / "swarm_logging"
)
if _canonical_pkg.is_dir():
    __path__ = [str(_canonical_pkg)] + list(__path__)


def __getattr__(name: str):
    import heretek_swarm_core.swarm_logging as _core

    return getattr(_core, name)


def __dir__() -> list[str]:
    import heretek_swarm_core.swarm_logging as _core

    return sorted(set(globals()) | set(dir(_core)))
