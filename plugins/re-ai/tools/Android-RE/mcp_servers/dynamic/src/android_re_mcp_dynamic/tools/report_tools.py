"""Session reporting."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

from android_re_mcp_dynamic.server import (
    get_script_store,
    get_session_store,
)

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register session reporting tools."""

    @mcp.tool(
        name="build_session_report",
        description=(
            "Build a consolidated report for a single session: the "
            "session info, every script loaded on it, the buffered "
            "messages from each script, and the list of rpc calls "
            "made so far (Phase 3 does not yet track RPC calls "
            "automatically). Writes a JSON copy to "
            "``Output/<apk>-<sha>/dynamic/session-report.json`` by "
            "default; override with ``output_path``."
        ),
    )
    def build_session_report(
        session_id: Annotated[str, Field(description="Session id")],
        output_path: Annotated[
            str | None,
            Field(
                description=(
                    "Host path to write the report JSON. Defaults to "
                    "``Output/<apk>-<sha>/dynamic/session-report.json`` "
                    "(computed from the session's package)."
                )
            ),
        ] = None,
    ) -> dict[str, Any]:
        session = get_session_store().try_get(session_id)
        if session is None:
            return {"error": {"code": "session_not_found", "message": session_id}}
        scripts = get_script_store().list_for_session(session_id)
        scripts_full = []
        for s in scripts:
            wrapper = get_script_store().try_get(s.script_id)
            scripts_full.append(
                {
                    **s.to_dict(),
                    "is_destroyed": (wrapper.is_destroyed if wrapper else True),
                    "message_count": (len(wrapper.messages) if wrapper else 0),
                    "messages_preview": (wrapper.messages[-10:] if wrapper else []),
                }
            )
        result = {
            "session": session.info.to_dict(),
            "is_detached": session.is_detached,
            "script_count": len(scripts_full),
            "scripts": scripts_full,
        }
        if output_path:
            out_path = Path(output_path).expanduser()
        else:
            # Fall back to /tmp if we can't resolve a per-APK output dir
            # (the dynamic server doesn't track APK paths directly; we
            # default to a deterministic per-session tmp path so the
            # agent always has a place to look).
            pkg = session.info.package or session_id
            out_path = (
                Path(os.environ.get("ANDROID_RE_OUTPUT_DIR", "/tmp"))
                / "dynamic"
                / f"session-{pkg}-{session_id[:8]}.json"
            )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        except OSError as e:
            return {"error": {"code": "write_failed", "message": str(e)}}
        return {**result, "output_path": str(out_path)}
