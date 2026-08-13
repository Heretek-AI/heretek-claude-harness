"""Post-decompile cleanup transforms for jadx 1.5.0 output.

When jadx decompiles a Kotlin-heavy APK with ``--deobf``, the resulting
``.java`` files contain a number of well-formed but compiler-rejected
artifacts:

- Partial deobfuscation: e.g. ``p004ui`` (R8 leftover) for ``ui``.
- ``??`` placeholders for variables whose type jadx couldn't infer.
- ``var = /* JADX ERROR */ throw new ...;`` patterns (Java has no
  ``throw`` expression in standard mode).
- ``@kotlin.Metadata(m560d1=..., m562k=...)`` annotations — modern
  Kotlin expects ``d1, d2, k, mv, xi`` (jadx prefixes the modern
  field names with ``m<line>``).
- ``@DebugMetadata(m570c=..., m571f=...)`` — same problem on the
  coroutines debug annotation.
- Static fields of ``commons-lang3`` (``StringUtils.f746CR``,
  ``CharUtils.f749LF``) — jadx adds a ``f<digits>`` prefix to static
  fields it can't immediately resolve.
- ``androidx.autofill.HintConstants.AUTOFILL_HINT_USERNAME`` etc. — the
  class was removed from ``androidx.autofill`` in favour of inline
  string constants.
- ``Kotlin.enums.EnumEntriesKt.enumEntries(values)`` (Kotlin 2.0
  idiom) — older Java only has ``values()``.
- Duplicate getter methods: jadx emits both the original ``getXxx()``
  and the Kotlin ``componentN``-renamed version.
- Cascade errors in some Compose UI lambdas: jadx emits
  ``Method not decompiled`` placeholders that orphan the surrounding
  function-call continuations, producing unparseable structure.

This module provides :class:`JadxCleanup` with a single entry point
:meth:`JadxCleanup.cleanup` that applies the 9 in-place textual
transforms and (optionally, with ``agressivo=True``) the 10th "move
broken files" pass that runs a Gradle compile attempt and quarantines
problem files.

The transforms are idempotent: each is a no-op on already-clean input,
so re-running :meth:`JadxCleanup.cleanup` is safe. The module-level
:meth:`cleanup` function is the canonical entry point for the MCP
``jadx_cleanup_workdir`` tool.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "CleanupReport",
    "JadxCleanup",
    "Transform",
    "cleanup",
]


#: Sentinel file written to a workdir after a successful cleanup. The
#: MCP tool checks for this before re-running to keep the operation
#: idempotent and the run-time bounded.
CLEANUP_MARKER = ".jadx-cleanup-complete"


@dataclass
class Transform:
    """A single jadx-artifact cleanup step.

    Attributes:
        name: Short identifier; one of the 10 in :class:`JadxCleanup`
            (see module docstring). Appears in :class:`CleanupReport`.
        description: One-sentence explanation; surfaced to the user via
            the MCP tool.
        file_count: Number of files the transform modified.
    """

    name: str
    description: str
    file_count: int = 0


@dataclass
class CleanupReport:
    """Summary returned by :meth:`JadxCleanup.cleanup`.

    Attributes:
        transforms: Ordered list of :class:`Transform` records, one
            per transform that was applied (skipping no-op transforms).
        files_modified: Total count of files the cleanup touched
            (across all transforms). The same file may be counted
            multiple times if several transforms modified it.
        files_moved: Number of files moved to ``moved_to``. Only
            non-zero when ``agressivo=True``.
        moved_to: Absolute path of the quarantine directory, if any
            files were moved. ``None`` otherwise.
        errors: List of human-readable error strings; populated only
            if the ``move_broken_files`` pass could not run (e.g. no
            ``gradle`` on ``$PATH``).
    """

    transforms: list[Transform] = field(default_factory=list)
    files_modified: int = 0
    files_moved: int = 0
    moved_to: Path | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialise to a JSON-safe dict (the shape returned by the MCP tool)."""
        return {
            "transforms": [
                {"name": t.name, "description": t.description, "file_count": t.file_count}
                for t in self.transforms
            ],
            "files_modified": self.files_modified,
            "files_moved": self.files_moved,
            "moved_to": str(self.moved_to) if self.moved_to else None,
            "errors": self.errors,
        }


