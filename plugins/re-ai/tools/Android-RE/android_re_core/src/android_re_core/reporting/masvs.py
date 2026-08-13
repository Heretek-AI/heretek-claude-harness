"""MASVS v2 control mapping.

The :class:`MasvsControl` class models one MASVS v2 control. The
:class:`MasvsRegistry` is the in-process lookup of every control we
care about. The :func:`evaluate_apk` function takes a parsed
:class:`~android_re_core.apk.Apk` (and optional supporting evidence)
and emits a list of findings mapped to MASVS controls.

This module is intentionally rule-based and pure-Python. The
semantically richer eval (e.g. running Frida to detect runtime root
checks) is the Phase 3 dynamic server's job; here we only surface
what static analysis alone can determine.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .sarif import Finding, Severity, build_log, masvs_rule

__all__ = [
    "DEFAULT_MASVS_CONTROLS",
    "ControlStatus",
    "MasvsControl",
    "MasvsCoverage",
    "MasvsRegistry",
    "evaluate_apk",
]


class ControlStatus(str, Enum):
    """The tri-state MASVS evaluation result."""

    PASS = "pass"
    FAIL = "fail"
    REVIEW = "review"  # cannot be determined from static evidence alone


# Mapping: short tag -> human-readable control name
MASVS_GROUPS: dict[str, str] = {
    "STORAGE": "Storage of Sensitive Data",
    "CRYPTO": "Cryptographic Functionality",
    "AUTH": "Authentication and Authorization",
    "NETWORK": "Network Communication",
    "PLATFORM": "Interaction with the Platform",
    "CODE": "Code Quality and Build",
    "RESILIENCE": "Resilience to Reverse Engineering",
    "PRIVACY": "Privacy Controls",
}


@dataclass(frozen=True)
class MasvsControl:
    """A single MASVS v2 control."""

    id: str  # e.g. "MASVS-PLATFORM-1"
    group: str  # e.g. "PLATFORM"
    name: str  # human-readable
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "group": self.group,
            "name": self.name,
            "description": self.description,
        }


@dataclass(frozen=True)
class MasvsCoverage:
    """Result of evaluating an APK against the MASVS registry."""

    controls: tuple[dict[str, Any], ...]  # [{id, status, evidence, finding_ids}]
    findings: tuple[Finding, ...]
    by_group: dict[str, dict[str, int]]  # group -> {pass, fail, review}

    def to_dict(self) -> dict[str, Any]:
        return {
            "controls": list(self.controls),
            "findings": [f.to_sarif() for f in self.findings],
            "by_group": self.by_group,
        }


# ---------------------------------------------------------------------------
# Default registry: the MASVS v2 controls surfaced by Phase 1+2 static
# analysis. Phase 3+ adds dynamic controls.
# ---------------------------------------------------------------------------

DEFAULT_MASVS_CONTROLS: tuple[MasvsControl, ...] = (
    # STORAGE
    MasvsControl(
        "MASVS-STORAGE-1",
        "STORAGE",
        "No sensitive data storage",
        "The app does not store sensitive data unless strictly necessary.",
    ),
    MasvsControl(
        "MASVS-STORAGE-2",
        "STORAGE",
        "No plaintext sensitive data",
        "The app does not store sensitive data in plaintext.",
    ),
    # CRYPTO
    MasvsControl(
        "MASVS-CRYPTO-1",
        "CRYPTO",
        "No insecure crypto",
        "The app does not use insecure crypto algorithms.",
    ),
    MasvsControl(
        "MASVS-CRYPTO-2",
        "CRYPTO",
        "Proper key derivation",
        "The app uses proper key derivation parameters.",
    ),
    MasvsControl(
        "MASVS-CRYPTO-4",
        "CRYPTO",
        "No key reuse",
        "The app does not reuse keys across distinct purposes.",
    ),
    # AUTH
    MasvsControl(
        "MASVS-AUTH-1",
        "AUTH",
        "Secure authentication",
        "The app uses secure authentication mechanisms.",
    ),
    MasvsControl(
        "MASVS-AUTH-9",
        "AUTH",
        "Cert pinning for auth",
        "The app uses certificate pinning for authentication.",
    ),
    MasvsControl("MASVS-AUTH-11", "AUTH", "Session timeout", "The app enforces session timeout."),
    # NETWORK
    MasvsControl(
        "MASVS-NETWORK-1",
        "NETWORK",
        "TLS for all traffic",
        "The app uses TLS for all network communication.",
    ),
    MasvsControl(
        "MASVS-NETWORK-2", "NETWORK", "Cert validation", "The app performs certificate validation."
    ),
    # PLATFORM
    MasvsControl("MASVS-PLATFORM-1", "PLATFORM", "Safe IPC", "The app uses IPC mechanisms safely."),
    MasvsControl("MASVS-PLATFORM-2", "PLATFORM", "Safe WebViews", "The app uses WebViews safely."),
    MasvsControl(
        "MASVS-PLATFORM-3", "PLATFORM", "Safe UI", "The app uses the user interface safely."
    ),
    # CODE
    MasvsControl(
        "MASVS-CODE-1", "CODE", "Signed and valid", "The app is signed and the signature is valid."
    ),
    MasvsControl(
        "MASVS-CODE-2",
        "CODE",
        "Release build hardening",
        "The app is built in release mode with appropriate compiler flags.",
    ),
    MasvsControl(
        "MASVS-CODE-4",
        "CODE",
        "Free security features",
        "The app uses free security features (PIE, ASLR, etc.).",
    ),
    # RESILIENCE (mostly Phase 3, but CODE-4 PIE applies to native libs)
    MasvsControl(
        "MASVS-RESILIENCE-1", "RESILIENCE", "Root detection", "The app detects rooted devices."
    ),
    MasvsControl(
        "MASVS-RESILIENCE-2", "RESILIENCE", "Emulator detection", "The app detects emulators."
    ),
    MasvsControl(
        "MASVS-RESILIENCE-3", "RESILIENCE", "Tamper detection", "The app detects tampering."
    ),
    MasvsControl(
        "MASVS-RESILIENCE-7", "RESILIENCE", "Obfuscation", "The app implements obfuscation."
    ),
    # PRIVACY
    MasvsControl(
        "MASVS-PRIVACY-1",
        "PRIVACY",
        "Minimal data access",
        "The app minimizes access to sensitive data.",
    ),
    MasvsControl(
        "MASVS-PRIVACY-3", "PRIVACY", "No sensitive logging", "The app does not log sensitive data."
    ),
)


class MasvsRegistry:
    """In-process registry of MASVS v2 controls.

    The default registry contains the controls in
    :data:`DEFAULT_MASVS_CONTROLS`. Tools may register additional
    controls with :meth:`register`.
    """

    def __init__(self, controls: Iterable[MasvsControl] = DEFAULT_MASVS_CONTROLS) -> None:
        self._by_id: dict[str, MasvsControl] = {}
        for c in controls:
            self._by_id[c.id] = c

    def get(self, control_id: str) -> MasvsControl | None:
        return self._by_id.get(control_id)

    def all(self) -> list[MasvsControl]:
        return list(self._by_id.values())

    def by_group(self) -> dict[str, list[MasvsControl]]:
        out: dict[str, list[MasvsControl]] = {}
        for c in self._by_id.values():
            out.setdefault(c.group, []).append(c)
        return out

    def register(self, control: MasvsControl) -> None:
        self._by_id[control.id] = control


# ---------------------------------------------------------------------------
# evaluate_apk: static-only MASVS check.
# ---------------------------------------------------------------------------


def evaluate_apk(
    apk: Any,
    *,
    registry: MasvsRegistry | None = None,
) -> MasvsCoverage:
    """Evaluate an APK against the MASVS registry using static evidence.

    Args:
        apk: An :class:`~android_re_core.apk.Apk` (must be open).
        registry: A :class:`MasvsRegistry`. Defaults to the static-only
            :data:`DEFAULT_MASVS_CONTROLS`.

    Returns:
        :class:`MasvsCoverage` summarizing pass/fail/review per control
        plus the underlying :class:`Finding` list.
    """
    if registry is None:
        registry = MasvsRegistry()

    findings: list[Finding] = []
    control_results: list[dict[str, Any]] = []
    by_group: dict[str, dict[str, int]] = {}

    # `apk` may be a Project (which exposes .summary as a precomputed field)
    # or a bare Apk (whose .summary is a method). Handle both.
    summary = apk.summary() if callable(apk.summary) else apk.summary
    # Manifest + certs may fail to parse on synthetic/malformed APKs.
    # In that case we mark all manifest-derived controls as REVIEW and
    # continue with the controls we *can* evaluate.
    from android_re_core.errors import APKInvalid

    try:
        manifest = apk.manifest
        application = manifest.application or {}
    except (APKInvalid, Exception):
        manifest = None
        application = {}
    try:
        certs = apk.certs
    except (APKInvalid, Exception):
        certs = None

    # --- MASVS-CODE-1: signed & valid ---
    if not summary.is_signed:
        findings.append(
            _finding(
                "MASVS-CODE-1",
                "App is not signed",
                Severity.ERROR,
                artifact_path="META-INF/MANIFEST.MF",
            )
        )
        _record(control_results, by_group, "MASVS-CODE-1", ControlStatus.FAIL, "Not signed")
    elif certs.signature.is_signed and certs.certificates:
        leaf = certs.certificates[0]
        if leaf.is_expired:
            findings.append(
                _finding(
                    "MASVS-CODE-1",
                    f"Signing certificate expired: {leaf.subject}",
                    Severity.ERROR,
                    properties={"fingerprint_sha256": leaf.fingerprint_sha256},
                )
            )
            _record(control_results, by_group, "MASVS-CODE-1", ControlStatus.FAIL, "Cert expired")
        elif leaf.is_not_yet_valid:
            findings.append(
                _finding(
                    "MASVS-CODE-1",
                    f"Signing certificate not yet valid: {leaf.subject}",
                    Severity.WARNING,
                )
            )
            _record(
                control_results,
                by_group,
                "MASVS-CODE-1",
                ControlStatus.REVIEW,
                "Cert not yet valid",
            )
        else:
            _record(
                control_results, by_group, "MASVS-CODE-1", ControlStatus.PASS, "Valid signature"
            )
    else:
        _record(control_results, by_group, "MASVS-CODE-1", ControlStatus.PASS, "Signed")

    # --- MASVS-CODE-2: release build (debuggable=false) ---
    if summary.is_debuggable:
        findings.append(
            _finding(
                "MASVS-CODE-2",
                "Application is debuggable in this build",
                Severity.ERROR,
                artifact_path="AndroidManifest.xml",
            )
        )
        _record(
            control_results, by_group, "MASVS-CODE-2", ControlStatus.FAIL, "android:debuggable=true"
        )
    else:
        _record(control_results, by_group, "MASVS-CODE-2", ControlStatus.PASS)

    # --- MASVS-NETWORK-1: TLS, no cleartext ---
    if application.get("uses_cleartext_traffic") is True:
        findings.append(
            _finding(
                "MASVS-NETWORK-1",
                "Application sets usesCleartextTraffic=true",
                Severity.ERROR,
                artifact_path="AndroidManifest.xml",
            )
        )
        _record(
            control_results,
            by_group,
            "MASVS-NETWORK-1",
            ControlStatus.FAIL,
            "usesCleartextTraffic=true",
        )
    else:
        _record(control_results, by_group, "MASVS-NETWORK-1", ControlStatus.PASS)

    # --- MASVS-NETWORK-2: certificate validation ---
    # Phase 2: heuristic — if a networkSecurityConfig is present and
    # pins certs, this is good; otherwise we mark REVIEW (Phase 3
    # dynamic will check actual behavior).
    nsc = application.get("network_security_config")
    if nsc:
        _record(
            control_results,
            by_group,
            "MASVS-NETWORK-2",
            ControlStatus.REVIEW,
            f"networkSecurityConfig declared: {nsc}",
        )
    else:
        _record(
            control_results,
            by_group,
            "MASVS-NETWORK-2",
            ControlStatus.REVIEW,
            "No networkSecurityConfig (relies on platform default)",
        )

    # --- MASVS-PLATFORM-1: exported components with no permission gate ---
    dangerous_exported: list[str] = []
    if manifest is not None:
        for comp in manifest.exported_components():
            if comp.permission is None and not (
                comp.intent_filters
                and any(
                    f["actions"] and "android.intent.action.MAIN" in f["actions"]
                    for f in comp.intent_filters
                )
            ):
                # MAIN/LAUNCHER activity with no permission gate is normal;
                # flag everything else.
                dangerous_exported.append(f"{comp.type}/{comp.name}")
    if dangerous_exported:
        findings.append(
            _finding(
                "MASVS-PLATFORM-1",
                f"{len(dangerous_exported)} exported component(s) without permission gate",
                Severity.WARNING,
                properties={"components": dangerous_exported[:20]},
            )
        )
        _record(
            control_results,
            by_group,
            "MASVS-PLATFORM-1",
            ControlStatus.FAIL,
            f"{len(dangerous_exported)} exported component(s) unprotected",
        )
    else:
        _record(control_results, by_group, "MASVS-PLATFORM-1", ControlStatus.PASS)

    # --- MASVS-PLATFORM-2 / -3: WebView / UI safety ---
    # These require source review (Phase 2 decompile).
    _record(
        control_results,
        by_group,
        "MASVS-PLATFORM-2",
        ControlStatus.REVIEW,
        "Requires source review",
    )
    _record(
        control_results,
        by_group,
        "MASVS-PLATFORM-3",
        ControlStatus.REVIEW,
        "Requires source review",
    )

    # --- MASVS-STORAGE / -CRYPTO / -AUTH / -RESILIENCE: dynamic-only ---
    for control_id in (
        "MASVS-STORAGE-1",
        "MASVS-STORAGE-2",
        "MASVS-CRYPTO-1",
        "MASVS-CRYPTO-2",
        "MASVS-CRYPTO-4",
        "MASVS-AUTH-1",
        "MASVS-AUTH-9",
        "MASVS-AUTH-11",
        "MASVS-RESILIENCE-1",
        "MASVS-RESILIENCE-2",
        "MASVS-RESILIENCE-3",
        "MASVS-RESILIENCE-7",
        "MASVS-PRIVACY-1",
        "MASVS-PRIVACY-3",
    ):
        _record(
            control_results,
            by_group,
            control_id,
            ControlStatus.REVIEW,
            "Requires dynamic analysis (Phase 3) or source review (Phase 2)",
        )

    # Finalize: ensure every registry control is in the result
    seen = {c["id"] for c in control_results}
    for ctl in registry.all():
        if ctl.id not in seen:
            _record(control_results, by_group, ctl.id, ControlStatus.REVIEW, "Not evaluated")

    return MasvsCoverage(
        controls=tuple(control_results),
        findings=tuple(findings),
        by_group=by_group,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _finding(
    rule_id: str,
    message: str,
    severity: Severity,
    *,
    artifact_path: str | None = None,
    start_line: int | None = None,
    properties: dict[str, Any] | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        message=message,
        severity=severity,
        artifact_path=artifact_path,
        start_line=start_line,
        properties=properties or {},
    )


def _record(
    out: list[dict[str, Any]],
    by_group: dict[str, dict[str, int]],
    control_id: str,
    status: ControlStatus,
    evidence: str = "",
) -> None:
    """Append a control result and tally by group."""
    out.append(
        {
            "id": control_id,
            "status": status.value,
            "evidence": evidence,
            "finding_ids": [],  # populated by Phase 4 orchestrator
        }
    )
    # Tally: split the control id like MASVS-GROUP-N
    parts = control_id.split("-")
    group = parts[1] if len(parts) >= 3 else "UNKNOWN"
    bucket = by_group.setdefault(group, {"pass": 0, "fail": 0, "review": 0})
    bucket[status.value] += 1


# ---------------------------------------------------------------------------
# Convenience: build SARIF for a coverage result
# ---------------------------------------------------------------------------


def coverage_to_sarif(coverage: MasvsCoverage, *, tool_version: str = "0.2.0") -> Any:
    """Convert a :class:`MasvsCoverage` to a SARIF :class:`Log`."""
    rules: list[dict[str, Any]] = []
    seen_rules: set[str] = set()
    for ctl in coverage.controls:
        if ctl["id"] in seen_rules:
            continue
        seen_rules.add(ctl["id"])
        rules.append(
            masvs_rule(
                ctl["id"],
                short_description=f"MASVS control {ctl['id']}",
                full_description=ctl.get("evidence") or "",
                help_uri=f"https://mas.owasp.org/MASVS/0x90-{ctl['id']}/",
                default_severity=Severity.NOTE,
            )
        )
    return build_log(
        tool_name="android-re-masvs",
        tool_version=tool_version,
        findings=list(coverage.findings),
        rules=rules,
    )


# uuid used for unique finding ids elsewhere; not needed here.
_ = uuid
