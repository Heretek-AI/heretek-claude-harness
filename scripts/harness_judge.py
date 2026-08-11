"""Layer 2 LLM-judge. STUB for v3.5 sprint — calibration is a follow-up.

Returns a deterministic stub verdict. Real implementation will call the
claude API with the rubric prompt from eval_input.expected.rubric.llm_judge_prompt.

Entry: scripts/harness_judge.py <bundle-dir>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def stub_judge(eval_input: dict[str, Any], patch_diff: str) -> dict[str, Any]:
    """Stub: pass if diff is non-empty, fail otherwise. Calibration is follow-up."""
    return {
        "fixture": eval_input.get("fixture"),
        "layer": "stub",
        "verdict": "pass" if patch_diff.strip() else "fail",
        "calibration_required": True,
        "rubric_prompt": eval_input.get("expected", {}).get("rubric", {}).get("llm_judge_prompt"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Layer 2 LLM-judge (stub)")
    p.add_argument("bundle_dir", type=Path)
    args = p.parse_args()

    eval_input = json.loads((args.bundle_dir / "eval_input.json").read_text())
    patch_diff = (args.bundle_dir / "patch.diff").read_text()

    result = stub_judge(eval_input, patch_diff)
    (args.bundle_dir / "result-llm.json").write_text(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
