"""Tests for security/sandbox.py — SubprocessSandbox (G-01)."""

import pytest

from heretek_swarm.security.sandbox import SubprocessSandbox


@pytest.mark.asyncio
class TestSubprocessSandbox:
    async def test_benign_code_succeeds(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("print('hello')")
        assert r.return_code == 0
        assert "hello" in r.stdout

    async def test_os_system_rejected(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("import os; os.system('ls')")
        assert r.rejected
        assert "os.system" in r.rejection_reason

    async def test_subprocess_run_rejected(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("import subprocess; subprocess.run(['ls'])")
        assert r.rejected

    async def test_eval_rejected(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("eval('1+1')")
        assert r.rejected

    async def test_exec_rejected(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("exec('print(1)')")
        assert r.rejected

    async def test_open_rejected(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("open('/etc/passwd').read()")
        assert r.rejected

    async def test_syntax_error_rejected(self):
        sandbox = SubprocessSandbox()
        r = await sandbox.run_code("not valid python")
        assert r.rejected

    async def test_timeout_kills_long_running_code(self):
        sandbox = SubprocessSandbox(timeout=2.0)
        r = await sandbox.run_code("import time; time.sleep(999)")
        assert r.timed_out
