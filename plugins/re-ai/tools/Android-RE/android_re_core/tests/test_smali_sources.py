"""Tests for the :mod:`android_re_core.smali` and :mod:`android_re_core.sources` modules.

The first half of the file exercises pure-Python error paths (no
apktool / jadx installs required). The second half drives the real
``SourcesView`` end-to-end against ``tests/fixtures/bin/fake-jadx``,
so we can assert method slicing, cache behaviour, flag pass-through,
and path-traversal defence without a real jadx install or a binary
APK in the repo.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from android_re_core.errors import APKInvalid, ToolNotFound
from android_re_core.smali import SmaliView
from android_re_core.sources import (
    MAX_READ_SOURCE_BYTES,
    SourcesView,
    _descriptor_to_return_type,
    _find_method_end,
    _find_method_signature,
    _is_valid_cache,
)

# ---------------------------------------------------------------------------
# Pure-Python error-path tests
# ---------------------------------------------------------------------------


def test_smali_decode_missing_apk(tmp_path: Path):
    """SmaliView.decode raises APKInvalid for a missing APK."""
    with pytest.raises(APKInvalid):
        SmaliView.decode(tmp_path / "does-not-exist.apk", workdir=tmp_path / "out")


def test_sources_decompile_missing_apk(tmp_path: Path):
    """SourcesView.decompile raises APKInvalid for a missing APK."""
    with pytest.raises(APKInvalid):
        SourcesView.decompile(tmp_path / "does-not-exist.apk", workdir=tmp_path / "out")


def test_apktool_missing_raises_toolnotfound(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """If apktool jar is not findable, SmaliView.decode raises ToolNotFound."""
    apk = tmp_path / "test.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("classes.dex", b"")
    monkeypatch.setenv("APKTOOL_JAR", "/nonexistent/path/apktool.jar")
    monkeypatch.setenv("JAVA_HOME", "")
    monkeypatch.setenv("JAVA", "")
    from android_re_core import paths

    def _fake_find():
        raise ToolNotFound("apktool")

    monkeypatch.setattr(paths, "find_apktool", _fake_find)
    with pytest.raises((ToolNotFound, FileNotFoundError, Exception)):
        SmaliView.decode(apk, workdir=tmp_path / "out")


# ---------------------------------------------------------------------------
# Pure-Python method-slice tests (no subprocess)
# ---------------------------------------------------------------------------


def test_descriptor_to_return_type():
    assert _descriptor_to_return_type("()V") == "void"
    assert _descriptor_to_return_type("(I)Z") == "boolean"
    assert _descriptor_to_return_type("(Ljava/lang/String;)I") == "int"
    assert _descriptor_to_return_type("(JJ)D") == "double"
    assert _descriptor_to_return_type("()Lcom/example/Foo;") == "Foo"
    # Multi-dim arrays: unrecognised → None (fall back to name-only)
    assert _descriptor_to_return_type("()[[I") is None
    # Bogus descriptors
    assert _descriptor_to_return_type("") is None
    assert _descriptor_to_return_type("Q") is None


def test_method_signature_finds_primitive_return():
    text = (
        "package x;\n"
        "public class A {\n"
        "    public void m1() { int x = 1; }\n"
        "    public int m2(int a) { return a; }\n"
        "}\n"
    )
    idx = _find_method_signature(text, "m1", "()V")
    assert idx is not None
    end, _ = _find_method_end(text, idx)
    assert "int x = 1" in text[idx : end + 1]
    assert "m2" not in text[idx : end + 1]


def test_method_slice_with_brace_in_string_literal():
    text = (
        "class B {\n"
        "    void foo() {\n"
        '        String s = "hello } world";\n'
        "    }\n"
        "    void bar() { int x = 0; }\n"
        "}\n"
    )
    idx = _find_method_signature(text, "foo", "()V")
    assert idx is not None
    end, _ = _find_method_end(text, idx)
    slice_ = text[idx : end + 1]
    assert 'String s = "hello } world"' in slice_
    assert "bar" not in slice_, "brace in string literal confused the counter"


def test_method_slice_with_braces_in_block_comment():
    text = (
        "class C {\n"
        "    /* { not a brace } */\n"
        "    void alpha() { int a = 1; }\n"
        "    /* another { brace */\n"
        "    void beta() { int b = 2; }\n"
        "}\n"
    )
    idx = _find_method_signature(text, "alpha", "()V")
    assert idx is not None
    end, _ = _find_method_end(text, idx)
    slice_ = text[idx : end + 1]
    assert "beta" not in slice_, "brace in block comment confused the counter"


def test_method_slice_with_anonymous_inner_class():
    text = (
        "class D {\n"
        "    void run() {\n"
        "        Runnable r = new Runnable() {\n"
        "            @Override public void run() { int x = 0; }\n"
        "        };\n"
        "        r.run();\n"
        "    }\n"
        "    void next() { int z = 0; }\n"
        "}\n"
    )
    idx = _find_method_signature(text, "run", "()V")
    assert idx is not None
    end, _ = _find_method_end(text, idx)
    slice_ = text[idx : end + 1]
    assert "next" not in slice_, "anonymous inner class confused brace counter"


def test_method_slice_with_text_block():
    text = (
        "class E {\n"
        "    String make() {\n"
        '        String s = """\n'
        "        {not a brace}\n"
        '        """;\n'
        "        return s;\n"
        "    }\n"
        "    void next() { int z = 0; }\n"
        "}\n"
    )
    idx = _find_method_signature(text, "make", "()Ljava/lang/String;")
    if idx is not None:
        end, _ = _find_method_end(text, idx)
        slice_ = text[idx : end + 1]
        assert "next" not in slice_, "text block confused brace counter"


