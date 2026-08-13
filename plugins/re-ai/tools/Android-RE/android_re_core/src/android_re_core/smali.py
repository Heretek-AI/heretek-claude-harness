"""apktool-backed smali decode / build pipeline.

Apktool is the de-facto tool for round-tripping an APK to/from smali +
decoded resources. This module wraps its CLI as a subprocess and
exposes a typed, Pythonic interface.

Typical usage::

    smali = SmaliView.decode(apk_path, workdir=tmp_path / "decode")
    smali_classes = smali.list_classes()
    smali.rebuild(output_path=tmp_path / "out.apk")

The wrapper does not ship apktool; it is expected to be available via
:meth:`android_re_core.paths.find_apktool` (which honours
``APKTOOL_JAR``, ``$PATH``, and the vendored copy in ``./vendor/``).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import APKInvalid, ToolError, ToolFailed, ToolNotFound, ToolTimeout
from .paths import find_apktool

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "SmaliView",
]


#: Default subprocess timeout (5 minutes). Override per-call.
DEFAULT_TIMEOUT_S: int = 300


@dataclass
class SmaliView:
    """A decoded apktool project on disk.

    Construct with :meth:`decode` (classmethod). The view is bound to
    the decoded project directory and exposes typed operations on it.
    """

    apk_path: Path
    workdir: Path
    manifest_path: Path
    smali_dirs: list[Path]
    apktool_yml: Path | None

    # ------------------------------------------------------------------
    # Decode
    # ------------------------------------------------------------------

    @classmethod
    def decode(
        cls,
        apk_path: str | Path,
        *,
        workdir: str | Path | None = None,
        force: bool = False,
        no_src: bool = False,
        no_res: bool = False,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> SmaliView:
        """Run ``apktool d`` and return a :class:`SmaliView`.

        Args:
            apk_path: The APK file to decode.
            workdir: Where to put the decoded project. Defaults to a
                fresh :class:`tempfile.TemporaryDirectory`.
            force: Pass ``-f`` to apktool to overwrite an existing dir.
            no_src: Skip disassembling DEX (faster, no smali output).
            no_res: Skip decoding resources.
            timeout_s: Subprocess timeout in seconds.
        """
        apk = Path(apk_path).expanduser().resolve()
        if not apk.exists():
            raise APKInvalid(
                f"APK not found: {apk}",
                details={"apk_path": str(apk)},
            )
        # Pick a workdir
        if workdir is None:
            workdir = Path(tempfile.mkdtemp(prefix="apktool-"))
        else:
            workdir = Path(workdir).expanduser().resolve()
            if workdir.exists():
                if not force:
                    raise ToolFailed(
                        f"Workdir already exists: {workdir}",
                        details={"workdir": str(workdir)},
                    )
                shutil.rmtree(workdir)
            workdir.mkdir(parents=True, exist_ok=True)

        # Build the apktool command. apktool is a Java jar.
        jar = _resolve_apktool_jar()
        java = _resolve_java_exe()
        cmd: list[str] = [str(java), "-jar", str(jar), "d", "-o", str(workdir), "-f"]
        if no_src:
            cmd.append("-s")
        if no_res:
            cmd.append("-r")
        cmd.append(str(apk))

        cls._run(cmd, timeout_s=timeout_s)

        # Validate the decode output
        manifest = workdir / "AndroidManifest.xml"
        if not manifest.exists():
            raise ToolFailed(
                "apktool decode succeeded but AndroidManifest.xml is missing",
                details={"workdir": str(workdir), "manifest": str(manifest)},
            )
        smali_dirs = sorted(p for p in workdir.glob("smali*") if p.is_dir())
        yml = workdir / "apktool.yml"

        return cls(
            apk_path=apk,
            workdir=workdir,
            manifest_path=manifest,
            smali_dirs=smali_dirs,
            apktool_yml=yml if yml.exists() else None,
        )

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def rebuild(
        self,
        *,
        output_path: str | Path | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> Path:
        """Run ``apktool b`` and return the path to the rebuilt APK.

        The output APK is unsigned. Sign it with uber-apk-signer or
        apksigner before installing.
        """
        if output_path is None:
            output_path = self.workdir / "dist" / "rebuilt.apk"
        output_path = Path(output_path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        jar = _resolve_apktool_jar()
        java = _resolve_java_exe()
        cmd: list[str] = [
            str(java),
            "-jar",
            str(jar),
            "b",
            str(self.workdir),
            "-o",
            str(output_path),
        ]
        self._run(cmd, timeout_s=timeout_s)
        if not output_path.exists():
            raise ToolFailed(
                "apktool build reported success but the output APK is missing",
                details={"output": str(output_path)},
            )
        return output_path

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_classes(self) -> list[Path]:
        """List every smali file across all smali*/ directories."""
        out: list[Path] = []
        for d in self.smali_dirs:
            out.extend(sorted(d.rglob("*.smali")))
        return out

    def class_count(self) -> int:
        return len(self.list_classes())

    def get_smali(self, fqcn: str) -> str | None:
        """Return the smali text for a fully-qualified class name.

        ``fqcn`` is the JNI-style name, e.g. ``Lcom/example/Foo;``.
        Returns None if the class is not present.
        """
        # fqcn like Lcom/example/Foo; -> com/example/Foo.smali
        if not fqcn.startswith("L") or not fqcn.endswith(";"):
            return None
        rel = fqcn[1:-1] + ".smali"
        for d in self.smali_dirs:
            candidate = d / rel
            if candidate.exists():
                return candidate.read_text(encoding="utf-8", errors="replace")
        return None

    def read_manifest(self) -> str:
        """Return the decoded AndroidManifest.xml as text."""
        return self.manifest_path.read_text(encoding="utf-8", errors="replace")

    def patch_manifest(self, diff: dict[str, Any], *, dry_run: bool = True) -> str:
        """Apply a structured patch to the manifest.

        Phase 2 ships a minimal implementation that supports the
        ``application`` attributes ``debuggable``, ``allowBackup``,
        ``usesCleartextTraffic`` and ``networkSecurityConfig``. Full
        support lands in Phase 3.
        """
        text = self.read_manifest()
        if not dry_run:
            # Phase 2: don't actually write; refuse if not dry-run.
            raise ToolError(
                "patch_manifest with dry_run=false is a Phase 3 feature. "
                "Use the diff returned by dry_run to apply manually.",
            )
        return text  # Phase 2: return current; Phase 3 will implement diff

    # ------------------------------------------------------------------
    # Subprocess
    # ------------------------------------------------------------------

    @staticmethod
    def _run(cmd: list[str], *, timeout_s: int) -> None:
        """Run an apktool subprocess with a timeout and structured errors."""
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise ToolTimeout(
                f"apktool timed out after {timeout_s}s",
                details={"cmd": cmd, "timeout_s": timeout_s},
            ) from e
        except FileNotFoundError as e:
            raise ToolNotFound(
                "Java or apktool jar not found",
                details={"cmd": cmd, "error": str(e)},
            ) from e
        if proc.returncode != 0:
            raise ToolFailed(
                f"apktool failed (exit {proc.returncode})",
                details={
                    "cmd": cmd,
                    "stdout": proc.stdout[-2000:],
                    "stderr": proc.stderr[-2000:],
                },
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_apktool_jar() -> Path:
    """Locate the apktool jar (env, vendor, PATH)."""
    if env := os.environ.get("APKTOOL_JAR"):
        p = Path(env).expanduser()
        if p.exists():
            return p
    p = find_apktool()
    return p


def _resolve_java_exe() -> str:
    """Locate the java executable (env, PATH)."""
    if env := os.environ.get("JAVA_HOME"):
        candidate = Path(env) / "bin" / "java"
        if candidate.exists():
            return str(candidate)
    if env := os.environ.get("JAVA"):
        if Path(env).exists():
            return str(Path(env).expanduser())
    which = shutil.which("java")
    if which:
        return which
    raise ToolNotFound(
        "java",
        details={"hint": "Install Java 17+ or set JAVA_HOME."},
    )
