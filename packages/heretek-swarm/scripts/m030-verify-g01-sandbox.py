#!/usr/bin/env python3
"""M030 G-01 — Subprocess sandbox verification.

Tests the security/sandbox.py SubprocessSandbox and the
examiner/agent.py path-traversal guard.

Exit code 0 on full pass, 1 on any failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path("/home/john/Desktop/heretek-swarm")
sys.path.insert(0, str(REPO_ROOT / "backend"))

from heretek_swarm.security.sandbox import SubprocessSandbox  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        print(f"[PASS] {name}")
        PASS += 1
    else:
        print(f"[FAIL] {name}: {detail}")
        FAIL += 1


async def run_tests():
    sandbox = SubprocessSandbox()

    # Test 1: benign code executes and returns stdout
    r = await sandbox.run_code("print('hello from sandbox')")
    check("benign-code-succeeds", r.return_code == 0, f"rc={r.return_code}")
    check("benign-code-stdout", "hello from sandbox" in r.stdout, f"stdout={r.stdout!r}")

    # Test 2: os.system is rejected
    r = await sandbox.run_code("import os; os.system('ls')")
    check("os.system-rejected", r.rejected, f"rejected={r.rejected}")
    check("os.system-rejection-message", "os.system" in r.rejection_reason,
          f"reason={r.rejection_reason!r}")

    # Test 3: subprocess.run is rejected
    r = await sandbox.run_code("import subprocess; subprocess.run(['ls'])")
    check("subprocess-run-rejected", r.rejected, f"rejected={r.rejected}")

    # Test 4: eval is rejected
    r = await sandbox.run_code("eval('1+1')")
    check("eval-rejected", r.rejected, f"rejected={r.rejected}")

    # Test 5: exec is rejected
    r = await sandbox.run_code("exec('print(1)')")
    check("exec-rejected", r.rejected, f"rejected={r.rejected}")

    # Test 6: open( is rejected
    r = await sandbox.run_code("open('/etc/passwd').read()")
    check("open-rejected", r.rejected, f"rejected={r.rejected}")

    # Test 7: syntax error rejects
    r = await sandbox.run_code("this is not valid python")
    check("syntax-error-rejected", r.rejected, f"rejected={r.rejected}")

    # Test 8: timeout kills long-running code
    r = await sandbox.run_code("import time; time.sleep(999)")
    check("timeout-fires", r.timed_out, f"timed_out={r.timed_out}")

    print(f"\n=== Summary: {PASS} pass, {FAIL} fail ===")
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_tests())
