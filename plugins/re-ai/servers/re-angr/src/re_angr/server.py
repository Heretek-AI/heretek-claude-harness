"""MCP server entry point for re-angr.

Exposes angr symbolic-execution + CFG + reaching-definitions
tools to Claude Code via the Model Context Protocol stdio
transport. The Python server is a thin wrapper around an
``angr-cli`` Python helper installed by install.sh via
``pip install 're-angr[core]'``.

When the helper is missing, the server reports ``WARN`` (not
``ERROR``) and the tools return a clean install hint — the
Python server itself always loads.

All output is vendor-neutral: CFG / constraints / def-use
descriptions name the *function* or *block*, not a specific
commercial product. The encrypted-VM bytecode detection work
that uses these tools never names a specific product.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from re_angr import runner

logger = logging.getLogger("re_angr")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-angr")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_angr() -> dict:
    """Return angr-cli + angr package version + Python import probe.

    Reports ``WARN`` (not ``ERROR``) when the helper or the Python
    module is not importable. The fallback chain for the CLI
    binary: ``$RE_ANGR_CLI_PATH`` -> ``<server>/bin/angr-cli`` ->
    PATH. The Python import probe (added in v2.9.1 to fix Gap 23)
    runs ``import angr; import cle`` in a subprocess using the
    same Python interpreter the MCP server runs under. The CLI
    check alone is insufficient: the CLI can be installed while
    the server's interpreter lacks the angr package, which
    causes downstream tools (``build_cfg``, ``symbolic_exec``,
    ``reaching_definitions``) to emit ``No module named 'angr'``.

    Status is ``OK`` only when BOTH the CLI is present AND the
    Python import probe succeeds. Otherwise status is ``WARN``
    with a concrete install hint.
    """
    cli = runner._binary_path()
    info: dict = {"server": "re-angr", "version": "0.1.0"}
    cli_ok = cli is not None
    if cli_ok:
        info["cli_path"] = str(cli)
    else:
        info["error"] = "angr-cli not found"
    # Python import probe (Gap 23 fix, v2.9.1). This catches
    # the case where the CLI helper is present but the angr
    # package isn't importable in the server's interpreter.
    import_probe = runner.python_import_check()
    info.update(import_probe)
    # CLI version sub-check (only meaningful when CLI is present).
    if cli_ok:
        out = runner.run_subcommand("check")
        if out is None or "error" in out:
            info["error"] = (out or {}).get("error", "angr-cli check failed")
        else:
            info["angr_version"] = out.get("angr_version")
            info["cle_version"] = out.get("cle_version")
    # Status logic: OK only if CLI present AND import probe ok.
    if cli_ok and import_probe.get("python_import_ok"):
        info["status"] = "OK"
    else:
        info["status"] = "WARN"
        if not cli_ok:
            info.setdefault("hint", (
                "Run the installer (./install.sh) — it installs "
                "angr>=9.2 + the angr-cli helper. Or set "
                "RE_ANGR_CLI_PATH=/path/to/angr-cli."
            ))
        else:
            # CLI is fine but angr package is missing — this is
            # the v2.9.1 Gap 23 case the new check catches.
            info.setdefault("hint", (
                "angr-cli is on PATH but `import angr` failed in "
                f"{import_probe.get('python_executable', 'the active Python')}. "
                "Run `pip install 'angr>=9.2' cle` into the active venv."
            ))
    return info


# ── CFG + symbolic execution ──────────────────────────────────────────


@mcp.tool()
def build_cfg(path: str, function: str | None = None) -> dict:
    """Build a control-flow graph of *path* (optionally one function).

    Args:
        path: PE / ELF / MachO to analyze
        function: optional function name (e.g. ``"main"``) — when
            given, only the CFG of that function is returned; when
            ``None``, the full program CFG is returned.

    Returns::

        {"path": "...",
         "function": "..." | null,
         "nodes": [{"addr": N, "size": M, "successors": [...]}],
         "edges": [{"src": N, "dst": M, "kind": "fall-through|jmp|call|ret"}]}

    The CFG is the first thing an analyst needs for VM detection
    (high incoming-edge count on a single block = dispatcher
    candidate) and for binary comprehension in general.
    """
    args = [path]
    if function:
        args.append(function)
    out = runner.run_subcommand("cfg", *args)
    if out is None:
        return {
            "path": path,
            "function": function,
            "status": "WARN",
            "error": "angr-cli not installed; run install.sh",
        }
    if "error" in out:
        return {"path": path, "function": function, "error": out["error"]}
    return {
        "path": path,
        "function": function,
        "nodes": out.get("nodes", []),
        "edges": out.get("edges", []),
    }


@mcp.tool()
def symbolic_exec(path: str, address: str, args: list[str] | None = None) -> dict:
    """Run angr symbolic execution starting at *address*.

    Args:
        path: PE / ELF / MachO to analyze
        address: entry point as a hex string (e.g. ``"0x401000"``)
        args: optional list of symbolic-arg names (default:
            none — angr marks stdin / argv as symbolic depending
            on the binary's entry point conventions)

    Returns::

        {"path": "...",
         "address": "0x401000",
         "states_explored": N,
         "constraints": [{"path": [...], "expr": "..."}],
         "dead_ends": N}

    The output is a *partial* trace — angr explores until either
    all paths are explored or the timeout is hit. The result is
    useful for cross-validation: "angr and Triton both find
    this MBA identity holds" is a much stronger signal than
    either alone.
    """
    argv = [path, address]
    if args:
        argv += ["--args", ",".join(args)]
    out = runner.run_subcommand("symbolic-exec", *argv)
    if out is None:
        return {
            "path": path,
            "address": address,
            "status": "WARN",
            "error": "angr-cli not installed; run install.sh",
        }
    if "error" in out:
        return {"path": path, "address": address, "error": out["error"]}
    return {
        "path": path,
        "address": address,
        "states_explored": out.get("states_explored", 0),
        "constraints": out.get("constraints", []),
        "dead_ends": out.get("dead_ends", 0),
    }


@mcp.tool()
def reaching_definitions(path: str, function: str) -> dict:
    """Compute the reaching-definitions graph for *function*.

    A *reaching definition* is "where was the value used at
    instruction X defined?" angr computes the dataflow analysis
    statically. The output is a def-use graph: every variable
    gets a list of definitions; every instruction that reads
    a variable gets the list of definitions that *may* reach it.

    Useful for the ``re-mba-deobfuscate`` skill: the MBA
    identity ``x + y == (x & y) + (x | y)`` looks like
    arithmetic, but the reaching-defs graph reveals that ``(x & y)``
    and ``(x | y)`` were both defined from the same source — the
    identity is a no-op substitution.

    Args:
        path: PE / ELF / MachO
        function: function name (e.g. ``"main"``)

    Returns::

        {"path": "...", "function": "...",
         "defs": [{"variable": "...", "defined_at": "0x..."}],
         "uses": [{"at": "0x...", "reads": ["var1", "var2"]}]}
    """
    out = runner.run_subcommand("reaching-defs", path, function)
    if out is None:
        return {
            "path": path,
            "function": function,
            "status": "WARN",
            "error": "angr-cli not installed; run install.sh",
        }
    if "error" in out:
        return {"path": path, "function": function, "error": out["error"]}
    return {
        "path": path,
        "function": function,
        "defs": out.get("defs", []),
        "uses": out.get("uses", []),
    }


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
