"""Tests for scripts/error_translator.py diagnostic parser and translator."""

from __future__ import annotations

from scripts.error_translator import (
    Diagnostic,
    parse_cargo_output,
    parse_pyright_output,
    parse_ruff_output,
    parse_tsc_output,
    translate_output,
)


def test_parse_ruff_output() -> None:
    sample = "app.py:42:10: F841 Local variable `x` is assigned to but never used"
    diags = parse_ruff_output(sample)
    assert len(diags) == 1
    assert diags[0] == Diagnostic(
        file_path="app.py",
        line=42,
        column=10,
        message="Local variable `x` is assigned to but never used",
        code="F841",
        level="ERROR",
    )
    assert (
        diags[0].format_minimal()
        == "[ERROR] app.py:42:10 - Local variable `x` is assigned to but never used (F841)"
    )


def test_parse_pyright_output() -> None:
    sample = (
        '/path/to/main.py:15:5 - error: Type "int" is not assignable to "str" (reportArgumentType)'
    )
    diags = parse_pyright_output(sample)
    assert len(diags) == 1
    assert diags[0].file_path == "/path/to/main.py"
    assert diags[0].line == 15
    assert diags[0].column == 5
    assert diags[0].code == "reportArgumentType"
    assert (
        diags[0].format_minimal()
        == '[ERROR] /path/to/main.py:15:5 - Type "int" is not assignable to "str" (reportArgumentType)'
    )


def test_parse_cargo_output() -> None:
    sample = """error[E0308]: mismatched types
  --> src/main.rs:42:10
   |
42 |     let x: u32 = "hello";
   |"""
    diags = parse_cargo_output(sample)
    assert len(diags) == 1
    assert diags[0].file_path == "src/main.rs"
    assert diags[0].line == 42
    assert diags[0].column == 10
    assert diags[0].code == "E0308"
    assert diags[0].format_minimal() == "[ERROR] src/main.rs:42:10 - mismatched types (E0308)"


def test_parse_tsc_output() -> None:
    sample = "src/index.ts(20,8): error TS2322: Type 'number' is not assignable to type 'string'."
    diags = parse_tsc_output(sample)
    assert len(diags) == 1
    assert diags[0].file_path == "src/index.ts"
    assert diags[0].line == 20
    assert diags[0].column == 8
    assert diags[0].code == "TS2322"
    assert (
        diags[0].format_minimal()
        == "[ERROR] src/index.ts:20:8 - Type 'number' is not assignable to type 'string'. (TS2322)"
    )


def test_translate_output_fallback() -> None:
    raw = "Fatal build crash\nError: unexpected EOF\nLine 3"
    result = translate_output(raw, tool_hint="custom")
    assert "[ERROR] Error: unexpected EOF" in result
