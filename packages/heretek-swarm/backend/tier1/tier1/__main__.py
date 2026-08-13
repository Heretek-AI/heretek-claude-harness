"""CLI entry point. `python -m tier1 serve` starts the API."""

import argparse
import sys
from pathlib import Path

import uvicorn

from tier1.api.app import create_app
from tier1.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(prog="tier1")
    sub = parser.add_subparsers(dest="cmd", required=True)
    serve = sub.add_parser("serve", help="Run the API server")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--reload", action="store_true")
    serve.add_argument(
        "--dashboard-path",
        type=Path,
        default=None,
        help="Path to the built dashboard directory (mounts under /dashboard)",
    )
    args = parser.parse_args()

    if args.cmd != "serve":
        parser.error("unknown command")
        return 2

    settings = get_settings()
    dashboard_path = args.dashboard_path or (
        Path(settings.dashboard_path) if settings.dashboard_path else None
    )
    app = create_app(dashboard_path=dashboard_path)
    uvicorn.run(
        app,
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
        reload=args.reload,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
