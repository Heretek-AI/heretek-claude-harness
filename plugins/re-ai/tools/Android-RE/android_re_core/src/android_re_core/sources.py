"""jadx-backed Java decompilation.

Wraps the jadx CLI as a subprocess. Used for high-quality
class/method-level decompilation when androguard's output is not
readable enough.

Typical usage::

    sources = SourcesView.decompile(apk_path, workdir=tmp_path / "out")
    java_text = sources.decompile_class("Lcom/example/Foo;")

.. note::

    The vendored jadx (``vendor/jadx/0.1.0/lib/jadx-1.5.0-all.jar``) does
    **not** support Kotlin-source output: its ``--output-format`` flag
    only accepts ``java`` or ``json``, and it rejects the
    ``--use-kotlin-source`` flag with "Unknown option". To decompile
    a Kotlin-heavy APK, use ``output_format="java"`` (the default).
    jadx emits ``.java`` files with ``@kotlin.Metadata`` annotations
    on every Kotlin class, so the Kotlin Gradle plugin can compile
    them as if they were written in Java — the dex bytecode is
    indistinguishable from a real Kotlin build at the file-shape level.
    See ``skills/android-re-decompile/references/jadx-tips.md`` for the
    full rationale and the recommended Gradle configuration.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from .errors import APKInvalid, ToolFailed, ToolNotFound, ToolTimeout
from .paths import find_jadx

__all__ = [
    "DEFAULT_JADX_FLAGS",
    "DEFAULT_TIMEOUT_S",
    "MAX_READ_SOURCE_BYTES",
    "MethodSlice",
    "OutputFormat",
    "SourcesView",
]


#: Default subprocess timeout (10 minutes). jadx can be slow on large APKs.
DEFAULT_TIMEOUT_S: int = 600

#: Default jadx flags. Override with the ``JADX_FLAGS`` env var; kwargs to
#: :meth:`SourcesView.decompile` are appended and win on conflict.
DEFAULT_JADX_FLAGS: list[str] = [
    "--no-res",
    "--show-bad-code",
    "--no-imports",
]

#: Maximum file size :meth:`SourcesView.read_source` will load into memory.
#: Generates guards against the MCP tool being used to fetch multi-GB blobs.
MAX_READ_SOURCE_BYTES: int = 10 * 1024 * 1024  # 10 MB


class OutputFormat(str, Enum):  # noqa: UP042 — str+Enum retained for pre-3.11 compat
    """Output language for jadx decompilation.

    Only ``"java"`` is supported by the vendored jadx 1.5.0 — see the
    module docstring for the rationale. The enum value is preserved for
    API stability but accepts only ``"java"``; passing anything else
    raises ``ValueError`` from :class:`Enum.__init__`.
    """

    JAVA = "java"


@dataclass
class MethodSlice:
    """A sliced span of a decompiled class containing one method.

    Returned by :meth:`SourcesView.decompile_method`. ``start_line`` and
    ``end_line`` are 1-indexed and inclusive.
    """

    fqcn: str
    method_name: str
    descriptor: str
    source: str
    start_line: int
    end_line: int
    full_class_source: str  # for callers that want context around the slice


@dataclass
class SourcesView:
    """A jadx-decompiled source tree on disk.

    Construct with :meth:`decompile` (classmethod). The view is bound
    to the decompiled output directory.
    """

    apk_path: Path
    workdir: Path
    sources_dir: Path
    resources_dir: Path | None
    manifest_path: Path | None
    deobfuscate: bool = False
    output_format: OutputFormat = OutputFormat.JAVA
    threads: int | None = None
    jadx_duration_s: float = 0.0
    _java_files_cache: list[Path] | None = field(default=None, init=False, repr=False)

    @classmethod
    def decompile(
        cls,
        apk_path: str | Path,
        *,
        workdir: str | Path | None = None,
        force: bool = False,
        deobfuscate: bool = False,
        threads: int | None = None,
        output_format: Literal["java"] | OutputFormat = "java",
        no_res: bool = False,
        extra_flags: list[str] | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> SourcesView:
        """Run ``jadx -d <workdir>`` and return a :class:`SourcesView`.

        Args:
            apk_path: The APK file to decompile.
            workdir: Where to put the decompiled output. Defaults to a
                fresh :class:`tempfile.TemporaryDirectory`.
            force: Re-run jadx even if ``<workdir>/sources/`` already
                contains ``.java`` files. Use after changing
                ``deobfuscate`` / ``output_format`` on the same workdir.
            deobfuscate: Pass ``--deobf`` to jadx (R8/ProGuard name
                recovery).
            threads: Optional jadx thread count (``--threads-count``).
            output_format: ``"java"`` (only option supported by
                vendored jadx 1.5.0; see module docstring). When ``"java"``,
                jadx emits ``.java`` files with ``@kotlin.Metadata``
                annotations on Kotlin classes — these compile via the
                Kotlin Gradle plugin as if written in Java.
            no_res: If true, do not decode resources.
            extra_flags: Additional jadx flags to pass.
            timeout_s: Subprocess timeout in seconds.

        Flag precedence: the ``JADX_FLAGS`` env var (space-separated)
        is used as the base if set, otherwise :data:`DEFAULT_JADX_FLAGS`.
        ``no_res`` / ``deobfuscate`` / ``threads`` / ``output_format``
        / ``extra_flags`` are appended after. Because jadx's CLI parser
        is "last wins", kwargs override equivalent env-var flags.
        """
        apk = Path(apk_path).expanduser().resolve()
        if not apk.exists():
            raise APKInvalid(
                f"APK not found: {apk}",
                details={"apk_path": str(apk)},
            )
        output_format = OutputFormat(output_format)

        if workdir is None:
            workdir = Path(tempfile.mkdtemp(prefix="jadx-"))
        else:
            workdir = Path(workdir).expanduser().resolve()

        # Cache check: skip the jadx subprocess if the workdir already
        # has a populated sources/ tree and force is False.
        sources_dir = workdir / "sources"
        if not force and _is_valid_cache(sources_dir):
            # Reuse existing decode.
            jadx_duration_s = 0.0
        else:
            if workdir.exists():
                # Wipe partial / stale output before re-running.
                shutil.rmtree(workdir)
            workdir.mkdir(parents=True, exist_ok=True)

            jadx_bin = find_jadx()
            base_flags_str = os.environ.get("JADX_FLAGS", "").strip()
            flags: list[str] = (
                base_flags_str.split() if base_flags_str else list(DEFAULT_JADX_FLAGS)
            )
            if no_res and "--no-res" not in flags:
                flags.append("--no-res")
            if deobfuscate and "--deobf" not in flags:
                flags.append("--deobf")
            if threads is not None:
                flags.extend(["--threads-count", str(int(threads))])
            # Note: jadx 1.5.0 does not support --use-kotlin-source.
            # Kotlin classes are decompiled as .java with @kotlin.Metadata
            # annotations. See module docstring.
            if extra_flags:
                flags.extend(extra_flags)

            cmd: list[str] = [str(jadx_bin), *flags, "-d", str(workdir), str(apk)]
            started = time.monotonic()
            cls._run(cmd, timeout_s=timeout_s)
            jadx_duration_s = time.monotonic() - started

            if not sources_dir.exists():
                # jadx 1.5.x default layout puts Java in <workdir>/sources/.
                # Older versions put it directly in <workdir>/. Handle both.
                if any(workdir.glob("**/*.java")) or any(workdir.glob("**/*.kt")):
                    sources_dir = workdir
                else:
                    raise ToolFailed(
                        "jadx produced no sources directory",
                        details={"workdir": str(workdir), "cmd": cmd},
                    )

        resources_dir = workdir / "resources"
        manifest = workdir / "resources" / "AndroidManifest.xml"
        if not manifest.exists():
            manifest = workdir / "AndroidManifest.xml"
        return cls(
            apk_path=apk,
            workdir=workdir,
            sources_dir=sources_dir,
            resources_dir=resources_dir if resources_dir.exists() else None,
            manifest_path=manifest if manifest.exists() else None,
            deobfuscate=deobfuscate,
            output_format=output_format,
            threads=threads,
            jadx_duration_s=jadx_duration_s,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_java(self, fqcn: str) -> Path | None:
        """Locate the .java (or .kt) file for a fully-qualified class name.

        ``fqcn`` is the JNI-style name, e.g. ``Lcom/example/Foo;``.
        Returns None if the class is not present.
        """
        if not fqcn.startswith("L") or not fqcn.endswith(";"):
            return None
        rel = fqcn[1:-1]
        for ext in (".java", ".kt"):
            candidate = self.sources_dir / (rel + ext)
            if candidate.exists():
                return candidate
        return None

    def decompile_class(self, fqcn: str) -> str | None:
        """Return the decompiled Java/Kotlin source for a class, or None."""
        p = self.find_java(fqcn)
        if p is None:
            return None
        return p.read_text(encoding="utf-8", errors="replace")

    def decompile_method(
        self,
        fqcn: str,
        method_name: str,
        descriptor: str,
    ) -> MethodSlice | None:
        """Return a :class:`MethodSlice` for one method, or None.

        The slice is computed by anchoring on the method's signature
        line (matched by name + descriptor) and walking forward with a
        token-aware brace counter. Brace pairs inside string/char
        literals, line/block comments, and Java text blocks are not
        counted. The slice spans from the signature line to the
        matching closing ``}`` (inclusive).

        Returns ``None`` when the class is absent or the method
        signature cannot be located in the decompiled output.
        """
        full = self.decompile_class(fqcn)
        if full is None:
            return None

        sig_idx = _find_method_signature(full, method_name, descriptor)
        if sig_idx is None:
            return None

        end_idx, end_line = _find_method_end(full, sig_idx)
        start_line = full.count("\n", 0, sig_idx) + 1
        # ``end_idx`` is the index of the closing ``}``; ``end_line``
        # is computed from there. Inclusive of the closing brace.
        return MethodSlice(
            fqcn=fqcn,
            method_name=method_name,
            descriptor=descriptor,
            source=full[sig_idx : end_idx + 1],
            start_line=start_line,
            end_line=end_line,
            full_class_source=full,
        )

    def read_source(self, rel_path: str) -> tuple[str, int, int] | None:
        """Read a file from the decompiled sources/ tree.

        ``rel_path`` is interpreted relative to ``self.sources_dir``.
        Path traversal is blocked: ``..`` segments and symlinks that
        escape the sources dir are rejected. Files larger than
        :data:`MAX_READ_SOURCE_BYTES` are also rejected to bound
        memory.

        Returns ``(content, line_count, byte_size)`` on success, or
        ``None`` if the path is missing / unsafe / oversized.
        """
        if not rel_path:
            return None
        candidate = (self.sources_dir / rel_path).resolve()
        sources_root = self.sources_dir.resolve()
        try:
            candidate.relative_to(sources_root)
        except ValueError:
            return None
        if not candidate.is_file():
            return None
        try:
            size = candidate.stat().st_size
        except OSError:
            return None
        if size > MAX_READ_SOURCE_BYTES:
            return None
        try:
            content = candidate.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        return content, content.count("\n") + (0 if content.endswith("\n") else 1), size

    def list_java_files(self) -> list[Path]:
        """List every ``.java`` and ``.kt`` file in the decompiled tree."""
        if self._java_files_cache is None:
            found: list[Path] = []
            found.extend(self.sources_dir.rglob("*.java"))
            found.extend(self.sources_dir.rglob("*.kt"))
            self._java_files_cache = sorted(set(found))
        return list(self._java_files_cache)

    def class_count(self) -> int:
        return len(self.list_java_files())

    def summary(self, *, limit: int = 500, offset: int = 0) -> dict:
        """Enumerate the decompiled tree with bounded response size.

        Returns a dict with ``workdir``, ``class_count``, ``files``
        (a list of ``{path, line_count, byte_size}`` dicts, sliced by
        ``offset``/``limit``), ``total_files``, ``deobfuscated``,
        ``output_format``, and ``jadx_duration_s``.
        """
        all_files = self.list_java_files()
        sliced = all_files[offset : offset + limit]
        files: list[dict] = []
        for p in sliced:
            try:
                stat = p.stat()
            except OSError:
                continue
            try:
                rel = str(p.relative_to(self.sources_dir))
            except ValueError:
                rel = str(p)
            line_count = stat.st_size  # placeholder; refined below if small
            if stat.st_size <= 1 * 1024 * 1024:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
                except OSError:
                    pass
            files.append(
                {
                    "path": rel,
                    "line_count": line_count,
                    "byte_size": stat.st_size,
                }
            )
        return {
            "workdir": str(self.workdir),
            "class_count": len(all_files),
            "files": files,
            "total_files": len(all_files),
            "deobfuscated": self.deobfuscate,
            "output_format": self.output_format.value,
            "threads": self.threads,
            "jadx_duration_s": self.jadx_duration_s,
            "truncated": offset + limit < len(all_files),
        }

    @staticmethod
    def _run(cmd: list[str], *, timeout_s: int) -> None:
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
                f"jadx timed out after {timeout_s}s",
                details={"cmd": cmd, "timeout_s": timeout_s},
            ) from e
        except FileNotFoundError as e:
            raise ToolNotFound(
                "jadx binary not found",
                details={"cmd": cmd, "error": str(e)},
            ) from e
        if proc.returncode != 0:
            raise ToolFailed(
                f"jadx failed (exit {proc.returncode})",
                details={
                    "cmd": cmd,
                    "stdout": proc.stdout[-2000:],
                    "stderr": proc.stderr[-2000:],
                },
            )


# Convenience wrapper used by the static MCP server.
def decompile_to_workdir(
    apk_path: str | Path,
    *,
    workdir: str | Path | None = None,
) -> SourcesView:
    """Convenience wrapper: return a :class:`SourcesView` for an APK path.

    Kept for one release as a thin alias for
    :meth:`SourcesView.decompile`. Will be removed in a follow-up.
    """
    return SourcesView.decompile(apk_path, workdir=workdir)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_valid_cache(sources_dir: Path) -> bool:
    """A cache is valid if ``sources_dir`` exists and contains at least one
    ``.java`` or ``.kt`` file. Guards against partial / empty runs being
    treated as hits.
    """
    if not sources_dir.is_dir():
        return False
    try:
        next(sources_dir.rglob("*.java"))
        return True
    except StopIteration:
        pass
    try:
        next(sources_dir.rglob("*.kt"))
        return True
    except StopIteration:
        return False


#: Tokens that mark the boundary of a method signature we're willing to
#: anchor on. The signature must be at the start of a line (allowing
#: leading whitespace and standard modifiers).
_METHOD_MODIFIERS = (
    r"(?:public|private|protected|static|final|abstract|synchronized|"
    r"native|default|transient|volatile|strictfp|sealed|non-sealed)"
)


def _method_signature_pattern(method_name: str, descriptor: str) -> re.Pattern[str]:
    """Build a regex that finds a Java method declaration matching both
    the method name and the descriptor.

    The descriptor is mapped to a Java return-type token. For example,
    ``()V`` → return type ``void``; ``(I)Z`` → returns ``boolean``.
    The argument types are ignored at the regex level because jadx may
    reformat them; we only need a unique anchor to disambiguate
    overloads, and the method name is the most reliable anchor.
    """
    return_type = _descriptor_to_return_type(descriptor)
    if return_type is None:
        # Fall back to name-only if the descriptor is unrecognised.
        return re.compile(
            r"(?m)^[ \t]*(?:" + _METHOD_MODIFIERS + r"[ \t]+)*"
            r"[A-Za-z_][A-Za-z0-9_<>,\s\[\]?&\.]*[ \t]+"
            + re.escape(method_name)
            + r"[ \t]*\([^)]*\)[ \t]*(?:throws[^{]+)?\{"
        )
    return re.compile(
        r"(?m)^[ \t]*(?:"
        + _METHOD_MODIFIERS
        + r"[ \t]+)*"
        + re.escape(return_type)
        + r"[ \t]+"
        + re.escape(method_name)
        + r"[ \t]*\([^)]*\)[ \t]*(?:throws[^{]+)?\{"
    )


def _descriptor_to_return_type(descriptor: str) -> str | None:
    """Map a JVM return-type descriptor to its Java source spelling.

    Handles the common cases (primitives, ``void``, class refs,
    arrays). Returns ``None`` for unrecognised descriptors.
    """
    if not descriptor or descriptor[0] not in "()":
        return None
    ret = descriptor.rsplit(")", 1)[-1] if ")" in descriptor else descriptor
    if ret == "V":
        return "void"
    primitive_map = {
        "Z": "boolean",
        "B": "byte",
        "C": "char",
        "S": "short",
        "I": "int",
        "J": "long",
        "F": "float",
        "D": "double",
    }
    if ret in primitive_map:
        return primitive_map[ret]
    if ret.startswith("["):
        # Arrays: jadx renders as ``Type[]``. Skip the regex match for
        # multi-dim arrays; caller will fall back to the name-only regex.
        if ret.count("[") > 1:
            return None
        inner = _descriptor_to_return_type("()" + ret[1:])  # reuse recursion
        if inner is None:
            return None
        return inner + "[]"
    if ret.startswith("L") and ret.endswith(";"):
        # Class reference: ``Lcom/example/Foo;`` → ``Foo``
        return ret[1:-1].rsplit("/", 1)[-1]
    return None


def _find_method_signature(text: str, method_name: str, descriptor: str) -> int | None:
    """Return the character offset of the start of the method's signature
    line, or None if no match.
    """
    pat = _method_signature_pattern(method_name, descriptor)
    m = pat.search(text)
    if m is None:
        # Fall back to a name-only search so we don't return None for
        # the trickier descriptors (generics, multi-dim arrays).
        fallback = re.compile(
            r"(?m)^[ \t]*(?:" + _METHOD_MODIFIERS + r"[ \t]+)*"
            r"[A-Za-z_][A-Za-z0-9_<>,\s\[\]?&\.]*[ \t]+"
            + re.escape(method_name)
            + r"[ \t]*\([^)]*\)[ \t]*(?:throws[^{]+)?\{"
        )
        m = fallback.search(text)
    if m is None:
        return None
    return m.start()


# Token context for the brace walker. Code is the default; the other
# states skip over their content without counting braces.
class _Ctx:
    CODE = "code"
    LINE_COMMENT = "line_comment"
    BLOCK_COMMENT = "block_comment"
    STRING = "string"
    CHAR = "char"
    TEXT_BLOCK = "text_block"


def _find_method_end(text: str, start: int) -> tuple[int, int]:
    """Walk forward from ``start`` and return ``(index, line)`` of the
    closing ``}`` of the method, counting braces only in the CODE
    context. Skips string/char literals, line/block comments, and
    Java text blocks.
    """
    depth = 0
    seen_open = False
    i = start
    n = len(text)
    ctx = _Ctx.CODE
    line = text.count("\n", 0, start) + 1
    while i < n:
        c = text[i]
        nl = c == "\n"
        if nl:
            line += 1

        if ctx == _Ctx.CODE:
            if c == "/" and i + 1 < n and text[i + 1] == "/":
                ctx = _Ctx.LINE_COMMENT
                i += 2
                continue
            if c == "/" and i + 1 < n and text[i + 1] == "*":
                ctx = _Ctx.BLOCK_COMMENT
                i += 2
                continue
            if c == '"' and i + 2 < n and text[i + 1] == '"' and text[i + 2] == '"':
                ctx = _Ctx.TEXT_BLOCK
                i += 3
                continue
            if c == '"':
                ctx = _Ctx.STRING
                i += 1
                continue
            if c == "'":
                ctx = _Ctx.CHAR
                i += 1
                continue
            if c == "{":
                depth += 1
                seen_open = True
            elif c == "}":
                depth -= 1
                if seen_open and depth == 0:
                    return i, line
            i += 1
            continue

        if ctx == _Ctx.LINE_COMMENT:
            if c == "\n":
                ctx = _Ctx.CODE
            i += 1
            continue

        if ctx == _Ctx.BLOCK_COMMENT:
            if c == "*" and i + 1 < n and text[i + 1] == "/":
                ctx = _Ctx.CODE
                i += 2
                continue
            i += 1
            continue

        if ctx == _Ctx.STRING:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                ctx = _Ctx.CODE
            i += 1
            continue

        if ctx == _Ctx.CHAR:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == "'":
                ctx = _Ctx.CODE
            i += 1
            continue

        if ctx == _Ctx.TEXT_BLOCK:
            # Java text blocks: triple-quoted strings that can span
            # multiple lines and end with """. Embedded """ is escaped
            # as \"\"".
            if c == "\\" and i + 1 < n and text[i + 1] == '"':
                i += 2
                continue
            if c == '"' and i + 2 < n and text[i + 1] == '"' and text[i + 2] == '"':
                ctx = _Ctx.CODE
                i += 3
                continue
            i += 1
            continue

    # Reached EOF without finding the matching brace. Return the last
    # seen position so the caller still gets *something* (it'll be
    # the whole rest of the file).
    return n - 1, line
