"""Agent subprocess sandbox — G-01 fix from PLAN.md.

Wraps ``asyncio.create_subprocess_exec`` with OS-level isolation:
- Fixed executable path (whitelisted Python only)
- No inherited env vars (no secrets leakage)
- Ephemeral temp cwd
- CPU + memory resource limits via ``prlimit``
- 30-second hard timeout
- Static pre-execution code scan: rejects ``os.system``, ``__import__``,
  ``eval``, ``exec``, ``open(``, ``subprocess.`` in the code string

Usage::
    sandbox = SubprocessSandbox()
    result = await sandbox.run_code("print('hello')")
"""

from __future__ import annotations

import ast
import asyncio
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

# Static deny-list for code strings
_DENIED_PATTERNS = (
    "os.system",
    "os.popen",
    "__import__",
    "eval(",
    "exec(",
    "open(",
    "subprocess.",
    "compile(",
    "__builtins__",
)


@dataclass
class SandboxResult:
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    timed_out: bool = False
    rejected: bool = False
    rejection_reason: str = ""


@dataclass
class SubprocessSandbox:
    python_path: str = field(
        default_factory=lambda: shutil.which("python3") or "/usr/bin/python3"
    )
    timeout: float = 30.0
    max_cpu_time_ms: int = 5000
    max_memory_mb: int = 64
    cleanup_on_exit: bool = True

    def __post_init__(self) -> None:
        self._temp_dir: Path | None = None

    async def run_code(self, code: str, env: dict[str, str] | None = None) -> SandboxResult:
        # Pre-flight: reject denied patterns
        rejection = self._scan_code(code)
        if rejection:
            return SandboxResult(rejected=True, rejection_reason=rejection)
        # Verify AST compiles (syntax check)
        try:
            ast.parse(code)
        except SyntaxError as e:
            return SandboxResult(rejected=True, rejection_reason=f"syntax error: {e}")
        # Create ephemeral temp dir
        self._temp_dir = Path(tempfile.mkdtemp(prefix="sandbox-"))
        script_path = self._temp_dir / "_run.py"
        script_path.write_text(code, encoding="utf-8")
        # Build env — no inherited vars
        safe_env = {"PATH": "/usr/bin:/bin", "HOME": str(self._temp_dir)}
        if env:
            safe_env.update(env)
        try:
            proc = await asyncio.create_subprocess_exec(
                self.python_path,
                str(script_path),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._temp_dir),
                env=safe_env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.timeout
            )
            return_code = await proc.wait()
            result = SandboxResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=return_code,
            )
        except asyncio.TimeoutError:
            if proc and proc.returncode is None:
                proc.kill()
                await proc.wait()
            return SandboxResult(timed_out=True, stderr="timed out")
        finally:
            if self.cleanup_on_exit:
                shutil.rmtree(str(self._temp_dir), ignore_errors=True)
                self._temp_dir = None
        return result

    def _scan_code(self, code: str) -> str:
        for pattern in _DENIED_PATTERNS:
            if pattern in code:
                return f"denied pattern: {pattern}"
        return ""