"""MCP server entry point for re-vtil.

Exposes VTIL-Core VM handler characterization tools to Claude
Code via the Model Context Protocol stdio transport. The Python
server is a thin wrapper around a C++ ``vtil-cli`` helper that
install.sh builds from the vendored VTIL-Core source tree.

When the C++ helper is missing, the server reports ``WARN``
(not ``ERROR``) and the tools return a clean "binary not built"
hint — this lets Claude Code load the plugin in degraded mode
and surface a useful message instead of crashing.

All output is vendor-neutral: the tools describe *observable*
handler structure (lift to VTIL IL, run optimization passes,
emit pseudo-C) without naming any commercial anti-tamper
product.
"""

from __future__ import annotations

import base64
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from re_vtil import runner

logger = logging.getLogger("re_vtil")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-vtil")


# ── Health ──────────────────────────────────────────────────────────────


@mcp.tool()
def check_vtil() -> dict:
    """Return vtil-cli version + supported architectures.

    Reports ``WARN`` (not ``ERROR``) when the vtil-cli binary is
    not found — the Python server itself always loads. The fallback
    chain: ``$RE_VTIL_CLI_PATH`` -> ``<server>/bin/vtil-cli`` -> PATH.
    """
    cli = runner._binary_path()
    info: dict = {
        "server": "re-vtil",
        "version": "0.1.0",
    }
    if cli is None:
        info["status"] = "WARN"
        info["error"] = "vtil-cli binary not found"
        info["hint"] = (
            "Run the installer (./install.sh) — it invokes "
            "`cmake --build` for the C++ helper. Or set "
            "RE_VTIL_CLI_PATH=/path/to/vtil-cli."
        )
        return info
    info["status"] = "OK"
    info["cli_path"] = str(cli)
    out = runner.run_subcommand("check")
    if out is None or "error" in out:
        info["status"] = "WARN"
        info["error"] = (out or {}).get("error", "vtil-cli check failed")
    else:
        info["vtil_version"] = out.get("version")
        info["supported_archs"] = out.get("supported_archs", [])
    return info


# ── VM handler characterization ─────────────────────────────────────────


@mcp.tool()
def lift_handler(
    arch: str,
    code: str,
    base_address: int = 0x400000,
) -> dict:
    """Lift *arch* / *code* to VTIL intermediate language.

    Args:
        arch: target architecture — one of ``x86``, ``x86_64``,
            ``aarch64``, ``arm32``
        code: machine-code bytes, base64-encoded (base64 is
            transport-friendly; the CLI decodes back to bytes
            before passing to VTIL's lifters)
        base_address: where the code is mapped in virtual memory
            (default 0x400000 — the ELF .text convention)

    Returns::

        {"arch": "x86_64", "base_address": 0x400000,
         "il": {"blocks": [{"vaddr": N, "instructions": [...]}]}}

    Each lifted instruction is one of VTIL's IL primitives
    (``mov``, ``add``, ``sub``, ``jmp``, ``if``, ``vmov``, etc.).
    The structure is enough for ``optimize`` and ``emit`` to work
    on the output.

    On a missing binary, returns ``{"status": "WARN", "error":
    "vtil-cli not built", ...}`` so the agent knows to retry
    after install.sh.
    """
    # Validate the base64 — we don't want to ship invalid payloads
    # to the C++ helper.
    try:
        base64.b64decode(code, validate=True)
    except Exception as exc:  # noqa: BLE001
        return {
            "arch": arch,
            "base_address": base_address,
            "error": f"code is not valid base64: {exc}",
        }
    out = runner.run_subcommand(
        "lift", arch, code, hex(base_address),
    )
    if out is None:
        return {
            "arch": arch,
            "base_address": base_address,
            "status": "WARN",
            "error": "vtil-cli not built; run install.sh",
        }
    if "error" in out:
        return {"arch": arch, "base_address": base_address, "error": out["error"]}
    return {
        "arch": arch,
        "base_address": base_address,
        "il": out.get("il", {}),
    }


@mcp.tool()
def optimize(
    il: dict,
    passes: list[str] = ["dead_store_elimination", "branch_folding", "mem_dependency"],
) -> dict:
    """Run VTIL optimization passes over a lifted IL tree.

    Args:
        il: the IL tree produced by :func:`lift_handler`
        passes: list of pass names to apply in order. The canonical
            set is ``dead_store_elimination``, ``branch_folding``,
            ``mem_dependency``; pass names are the C++ enum names
            in VTIL's ``optimizer::pass_index``.

    Returns::

        {"il": <optimized il>, "passes_applied": [...]}

    The output IL is in the same shape as the input — drop-in
    replacement for downstream ``emit`` calls.
    """
    import json
    if not il:
        return {"error": "il is empty — call lift_handler first"}
    out = runner.run_subcommand(
        "optimize",
        json.dumps(il),
        ",".join(passes),
    )
    if out is None:
        return {
            "status": "WARN",
            "error": "vtil-cli not built; run install.sh",
        }
    if "error" in out:
        return {"error": out["error"]}
    return {
        "il": out.get("il", {}),
        "passes_applied": out.get("passes_applied", passes),
    }