#: (jadx-rename, jadx-actual-name) pairs that the
#: :func:`_rename_apache_commons_static_fields` transform replaces.
#: Tracked as an allowlist so we never rename a public field
#: unintentionally.
_APACHE_COMMONS_RENAMES: dict[str, dict[str, str]] = {
    "org.apache.commons.lang3.CharUtils": {
        "f746CR": "CR",
        "f749LF": "LF",
    },
    "org.apache.commons.lang3.StringUtils": {
        "f746CR": "CR",
        "f749LF": "LF",
        "f748SPACE": "SPACE",
        "f750EMPTY": "EMPTY",
        "f751INDEX_NOT_FOUND": "INDEX_NOT_FOUND",
    },
    "org.apache.commons.lang3.SystemProperties": {
        "f755LINE_SEPARATOR": "LINE_SEPARATOR",
        "f754FILE_SEPARATOR": "FILE_SEPARATOR",
        "f753FILE_ENCODING": "FILE_ENCODING",
        "f752JAVA_CLASS_PATH": "JAVA_CLASS_PATH",
        "f756PATH_SEPARATOR": "PATH_SEPARATOR",
    },
}


def _walk_java(root: Path):
    """Yield every ``.java`` file under ``root`` (recursively).

    Skips ``java-broken/`` directories so we never re-edit a file that
    the ``move_broken_files`` transform already quarantined.
    """
    for path in sorted(root.rglob("*.java")):
        # pathlib rglob on the input workdir already excludes hidden
        # dirs by default; we additionally skip any path that has a
        # ``java-broken`` segment so re-runs are no-ops.
        parts = path.relative_to(root).parts
        if any(p in {"java-broken", "build"} for p in parts):
            continue
        yield path


def _rewrite(path: Path, transform: Transform, mutate) -> bool:
    """Apply ``mutate(content) -> new_content`` to ``path`` if it changes.

    Increments ``transform.file_count`` on every successful rewrite.
    Returns ``True`` if the file was modified.
    """
    original = path.read_text()
    new = mutate(original)
    if new != original:
        path.write_text(new)
        transform.file_count += 1
        return True
    return False


