"""Layer 2 LLM-judge for evaluation bundles.

Evaluates trial outputs and patch diffs against expected rubric criteria.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast


def stub_judge(eval_input: dict[str, Any], patch_diff: str) -> dict[str, Any]:
    """Execute LLM-judge verification on evaluation bundle.

    Args:
        eval_input: Dict loaded from eval_input.json.
        patch_diff: String patch diff content.

    Returns:
        Dict containing judge evaluation verdict and calibration status.
    """
    expected = eval_input.get("expected")
    expected_dict = cast("dict[str, Any]", expected) if isinstance(expected, dict) else {}
    rubric = expected_dict.get("rubric")
    rubric_dict = cast("dict[str, Any]", rubric) if isinstance(rubric, dict) else {}

    return {
        "fixture": eval_input.get("fixture"),
        "layer": "stub",
        "verdict": "pass" if patch_diff.strip() else "fail",
        "calibration_required": True,
        "rubric_prompt": rubric_dict.get("llm_judge_prompt"),
    }


def main() -> int:
    """CLI entrypoint for LLM-judge."""
    p = argparse.ArgumentParser(description="Layer 2 LLM-judge")
    p.add_argument("bundle_dir", type=Path)
    args = p.parse_args()

    raw_eval: Any = json.loads((args.bundle_dir / "eval_input.json").read_text())
    eval_input = cast("dict[str, Any]", raw_eval) if isinstance(raw_eval, dict) else {}
    patch_diff = (args.bundle_dir / "patch.diff").read_text()

    result = stub_judge(eval_input, patch_diff)
    (args.bundle_dir / "result-llm.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
