"""MCP server entry point for re-dotnet.

Exposes .NET assembly analysis tools to Claude Code via the
Model Context Protocol stdio transport. Metadata operations
delegate to a self-contained .NET 10 CLI binary built from
``src/re_dotnet/dotnet/Re.Dotnet.Cli/`` (System.Reflection.Metadata
only — no external NuGet deps). C# decompilation delegates to
``ilspycmd``, installed as a global dotnet tool by install.sh.

All tools are vendor-neutral: they describe observable structure
(types, methods, fields, strings, decompiled C#) without
naming any commercial obfuscation product.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_dotnet import runner

logger = logging.getLogger("re_dotnet")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-dotnet")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_dotnet() -> dict:
    """Return .NET runtime + re-dotnet-cli + ilspycmd availability.

    Reports ``WARN`` (not ``ERROR``) if either binary is not found —
    this lets Claude Code load the plugin in degraded mode and
    surface a useful message instead of crashing.

    The :func:`runner._cli_binary` / :func:`runner._decompiler_binary`
    fallback chains search ``$RE_DOTNET_CLI_PATH`` /
    ``$RE_DOTNET_DECOMPILER_PATH`` first, then
    ``<server>/bin/``, then ``$PATH``.
    """
    import shutil

    cli = runner._cli_binary()
    decompiler = runner._decompiler_binary()
    info: dict = {
        "server": "re-dotnet",
        "version": "0.1.0",
        "decompiler": "ilspycmd (external)",
    }
    if cli is None:
        info["status"] = "WARN"
        info["error"] = "re-dotnet-cli binary not found"
        info["hint"] = (
            "Run the installer (./install.sh) — it invokes "
            "`dotnet publish` for the metadata helper."
        )
        return info

    info["cli_path"] = str(cli)
    info["dotnet_runtime"] = (
        shutil.which("dotnet") or "not on PATH (using published binary)"
    )
    cli_output = runner.run_subcommand("check")
    if "error" in cli_output:
        info["status"] = "WARN"
        info["error"] = cli_output["error"]
    else:
        info["status"] = "OK"
        info["dotnet_runtime_version"] = cli_output.get("dotnet_runtime")
        info["decompiler_availability"] = (
            "available" if decompiler is not None
            else "missing — decompile_type / decompile_method will fail"
        )
        if decompiler is not None:
            info["decompiler_path"] = str(decompiler)
    return info


# ── Top-level parse ────────────────────────────────────────────────────


@mcp.tool()
def parse_assembly(path: str) -> dict:
    """Enumerate TypeDef rows in *path*.

    Returns the assembly header (name, version, target framework,
    entry point) plus a one-row-per-type summary. This is the
    .NET cousin of ``re-lief.parse_binary`` and ``re-il2cpp
    .get_assembly_types`` — the analyst's first call on a
    .NET-style launcher or mod-loader.

    Output shape::

        {
          "header": {
            "path": "...",
            "assembly_name": "...",
            "assembly_version": "...",
            "target_framework": "...",
            "corlib": "...",
            "is_mixed_mode": bool,
            "entry_point": "Namespace.Type::Method",
            "file_kind": "assembly" | "netmodule",
            "type_count": N,
            "method_count": N,
            "field_count": N,
          },
          "types": [
            {"fqn": "...", "namespace": "...", "name": "...",
             "is_public": bool, "method_count": N, "field_count": N,
             "property_count": N, "event_count": N, "nested_type_count": N,
             "base_type": "..."},
            ...
          ],
          "truncated": false
        }
    """
    header = runner.run_subcommand("read-header", path)
    if "error" in header:
        return header
    types = runner.run_subcommand("list-types", path)
    if "error" in types:
        return {**header, "types": [], "truncated": False, "error": types["error"]}
    return {
        "header": header,
        "types": types.get("types", []),
        "truncated": types.get("count", 0) >= 5000,
    }


@mcp.tool()
def decompile_type(path: str, fqn: str) -> dict:
    """Decompile a single class to C# via ilspycmd.

    Args:
        path: path to a ``.dll`` / ``.exe`` .NET assembly
        fqn: fully-qualified type name (e.g. ``MyGame.PlayerController``).
             Discover candidates with :func:`parse_assembly` first.

    Returns::

        {"path": "...", "fqn": "...", "code": "C# source..."}

    On decompiler failure (e.g. an obfuscated control-flow pattern
    ilspycmd refuses to lift, or ilspycmd not installed), returns
    ``code: null`` and a non-null ``error`` field. ilspycmd is the
    industry-standard CLI for ILSpy; for protected binaries the next
    step is ``re-decompile`` (which calls into de4dot for unpacking)
    before re-running this tool.
    """
    code = runner.decompile_type(path, fqn)
    if code is None:
        return {
            "path": path,
            "fqn": fqn,
            "code": None,
            "error": (
                "ilspycmd decompile failed (binary missing, type not found, "
                "or obfuscated IL)."
            ),
        }
    return {"path": path, "fqn": fqn, "code": code}


@mcp.tool()
def decompile_method(path: str, fqn: str) -> dict:
    """Decompile a single method to C# via ilspycmd.

    Args:
        path: path to a ``.dll`` / ``.exe`` .NET assembly
        fqn: ``"Namespace.Type::MethodName"`` (the ``::`` separator
             matches the C++ convention; do not use ``.`` between
             type and method name — those are both parts of the
             type FQN)

    Returns::

        {"path": "...", "fqn": "...", "code": "C# method body..."}
    """
    code = runner.decompile_method(path, fqn)
    if code is None:
        return {
            "path": path,
            "fqn": fqn,
            "code": None,
            "error": "ilspycmd decompile failed (see server log).",
        }
    return {"path": path, "fqn": fqn, "code": code}


@mcp.tool()
def list_strings(path: str, mode: str = "field-default", limit: int = 500) -> dict:
    """Extract user-visible strings from the .NET #US heap.

    Two modes:
      - ``"field-default"`` (default): walks every type's
        ``const string`` field-default values. Best for the
        pure-.NET path where most strings live in static readonly
        fields.
      - ``"ldstr"`` (v2.8.1, A11): walks every method body's IL
        stream and captures every ``ldstr`` operand. Best for the
        Mono path (CD's MonoLauncher is the canonical example) where
        most useful strings live in ``ldstr`` operands, not
        field-defaults.

    The C# CLI subcommand is ``list-strings`` for ``field-default``
    and ``list-ldstr`` for ``ldstr`` (both implemented in
    :mod:`Re.Dotnet.Cli.Ops.MetadataOps`). On encrypted /
    obfuscated #US heaps the CLI returns ``count: 0`` silently —
    that's a legitimate "heap unreadable" signal, not a regression.

    Args:
        path: path to a ``.dll`` / ``.exe`` .NET assembly
        mode: ``"field-default"`` (default) or ``"ldstr"``
        limit: maximum strings to return (default 500)

    Returns::

        {"path": "...", "mode": "...", "count": N, "truncated": bool,
         "strings": [{"fqn": "...", "kind": "...", "il_offset": N,
                      "string": "..."}, ...]}
    """
    subcommand = "list-ldstr" if mode == "ldstr" else "list-strings"
    out = runner.run_subcommand(subcommand, path, "", str(limit))
    if "error" in out:
        return {
            "path": path,
            "mode": mode,
            "count": 0,
            "truncated": False,
            "strings": [],
            "error": out["error"],
        }
    return {
        "path": path,
        "mode": mode,
        "count": out.get("count", 0),
        "truncated": out.get("truncated", False),
        "strings": out.get("strings", []),
    }


@mcp.tool()
def get_entry_point(path: str) -> dict:
    """Return the managed entry point (``<Module>::.cctor`` or ``Main``).

    Useful for "what does the launcher do first?" — point a
    decompiler at the entry point before reading the rest of the
    class graph.
    """
    return runner.run_subcommand("get-entry-point", path)


# ── A12 (v2.8.1): Mono path routing ───────────────────────────────────


@mcp.tool()
def get_methods(path: str, fqn: str, limit: int = 500) -> dict:
    """List the methods of one type (Mono / .NET pure assembly).

    Pure routing: the C# CLI already implements ``list-methods``
    in :mod:`Re.Dotnet.Cli.Ops.MetadataOps` (uses
    ``System.Reflection.Metadata`` via the .NET 10 runtime). This
    MCP wrapper is the v2.8.1 (A12) addition that exposes the
    Mono path the r03-stress run flagged as missing.

    A12 note (v2.8.0): on Mono assemblies (e.g. CD's MonoLauncher)
    this tool did not exist; callers had to fall back to
    ``decompile_type`` + regex on the C# source. The MCP wrapper
    fixes the routing gap; the underlying CLI subcommand is
    already battle-tested on the IL2CPP path
    (``re-il2cpp.get_methods`` uses the same code path).

    Args:
        path: path to a .dll / .exe .NET or Mono assembly
        fqn: fully-qualified type name (e.g. ``MyGame.PlayerController``)
        limit: max rows to return (default 500)

    Returns::

        {"path": "...", "fqn": "...", "type_fqn": "...",
         "count": N,
         "methods": [{"name": "...", "signature": "...",
                      "is_public": bool, "is_static": bool,
                      "is_virtual": bool, "is_abstract": bool,
                      "is_final": bool, "is_special_name": bool,
                      "rva": N, "token": "..."}, ...]}
    """
    return runner.run_subcommand("list-methods", path, fqn, str(limit))


@mcp.tool()
def get_fields(path: str, fqn: str, limit: int = 200) -> dict:
    """List the fields of one type (Mono / .NET pure assembly).

    Same routing pattern as :func:`get_methods`. The CLI
    subcommand is ``list-fields`` in
    :mod:`Re.Dotnet.Cli.Ops.MetadataOps`.

    A12 (v2.8.1): added so the CD-3 patch coordinates (which
    need the field name ``_isSteam``) can be discovered without
    ``decompile_type`` first.

    Args:
        path: path to a .dll / .exe .NET or Mono assembly
        fqn: fully-qualified type name
        limit: max rows to return (default 200)

    Returns::

        {"path": "...", "fqn": "...", "type_fqn": "...",
         "count": N,
         "fields": [{"name": "...", "field_type": "...",
                     "is_public": bool, "is_static": bool,
                     "is_read_only": bool, "is_literal": bool,
                     "constant": "..."}, ...]}
    """
    return runner.run_subcommand("list-fields", path, fqn, str(limit))


# ── .NET protection classification + deobfuscation (v2.7.0) ──────────


@mcp.tool()
def classify_dotnet_protection(path: str, max_per_category: int = 50) -> dict:
    """Walk a .NET assembly for canonical obfuscation patterns.

    Returns category-only labels (``type-name-renaming``,
    ``control-flow-flattening``, ``string-encryption``,
    ``managed-anti-debug``, ``resource-encryption``,
    ``native-aot-stub``). Never names a specific commercial
    obfuscator.

    The walker uses the ``re-dotnet`` Python helper
    :mod:`re_dotnet.protection_classifier` (pure-Python
    IL/Metadata subset; no need for the .NET CLI binary
    to be built). The CLI is only used for type-name listing
    (already covered by :func:`parse_assembly`).

    Args:
        path: path to a ``.dll`` / ``.exe`` .NET assembly
        max_per_category: per-category cap (default 50)

    Returns::

        {
          "path": "...",
          "matches": [{"category": "...", "evidence": "...",
                       "evidence_member": "..."}, ...],
          "by_category": {"type-name-renaming": 12, "string-encryption": 4, ...}
        }
    """
    try:
        from re_dotnet import protection_classifier
    except ImportError as exc:
        return {
            "path": path,
            "matches": [],
            "by_category": {},
            "error": f"re_dotnet.protection_classifier module not available: {exc}",
        }
    return protection_classifier.classify(path, max_per_category=max_per_category)


@mcp.tool()
def detect_managed_anti_debug(path: str, max_per_method: int = 500) -> dict:
    """Scan IL method bodies for managed anti-debug primitives.

    Looks for ``IsDebuggerPresent``, ``Debugger.IsAttached``,
    ``Debug.Assert``, ``Debugger.Break``, and the curated
    indirect-check set (timing traps, process-name blacklists,
    registry probes). Returns ``{method_fqn, primitive,
    evidence_il_offset}`` per hit. The category is
    ``"managed-anti-debug"``; no vendor is named.

    Args:
        path: path to a .NET assembly
        max_per_method: cap per method (default 500; a single
            method with 500+ anti-debug calls is itself a
            signal — the cap is for safety, not for
            normality)

    Returns::

        {
          "path": "...",
          "hits": [{"method_fqn": "...", "primitive": "...",
                    "evidence_il_offset": N}, ...],
          "by_primitive": {"IsDebuggerPresent": 4, ...}
        }
    """
    try:
        from re_dotnet import protection_classifier
    except ImportError as exc:
        return {
            "path": path,
            "hits": [],
            "by_primitive": {},
            "error": f"re_dotnet.protection_classifier module not available: {exc}",
        }
    return protection_classifier.detect_managed_anti_debug(
        path, max_per_method=max_per_method,
    )


@mcp.tool()
def run_il_simplification(
    path: str,
    method_fqn: str,
    passes: list[str] | None = None,
) -> dict:
    """Run a d810-ng-style IL simplification pass set on one method.

    Currently supported passes:

    - ``constant_fold`` — replace arithmetic on constants with
      the constant result.
    - ``dead_branch_elim`` — remove branches that are provably
      dead after constant folding.
    - ``opaque_predicate_eval`` — evaluate predicates whose
      truth is provable from prior dataflow.
    - ``string_decrypt`` — replace
      ``ldstr; call Get<name>(); ret`` patterns with the
      literal string. The decryption function name is
      auto-detected from the assembly's #Strings heap.

    Args:
        path: path to a .NET assembly
        method_fqn: ``"Namespace.Type::MethodName"``
        passes: optional override; default is
            ``["constant_fold", "dead_branch_elim",
            "opaque_predicate_eval", "string_decrypt"]``.

    Returns::

        {
          "path": "...",
          "method_fqn": "...",
          "passes_applied": [...],
          "before_il_size": N,
          "after_il_size": M,
          "il_before": "...",
          "il_after": "..."
        }
    """
    try:
        from re_dotnet import simplifier as simplifier_mod
    except ImportError as exc:
        return {
            "path": path,
            "method_fqn": method_fqn,
            "passes_applied": [],
            "before_il_size": 0,
            "after_il_size": 0,
            "il_before": "",
            "il_after": "",
            "error": f"re_dotnet.simplifier module not available: {exc}",
        }
    if passes is None:
        passes = ["constant_fold", "dead_branch_elim",
                  "opaque_predicate_eval", "string_decrypt"]
    return simplifier_mod.run_passes(path, method_fqn, passes)


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
