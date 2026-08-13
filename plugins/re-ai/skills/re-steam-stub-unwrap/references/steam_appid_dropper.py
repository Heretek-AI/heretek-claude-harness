"""steam_appid_dropper.py — emit the canonical steam_appid.txt payload.

Standalone helper for the re-steam-stub-unwrap skill. Pure stdlib +
urllib for the SteamDB / store.steampowered.com lookup. Replaces
the manual `Write` workaround from r03-stress.

Usage:
    python3 steam_appid_dropper.py <app_id> [<dst_dir>]
    python3 steam_appid_dropper.py --verify <app_id>

The verify subcommand probes store.steampowered.com to confirm the
AppID resolves to a real published page (best-effort; does not
require an API key).
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path


def emit_payload(app_id: int) -> bytes:
    """Return the canonical steam_appid.txt content (AppID + newline)."""
    return f"{int(app_id)}\n".encode("ascii")


def drop_side_file(app_id: int, dst_dir: str) -> Path:
    """Write steam_appid.txt to *dst_dir*; returns the written path."""
    p = Path(dst_dir) / "steam_appid.txt"
    p.write_bytes(emit_payload(app_id))
    return p


def verify_app_id(app_id: int, timeout: float = 5.0) -> dict:
    """Probe store.steampowered.com/app/<id>/ — return reachability dict.

    Returns:
        {
            "app_id": int,
            "url": "https://store.steampowered.com/app/<id>/",
            "http_status": int | None,
            "exists": bool,    # True if 200, False if 404 / unreachable
            "reason": "...",
        }
    """
    url = f"https://store.steampowered.com/app/{int(app_id)}/"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "re-ai/2.8.0 steam-stub-unwrap"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            exists = status == 200
            return {
                "app_id": app_id,
                "url": url,
                "http_status": status,
                "exists": exists,
                "reason": "ok" if exists else f"HTTP {status}",
            }
    except urllib.error.HTTPError as exc:
        return {
            "app_id": app_id,
            "url": url,
            "http_status": exc.code,
            "exists": False,
            "reason": f"HTTP {exc.code}",
        }
    except (urllib.error.URLError, TimeoutError) as exc:
        return {
            "app_id": app_id,
            "url": url,
            "http_status": None,
            "exists": False,
            "reason": f"unreachable: {exc}",
        }


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("app_id", type=int, help="Steam AppID (positive int)")
    ap.add_argument(
        "dst_dir", nargs="?", default=".",
        help="Directory to write steam_appid.txt to (default: cwd)",
    )
    ap.add_argument(
        "--verify", action="store_true",
        help="Probe store.steampowered.com instead of writing the file",
    )
    args = ap.parse_args()
    if args.verify:
        import json
        result = verify_app_id(args.app_id)
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if result["exists"] else 1
    p = drop_side_file(args.app_id, args.dst_dir)
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
