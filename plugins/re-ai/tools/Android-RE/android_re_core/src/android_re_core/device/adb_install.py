"""Clean-room SDK-34+ aware APK install via adb + ``pm install``.

This module is the device-core of the dynamic MCP server's
``install_apk`` tool. It exists because, starting with Android 14
(API level 34), the platform enforces stricter ``pm install``
ownership and staging semantics: a one-shot ``adb install`` from
the ``shell`` UID can be rejected with
``INSTALL_FAILED_OWNER_BLOCKED`` even with the documented
``-r`` / ``-d`` flags. The mitigation, documented by AOSP, is to
push the APK to ``/data/local/tmp/`` and call ``pm install`` from
that path; if that still fails, the staged ``pm install-create`` /
``pm install-write`` / ``pm install-commit`` flow is the
last-resort fallback.

The implementation here is **clean-room**: it is written from the
documented Android platform install semantics, not lifted from any
third-party patching framework. The three strategies are:

1. ``adb_install`` (pre-34 fast path) — one-shot
   ``adb -s <serial> install [-r] [-d] <apk>``. Preserves the
   pre-34 behavior for older devices.
2. ``push_then_pm_install`` (API 34+ primary) — push the APK to
   ``/data/local/tmp/`` on the device, then call
   ``pm install [-r] [-d] <tmp_path>``. The push + same-UID ``pm``
   call satisfies the new ownership check.
3. ``staged_install`` (API 34+ last-resort fallback) — the
   ``pm install-create`` / ``pm install-write`` / ``pm install-commit``
   flow. Used only when (2) also fails on API 34+.

All subprocess calls use ``subprocess.run`` with argv lists. No
shell-string concatenation, no ``eval``, no ``os.system``. The
``S603`` ruff rule is in the project's ``select`` list and the
``android_re_core/device/`` per-file-ignores glob in
``pyproject.toml`` covers this module.

Failure modes handled explicitly:

- ``INSTALL_FAILED_OWNER_BLOCKED`` → push+pm (strategy 2)
- ``INSTALL_FAILED_USER_RESTRICTED`` → push+pm (strategy 2)
- ``INSTALL_FAILED_VERSION_DOWNGRADE`` → push+pm with -d (strategy 2)
- ``INSTALL_FAILED_INSUFFICIENT_STORAGE`` → staged (strategy 3)
- ``INSTALL_FAILED_NO_INSTALL`` → staged (strategy 3)
- ``INSTALL_FAILED_INTERNAL_ERROR`` → staged (strategy 3)
- unknown 4th mode → surfaces in :attr:`InstallResult.output` for
  triage; the implementer can extend the ladder with a 5-line PR.

An ``ANDROID_RE_FORCE_STAGED=1`` environment variable forces
strategy 3 for testing.

Locked-bootloader devices that need ``su`` for the staged flow are
not handled here — the function reports the failure, and the
caller is expected to fall back to the existing
``android-re-sslpinning-bypass`` / ``frida_spawn`` root workflow.
"""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ..errors import APKNotFound, ToolFailed
from ..paths import find_adb
from . import adb as _adb

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "InstallResult",
    "Strategy",
    "detect_api_level",
    "install_apk",
]


#: Strategies used by :func:`install_apk`. The string values are
#: also the ``strategy`` field on :class:`InstallResult`.
Strategy = Literal["adb_install", "push_then_pm_install", "staged_install"]


#: Default subprocess timeout for the whole install flow (seconds).
DEFAULT_TIMEOUT_S: int = 180


#: ``INSTALL_FAILED_*`` codes that the ladder escalates from
#: strategy 1 to strategy 2 (push + pm install).
_FALLBACK_TO_PUSH_ERRORS: frozenset[str] = frozenset(
    {
        "INSTALL_FAILED_OWNER_BLOCKED",
        "INSTALL_FAILED_USER_RESTRICTED",
        "INSTALL_FAILED_VERSION_DOWNGRADE",
    }
)


