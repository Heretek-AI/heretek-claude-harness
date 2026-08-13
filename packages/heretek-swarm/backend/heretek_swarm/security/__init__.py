"""Backward-compat shim for moved security/ package.

Phase 2 Task 3 moved security/ from backend/heretek_swarm/security/
to packages/core/src/heretek_swarm_core/security/. Importing this
package as ``heretek_swarm.security`` continues to work — symbols
and submodules are resolved lazily through ``heretek_swarm_core.security``.

Why fully lazy
--------------
The security shim is reachable mid-import by ``heretek_swarm.consciousness
.fep_active_inference`` (which imports ``ZeroTrustValidator`` from
``heretek_swarm.security.zero_trust``). That mid-import re-entry triggers
a partial load of this module. Touching ``heretek_swarm_core.security``
at module-load time re-enters the cycle through
``heretek_swarm_core.__init__`` → ``runtime.main_loop`` →
``actors.supervisor`` → ``actors.mixins``. Resolving every attribute
through PEP 562 ``__getattr__`` ensures this shim contributes nothing
to module-load execution until a real consumer asks for something.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

__all__ = ["__getattr__", "__dir__"]


# Resolve the canonical security package directory once at module-load
# time. Using ``parents[3]`` walks from
# ``backend/heretek_swarm/security/__init__.py`` -> repo root -> packages/
# core/src/heretek_swarm_core/security/. ``__path__`` makes this shim a
# real package to Python's importer, so ``from heretek_swarm.security
# .immune import ...`` is a normal submodule lookup rather than an
# attribute access.
_CORE_SECURITY_ROOT = (
    Path(__file__).resolve().parents[3] / "packages" / "core" / "src" / "heretek_swarm_core" / "security"
)
__path__ = [str(_CORE_SECURITY_ROOT)]  # type: ignore[misc]


def __getattr__(name: str) -> Any:
    # Submodule lookup: ``heretek_swarm.security.immune``.
    try:
        submodule = importlib.import_module(f"heretek_swarm_core.security.{name}")
    except ModuleNotFoundError:
        submodule = None

    if submodule is not None:
        globals()[name] = submodule
        sys.modules[f"heretek_swarm.security.{name}"] = submodule
        return submodule

    # Top-level re-export (e.g. ``ZeroTrustValidator``).
    try:
        parent = importlib.import_module("heretek_swarm_core.security")
    except ImportError as exc:
        raise AttributeError(f"module 'heretek_swarm.security' has no attribute {name!r}") from exc

    if hasattr(parent, name):
        value = getattr(parent, name)
        globals()[name] = value
        return value

    raise AttributeError(f"module 'heretek_swarm.security' has no attribute {name!r}")


def __dir__() -> list[str]:
    try:
        parent = importlib.import_module("heretek_swarm_core.security")
    except ImportError:
        return sorted(k for k in globals() if not k.startswith("_"))
    names = set(globals().keys()) | set(getattr(parent, "__all__", ()))
    return sorted(n for n in names if not n.startswith("_"))