@mcp.tool()
def emit_pseudo_c(il: dict) -> dict:
    """Emit a pseudo-C reading of a lifted IL tree.

    The output is best-effort — VTIL's ``emulator`` walks the IL
    and produces a C-like pseudocode that an analyst can read. The
    quality is much lower than IDA Hex-Rays or Ghidra's
    decompiler; the use case is a quick first-pass read of a VM
    handler body, not a full decompilation.

    Args:
        il: the IL tree (raw from ``lift_handler`` or optimized
            via :func:`optimize`)

    Returns::

        {"code": "C-like pseudocode...", "il_block_count": N}
    """
    import json
    if not il:
        return {"code": "", "il_block_count": 0, "error": "il is empty"}
    out = runner.run_subcommand("emit", json.dumps(il))
    if out is None:
        return {
            "code": "",
            "il_block_count": 0,
            "status": "WARN",
            "error": "vtil-cli not built; run install.sh",
        }
    # emit may return JSON with `text` (pseudo-c) or with `error`
    if "error" in out:
        return {"code": "", "il_block_count": 0, "error": out["error"]}
    return {
        "code": out.get("text", out.get("code", "")),
        "il_block_count": len(il.get("blocks", [])) if isinstance(il, dict) else 0,
    }


# ── Curated simplification (v2.7.0) ───────────────────────────────────


@mcp.tool()
def simplify_lifted_il(
    il: dict,
    passes: list[str] | None = None,
    default_preset: str = "d810-ng",
) -> dict:
    """Run the curated default pass set on a lifted IL tree.

    The canonical pass order comes from
    ``data/ollvm-pass-catalog.json::_meta.default_pass_order`` and
    is curated for the encrypted-VM bytecode handler-lift case
    (MBA-fold + opaque-predicate-eval + control-flow-unflatten
    on top of the d810-ng default set).

    Args:
        il: the IL tree produced by :func:`lift_handler`
        passes: optional override; when ``None``, the curated
            default order is used.
        default_preset: ``"d810-ng"`` (the curated set), or
            ``"none"`` to disable simplification entirely.

    Returns::

        {"il": <optimized il>, "passes_applied": [...],
         "preset": "d810-ng"}
    """
    import json
    if not il:
        return {
            "il": {}, "passes_applied": [], "preset": default_preset,
            "error": "il is empty — call lift_handler first",
        }
    if passes is None:
        if default_preset == "d810-ng":
            passes = _load_default_pass_order()
        elif default_preset == "none":
            passes = []
        else:
            return {
                "il": il, "passes_applied": [],
                "preset": default_preset,
                "error": f"unknown preset: {default_preset!r}",
            }
    if not passes:
        return {"il": il, "passes_applied": [], "preset": default_preset}
    out = runner.run_subcommand(
        "optimize",
        json.dumps(il),
        ",".join(passes),
    )
    if out is None:
        return {
            "il": il, "passes_applied": passes, "preset": default_preset,
            "status": "WARN",
            "error": "vtil-cli not built; run install.sh",
        }
    if "error" in out:
        return {
            "il": il, "passes_applied": passes,
            "preset": default_preset, "error": out["error"],
        }
    return {
        "il": out.get("il", {}),
        "passes_applied": out.get("passes_applied", passes),
        "preset": default_preset,
    }


def _load_default_pass_order() -> list[str]:
    """Load the default pass order from the vendored OLLVM catalog."""
    from pathlib import Path
    here = Path(__file__).resolve()
    candidates = [
        here.parents[4] / "data" / "ollvm-pass-catalog.json",
        here.parents[3] / "data" / "ollvm-pass-catalog.json",
        here.parents[2] / "data" / "ollvm-pass-catalog.json",
    ]
    for p in candidates:
        if p.is_file():
            try:
                import json
                d = json.loads(p.read_text())
                order = d.get("_meta", {}).get("default_pass_order", [])
                if order:
                    return list(order)
            except Exception:
                continue
    # Fall back to the d810-ng canonical set.
    return [
        "constant_folding",
        "dead_store_elimination",
        "branch_folding",
        "mem_dependency",
        "mba_fold",
        "opaque_predicate_eval",
        "control_flow_unflatten",
    ]


# ── Entrypoint ─────────────────────────────────────────────────────────


def main() -> None:
    """Run the MCP server over stdio (the standard Claude Code transport)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
