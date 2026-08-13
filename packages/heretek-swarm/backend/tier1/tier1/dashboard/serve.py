"""Static dashboard serving. Mounts the built React app under /dashboard/*."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def mount_static(app: FastAPI, path: str | Path) -> None:
    """Mount a directory of static files at /dashboard.

    The React build outputs HTML/JS/CSS into the path. SPA fallback
    (so client-side routes work) is handled by the SPA returning
    index.html for unknown paths — we use a small wrapper.
    """
    p = Path(path).resolve()
    if not p.exists():
        return

    @app.api_route("/dashboard", methods=["GET", "HEAD"], include_in_schema=False)
    async def dashboard_index():
        return FileResponse(p / "index.html")

    @app.api_route("/dashboard/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def dashboard_assets(full_path: str):
        # Try the literal path first; fall back to index.html for SPA routing.
        candidate = p / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(p / "index.html")