def test_method_signature_returns_none_for_missing_method():
    text = "class A { void foo() {} }"
    assert _find_method_signature(text, "bar", "()V") is None


def test_method_slice_returns_none_for_missing_method():
    text = "class A { void foo() {} }"
    idx = _find_method_signature(text, "bar", "()V")
    assert idx is None


# ---------------------------------------------------------------------------
# Path-traversal + size-cap tests for read_source (no subprocess)
# ---------------------------------------------------------------------------


def _make_view_with_sources(tmp_path: Path, files: dict[str, str]) -> SourcesView:
    """Build a SourcesView pointing at a hand-crafted sources/ tree.

    Returns the view; does not invoke jadx. Useful for read_source tests.
    """
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    for rel, content in files.items():
        path = sources_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return SourcesView(
        apk_path=tmp_path / "fake.apk",
        workdir=tmp_path,
        sources_dir=sources_dir,
        resources_dir=None,
        manifest_path=None,
    )


def test_read_source_returns_content(tmp_path: Path):
    view = _make_view_with_sources(tmp_path, {"com/example/Foo.java": "class Foo {}"})
    result = view.read_source("com/example/Foo.java")
    assert result is not None
    content, line_count, byte_size = result
    assert content == "class Foo {}"
    assert line_count == 1
    assert byte_size == len(b"class Foo {}")


def test_read_source_refuses_parent_traversal(tmp_path: Path):
    view = _make_view_with_sources(tmp_path, {"com/example/Foo.java": "x"})
    assert view.read_source("../etc/passwd") is None
    assert view.read_source("com/../../etc/passwd") is None
    assert view.read_source("/etc/passwd") is None


def test_read_source_refuses_oversized_file(tmp_path: Path):
    big = "x" * (MAX_READ_SOURCE_BYTES + 1)
    view = _make_view_with_sources(tmp_path, {"big.java": big})
    assert view.read_source("big.java") is None


def test_read_source_returns_none_for_missing(tmp_path: Path):
    view = _make_view_with_sources(tmp_path, {})
    assert view.read_source("com/example/DoesNotExist.java") is None


def test_read_source_defeats_symlink_escape(tmp_path: Path):
    """A symlink inside sources/ that points outside should be rejected."""
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    link = tmp_path / "sources" / "leak.txt"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside)
    view = SourcesView(
        apk_path=tmp_path / "fake.apk",
        workdir=tmp_path,
        sources_dir=tmp_path / "sources",
        resources_dir=None,
        manifest_path=None,
    )
    # The link resolves outside sources_dir, so is_relative_to() must
    # reject it. If symlink following is not in effect, the read also
    # fails (size of the symlink target is fine but resolve() returns
    # the outside path).
    result = view.read_source("leak.txt")
    assert result is None, "symlink escaped the sources dir"


# ---------------------------------------------------------------------------
# Cache-validation tests (no subprocess)
# ---------------------------------------------------------------------------


def test_is_valid_cache_rejects_empty_dir(tmp_path: Path):
    sources = tmp_path / "sources"
    sources.mkdir()
    assert _is_valid_cache(sources) is False


def test_is_valid_cache_rejects_missing_dir(tmp_path: Path):
    assert _is_valid_cache(tmp_path / "nonexistent") is False


def test_is_valid_cache_accepts_populated_dir(tmp_path: Path):
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "A.java").write_text("class A {}")
    assert _is_valid_cache(sources) is True


