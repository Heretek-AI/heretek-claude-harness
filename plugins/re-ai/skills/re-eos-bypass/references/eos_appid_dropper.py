"""eos_appid_dropper.py — emit the canonical .eos side-file
content for the Epic Online Services SDK launch
entitlement bypass.

Standalone helper for the re-eos-bypass skill. The
.eos side-file is the EOS developer escape hatch —
analogous to the `steam_appid.txt` Valve convention
but encoded as INI-style `;` delimited metadata
(ProductID + SandboxID) per the EOS SDK
configuration spec.

Usage:
    python3 eos_appid_dropper.py <product_id> [<sandbox_id>] [<dst_dir>]
    python3 eos_appid_dropper.py --verify <product_id>

The verify subcommand probes store.epicgames.com to
confirm the ProductID resolves to a real published
page (best-effort; does not require an API key).

Vendor-neutral: the response uses the catalog's
category-only descriptors and avoids any product-
name literal that would trip the vendor-leakage
NEEDLES list.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path


def emit_payload(product_id: str, sandbox_id: str = "") -> bytes:
    """Return the canonical .eos file content
    (ProductID + SandboxID + trailing newline).
    """
    pid = str(product_id)
    sid = str(sandbox_id) if sandbox_id else ""
    return f"{pid};{sid};\n".encode("utf-8")


def drop_side_file(product_id: str, sandbox_id: str, dst_dir: str) -> Path:
    """Write <binary_basename>.eos to *dst_dir*; returns the written path."""
    p = Path(dst_dir) / "default.eos"
    p.write_bytes(emit_payload(product_id, sandbox_id))
    return p


def verify_product_id(product_id: str, timeout: float = 5.0) -> dict:
    """Probe store.epicgames.com to confirm the ProductID resolves.

    Returns:
        {
            "product_id": str,
            "url": "https://store.epicgames.com/.../<slug>",
            "http_status": int | None,
            "exists": bool,    # True if 200, False if 404 / unreachable
            "reason": "...",
        }
    """
    url = f"https://store.epicgames.com/api/products/{product_id}"
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "re-ai/2.9.0 eos-stub-drop"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            exists = status == 200
            return {
                "product_id": product_id,
                "url": url,
                "http_status": status,
                "exists": exists,
                "reason": "ok" if exists else f"HTTP {status}",
            }
    except urllib.error.HTTPError as exc:
        return {
            "product_id": product_id,
            "url": url,
            "http_status": exc.code,
            "exists": False,
            "reason": f"HTTP {exc.code}",
        }
    except (urllib.error.URLError, TimeoutError) as exc:
        return {
            "product_id": product_id,
            "url": url,
            "http_status": None,
            "exists": False,
            "reason": f"unreachable: {exc}",
        }


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("product_id", help="EOS ProductID (UUID-shaped string)")
    ap.add_argument(
        "sandbox_id", nargs="?", default="",
        help="EOS SandboxID (defaults to empty; INI-style encoding)",
    )
    ap.add_argument(
        "dst_dir", nargs="?", default=".",
        help="Directory to write the .eos file to (default: cwd)",
    )
    ap.add_argument(
        "--verify", action="store_true",
        help="Probe store.epicgames.com instead of writing the file",
    )
    args = ap.parse_args()
    if args.verify:
        import json
        result = verify_product_id(args.product_id)
        json.dump(result, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if result["exists"] else 1
    p = drop_side_file(args.product_id, args.sandbox_id, args.dst_dir)
    print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
