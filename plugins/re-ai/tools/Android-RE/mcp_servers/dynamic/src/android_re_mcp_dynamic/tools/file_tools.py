"""File / heap tools (read app's files, dump heap)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP  # type: ignore[import-untyped]
from pydantic import Field

__all__ = ["register"]


def register(mcp: FastMCP) -> None:
    """Register file / heap tools."""

    @mcp.tool(
        name="read_file_via_runas",
        description=(
            "Read a file on the device as the app's UID, using "
            "``run-as <package> cat <path>``. The package must be "
            "debuggable."
        ),
    )
    def read_file_via_runas(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier (must be debuggable)")],
        path: Annotated[str, Field(description="Absolute path on the device")],
    ) -> dict[str, Any]:
        from android_re_core.device.adb import shell

        try:
            out = shell(f"run-as {package} cat {path}", serial=serial, timeout_s=30)
        except Exception as e:
            return {"error": {"code": "read_failed", "message": str(e)}}
        return {
            "serial": serial,
            "package": package,
            "path": path,
            "content": out,
        }

    @mcp.tool(
        name="list_app_files",
        description=(
            "List files in /data/data/<pkg>/ via run-as. Recursive by "
            "default; non-recursive lists one level."
        ),
    )
    def list_app_files(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier")],
        path: Annotated[str, Field(description="Path under /data/data/<pkg>/ to list")] = "",
        recursive: Annotated[bool, Field(description="Recursive walk")] = False,
    ) -> dict[str, Any]:
        from android_re_core.device.adb import shell

        target = f"/data/data/{package}/{path}" if path else f"/data/data/{package}"
        cmd = f"run-as {package} find {target} -maxdepth 1"
        if recursive:
            cmd = f"run-as {package} find {target}"
        try:
            out = shell(cmd, serial=serial, timeout_s=30)
        except Exception as e:
            return {"error": {"code": "list_failed", "message": str(e)}}
        files: list[dict[str, Any]] = []
        for line in out.splitlines():
            line = line.strip()
            if not line or line == target:
                continue
            name = line.rsplit("/", 1)[-1]
            is_dir = False  # We don't get type info from a plain `find` here;
            # for a real check we'd need `-printf` or `ls`.
            files.append({"path": line, "name": name, "is_dir": is_dir})
        return {
            "serial": serial,
            "package": package,
            "path": target,
            "count": len(files),
            "files": files,
        }

    @mcp.tool(
        name="dump_heap",
        description=(
            "Capture a heap dump from a running process via "
            "``am dumpheap``. REQUIRES confirm=true. The .hprof "
            "file is pulled to ``output_path`` on the host."
        ),
    )
    def dump_heap(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier")],
        output_path: Annotated[str, Field(description="Host path to write the .hprof to")],
        confirm: Annotated[bool, Field(description="Must be true to dump")] = False,
    ) -> dict[str, Any]:
        if not confirm:
            return {
                "error": {"code": "confirm_required", "message": "dump_heap requires confirm=true"}
            }
        from android_re_core.device.adb import run_adb, shell

        remote_path = f"/data/local/tmp/{package}-heap.hprof"
        try:
            shell(f"am dumpheap {package} {remote_path}", serial=serial, timeout_s=120)
        except Exception as e:
            return {"error": {"code": "dump_failed", "message": str(e)}}
        # Pull the file
        try:
            run_adb(["-s", serial, "pull", remote_path, output_path], timeout_s=120)
        except Exception as e:
            return {"error": {"code": "pull_failed", "message": str(e)}}
        try:
            run_adb(["-s", serial, "shell", "rm", remote_path], timeout_s=10)
        except Exception:
            pass
        try:
            size = os.path.getsize(output_path)
        except OSError:
            size = 0
        return {"ok": True, "output_path": output_path, "size": size}

    @mcp.tool(
        name="list_activities",
        description=(
            "Enumerate the activities declared by a package using "
            "``pm dump <pkg>`` and parsing the activity table."
        ),
    )
    def list_activities(
        serial: Annotated[str, Field(description="Device serial")],
        package: Annotated[str, Field(description="Package identifier")],
    ) -> dict[str, Any]:
        from android_re_core.device.adb import run_adb

        try:
            proc = run_adb(["-s", serial, "shell", "pm", "dump", package], timeout_s=30)
        except Exception as e:
            return {"error": {"code": "pm_dump_failed", "message": str(e)}}
        # Look for "Activity Resolver Table:" section
        activities: list[str] = []
        in_activities = False
        for line in proc.stdout.splitlines():
            if "Activity Resolver Table:" in line:
                in_activities = True
                continue
            if in_activities and line.strip().startswith(package + "/"):
                activities.append(line.strip())
            elif in_activities and line.strip() == "":
                if activities:
                    break
        return {
            "serial": serial,
            "package": package,
            "count": len(activities),
            "activities": activities,
        }

    _ = time, Path  # silence linter