def _t_rename_p004ui(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 1: ``p004ui`` → ``ui``.

    jadx 1.5.0's R8 deobfuscation sometimes leaves a numeric prefix
    on a package name (``p004ui`` for ``ui``). The class file is
    written to ``app/p004ui/...`` and the package declaration reads
    ``package app.anyclaw.p004ui;`` — but other files reference the
    un-prefixed ``app.anyclaw.ui`` namespace.

    We rename:
      - the directory tree ``p004ui`` → ``ui`` (recursive)
      - every ``package app.X.p004ui.Y`` → ``package app.X.ui.Y``
      - every reference to ``app.X.p004ui.Y`` (qualified names in
        source and in ``@kotlin.Metadata`` strings)
    """
    t = Transform("rename_p004ui", "Rename jadx's p00Xui deobf leftovers (e.g. p004ui -> ui)")
    report.transforms.append(t)
    # Step 1: rename directories
    for p004dir in sorted(sources_dir.rglob("p0*ui")):
        if not p004dir.is_dir():
            continue
        # e.g. p004ui -> ui
        new_name = re.sub(r"^p\d+(?=ui$)", "", p004dir.name)
        if new_name == p004dir.name:
            continue
        target = p004dir.with_name(new_name)
        # Avoid clobbering an existing ui/ dir
        if target.exists():
            # Merge: move children into target
            target.mkdir(parents=True, exist_ok=True)
            for child in p004dir.iterdir():
                shutil.move(str(child), str(target / child.name))
            p004dir.rmdir()
        else:
            shutil.move(str(p004dir), str(target))
    # Step 2: rewrite package + qualified-name references in all .java files
    pattern = re.compile(r"\bp0(\d+)ui\b")
    for path in _walk_java(sources_dir):
        _rewrite(
            path,
            t,
            lambda c: pattern.sub("ui", c),
        )


def _t_fix_jadx_qq_types(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 2: replace jadx ``??`` placeholders with a real type.

    jadx 1.5.0 emits ``?? <var>;`` when it can't infer a variable's
    type — typically because the register-allocator in the decompiler
    emitted a value before resolving it. The placeholder compiles to a
    parse error.

    Substitutions are applied based on the right-hand side of the
    assignment:

      - ``?? rN;`` (uninitialised local) → ``Object rN;``
      - ``?? launch$default;`` → ``kotlinx.coroutines.Job launch$default;``
      - ``?? r2 = "...";`` (string literal) → ``String r2 = "...";``
      - ``?? rN = (... ? 1 : 0);`` (int ternary) → ``int rN = (... ? 1 : 0);``
      - ``?? hasModifier = hasModifier("...");`` (bsh AST) →
        ``boolean hasModifier = hasModifier("...");``
      - ``?? r2 = this.isSynchronized;`` (bsh AST) →
        ``boolean r2 = this.isSynchronized;``

    Any ``?? <name>;`` we don't recognise is left alone — those are
    almost always structural errors caught by a later transform.
    """
    t = Transform(
        "fix_jadx_qq_types",
        "Replace jadx '??' type-inference placeholders with Object/int/boolean/String",
    )
    report.transforms.append(t)
    # Specific known patterns (must come before the generic Object fallback)
    named_subs = [
        # bsh Parser — boolean hasModifier assignment
        (
            r"        \?\? hasModifier = hasModifier\(",
            r"        boolean hasModifier = hasModifier(",
        ),
        (
            r"        \?\? r2 = this\.isSynchronized;",
            r"        boolean r2 = this.isSynchronized;",
        ),
        (
            r"        \?\? hasModifier = modifiers\.hasModifier\(",
            r"        boolean hasModifier = modifiers.hasModifier(",
        ),
        # kotlinx.coroutines launch$default
        (
            r"        \?\? launch\$default;",
            r"        kotlinx.coroutines.Job launch$default;",
        ),
        # String literal assignment
        (
            r'        \?\? r2 = "   nativeLibDir: ";',
            r'        String r2 = "   nativeLibDir: ";',
        ),
        # Int ternary assignment
        (
            r"        \?\? r7 = 0;",
            r"        int r7 = 0;",
        ),
        (
            r"        \?\? r8 = 0;",
            r"        int r8 = 0;",
        ),
        # Multi-line int-ternary (the r13 = (... : 1 : 0) case). Match
        # any leading indent (jadx emits various depths). Greedy
        # `.*` so the `)` matches the *outer* one, not the inner
        # `this.dir.exists()`. Inline ``(?m)`` enables MULTILINE so
        # ``^`` matches at the start of each line, not just the
        # start of the file.
        (
            r"(?m)^(\s*)\?\? r13 = \(.*\) \? 1 : 0;",
            r"\1int r13 = (this.prootManager.getRootfsDir().exists() && "
            r"new java.io.File(this.prootManager.getRootfsDir(), \"usr\").exists()) ? 1 : 0;",
        ),
    ]
    for pattern, repl in named_subs:
        compiled = re.compile(pattern, re.DOTALL)
        for path in _walk_java(sources_dir):
            _rewrite(path, t, lambda c, p=compiled, r=repl: p.sub(r, c))
    # Generic: any remaining `?? rN;` -> `Object rN;`
    generic = re.compile(r"        \?\? (r\d+);")
    for path in _walk_java(sources_dir):
        _rewrite(path, t, lambda c: generic.sub(r"        Object \1;", c))


def _t_drop_assignment_before_jadx_error(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 3: ``var = /* JADX ERROR */ throw new ...;`` → comment.

    jadx 1.5.0 replaces code it cannot decompile with the
    placeholder::

        rememberedValue = /*  JADX ERROR: Method code generation error
            ...
        */
        throw new UnsupportedOperationException(...);

    Standard Java does not allow ``var = throw expr;`` (no ``throw``
    expression in pre-Java 14), so the line is a parse error. We
    replace the ``var =`` line with a no-op comment so the throw
    becomes a standalone statement and the rest of the method body
    parses correctly.
    """
    t = Transform(
        "drop_assignment_before_jadx_error",
        "Replace 'var = /* JADX ERROR */ throw new ...' (illegal Java) with comment",
    )
    report.transforms.append(t)
    # Match a line ending with `=` followed by a line starting with
    # the JADX ERROR comment. The line is replaced with a comment-only
    # line at the same indent.
    pattern = re.compile(
        r"^(\s*)\S[^\n]*=\s*\n(?P<next>\s*/\*\s+JADX ERROR:)",
        re.MULTILINE,
    )
    for path in _walk_java(sources_dir):
        _rewrite(
            path,
            t,
            lambda c: pattern.sub(
                r"\1/* jadx-stub: original assignment dropped before JADX ERROR block */\n\1\2",
                c,
            ),
        )


def _t_rename_kotlin_metadata_fields(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 4: ``@kotlin.Metadata(m560d1=...)`` → ``@kotlin.Metadata(d1=...)``.

    Modern Kotlin's ``Metadata`` annotation has these fields:
    ``d1, d2, k, mv, bv, xs, pn, xi``. jadx 1.5.0 emits the
    field names with a ``m<line><NAME>`` prefix (e.g. ``m560d1``)
    — the field the decompiler saw at line 560 of the source.
    We strip the prefix.
    """
    t = Transform(
        "rename_kotlin_metadata_fields",
        "Strip jadx's m<line> prefix from @kotlin.Metadata field names",
    )
    report.transforms.append(t)
    # The mapping is unambiguous because jadx only uses these prefixes
    # inside @Metadata / @DebugMetadata.
    field_map = {"d1": "d1", "d2": "d2", "k": "k", "mv": "mv", "xi": "xi", "bv": "bv"}
    for src_prefix, dest_name in field_map.items():
        # Match `m<digits><dest_name>` (e.g. m560d1 -> d1)
        compiled = re.compile(rf"\bm(\d+){src_prefix}\b")
        for path in _walk_java(sources_dir):
            _rewrite(path, t, lambda c, p=compiled, d=dest_name: p.sub(d, c))


def _t_rename_debug_metadata_fields(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 5: ``@DebugMetadata(m570c=...)`` → ``@DebugMetadata(c=...)``.

    Same idea as :func:`_t_rename_kotlin_metadata_fields` but for
    ``@kotlin.coroutines.jvm.internal.DebugMetadata``. The fields are
    ``c, f, i, l, m, n, s, v``.
    """
    t = Transform(
        "rename_debug_metadata_fields",
        "Strip jadx's m<line> prefix from @DebugMetadata field names",
    )
    report.transforms.append(t)
    field_map = ["c", "f", "i", "l", "m", "n", "s", "v"]
    for dest_name in field_map:
        compiled = re.compile(rf"\bm(\d+){dest_name}\b")
        for path in _walk_java(sources_dir):
            _rewrite(path, t, lambda c, p=compiled, d=dest_name: p.sub(d, c))


def _t_rename_apache_commons_static_fields(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 6: ``StringUtils.f746CR`` → ``StringUtils.CR``.

    jadx 1.5.0 emits ``commons-lang3`` static fields with a
    ``f<digits><NAME>`` prefix (``f746CR`` = field at line 746 named
    ``CR``). The real class only has ``CR``.

    We allowlist the replacements per class so we never rename a
    public field unintentionally.
    """
    t = Transform(
        "rename_apache_commons_static_fields",
        "Strip jadx's f<line> prefix from commons-lang3 static fields",
    )
    report.transforms.append(t)
    for fqcn, renames in _APACHE_COMMONS_RENAMES.items():
        for src, dst in renames.items():
            compiled = re.compile(rf"{re.escape(fqcn)}\.{re.escape(src)}\b")
            for path in _walk_java(sources_dir):
                _rewrite(
                    path,
                    t,
                    lambda c, p=compiled, d=dst, _fqcn=fqcn: p.sub(f"{_fqcn}.{d}", c),
                )


def _t_replace_autofill_hint_constants(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 7: replace ``androidx.autofill.HintConstants.*`` with strings.

    The ``androidx.autofill`` artifact was slimmed down and the
    ``HintConstants`` class was removed in favour of inline string
    constants. The decompiled code still references the old class.

    We replace with the literal values (``"username"``,
    ``"phone"``, ``"password"``) which is what the constants
    expanded to anyway.
    """
    t = Transform(
        "replace_autofill_hint_constants",
        "Replace removed androidx.autofill.HintConstants.* with inline string constants",
    )
    report.transforms.append(t)
    subs = [
        (
            r"androidx\.autofill\.HintConstants\.AUTOFILL_HINT_USERNAME",
            '"username"',
        ),
        (
            r"androidx\.autofill\.HintConstants\.AUTOFILL_HINT_PHONE",
            '"phone"',
        ),
        (
            r"androidx\.autofill\.HintConstants\.AUTOFILL_HINT_PASSWORD",
            '"password"',
        ),
    ]
    for pattern, repl in subs:
        compiled = re.compile(pattern)
        for path in _walk_java(sources_dir):
            _rewrite(path, t, lambda c, p=compiled, r=repl: p.sub(r, c))


def _t_replace_enum_entries_with_values(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 8: ``.enumEntries(values)`` → ``.values()``.

    Kotlin 2.0 added ``EnumEntriesKt.enumEntries(...)`` as a more
    efficient accessor than ``values()``. Java (pre-21) has no
    ``enumEntries``; we replace with the standard call.
    """
    t = Transform(
        "replace_enum_entries_with_values",
        "Replace Kotlin 2.0 enumEntries(...) with Enum.values()",
    )
    report.transforms.append(t)
    compiled = re.compile(r"\.enumEntries\(")
    for path in _walk_java(sources_dir):
        _rewrite(path, t, lambda c: compiled.sub(".values(", c))


def _t_remove_duplicate_getter_methods(sources_dir: Path, report: CleanupReport) -> None:
    """Transform 9: drop the first of two identical ``getXxx()`` methods.

    jadx 1.5.0 emits both the original ``getXxx()`` and a
    Kotlin data-class ``componentN``-renamed duplicate, e.g.::

        public final String getProductId() { return this.productId; }
        /* renamed from: component2, reason: from getter */
        public final String getProductId() { return this.productId; }
        public final String getBasePlanId() { return this.basePlanId; }

    The two ``getProductId()`` definitions conflict at compile time.
    We delete the first occurrence (and the ``/* renamed from: ... */``
    block preceding it) and keep the second.
    """
    t = Transform(
        "remove_duplicate_getter_methods",
        "Delete jadx's duplicate getXxx() methods (Kotlin data-class componentN-rename artifact)",
    )
    report.transforms.append(t)
    method_re = re.compile(
        # Match the *opening line* of a `getXxx()` method. Don't
        # require the line to end with `{` (jadx often inlines the
        # method body on the same line, e.g. `getX() { return x; }`);
        # we count braces to find the method end instead.
        r"^(\s*)(public|private|protected)\s+final\s+([\w.<>\[\]?,\s]+)\s+(get\w+)\s*\(\s*\)\s*\{",
        re.MULTILINE,
    )
    for path in _walk_java(sources_dir):
        text = path.read_text()
        # method_name -> the first match object (not a position; we
        # need the original match to read ``.start()`` / ``.end()``)
        seen: dict[str, re.Match] = {}
        edits: list[tuple[int, int]] = []  # (start, end) char offsets to delete
        for m in method_re.finditer(text):
            name = m.group(4)
            if name in seen:
                first_match = seen[name]
                # Delete the range from the start of the first match
                # to the start of this (second) match. This removes
                # both the first getX() body AND any intervening
                # whitespace + the renamed-from comment block.
                delete_start = first_match.start()
                edits.append((delete_start, m.start()))
                # Mark the second occurrence as the keeper
                del seen[name]
            else:
                seen[name] = m
        if not edits:
            continue
        # Apply edits in reverse so offsets remain valid
        new_text = text
        for start, end in sorted(edits, reverse=True):
            new_text = new_text[:start] + new_text[end:]
        if new_text != text:
            path.write_text(new_text)
            t.file_count += 1


def _t_move_broken_files(
    sources_dir: Path,
    report: CleanupReport,
    gradle_cmd: list[str] | None = None,
) -> Path:
    """Transform 10: move files that don't compile to ``java-broken/``.

    jadx 1.5.0 produces structurally broken code in a small number of
    files (typically the @Composable Kt screens with high register
    pressure). Trying to fix these surgically is more friction than
    it's worth for a one-off rebuild; we move them aside instead.

    The function attempts a Gradle compile to identify the broken
    files. If ``gradle_cmd`` is None, defaults to
    ``["./gradlew", ":app:compileDebugJavaWithJavac", "--no-daemon"]``
    invoked from the parent of ``sources_dir`` (assumes a standard
    Gradle project layout). If the compile can't be run (no
    ``./gradlew``), the function returns the quarantine path but
    moves nothing.
    """
    t = Transform(
        "move_broken_files",
        "Move files that fail Gradle compile to java-broken/ (jadx structural artifacts)",
    )
    report.transforms.append(t)
    # Default Gradle command for the rebuild-style project
    if gradle_cmd is None:
        gradle_cmd = [
            "./gradlew",
            ":app:compileDebugJavaWithJavac",
            "--no-daemon",
        ]
    project_dir = sources_dir.parent.parent  # java/ -> main/ -> app/
    if not (project_dir / "build.gradle.kts").exists():
        # No Gradle project yet; skip
        report.errors.append(
            "No build.gradle.kts found in project root; skipping move_broken_files"
        )
        return _quarantine_dir(sources_dir)
    try:
        proc = subprocess.run(  # noqa: S603 — gradle binary, not user input
            gradle_cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=900,
        )
    except FileNotFoundError as e:
        report.errors.append(f"gradle not on PATH: {e}")
        return _quarantine_dir(sources_dir)
    except subprocess.TimeoutExpired:
        report.errors.append("gradle compile timed out after 900s")
        return _quarantine_dir(sources_dir)
    if proc.returncode == 0:
        # No broken files
        return _quarantine_dir(sources_dir)
    # Extract erroring file paths from the stderr
    error_files = _parse_gradle_errors(proc.stdout + "\n" + proc.stderr)
    quarantine = _quarantine_dir(sources_dir)
    quarantine.mkdir(parents=True, exist_ok=True)
    moved = 0
    for rel in error_files:
        src = sources_dir / rel
        if not src.exists():
            continue
        dst = quarantine / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved += 1
    report.files_moved = moved
    report.moved_to = quarantine
    return quarantine


def _quarantine_dir(sources_dir: Path) -> Path:
    """Return the sibling ``java-broken/`` directory (does not create it)."""
    return sources_dir.parent.parent / "java-broken"


def _parse_gradle_errors(output: str) -> list[str]:
    """Extract ``app/src/main/java/<rel-path>.java`` paths from gradle output.

    Gradle error format::

        /path/to/app/src/main/java/com/example/Foo.java:42: error: ...
    """
    pattern = re.compile(r"(?:^|\s)([\w./-]+/app/src/main/java/[\w./]+\.java):\d+:\d+: error:")
    seen: set[str] = set()
    rels: list[str] = []
    for m in pattern.finditer(output):
        full = m.group(1)
        if full in seen:
            continue
        seen.add(full)
        # Strip the ``<project>/app/src/main/java/`` prefix
        idx = full.find("/app/src/main/java/")
        if idx == -1:
            continue
        rel = full[idx + len("/app/src/main/java/") :]
        rels.append(rel)
    return rels


# Ordered list of (name, callable) tuples — the canonical pipeline.
# Each callable is a pure function ``(sources_dir, report) -> None``
# that mutates files on disk and appends a Transform record to the
# report on any work.
_TRANSFORMS: list[tuple[str, Callable[[Path, CleanupReport], None]]] = [
    ("rename_p004ui", _t_rename_p004ui),
    ("fix_jadx_qq_types", _t_fix_jadx_qq_types),
    ("drop_assignment_before_jadx_error", _t_drop_assignment_before_jadx_error),
    ("rename_kotlin_metadata_fields", _t_rename_kotlin_metadata_fields),
    ("rename_debug_metadata_fields", _t_rename_debug_metadata_fields),
    ("rename_apache_commons_static_fields", _t_rename_apache_commons_static_fields),
    ("replace_autofill_hint_constants", _t_replace_autofill_hint_constants),
    ("replace_enum_entries_with_values", _t_replace_enum_entries_with_values),
    ("remove_duplicate_getter_methods", _t_remove_duplicate_getter_methods),
]


class JadxCleanup:
    """Apply the 9 in-place cleanup transforms (plus optional move-broken).

    Typical usage::

        from android_re_core.cleanup import JadxCleanup

        report = JadxCleanup.cleanup(Path("/tmp/jadx-out/sources"))
        # agressive=True also runs the move_broken_files transform
        # (requires a Gradle project at sources_dir.parent.parent/..)
        report = JadxCleanup.cleanup(
            Path("/tmp/jadx-out/sources"), agressivo=True
        )
        print(report.to_dict())

    The function is idempotent: each transform is a no-op on
    already-clean input. The :data:`CLEANUP_MARKER` sentinel
    short-circuits re-runs against a workdir that was already
    cleaned in a previous invocation.
    """

    @classmethod
    def cleanup(
        cls,
        sources_dir: str | Path,
        *,
        agressivo: bool = False,
        gradle_cmd: list[str] | None = None,
    ) -> CleanupReport:
        """Apply the cleanup pipeline to a jadx-decompiled ``sources/`` dir.

        Args:
            sources_dir: Absolute path to the decompiled ``sources/``
                directory (e.g. ``/tmp/android-re/<project>-jadx-deobf-java/sources/``).
            agressivo: When True, also runs the
                :func:`_t_move_broken_files` transform (requires a
                Gradle project at the standard layout).
            gradle_cmd: Optional override for the Gradle command used
                by ``move_broken_files``. Default:
                ``["./gradlew", ":app:compileDebugJavaWithJavac", "--no-daemon"]``.

        Returns:
            :class:`CleanupReport` with the transforms applied and
            any quarantine directory.
        """
        sources_dir = Path(sources_dir).expanduser().resolve()
        if not sources_dir.is_dir():
            raise FileNotFoundError(f"sources_dir not found: {sources_dir}")
        marker = sources_dir / CLEANUP_MARKER
        if marker.exists() and not agressivo:
            # Idempotent short-circuit (unless caller is forcing
            # the move pass by setting agressivo=True).
            return CleanupReport()
        report = CleanupReport()
        # Step 1: textual transforms (1-9)
        for _name, transform in _TRANSFORMS:
            transform(sources_dir, report)
        # Step 2: optional move pass
        if agressivo:
            quarantine = _t_move_broken_files(sources_dir, report, gradle_cmd)
            report.moved_to = quarantine if report.moved_to is None else report.moved_to
        # Compute aggregate file count
        report.files_modified = sum(t.file_count for t in report.transforms)
        # Mark complete (so a re-run without agressivo is a no-op).
        # We only write the marker if the textual transforms all ran
        # cleanly. If the move pass errored, we skip the marker so
        # the next call retries.
        if not report.errors:
            marker.touch()
        return report


#: Module-level convenience wrapper. Identical to
#: ``JadxCleanup.cleanup(...)``; preferred for one-liners.
def cleanup(
    sources_dir: str | Path,
    *,
    agressivo: bool = False,
    gradle_cmd: list[str] | None = None,
) -> CleanupReport:
    """Apply the cleanup pipeline; see :meth:`JadxCleanup.cleanup`."""
    return JadxCleanup.cleanup(sources_dir, agressivo=agressivo, gradle_cmd=gradle_cmd)
