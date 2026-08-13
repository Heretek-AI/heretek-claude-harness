"""MCP server entry point for re-fuzz-replay.

Fuzz-style replay of a small input corpus against a
target function. Wraps ``re-triton`` (symbolic
exploration + emulation) and ``re-gdb`` (concrete
single-step). The server is a thin orchestrator — the
heavy lifting is in the wrapped tools.

The analyst reviews each new basic block; the tool
never auto-generates inputs.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("re_fuzz_replay")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-fuzz-replay")


@mcp.tool()
def check_fuzz_replay() -> dict:
    """Report server status + optional dep availability."""
    return {
        "server": "re-fuzz-replay",
        "version": "0.1.0",
        "status": "OK",
        "triton_available": _has_module("triton"),
        "gdb_available": _binary_on_path("gdb"),
    }


@mcp.tool()
def seed_replay(path: str, function: str, corpus_dir: str, max_replays: int = 100) -> dict:
    """Replay each file in *corpus_dir* against the target.

    Args:
        path: file containing the target function
        function: function name (e.g. ``sym.main``) or
            RVA (e.g. ``0x401000``)
        corpus_dir: directory containing input files to
            replay
        max_replays: cap (default 100)

    Returns::

        {
          "path": "...",
          "function": "...",
          "corpus_dir": "...",
          "replays": [{"input": "...", "edges_hit": N,
                       "new_edges": M, "crash": bool}, ...],
          "total_inputs": N,
          "total_new_edges": M
        }
    """
    import os
    if not os.path.isdir(corpus_dir):
        return {"path": path, "function": function, "error": "corpus_dir not found",
                "replays": [], "total_inputs": 0, "total_new_edges": 0}
    inputs = []
    for name in sorted(os.listdir(corpus_dir)):
        full = os.path.join(corpus_dir, name)
        if os.path.isfile(full):
            inputs.append(full)
            if len(inputs) >= max_replays:
                break
    replays = []
    total_new = 0
    seen_signature: str | None = None
    for inp in inputs:
        # Per-input replay: use re-triton emulate_function
        # to capture the edge signature, compare to the
        # prior signature, count new edges.
        try:
            data = open(inp, "rb").read()
        except OSError:
            continue
        import base64
        try:
            emu = _delegate_triton("emulate_function", {
                "code_b64": base64.b64encode(data).decode("ascii"),
            })
        except Exception:
            emu = {"edges": []}
        edges = emu.get("edges", []) if isinstance(emu, dict) else []
        sig = _sig_of(edges)
        new = (sig != seen_signature) and (sig is not None)
        if new:
            seen_signature = sig
        replays.append({
            "input": inp,
            "edges_hit": len(edges),
            "new_edges": 1 if new else 0,
            "crash": False,
        })
        if new:
            total_new += 1
    return {
        "path": path,
        "function": function,
        "corpus_dir": corpus_dir,
        "replays": replays,
        "total_inputs": len(replays),
        "total_new_edges": total_new,
    }


@mcp.tool()
def coverage_map(path: str, function: str, code_b64: str = "", concrete_inputs: dict | None = None) -> dict:
    """Return a coverage map for the target.

    Wraps ``re-triton.coverage_map``. ``code_b64`` may
    be the function's raw bytes (base64-encoded) or
    empty to use the .text-section scan.
    """
    return _delegate_triton("coverage_map", {
        "code_b64": code_b64,
        "concrete_inputs": concrete_inputs or {},
    })


@mcp.tool()
def edge_diff(before: dict, after: dict) -> dict:
    """Diff two coverage maps and return the new edges."""
    b_edges = set(tuple(e) if isinstance(e, (list, tuple)) else (e,) for e in before.get("edges", []))
    a_edges = set(tuple(e) if isinstance(e, (list, tuple)) else (e,) for e in after.get("edges", []))
    new = a_edges - b_edges
    return {"new_edges": [list(e) for e in new], "new_count": len(new)}


@mcp.tool()
def next_inputs(path: str, function: str, k: int = 8) -> dict:
    """Suggest next inputs to try (no auto-mutation).

    The default strategy is: the next input is the
    previous input + 1 byte at the end (the analyst
    reviews the result). The tool never auto-crates
    inputs.
    """
    return {
        "path": path,
        "function": function,
        "k": k,
        "suggestions": [
            "extend the existing corpus by 1 byte at the end",
            "flip the high bit of the last byte of the last replayed input",
            "try the empty input (0 bytes) and a single 0x00 byte",
            "use re-triton.find_magic_bytes to ask the symbolic engine for the next input",
        ][:k],
    }


# ── helpers ────────────────────────────────────────────────────────────


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _binary_on_path(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


def _sig_of(edges) -> str | None:
    if not edges:
        return None
    return "|".join(str(e) for e in sorted(edges))


def _delegate_triton(tool: str, params: dict) -> dict:
    """Stub: in production this would call the re-triton
    MCP server via JSON-RPC. In degraded mode returns a
    structured placeholder."""
    return {
        "delegated_to": "re-triton",
        "tool": tool,
        "params": params,
        "status": "DELEGATED",
        "edges": [],
        "blocks": [],
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
