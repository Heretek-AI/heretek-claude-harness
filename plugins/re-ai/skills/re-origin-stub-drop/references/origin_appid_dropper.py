"""origin_appid_dropper.py — return the canonical "no side-file
convention" result for the managed-launcher store-gate.

Standalone helper for the re-origin-stub-drop skill. Mirrors
the shape of the Steam side-file dropper (so callers can
slam-substitute the two helpers) but returns the documented
absence of a Valve-style side-file convention.

Usage:
    python3 origin_appid_dropper.py [--verify <stub_id>]

The default behavior (no args) returns the canonical
"no side-file convention" dict. The --verify probe is a
no-op reachability test (the managed-launcher client has
no public URL surface; we return a documented "unreachable"
shape so the caller can branch on it).

Vendor-neutral: the response uses the B3 catalog entry's
category-only descriptors and avoids any product-name
literal that would trip the vendor-leakage NEEDLES list.
"""

from __future__ import annotations

import argparse
import json
import sys


def side_file_convention() -> dict:
    """Return the canonical "no side-file convention" dict.

    The managed-launcher store-gate category has no Valve-style
    side-file equivalent. The launcher client (a separate
    process from the game) holds the entitlement state in
    its own per-user store; the side-file step is a documented
    no-op for this category.

    Returns:
        {
            "side_file_convention": null,
            "reason": "managed launcher client holds entitlement
                       state in its own per-user store; no
                       Valve-style side-file applies",
            "fallback": "nop the entitlement call site (Step 5
                         of re-origin-stub-drop SKILL.md)",
            "category_descriptor": "managed launcher store-gate",
            "catalog_source": "data/drm-indicators.yaml::B3"
        }
    """
    return {
        "side_file_convention": None,
        "reason": (
            "managed launcher client holds entitlement state in its own "
            "per-user store; no Valve-style side-file applies"
        ),
        "fallback": (
            "nop the entitlement call site (Step 5 of "
            "re-origin-stub-drop SKILL.md)"
        ),
        "category_descriptor": "managed launcher store-gate",
        "catalog_source": "data/drm-indicators.yaml::B3",
    }


def verify_stub_id(stub_id: str) -> dict:
    """No-op reachability probe for the managed-launcher stub.

    The managed-launcher client has no public URL surface for
    entitlement lookups; the canonical answer is "unreachable
    by design". The dict shape is consistent with the Steam
    helper's verify_app_id() so the caller can branch on
    `exists`.

    Args:
        stub_id: any opaque identifier (kept for shape parity;
            not used in the probe).

    Returns:
        {
            "stub_id": <str>,
            "url": None,
            "http_status": None,
            "exists": False,
            "reason": "managed-launcher entitlement has no public
                       URL surface; entitlement is brokered in the
                       launcher client's per-user store"
        }
    """
    return {
        "stub_id": stub_id,
        "url": None,
        "http_status": None,
        "exists": False,
        "reason": (
            "managed-launcher entitlement has no public URL surface; "
            "entitlement is brokered in the launcher client's per-user "
            "store"
        ),
    }


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--verify", dest="stub_id", default=None,
        help="Run the no-op reachability probe with this stub id",
    )
    args = ap.parse_args()
    if args.stub_id is not None:
        result = verify_stub_id(args.stub_id)
    else:
        result = side_file_convention()
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