# ---------------------------------------------------------------------------
# End-to-end: drive SourcesView against the fake-jadx fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_jadx_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Prepend the fake-jadx fixture dir to PATH and make find_jadx
    return the fake binary.
    """
    import os

    bin_dir = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "bin"
    assert (bin_dir / "fake-jadx").exists(), f"fake-jadx missing at {bin_dir}"

    cur = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{bin_dir}{':' if cur else ''}{cur}")
    monkeypatch.setenv("JADX", str(bin_dir / "fake-jadx"))
    from android_re_core import paths

    monkeypatch.setattr(paths, "find_jadx", lambda: bin_dir / "fake-jadx")
    return bin_dir / "fake-jadx"


@pytest.fixture()
def fake_apk(tmp_path: Path) -> Path:
    apk = tmp_path / "fake.apk"
    with zipfile.ZipFile(apk, "w") as zf:
        zf.writestr("classes.dex", b"")
    return apk


def test_sources_decompile_end_to_end(fake_jadx_path: Path, fake_apk: Path, tmp_path: Path):
    workdir = tmp_path / "out"
    view = SourcesView.decompile(fake_apk, workdir=workdir)
    assert view.sources_dir.is_dir()
    assert (view.sources_dir / "com" / "example" / "Foo.java").exists()
    src = view.decompile_class("Lcom/example/Foo;")
    assert src is not None
    assert "class Foo" in src


def test_sources_decompile_caches_on_repeat(fake_jadx_path: Path, fake_apk: Path, tmp_path: Path):
    workdir = tmp_path / "out"
    SourcesView.decompile(fake_apk, workdir=workdir)
    # Record the recorded-args file size after the first call.
    record = fake_jadx_path.parent.parent / "last-jadx-args.txt"
    record.unlink(missing_ok=True)
    # Second call should hit the cache → no new jadx invocation →
    # last-jadx-args.txt must not exist (or be empty / unchanged).
    view2 = SourcesView.decompile(fake_apk, workdir=workdir)
    assert view2.sources_dir.is_dir()
    assert not record.exists(), f"jadx was re-invoked: {record.read_text()}"


def test_sources_decompile_force_reruns(fake_jadx_path: Path, fake_apk: Path, tmp_path: Path):
    workdir = tmp_path / "out"
    record = fake_jadx_path.parent.parent / "last-jadx-args.txt"
    SourcesView.decompile(fake_apk, workdir=workdir)
    record.unlink(missing_ok=True)
    SourcesView.decompile(fake_apk, workdir=workdir, force=True)
    assert record.exists(), "force=True did not re-invoke jadx"


def test_sources_decompile_reruns_when_sources_dir_empty(
    fake_jadx_path: Path, fake_apk: Path, tmp_path: Path
):
    """A workdir that exists but has no .java files is treated as a
    cache miss.
    """
    workdir = tmp_path / "out"
    workdir.mkdir()
    (workdir / "sources").mkdir()
    record = fake_jadx_path.parent.parent / "last-jadx-args.txt"
    record.unlink(missing_ok=True)
    view = SourcesView.decompile(fake_apk, workdir=workdir)
    assert view.sources_dir.is_dir()
    assert record.exists(), "partial-cache hit; jadx should have re-run"


def test_sources_decompile_passes_deobf_flag(fake_jadx_path: Path, fake_apk: Path, tmp_path: Path):
    workdir = tmp_path / "out"
    record = fake_jadx_path.parent.parent / "last-jadx-args.txt"
    SourcesView.decompile(fake_apk, workdir=workdir, deobfuscate=True)
    text = record.read_text()
    assert "--deobf" in text, f"--deobf not in jadx argv:\n{text}"


def test_sources_decompile_passes_threads_count(
    fake_jadx_path: Path, fake_apk: Path, tmp_path: Path
):
    workdir = tmp_path / "out"
    record = fake_jadx_path.parent.parent / "last-jadx-args.txt"
    SourcesView.decompile(fake_apk, workdir=workdir, threads=4)
    text = record.read_text()
    assert "--threads-count" in text
    assert "4" in text


def test_sources_decompile_rejects_kotlin_output_format(
    fake_jadx_path: Path, fake_apk: Path, tmp_path: Path
):
    """``output_format="kotlin"`` is no longer supported on jadx 1.5.0.

    The MCP tool description and the underlying ``SourcesView.decompile()``
    no longer accept it. Passing "kotlin" raises ``ValueError`` (via
    ``OutputFormat("kotlin")``) before the subprocess is even invoked.
    """
    import pytest

    with pytest.raises(ValueError, match="kotlin"):
        SourcesView.decompile(fake_apk, workdir=tmp_path / "out", output_format="kotlin")


def test_sources_decompile_method_returns_slice(
    fake_jadx_path: Path, fake_apk: Path, tmp_path: Path
):
    workdir = tmp_path / "out"
    view = SourcesView.decompile(fake_apk, workdir=workdir)
    slice_ = view.decompile_method("Lcom/example/Foo;", "hello", "()Ljava/lang/String;")
    assert slice_ is not None
    assert slice_.start_line >= 1
    assert slice_.end_line >= slice_.start_line
    assert "hello" in slice_.source
    # Must NOT contain a sibling method body
    assert "return a + b" not in slice_.source


def test_sources_decompile_method_returns_none_for_missing(
    fake_jadx_path: Path, fake_apk: Path, tmp_path: Path
):
    workdir = tmp_path / "out"
    view = SourcesView.decompile(fake_apk, workdir=workdir)
    assert view.decompile_method("Lcom/example/Foo;", "nonexistent", "()V") is None


def test_sources_summary(fake_jadx_path: Path, fake_apk: Path, tmp_path: Path):
    workdir = tmp_path / "out"
    view = SourcesView.decompile(fake_apk, workdir=workdir)
    summary = view.summary(limit=10, offset=0)
    assert summary["class_count"] >= 1
    assert summary["total_files"] >= 1
    assert summary["deobfuscated"] is False
    assert summary["output_format"] == "java"
    assert summary["truncated"] is False
    assert summary["files"], "summary should include file entries"
    entry = summary["files"][0]
    assert "path" in entry and "line_count" in entry and "byte_size" in entry
