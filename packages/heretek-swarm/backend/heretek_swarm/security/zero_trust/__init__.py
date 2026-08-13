"""Backward-compat shim — zero_trust sub-package.

Phase 2 Task 3 moved ``security/zero_trust/`` to
``packages/core/src/heretek_swarm_core/security/zero_trust/``.
This stub forwards every attribute to the canonical sub-package
so ``from heretek_swarm_core.security.zero_trust import …`` keeps
working without re-running ``heretek_swarm_core.__init__.py``.
"""

from __future__ import annotations

import importlib.util as _importlib_util
import sys as _sys
from pathlib import Path as _Path
from types import ModuleType as _ModuleType
from typing import Any as _Any

_CORE_SECURITY_ROOT = _Path("/home/john/Projects/heretek-swarm/packages/core/src/heretek_swarm_core/security")
_CORE_ROOT = _CORE_SECURITY_ROOT.parent
_ZERO_TRUST_ROOT = _CORE_SECURITY_ROOT / "zero_trust"

if "heretek_swarm_core" not in _sys.modules:
    _stub = _ModuleType("heretek_swarm_core")
    _stub.__path__ = [str(_CORE_ROOT)]
    _sys.modules["heretek_swarm_core"] = _stub
if "heretek_swarm_core.security" not in _sys.modules:
    _stub = _ModuleType("heretek_swarm_core.security")
    _stub.__path__ = [str(_CORE_SECURITY_ROOT)]
    _sys.modules["heretek_swarm_core.security"] = _stub
if "heretek_swarm_core.security.zero_trust" not in _sys.modules:
    _stub = _ModuleType("heretek_swarm_core.security.zero_trust")
    _stub.__path__ = [str(_ZERO_TRUST_ROOT)]
    _sys.modules["heretek_swarm_core.security.zero_trust"] = _stub

# Pre-load every zero_trust/* module so relative imports inside
# __init__.py resolve to fully-populated modules in sys.modules
# (rather than empty stubs).
for _name in (
    "audit_logger",
    "context_validator",
    "exceptions",
    "external_validator",
    "input_validator",
    "orchestrator",
    "output_validator",
    "result_types",
):
    _fqn = f"heretek_swarm_core.security.zero_trust.{_name}"
    if _fqn not in _sys.modules or not hasattr(_sys.modules[_fqn], "__file__"):
        _spec = _importlib_util.spec_from_file_location(_fqn, str(_ZERO_TRUST_ROOT / f"{_name}.py"))
        _mod = _importlib_util.module_from_spec(_spec)
        _sys.modules[_fqn] = _mod
        _spec.loader.exec_module(_mod)


def __getattr__(name: str) -> _Any:
    fqn = f"heretek_swarm_core.security.zero_trust.{name}"
    if fqn in _sys.modules and hasattr(_sys.modules[fqn], name):
        return getattr(_sys.modules[fqn], name)
    spec = _importlib_util.spec_from_file_location(
        "heretek_swarm_core.security.zero_trust",
        str(_ZERO_TRUST_ROOT / "__init__.py"),
    )
    module = _importlib_util.module_from_spec(spec)
    _sys.modules["heretek_swarm_core.security.zero_trust"] = module
    spec.loader.exec_module(module)
    return getattr(module, name)


def __dir__() -> list[str]:
    return [
        "AuditLogConfig",
        "AuditLogger",
        "BehavioralBaseline",
        "ContextValidationConfig",
        "ContextValidator",
        "EXCEPTION_CATEGORIES",
        "EXCEPTION_RULES",
        "ExternalInputValidator",
        "ExternalThreatConfig",
        "InputValidationConfig",
        "InputValidator",
        "LayerResult",
        "OutputValidationConfig",
        "OutputValidator",
        "Severity",
        "ValidatedInput",
        "ZeroTrustResult",
        "ZeroTrustValidator",
        "create_default_validator",
        "create_external_validator",
        "create_strict_validator",
        "get_exception_rule",
        "is_exception_topic",
        "should_sanitize",
    ]


__all__ = __dir__()
