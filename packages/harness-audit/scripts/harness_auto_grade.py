"""Layer 1 auto-grade: deterministic checks against eval_input.json.

Reads eval_input.json (from sub-spec 2) + the patch.diff. Verifies sha256
integrity, runs auto-grade criteria from expected.auto_grade, writes
result.json. Refuses mismatched hashes.

Entry: scripts/harness_auto_grade.py <bundle-dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def compute_sha256(text: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def auto_grade(
    eval_input: dict[str, Any],
    *,
    patch_diff: str | None = None,
    expected_sha: str | None = None,
) -> dict[str, Any]:
    """Run deterministic auto-grade checks. Returns result dict with verdict."""
    if expected_sha is not None:
        actual_sha = compute_sha256(patch_diff or "")
        if actual_sha != expected_sha:
            raise ValueError(f"sha256 mismatch: expected {expected_sha}, got {actual_sha}")

    criteria = eval_input.get("expected", {}).get("auto_grade", {})
    checks: dict[str, Any] = {}

    if "patch_diff_max_bytes" in criteria:
        size = len(patch_diff or "")
        checks["patch_diff_bytes"] = size
        checks["patch_diff_max_bytes"] = criteria["patch_diff_max_bytes"]
        checks["patch_diff_under_limit"] = size <= criteria["patch_diff_max_bytes"]

    if "patch_diff_min_bytes" in criteria:
        size = len(patch_diff or "")
        checks["patch_diff_min_bytes"] = criteria["patch_diff_min_bytes"]
        checks["patch_diff_over_min"] = size >= criteria["patch_diff_min_bytes"]

    if "files_changed_required" in criteria:
        changed = []
        for line in (patch_diff or "").splitlines():
            if line.startswith("+++ b/"):
                changed.append(line[6:])
        missing = set(criteria["files_changed_required"]) - set(changed)
        checks["files_changed_required"] = criteria["files_changed_required"]
        checks["files_changed_actual"] = changed
        checks["files_changed_missing"] = list(missing)

    if "metadata_keys_required" in criteria:
        metadata = eval_input.get("metadata", {})
        missing = set(criteria["metadata_keys_required"]) - set(metadata.keys())
        checks["metadata_keys_required"] = criteria["metadata_keys_required"]
        checks["metadata_keys_missing"] = list(missing)

    verdict = (
        "pass"
        if all(v for k, v in checks.items() if isinstance(v, bool))
        and not any(
            checks.get(k)
            for k in ("files_changed_missing", "metadata_keys_missing")
            if checks.get(k)
        )
        else "fail"
    )

    return {"fixture": eval_input.get("fixture"), "verdict": verdict, "checks": checks}


def main() -> int:
    p = argparse.ArgumentParser(description="Layer 1 auto-grade")
    p.add_argument("bundle_dir", type=Path)
    args = p.parse_args()

    eval_input = json.loads((args.bundle_dir / "eval_input.json").read_text())
    patch_diff = (args.bundle_dir / "patch.diff").read_text()

    actual_sha = compute_sha256(patch_diff)
    if actual_sha != eval_input["patch_diff_sha256"]:
        print(
            f"sha256 mismatch: {actual_sha} != {eval_input['patch_diff_sha256']}", file=sys.stderr
        )
        return 1

    result = auto_grade(eval_input, patch_diff=patch_diff)
    (args.bundle_dir / "result.json").write_text(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
