"""Lightweight Reference Runner (scripts/issue_runner.py).

Demonstrates the end-to-end mechanical feedback loop:
1. Accept task / issue ref
2. Execute action / model task
3. Run mechanical gate stack (fast_gate, secrets_pre_tool, validation)
4. Translate verbose errors into high-signal LLM diagnostics on failure
5. Repeat feedback loop until clean pass or retry threshold reached
6. Finalize & merge on all-green
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from scripts.error_translator import translate_output

log = logging.getLogger("issue_runner")


@dataclass(frozen=True)
class IssueTask:
    task_id: str
    description: str
    target_files: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    task_id: str
    passed: bool
    attempts: int
    diagnostics: list[str] = field(default_factory=list)
    output: str = ""


class MechanicalGateRunner:
    """Executes Layer 1 and Layer 2 mechanical gates on target files."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()

    def check_file(self, rel_path: str) -> tuple[bool, str]:
        """Run fast gate and static checks on target file."""
        abs_path = self.repo_root / rel_path
        if not abs_path.exists():
            return False, f"[ERROR] {rel_path} does not exist"

        # 1. Secrets Pre-tool Sweep
        secrets_script = self.repo_root / "plugins" / "hooks" / "scripts" / "secrets_pre_tool.py"
        if secrets_script.exists():
            payload = json.dumps(
                {"tool_input": {"file_path": rel_path, "new_string": abs_path.read_text()}}
            )
            res = subprocess.run(
                [sys.executable, str(secrets_script)],
                input=payload,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 2:
                return False, translate_output(res.stderr, tool_hint="secrets")

        # 2. Fast Gate Dispatcher
        fast_gate_script = self.repo_root / "plugins" / "hooks" / "scripts" / "fast_gate.py"
        if fast_gate_script.exists():
            payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": rel_path}})
            res = subprocess.run(
                [sys.executable, str(fast_gate_script)],
                input=payload,
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 2:
                diag = translate_output(res.stderr or res.stdout, tool_hint="ruff")
                return False, diag or f"[ERROR] {rel_path} failed fast gate checks"

        return True, ""


class IssueRunner:
    """End-to-end mechanical feedback loop runner."""

    def __init__(
        self,
        gate_runner: MechanicalGateRunner | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.gate_runner = gate_runner or MechanicalGateRunner()
        self.max_attempts = max_attempts

    def run_task(
        self,
        task: IssueTask,
        executor_fn: Callable[[IssueTask, list[str]], str],
    ) -> RunResult:
        """Run feedback loop: executor -> gate check -> translate errors -> retry/pass."""
        history_diagnostics: list[str] = []

        for attempt in range(1, self.max_attempts + 1):
            log.info("Task %s: Attempt %d/%d", task.task_id, attempt, self.max_attempts)
            # Invoke executor (model or code patcher)
            output = executor_fn(task, history_diagnostics)

            # Mechanical gate evaluation on target files
            all_passed = True
            current_diagnostics: list[str] = []

            for rel_path in task.target_files:
                passed, diag = self.gate_runner.check_file(rel_path)
                if not passed:
                    all_passed = False
                    current_diagnostics.append(diag)

            if all_passed:
                log.info("Task %s: PASSED on attempt %d", task.task_id, attempt)
                return RunResult(
                    task_id=task.task_id,
                    passed=True,
                    attempts=attempt,
                    diagnostics=history_diagnostics,
                    output=output,
                )

            history_diagnostics.extend(current_diagnostics)

        log.warning("Task %s: FAILED after %d attempts", task.task_id, self.max_attempts)
        return RunResult(
            task_id=task.task_id,
            passed=False,
            attempts=self.max_attempts,
            diagnostics=history_diagnostics,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Heretek Mechanical Issue Runner")
    parser.add_argument("--task-id", default="demo-1", help="Task ID identifier")
    parser.add_argument("--description", default="Sample task description", help="Task prompt")
    parser.add_argument("--files", nargs="*", default=[], help="Target files to gate")
    args = parser.parse_args()

    task = IssueTask(task_id=args.task_id, description=args.description, target_files=args.files)
    runner = IssueRunner()

    def mock_executor(t: IssueTask, diags: list[str]) -> str:
        return f"Executed task {t.task_id} with {len(diags)} previous diagnostics"

    result = runner.run_task(task, mock_executor)
    print(
        json.dumps(
            {"task_id": result.task_id, "passed": result.passed, "attempts": result.attempts}
        )
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