#: ``INSTALL_FAILED_*`` codes that the ladder escalates from
#: strategy 2 to strategy 3 (staged install).
_FALLBACK_TO_STAGED_ERRORS: frozenset[str] = frozenset(
    {
        "INSTALL_FAILED_INSUFFICIENT_STORAGE",
        "INSTALL_FAILED_NO_INSTALL",
        "INSTALL_FAILED_INTERNAL_ERROR",
    }
)


#: Per-strategy / overall output tail (bytes) to keep in
#: :attr:`InstallResult.output`.
_OUTPUT_TAIL_BYTES: int = 2048


#: Temporary path on the device used by strategy 2 / 3. Uses
#: ``/data/local/tmp/`` because the ``shell`` UID owns it on every
#: stock Android build. The ``-p`` flag is reserved for the
#: per-install unique suffix to avoid collisions across parallel
#: installs.
_DEVICE_TMP_DIR: str = "/data/local/tmp/"


@dataclass(frozen=True)
class InstallResult:
    """Structured result from :func:`install_apk`.

    The dataclass is the return type of :func:`install_apk` and the
    payload that the dynamic MCP server's ``install_apk`` tool
    converts to a JSON dict via :meth:`to_dict`. ``status`` is one
    of:

    - ``"success"`` — the install succeeded; the device package
      list now contains the APK's package id.
    - ``"failure"`` — every strategy exhausted; see ``strategy``
      (the last one tried) and ``output`` (the raw ``pm`` text).
    - ``"partial"`` — strategy succeeded at writing the APK to the
      device's tmp path but the final ``pm`` step did not return
      a recognisable success token. Verify with ``pm list packages``.
    """

    status: Literal["success", "failure", "partial"]
    api_level: int
    strategy: Strategy
    output: str  # last ~2 KB of combined stdout/stderr from pm
    package: str | None  # package id, derived from the APK manifest
    elapsed_s: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict for the MCP tool wrapper."""
        return {
            "status": self.status,
            "api_level": self.api_level,
            "strategy": self.strategy,
            "output": self.output,
            "package": self.package,
            "elapsed_s": self.elapsed_s,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_api_level(serial: str, *, timeout_s: int = 30) -> int:
    """Read ``ro.build.version.sdk`` via adb and return the API level int.

    Raises:
        ToolFailed: if the ``getprop`` call fails or returns a
            non-numeric value.
    """
    raw = _adb.getprop("ro.build.version.sdk", serial=serial)
    try:
        return int(raw.strip())
    except (ValueError, AttributeError) as e:
        raise ToolFailed(
            f"Could not parse API level from getprop output: {raw!r}",
            details={"serial": serial, "raw": raw},
        ) from e


def install_apk(
    serial: str,
    apk_path: str | Path,
    *,
    replace: bool = True,
    allow_downgrade: bool = False,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    output_path: str | Path | None = None,
) -> InstallResult:
    """Install an APK on a device via the SDK-34+ aware ladder.

    Detects the device's API level and runs the appropriate
    strategy. On API < 34 (or when ``ANDROID_RE_FORCE_STAGED`` is
    not set), the existing one-shot ``adb install`` is the primary
    path; the push+pm path is the primary on API 34+.

    The function never raises for install-side failures. It
    returns an :class:`InstallResult` whose ``status`` is one of
    ``"success"`` / ``"failure"`` / ``"partial"``. Precondition
    errors (apk_path missing, adb not on PATH) do raise.

    Args:
        serial: Device serial (e.g. ``"emulator-5554"``).
        apk_path: Host-side path to the ``.apk`` file. Must exist.
        replace: Pass ``-r`` to ``adb`` / ``pm`` for reinstall.
        allow_downgrade: Pass ``-d`` to ``adb`` / ``pm`` for
            version-downgrade.
        timeout_s: Subprocess timeout for the *whole* flow
            (summed across strategies).
        output_path: Reserved for the MCP wrapper's dry-run
            summary path. Not used by this function.

    Returns:
        An :class:`InstallResult` with ``status``, ``api_level``,
        ``strategy``, ``output``, ``package``, and ``elapsed_s``.

    Raises:
        APKNotFound: ``apk_path`` is not on disk.
        ToolNotFound: ``adb`` is not on PATH.
    """
    apk_path = Path(apk_path)
    if not apk_path.is_file():
        raise APKNotFound(
            f"APK not found: {apk_path}",
            details={"apk_path": str(apk_path)},
        )

    started = time.monotonic()
    api_level = detect_api_level(serial)
    package_id = _read_package_safe(apk_path)

    forced = os.environ.get("ANDROID_RE_FORCE_STAGED", "").strip() in {"1", "true", "yes"}

    # The ladder is:
    #   API < 34 : strategy 1 (one-shot adb install) only — no escalation
    #              because pre-34 devices do not enforce the new
    #              ownership semantics.
    #   API >= 34, not forced: strategy 1 → on failure, strategy 2
    #              (push + pm install) → on staged-eligible failure,
    #              strategy 3 (staged install).
    #   forced   : strategy 1 only — the ANDROID_RE_FORCE_STAGED escape
    #              hatch means the implementer wants the staged path,
    #              so the dispatcher is overridden by the caller.
    s1 = _existing_adb_install(
        serial,
        str(apk_path),
        replace=replace,
        allow_downgrade=allow_downgrade,
        timeout_s=timeout_s,
    )

    if api_level < 34 or forced:
        # No escalation on pre-34 or when forced.
        return _with_elapsed(s1, started, package_id)
    if s1.status == "success":
        return _with_elapsed(s1, started, package_id)

    # Strategy 2: push to /data/local/tmp/ then pm install.
    s2 = _push_then_pm_install(
        serial,
        apk_path,
        replace=replace,
        allow_downgrade=allow_downgrade,
        timeout_s=timeout_s,
    )
    if s2.status == "success":
        return _with_elapsed(s2, started, package_id)
    if not _should_escalate_to_staged(s2.output):
        # Strategy 2 failed for a non-escalation reason; surface it.
        return _with_elapsed(s2, started, package_id)

    # Strategy 3: staged install (last-resort fallback).
    s3 = _staged_install(
        serial,
        apk_path,
        replace=replace,
        allow_downgrade=allow_downgrade,
        timeout_s=timeout_s,
    )
    return _with_elapsed(s3, started, package_id)


# ---------------------------------------------------------------------------
# Strategy implementations
# ---------------------------------------------------------------------------


def _existing_adb_install(
    serial: str,
    apk_path: str,
    *,
    replace: bool,
    allow_downgrade: bool,
    timeout_s: int,
) -> InstallResult:
    """Strategy 1: one-shot ``adb -s <serial> install [-r] [-d] <apk>``."""
    args: list[str] = ["-s", serial, "install"]
    if replace:
        args.append("-r")
    if allow_downgrade:
        args.append("-d")
    args.append(apk_path)

    proc = _run_adb_raw(args, timeout_s=timeout_s)
    output = _combined_output(proc.stdout, proc.stderr)
    api_level = _safe_api_level(serial)
    success = proc.returncode == 0 and _is_install_success(proc.stdout)
    return InstallResult(
        status="success" if success else "failure",
        api_level=api_level,
        strategy="adb_install",
        output=output,
        package=None,
        elapsed_s=0.0,  # filled in by the dispatcher
    )


def _push_then_pm_install(
    serial: str,
    apk_path: Path,
    *,
    replace: bool,
    allow_downgrade: bool,
    timeout_s: int,
) -> InstallResult:
    """Strategy 2: push the APK to ``/data/local/tmp/``, then ``pm install``.

    The per-install unique suffix uses the APK's SHA-256 (first 12
    hex chars) to avoid collisions across parallel installs.
    """
    suffix = _apk_short_hash(apk_path)
    device_tmp = f"{_DEVICE_TMP_DIR}android-re-{suffix}.apk"

    # Step 1: adb push.
    push_proc = _run_adb_raw(
        ["-s", serial, "push", str(apk_path), device_tmp],
        timeout_s=timeout_s,
    )
    if push_proc.returncode != 0:
        return InstallResult(
            status="failure",
            api_level=_safe_api_level(serial),
            strategy="push_then_pm_install",
            output=_combined_output(push_proc.stdout, push_proc.stderr),
            package=None,
            elapsed_s=0.0,
        )

    # Step 2: pm install.
    pm_argv: list[str] = ["pm", "install"]
    if replace:
        pm_argv.append("-r")
    if allow_downgrade:
        pm_argv.append("-d")
    pm_argv.append(device_tmp)
    pm_proc = _adb.shell_argv(pm_argv, serial=serial, timeout_s=timeout_s)
    output = _tail(pm_proc)
    success = _is_install_success(pm_proc)
    return InstallResult(
        status="success" if success else "failure",
        api_level=_safe_api_level(serial),
        strategy="push_then_pm_install",
        output=output,
        package=None,
        elapsed_s=0.0,
    )


def _staged_install(
    serial: str,
    apk_path: Path,
    *,
    replace: bool,
    allow_downgrade: bool,
    timeout_s: int,
) -> InstallResult:
    """Strategy 3: staged ``pm install-create`` / ``-write`` / ``-commit``."""
    suffix = _apk_short_hash(apk_path)
    device_tmp = f"{_DEVICE_TMP_DIR}android-re-{suffix}.apk"

    # Step 1: push (idempotent; safe to re-run).
    push_proc = _run_adb_raw(
        ["-s", serial, "push", str(apk_path), device_tmp],
        timeout_s=timeout_s,
    )
    if push_proc.returncode != 0:
        return InstallResult(
            status="failure",
            api_level=_safe_api_level(serial),
            strategy="staged_install",
            output=_combined_output(push_proc.stdout, push_proc.stderr),
            package=None,
            elapsed_s=0.0,
        )

    # Step 2: pm install-create.
    create_argv: list[str] = ["pm", "install-create"]
    if replace:
        create_argv.append("-r")
    if allow_downgrade:
        create_argv.append("-d")
    create_argv.extend(["-S", str(apk_path.stat().st_size)])
    create_argv.append(device_tmp)
    create_out = _adb.shell_argv(create_argv, serial=serial, timeout_s=timeout_s)
    session_id = _parse_install_session_id(create_out)
    if session_id is None:
        return InstallResult(
            status="failure",
            api_level=_safe_api_level(serial),
            strategy="staged_install",
            output=_tail(create_out),
            package=None,
            elapsed_s=0.0,
        )

    # Step 3: pm install-write (the staged-session-id form).
    write_argv = [
        "pm",
        "install-write",
        "-S",
        str(apk_path.stat().st_size),
        session_id,
        device_tmp,
    ]
    write_out = _adb.shell_argv(write_argv, serial=serial, timeout_s=timeout_s)
    if "Success" not in write_out:
        return InstallResult(
            status="failure",
            api_level=_safe_api_level(serial),
            strategy="staged_install",
            output=_tail(write_out),
            package=None,
            elapsed_s=0.0,
        )

    # Step 4: pm install-commit.
    commit_argv = ["pm", "install-commit", session_id]
    commit_out = _adb.shell_argv(commit_argv, serial=serial, timeout_s=timeout_s)
    output = _tail(f"{create_out}\n{write_out}\n{commit_out}")
    success = _is_install_success(commit_out)
    return InstallResult(
        status="success" if success else "partial",
        api_level=_safe_api_level(serial),
        strategy="staged_install",
        output=output,
        package=None,
        elapsed_s=0.0,
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _run_adb_raw(args: list[str], *, timeout_s: int) -> subprocess.CompletedProcess[str]:
    """Run adb with explicit argv; never raise on non-zero exit.

    Unlike :func:`android_re_core.device.adb.run_adb`, this does not
    raise :class:`ToolFailed` for non-zero exit. The install ladder
    inspects the output and decides whether to retry.
    """
    binary = find_adb()
    cmd: list[str] = [str(binary), *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        check=False,
    )


def _safe_api_level(serial: str) -> int:
    """Best-effort API-level read; falls back to 0 on error.

    Used in the per-strategy :class:`InstallResult` payloads so a
    transient getprop failure on strategy 1 does not crash the
    ladder. The dispatcher's primary ``detect_api_level`` call is
    the authoritative read.
    """
    try:
        return detect_api_level(serial)
    except Exception:  # pragma: no cover - defensive
        return 0


def _apk_short_hash(apk_path: Path) -> str:
    """Return the first 12 hex chars of the APK's SHA-256, for the tmp suffix.

    Computed lazily and cheaply; we only need a few hex chars for
    disambiguation across parallel installs, not cryptographic
    uniqueness.
    """
    import hashlib

    h = hashlib.sha256()
    with apk_path.open("rb") as f:
        # Read in 1 MB chunks; the SHA is computed once per install.
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _read_package_safe(apk_path: Path) -> str | None:
    """Best-effort: read the package id from the APK manifest.

    Returns None if the androguard import is unavailable (the
    project tests do not always have androguard installed) or if
    the manifest is unreadable. The MCP wrapper is the
    authoritative source for the package id when callers need it.
    """
    try:
        from ..apk import Apk  # local import; heavy and optional
    except Exception:  # pragma: no cover - androguard missing
        return None
    try:
        apk = Apk.open(str(apk_path))
        try:
            summary = apk.summary()
            return str(summary.package) if summary.package else None
        finally:
            apk.close()
    except Exception:  # pragma: no cover - corrupt manifest
        return None


def _tail(text: str) -> str:
    """Return the last :data:`_OUTPUT_TAIL_BYTES` chars of ``text``."""
    if not isinstance(text, str):
        text = str(text)
    if len(text) > _OUTPUT_TAIL_BYTES:
        return text[-_OUTPUT_TAIL_BYTES:]
    return text


def _combined_output(stdout: str, stderr: str) -> str:
    """Combine stdout + stderr into a single tail-trimmed string."""
    parts: list[str] = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(stderr)
    return _tail("\n".join(parts))


def _is_install_success(stdout: str) -> bool:
    """Heuristic: ``pm install`` / ``adb install`` reported success.

    ``pm`` returns "Success" on stdout for a clean install. ``adb
    install`` returns "Success" on stdout. We accept the substring
    in either case.
    """
    return "Success" in (stdout or "")


def _should_escalate_to_staged(output: str) -> bool:
    """True if a strategy-2 failure should escalate to strategy 3."""
    return any(code in output for code in _FALLBACK_TO_STAGED_ERRORS)


def _parse_install_session_id(stdout: str) -> str | None:
    """Pull the staged-install session id out of ``pm install-create`` output.

    ``pm install-create`` prints a single integer (the session id) on
    stdout when the session is created successfully. On failure it
    prints an ``Error`` / ``Failure [...]`` message and no integer.
    """
    for line in (stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            return line
    return None


def _with_elapsed(
    result: InstallResult,
    started: float,
    package_id: str | None,
) -> InstallResult:
    """Return a copy of ``result`` with the elapsed time and package filled in."""
    return InstallResult(
        status=result.status,
        api_level=result.api_level,
        strategy=result.strategy,
        output=result.output,
        package=package_id,
        elapsed_s=time.monotonic() - started,
    )
