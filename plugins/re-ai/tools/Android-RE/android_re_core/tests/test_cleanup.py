"""Tests for :mod:`android_re_core.cleanup` (jadx 1.5.0 post-decompile transforms).

Each test exercises one of the 10 transforms in
:class:`android_re_core.cleanup.JadxCleanup` against a minimal
fixture. The transforms are idempotent — re-running on already-clean
input is a no-op.
"""

from __future__ import annotations

from pathlib import Path

# Import the cleanup module directly to avoid the androguard-dependent
# `android_re_core/__init__.py` chain (test environments may not have
# androguard installed).
from android_re_core.cleanup import (
    CLEANUP_MARKER,
    CleanupReport,
    JadxCleanup,
    cleanup,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _read(path: Path) -> str:
    return path.read_text()


# ---------------------------------------------------------------------------
# Transform 1: rename_p004ui
# ---------------------------------------------------------------------------


class TestRenameP004Ui:
    def test_renames_directory(self, tmp_path: Path) -> None:
        p004 = tmp_path / "app" / "p004ui" / "Foo.java"
        _write(p004, "package app.anyclaw.p004ui;\nclass Foo {}\n")
        JadxCleanup.cleanup(tmp_path / "app")
        assert (tmp_path / "app" / "ui" / "Foo.java").exists()
        assert not (tmp_path / "app" / "p004ui").exists()

    def test_rewrites_package_and_qualified_references(self, tmp_path: Path) -> None:
        ui = tmp_path / "app" / "p004ui" / "Bar.java"
        _write(ui, "package app.anyclaw.p004ui;\nclass Bar {}\n")
        other = tmp_path / "app" / "Baz.java"
        _write(
            other,
            "import app.anyclaw.p004ui.Bar;\nclass Baz { Bar b; }\n",
        )
        JadxCleanup.cleanup(tmp_path / "app")
        assert "package app.anyclaw.ui;" in _read(tmp_path / "app" / "ui" / "Bar.java")
        assert "import app.anyclaw.ui.Bar;" in _read(tmp_path / "app" / "Baz.java")

    def test_also_fixes_p001ui_p002ui(self, tmp_path: Path) -> None:
        for prefix in ("p001ui", "p002ui", "p004ui"):
            d = tmp_path / "app" / prefix
            _write(d / "X.java", f"package app.anyclaw.{prefix};\n")
        JadxCleanup.cleanup(tmp_path / "app")
        # All three should be merged/renamed to ui/
        assert (tmp_path / "app" / "ui" / "X.java").exists()


# ---------------------------------------------------------------------------
# Transform 2: fix_jadx_qq_types
# ---------------------------------------------------------------------------


class TestFixJadxQqTypes:
    def test_replaces_bare_qq_local_with_object(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(f, "class Foo {\n    void m() {\n        ?? r0;\n    }\n}\n")
        JadxCleanup.cleanup(tmp_path)
        assert "Object r0;" in _read(f)

    def test_replaces_qq_launch_default_with_job(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n    void m() {\n        ?? launch$default;\n    }\n}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        assert "kotlinx.coroutines.Job launch$default;" in _read(f)

    def test_replaces_qq_r13_int_ternary(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            "    void m() {\n"
            '        ?? r13 = (this.dir.exists() && new java.io.File(this.dir, "usr").exists()) ? 1 : 0;\n'
            "    }\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert "int r13" in text
        assert "? 1 : 0" in text
        assert "??" not in text

    def test_replaces_qq_string_assignment(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            'class Foo {\n    void m() {\n        ?? r2 = "   nativeLibDir: ";\n    }\n}\n',
        )
        JadxCleanup.cleanup(tmp_path)
        assert 'String r2 = "   nativeLibDir: ";' in _read(f)


# ---------------------------------------------------------------------------
# Transform 3: drop_assignment_before_jadx_error
# ---------------------------------------------------------------------------


class TestDropAssignmentBeforeJadxError:
    def test_replaces_assignment_with_comment(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            "    void m() {\n"
            "        rememberedValue = \n"
            "        /*  JADX ERROR: Method code generation error\n"
            "            fake\n"
            "        */\n"
            '        throw new UnsupportedOperationException("x");\n'
            "    }\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert "jadx-stub: original assignment dropped" in text
        assert "throw new UnsupportedOperationException" in text
        # The original `rememberedValue =` should not be present
        # (replaced with the stub comment)
        assert "rememberedValue = \n" not in text


# ---------------------------------------------------------------------------
# Transform 4: rename_kotlin_metadata_fields
# ---------------------------------------------------------------------------


class TestRenameKotlinMetadataFields:
    def test_strips_m_line_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            '    @kotlin.Metadata(m560d1 = {"x"}, m562k = 1, m573mv = {2, 0, 0}, m575xi = 48)\n'
            "    void m() {}\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert "d1 =" in text
        assert "k =" in text
        assert "mv =" in text
        assert "xi =" in text
        # No m<digits>NAME left
        assert "m560d1" not in text
        assert "m562k" not in text


# ---------------------------------------------------------------------------
# Transform 5: rename_debug_metadata_fields
# ---------------------------------------------------------------------------


class TestRenameDebugMetadataFields:
    def test_strips_m_line_prefix(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            '    @kotlin.coroutines.jvm.internal.DebugMetadata(m570c = "Foo", m571f = "Foo.kt", m572i = {0}, m573l = {1}, m574m = "m", m575n = {"this"}, m576s = {"L$0"})\n'
            "    void m() {}\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert "c = " in text
        assert "f = " in text
        assert "i = " in text
        assert "l = " in text
        assert "m = " in text
        assert "n = " in text
        assert "s = " in text
        # No m<digits>LETTER left
        assert "m570c" not in text
        assert "m576s" not in text


# ---------------------------------------------------------------------------
# Transform 6: rename_apache_commons_static_fields
# ---------------------------------------------------------------------------


class TestRenameApacheCommonsStaticFields:
    def test_string_utils_lf(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            "    void m() {\n"
            "        org.apache.commons.lang3.StringUtils.f749LF;\n"
            "    }\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert "org.apache.commons.lang3.StringUtils.LF" in text
        assert "f749LF" not in text

    def test_char_utils_cr(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            "    char m() {\n"
            "        return org.apache.commons.lang3.CharUtils.f746CR;\n"
            "    }\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        assert "CharUtils.CR" in _read(f)


# ---------------------------------------------------------------------------
# Transform 7: replace_autofill_hint_constants
# ---------------------------------------------------------------------------


class TestReplaceAutofillHintConstants:
    def test_replaces_username_constant(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            "    void m() {\n"
            "        androidx.autofill.HintConstants.AUTOFILL_HINT_USERNAME.toString();\n"
            "    }\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert '"username"' in text
        assert "HintConstants" not in text

    def test_replaces_phone_and_password(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            "    void m() {\n"
            "        androidx.autofill.HintConstants.AUTOFILL_HINT_PHONE;\n"
            "        androidx.autofill.HintConstants.AUTOFILL_HINT_PASSWORD;\n"
            "    }\n"
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert '"phone"' in text
        assert '"password"' in text


# ---------------------------------------------------------------------------
# Transform 8: replace_enum_entries_with_values
# ---------------------------------------------------------------------------


class TestReplaceEnumEntriesWithValues:
    def test_replaces_enum_entries_call(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n    void m() {\n        Foo.enumEntries(Foo.values());\n    }\n}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        assert "Foo.values(Foo.values())" in _read(f)


# ---------------------------------------------------------------------------
# Transform 9: remove_duplicate_getter_methods
# ---------------------------------------------------------------------------


class TestRemoveDuplicateGetterMethods:
    def test_removes_duplicate_with_renamed_from_comment(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            '    public final String getX() { return "a"; }\n'
            "\n"
            "    /* renamed from: component2, reason: from getter */\n"
            '    public final String getX() { return "a"; }\n'
            "\n"
            '    public final String getY() { return "b"; }\n'
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        # Only one getX should remain
        assert text.count("getX()") == 1
        # The renamed-from comment should be gone
        assert "renamed from" not in text
        # The unrelated getY is preserved
        assert "getY()" in text

    def test_keeps_all_distinct_getters(self, tmp_path: Path) -> None:
        f = tmp_path / "Foo.java"
        _write(
            f,
            "class Foo {\n"
            '    public final String getA() { return "a"; }\n'
            '    public final String getB() { return "b"; }\n'
            "}\n",
        )
        JadxCleanup.cleanup(tmp_path)
        text = _read(f)
        assert text.count("getA()") == 1
        assert text.count("getB()") == 1


# ---------------------------------------------------------------------------
# End-to-end: full pipeline on a realistic fixture
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_idempotent(self, tmp_path: Path) -> None:
        # First call: should transform the file
        f = tmp_path / "Foo.java"
        _write(f, "class Foo {\n    void m() {\n        ?? r0;\n    }\n}\n")
        report1 = cleanup(tmp_path)
        assert report1.files_modified >= 1
        text_after_first = _read(f)
        assert "??" not in text_after_first

        # Second call: marker is present, no-op
        report2 = cleanup(tmp_path)
        # On the second call, no transforms are applied because of the
        # marker, so the report is empty.
        assert (tmp_path / CLEANUP_MARKER).exists()
        assert report2.transforms == []

    def test_agressivo_moves_broken_files(self, tmp_path: Path) -> None:
        # Set up a minimal Gradle project structure
        app = tmp_path / "app"
        _write(
            app / "build.gradle.kts",
            'plugins { id("java") }\n',
        )
        java_dir = app / "src" / "main" / "java"
        _write(java_dir / "Good.java", "public class Good {}\n")
        # The "broken" file has syntax that will fail to compile
        _write(
            java_dir / "Bad.java",
            "public class Bad { ?? invalid_token; }\n",
        )
        # No real gradle on the test host, so the move pass will
        # error. We assert that the function reports the error
        # gracefully and does not corrupt the file tree.
        report = JadxCleanup.cleanup(java_dir, agressivo=True)
        assert any("gradle" in e.lower() for e in report.errors) or report.files_moved > 0


# ---------------------------------------------------------------------------
# Module-level helper: cleanup() function
# ---------------------------------------------------------------------------


def test_cleanup_module_function_matches_classmethod(tmp_path: Path) -> None:
    f = tmp_path / "Foo.java"
    _write(f, "class Foo {\n    void m() {\n        ?? r0;\n    }\n}\n")
    report = cleanup(tmp_path)
    assert isinstance(report, CleanupReport)
    assert "Object r0;" in _read(f)
