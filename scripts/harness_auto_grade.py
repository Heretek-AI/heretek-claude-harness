"""Layer 1 auto-grade: deterministic checks against eval_input.json.

Reads `eval_input.json` + `patch.diff`. Verifies SHA-256 integrity,
runs auto-grade criteria from `expected.auto_grade`, and writes `result.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast


def compute_sha256(text: str) -> str:
    """Compute SHA-256 hex digest of a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def auto_grade(
    eval_input: dict[str, Any],
    *,
    patch_diff: str | None = None,
    expected_sha: str | None = None,
) -> dict[str, Any]:
    """Run deterministic auto-grade checks.

    Args:
        eval_input: Dict loaded from eval_input.json.
        patch_diff: Optional string containing patch diff content.
        expected_sha: Optional SHA-256 digest string to verify.

    Returns:
        Dict containing evaluation verdict and detailed check results.

    Raises:
        ValueError: If SHA-256 digest mismatches expected_sha.
    """
    if expected_sha is not None:
        actual_sha = compute_sha256(patch_diff or "")
        if actual_sha != expected_sha:
            raise ValueError(f"sha256 mismatch: expected {expected_sha}, got {actual_sha}")

    expected_val = eval_input.get("expected")
    expected_dict = cast("dict[str, Any]", expected_val) if isinstance(expected_val, dict) else {}
    criteria_val = expected_dict.get("auto_grade")
    criteria = cast("dict[str, Any]", criteria_val) if isinstance(criteria_val, dict) else {}
    checks: dict[str, Any] = {}

    if "patch_diff_max_bytes" in criteria:
        max_bytes = criteria["patch_diff_max_bytes"]
        if isinstance(max_bytes, (int, float)):
            size = len(patch_diff or "")
            checks["patch_diff_bytes"] = size
            checks["patch_diff_max_bytes"] = int(max_bytes)
            checks["patch_diff_under_limit"] = size <= int(max_bytes)

    if "patch_diff_min_bytes" in criteria:
        min_bytes = criteria["patch_diff_min_bytes"]
        if isinstance(min_bytes, (int, float)):
            size = len(patch_diff or "")
            checks["patch_diff_min_bytes"] = int(min_bytes)
            checks["patch_diff_over_min"] = size >= int(min_bytes)

    if "files_changed_required" in criteria:
        req_files_raw = criteria["files_changed_required"]
        if isinstance(req_files_raw, list):
            req_files = cast("list[Any]", req_files_raw)
            req_set: set[str] = {str(f) for f in req_files}
            changed: list[str] = []
            for line in (patch_diff or "").splitlines():
                if line.startswith("+++ b/"):
                    changed.append(line[6:])
            missing = req_set - set(changed)
            checks["files_changed_required"] = sorted(req_set)
            checks["files_changed_actual"] = changed
            checks["files_changed_missing"] = sorted(missing)

    if "metadata_keys_required" in criteria:
        req_keys_raw = criteria["metadata_keys_required"]
        if isinstance(req_keys_raw, list):
            req_keys = cast("list[Any]", req_keys_raw)
            req_key_set: set[str] = {str(k) for k in req_keys}
            metadata = eval_input.get("metadata")
            metadata_dict = cast("dict[str, Any]", metadata) if isinstance(metadata, dict) else {}
            missing_keys = req_key_set - set(metadata_dict.keys())
            checks["metadata_keys_required"] = sorted(req_key_set)
            checks["metadata_keys_missing"] = sorted(missing_keys)

    bool_checks: list[bool] = [v for v in checks.values() if isinstance(v, bool)]
    missing_files_val = checks.get("files_changed_missing")
    missing_files: list[str] = (
        cast("list[str]", missing_files_val) if isinstance(missing_files_val, list) else []
    )
    missing_meta_val = checks.get("metadata_keys_missing")
    missing_meta: list[str] = (
        cast("list[str]", missing_meta_val) if isinstance(missing_meta_val, list) else []
    )

    verdict = (
        "pass"
        if all(bool_checks) and len(missing_files) == 0 and len(missing_meta) == 0
        else "fail"
    )

    return {"fixture": eval_input.get("fixture"), "verdict": verdict, "checks": checks}


def main() -> int:
    """CLI entrypoint for auto-grader."""
    p = argparse.ArgumentParser(description="Layer 1 auto-grade")
    p.add_argument("bundle_dir", type=Path)
    args = p.parse_args()

    raw_eval: Any = json.loads((args.bundle_dir / "eval_input.json").read_text())
    eval_input = cast("dict[str, Any]", raw_eval) if isinstance(raw_eval, dict) else {}
    patch_diff = (args.bundle_dir / "patch.diff").read_text()

    actual_sha = compute_sha256(patch_diff)
    expected_sha = eval_input.get("patch_diff_sha256")
    if expected_sha and actual_sha != str(expected_sha):
        print(f"sha256 mismatch: {actual_sha} != {expected_sha}", file=sys.stderr)
        return 1

    result = auto_grade(eval_input, patch_diff=patch_diff)
    (args.bundle_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0 if result["verdict"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
