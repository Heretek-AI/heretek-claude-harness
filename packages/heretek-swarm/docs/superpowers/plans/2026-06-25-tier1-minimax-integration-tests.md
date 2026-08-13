# Tier 1 MiniMax Integration Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add live + recorded integration test coverage for the MiniMax provider in `tier1/llm/garage.py`, env-gated behind `MINIMAX_API_KEY`, with cassette scrubbing to prevent credential leaks.

**Architecture:** Two-tier test directory `tests/integration/` with `smoke/` (live-only, env-gated) and `behavior/` (vcrpy cassette replay). Top-level `conftest.py` provides env-gating fixtures. New `tier1-integration.yml` GitHub workflow runs marked tests on main-merge with the secret. Cassette safety + marker leak checks live in `tests/unit/` and run on every PR.

**Tech Stack:** pytest 8+, vcrpy 6+, openai SDK 1+, GitHub Actions, hatchling. No frontend changes.

## Global Constraints

- Working directory for all commands: `backend/tier1/` (matches existing `tier1-ci.yml` `defaults.run.working-directory`).
- All test files go under `backend/tier1/tests/integration/` and `backend/tier1/tests/unit/`.
- The MiniMax API base URL is `https://api.minimaxi.com/v1` (default in `tier1/config.py`).
- The MiniMax API key env var is `TIER1_MINIMAX_API_KEY` (pydantic-settings `env_prefix="TIER1_"` on `minimax_api_key`).
- Cassettes are scrubbed of all `Authorization: Bearer *` headers → `Authorization: Bearer REDACTED` on record.
- `pyproject.toml` addopts changes from `-v --cov=tier1 ...` to `-v --cov=tier1 ... -m "not integration"` so PR CI stays fast.
- Marker override: integration workflow runs `pytest -m integration` explicitly.
- Python 3.11. Project layout: `tier1/` package, `tests/` sibling.

## File Structure

**Modify:**
- `backend/tier1/pyproject.toml` — add `vcrpy` dev dep, add `markers` config, prepend `-m "not integration"` to `addopts`.

**Create:**
- `backend/tier1/tests/integration/__init__.py` — empty package marker.
- `backend/tier1/tests/integration/conftest.py` — env-gating fixtures: `minimax_api_key`, `require_minimax_key`, `cassette_dir`, `record_mode`.
- `backend/tier1/tests/integration/behavior/__init__.py` — empty.
- `backend/tier1/tests/integration/behavior/conftest.py` — vcrpy config with auth scrubbing and `vcr_cassette` fixture.
- `backend/tier1/tests/integration/behavior/test_minimax_behavior.py` — 4 behavior tests (always replay).
- `backend/tier1/tests/integration/smoke/__init__.py` — empty.
- `backend/tier1/tests/integration/smoke/test_minimax_smoke.py` — 2 smoke tests (live, env-gated).
- `backend/tier1/tests/integration/behavior/cassettes/` — directory for YAML cassettes (committed, scrubbed).
- `.github/workflows/tier1-integration.yml` — runs marked tests with `TIER1_MINIMAX_API_KEY` secret.
- `backend/tier1/tests/unit/test_cassette_safety.py` — scrub check (no live keys in cassettes).
- `backend/tier1/tests/unit/test_markers.py` — every test under `tests/integration/` is marked.

**Generated at runtime (recorded against live MiniMax):**
- `backend/tier1/tests/integration/behavior/cassettes/test_minimax_stream_tokens.yaml`
- `backend/tier1/tests/integration/behavior/cassettes/test_minimax_monotonic_seq.yaml`
- `backend/tier1/tests/integration/behavior/cassettes/test_minimax_empty_stream.yaml`
- `backend/tier1/tests/integration/behavior/cassettes/test_minimax_error_response.yaml`

---

## Task 1: Add vcrpy dependency and pytest markers

**Files:**
- Modify: `backend/tier1/pyproject.toml:30-51`

**Step 1: Add `vcrpy` to dev dependencies**

Edit `backend/tier1/pyproject.toml`. In the `[project.optional-dependencies].dev` list, after `"docker>=7.1"`, add `"vcrpy>=6.0"`. Final list:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "freezegun>=1.4",
    "ruff>=0.4",
    "mypy>=1.10",
    "respx>=0.21",
    "docker>=7.1",
    "vcrpy>=6.0",
]
```

**Step 2: Add pytest marker registration**

Replace the `[tool.pytest.ini_options]` block (lines 48-51) with:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-v --cov=tier1 --cov-report=term-missing --cov-fail-under=80 -m 'not integration'"
markers = [
    "integration: real-provider tests, env-gated; skipped by default in PR CI",
]
```

**Step 3: Install the new dep**

Run:
```bash
cd backend/tier1 && source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: install completes, `vcr` importable:
```bash
cd backend/tier1 && source .venv/bin/activate && python -c "import vcr; print(vcr.__version__)"
```
Prints version ≥ 6.0.

**Step 4: Verify pytest still runs unit tests**

Run:
```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/ -q
```

Expected: 104 passed, 12 skipped (existing baseline).

**Step 5: Commit**

```bash
cd backend/tier1 && git add pyproject.toml && git commit -m "build(tier1): add vcrpy dev dep + integration marker filter"
```

---

## Task 2: Create `tests/integration/` scaffolding and env-gating conftest

**Files:**
- Create: `backend/tier1/tests/integration/__init__.py`
- Create: `backend/tier1/tests/integration/conftest.py`

**Step 1: Create empty package marker**

Write `backend/tier1/tests/integration/__init__.py`:
```python
"""Integration tests for Tier 1 — env-gated, slow, hit real services."""
```

**Step 2: Create env-gating conftest**

Write `backend/tier1/tests/integration/conftest.py`:
```python
"""Shared fixtures for integration tests.

Skips smoke tests when MINIMAX_API_KEY is unset. Behavior tests are not
skipped here — they replay cassettes and always run.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


# pydantic-settings prefix: TIER1_MINIMAX_API_KEY
MINIMAX_ENV_VAR = "TIER1_MINIMAX_API_KEY"

CASSETTE_DIR = Path(__file__).parent / "behavior" / "cassettes"


@pytest.fixture(scope="session")
def cassette_dir() -> Path:
    """Directory where vcrpy cassettes are stored."""
    CASSETTE_DIR.mkdir(parents=True, exist_ok=True)
    return CASSETTE_DIR


@pytest.fixture(scope="session")
def record_mode() -> str:
    """`record` when RECORD_MINIMAX=1, else `none` (replay-only).

    Replay-only mode means missing cassettes fail loudly in CI rather than
    silently auto-recording against a real API.
    """
    return "record" if os.environ.get("RECORD_MINIMAX") == "1" else "none"


@pytest.fixture(scope="session")
def minimax_api_key() -> str | None:
    """The MiniMax API key, or None if not configured."""
    return os.environ.get(MINIMAX_ENV_VAR)


@pytest.fixture()
def require_minimax_key(minimax_api_key: str | None) -> str:
    """Skip the test if `TIER1_MINIMAX_API_KEY` is not set.

    Used by smoke tests that hit the live API. Behavior tests use the
    cassette fixture instead and don't need a live key.
    """
    if not minimax_api_key:
        pytest.skip(f"{MINIMAX_ENV_VAR} not set; skipping live integration test")
    return minimax_api_key
```

**Step 3: Verify conftest imports cleanly**

Run:
```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/integration/ --collect-only -q
```

Expected: "no tests ran" or "0 collected" (no tests yet, but no errors).

**Step 4: Commit**

```bash
cd backend/tier1 && git add tests/integration/__init__.py tests/integration/conftest.py && git commit -m "test(tier1): scaffold integration/ with env-gating fixtures"
```

---

## Task 3: Create `behavior/` conftest with vcrpy + auth scrubbing

**Files:**
- Create: `backend/tier1/tests/integration/behavior/__init__.py`
- Create: `backend/tier1/tests/integration/behavior/conftest.py`

**Step 1: Create behavior package marker**

Write `backend/tier1/tests/integration/behavior/__init__.py`:
```python
"""Behavior tests: replay recorded vcrpy cassettes to pin the SDK contract."""
```

**Step 2: Create behavior conftest with vcrpy config and auth scrubbing**

Write `backend/tier1/tests/integration/behavior/conftest.py`:
```python
"""vcrpy configuration for behavior tests.

Patches the openai SDK's HTTP transport. Cassettes are committed to the
repo (scrubbed of auth headers) so PR CI replays them without secrets.

Refresh a cassette:
    rm tests/integration/behavior/cassettes/test_foo.yaml
    RECORD_MINIMAX=1 TIER1_MINIMAX_API_KEY=<key> pytest tests/integration/behavior/test_foo.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
import vcr


# vcrpy cassettes are matched on method + URI. We filter Authorization
# so matches work even when the cassette is replayed in an environment
# with a different (or no) live key.
_AUTH_HEADER_FILTER = ("authorization",)
_OPENAI_BETA_HEADER_FILTER = ("x-stainless-raw-response", "x-stainless-raw-request")


def _scrub_request(request: vcr.request.Request) -> vcr.request.Request:
    """Replace live Authorization header values with REDACTED on record.

    Runs only when recording. On replay, vcrpy injects the recorded value
    verbatim — this scrubber doesn't fire.
    """
    auth = request.headers.get("authorization")
    if auth:
        request.headers["authorization"] = "Bearer REDACTED"
    return request


@pytest.fixture()
def vcr_cassette(cassette_dir: Path, record_mode: str, request: pytest.FixtureRequest) -> vcr.use_cassette:
    """A `vcr.use_cassette` context manager bound to the test's cassette file."""
    cassette_name = f"{request.node.name}.yaml"
    cassette_path = cassette_dir / cassette_name
    return vcr.use_cassette(
        str(cassette_path),
        record_mode=record_mode,
        filter_headers=_AUTH_HEADER_FILTER + _OPENAI_BETA_HEADER_FILTER,
        before_record_request=_scrub_request,
        match_on=["method", "scheme", "host", "port", "path", "query"],
    )
```

**Step 3: Verify vcr import + fixture discovery**

Run:
```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/integration/behavior/ --collect-only -q
```

Expected: "no tests ran" or "0 collected".

**Step 4: Commit**

```bash
cd backend/tier1 && git add tests/integration/behavior/ && git commit -m "test(tier1): behavior/ conftest with vcrpy + auth scrubbing"
```

---

## Task 4: Record initial MiniMax cassettes

**Files:**
- Create: `backend/tier1/tests/integration/behavior/cassettes/test_minimax_stream_tokens.yaml`
- Create: `backend/tier1/tests/integration/behavior/cassettes/test_minimax_monotonic_seq.yaml`
- Create: `backend/tier1/tests/integration/behavior/cassettes/test_minimax_empty_stream.yaml`
- Create: `backend/tier1/tests/integration/behavior/cassettes/test_minimax_error_response.yaml`

**This task requires a real `TIER1_MINIMAX_API_KEY`. If you don't have one, skip this task — behavior tests will fail until cassettes are recorded. Do not commit live credentials.**

**Step 1: Verify key is available**

Run:
```bash
echo "$TIER1_MINIMAX_API_KEY" | wc -c
```

Expected: count > 1 (env var set). If empty, stop and obtain a key.

**Step 2: Write the behavior test file first** (creates test names for cassettes)

Write `backend/tier1/tests/integration/behavior/test_minimax_behavior.py`:
```python
"""Behavior tests for MiniMax provider (replay via vcrpy cassettes)."""

from __future__ import annotations

import pytest

from tier1.config import Settings
from tier1.llm.garage import ModelGarage


def _settings() -> Settings:
    """Test settings — base_url pinned to production MiniMax API."""
    return Settings(minimax_api_key="sk-cassette-replay-not-live")


@pytest.fixture()
def garage() -> ModelGarage:
    return ModelGarage(_settings())


async def test_minimax_stream_tokens(garage: ModelGarage, vcr_cassette):
    """Smoke shape: at least one token comes back, has agent + seq."""
    async with vcr_cassette:
        chunks = []
        async for c in garage._stream_openai_provider("say hi", "alpha", "minimax"):
            chunks.append(c)
    assert len(chunks) >= 1
    assert all(c.agent == "alpha" for c in chunks)
    assert all(isinstance(c.token, str) and c.token for c in chunks)
    assert all(c.seq == i for i, c in enumerate(chunks))


async def test_minimax_monotonic_seq(garage: ModelGarage, vcr_cassette):
    """seq counter increments 0, 1, 2, … across the stream."""
    async with vcr_cassette:
        seqs = []
        async for c in garage._stream_openai_provider("count to 3", "beta", "minimax"):
            seqs.append(c.seq)
    assert seqs == list(range(len(seqs)))
    assert len(seqs) >= 1


async def test_minimax_empty_stream(garage: ModelGarage, vcr_cassette):
    """A response with no content chunks yields no StreamChunks."""
    async with vcr_cassette:
        chunks = []
        async for c in garage._stream_openai_provider("respond-empty-marker", "alpha", "minimax"):
            chunks.append(c)
    assert chunks == []


async def test_minimax_error_response(garage: ModelGarage, vcr_cassette):
    """A 401 from MiniMax raises LLMUnavailable, not a generic exception."""
    from tier1.llm.errors import LLMUnavailable

    async with vcr_cassette:
        with pytest.raises(LLMUnavailable):
            async for _ in garage._stream_openai_provider("trigger-401", "alpha", "minimax"):
                pass
```

**Step 3: Record cassettes**

For each test, run with `RECORD_MINIMAX=1` to capture the live exchange. The cassette file is named after the test:

```bash
cd backend/tier1 && source .venv/bin/activate
RECORD_MINIMAX=1 TIER1_MINIMAX_API_KEY=<your-key> pytest tests/integration/behavior/test_minimax_behavior.py::test_minimax_stream_tokens -v
RECORD_MINIMAX=1 TIER1_MINIMAX_API_KEY=<your-key> pytest tests/integration/behavior/test_minimax_behavior.py::test_minimax_monotonic_seq -v
RECORD_MINIMAX=1 TIER1_MINIMAX_API_KEY=<your-key> pytest tests/integration/behavior/test_minimax_behavior.py::test_minimax_empty_stream -v
RECORD_MINIMAX=1 TIER1_MINIMAX_API_KEY=<your-key> pytest tests/integration/behavior/test_minimax_behavior.py::test_minimax_error_response -v
```

**Step 4: Verify cassettes are scrubbed**

Run:
```bash
cd backend/tier1 && grep -l "Bearer sk-" tests/integration/behavior/cassettes/ || echo "OK: no live keys"
```

Expected: `OK: no live keys`. If it prints a filename, the scrubber failed — open the cassette and replace `Bearer sk-...` with `Bearer REDACTED` manually.

**Step 5: Verify cassettes replay without a live key**

Run (without `TIER1_MINIMAX_API_KEY`):
```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/integration/behavior/ -v
```

Expected: all 4 tests pass (replay).

**Step 6: Commit**

```bash
cd backend/tier1 && git add tests/integration/behavior/ && git commit -m "test(tier1): record MiniMax behavior cassettes (4 tests)"
```

---

## Task 5: Create smoke tests (live-only, env-gated)

**Files:**
- Create: `backend/tier1/tests/integration/smoke/__init__.py`
- Create: `backend/tier1/tests/integration/smoke/test_minimax_smoke.py`

**Step 1: Create smoke package marker**

Write `backend/tier1/tests/integration/smoke/__init__.py`:
```python
"""Smoke tests: live API calls, env-gated, no cassette replay."""
```

**Step 2: Write smoke tests**

Write `backend/tier1/tests/integration/smoke/test_minimax_smoke.py`:
```python
"""Live MiniMax smoke tests. Skip when TIER1_MINIMAX_API_KEY is unset.

These tests prove the SDK + key + base_url still work against the real API.
They're slow and incur cost — only run on main-merge or manual trigger.
"""

from __future__ import annotations

from tier1.config import Settings
from tier1.llm.garage import ModelGarage


def _settings(key: str) -> Settings:
    return Settings(minimax_api_key=key)


@pytest.fixture()
def garage(require_minimax_key: str) -> ModelGarage:
    """Garage with the live key from the env var."""
    return ModelGarage(_settings(require_minimax_key))


async def test_smoke_returns_tokens(garage: ModelGarage):
    """A trivial prompt yields at least one token chunk with the expected shape."""
    chunks = []
    async for c in garage._stream_openai_provider("say hi", "alpha", "minimax"):
        chunks.append(c)
    assert len(chunks) >= 1, "no tokens returned from MiniMax"
    first = chunks[0]
    assert isinstance(first.token, str) and first.token
    assert first.agent == "alpha"
    assert first.seq == 0
    # Monotonic seq
    assert all(c.seq == i for i, c in enumerate(chunks))


async def test_smoke_uses_minimax_url(garage: ModelGarage):
    """Verify base_url in the live client matches the configured MiniMax URL."""
    # Patch AsyncOpenAI to capture the constructed client and inspect its base_url.
    from openai import AsyncOpenAI
    captured: dict[str, object] = {}

    real_init = AsyncOpenAI.__init__

    def spy_init(self, **kwargs):
        captured.update(kwargs)
        real_init(self, **kwargs)

    AsyncOpenAI.__init__ = spy_init  # type: ignore[method-assign]
    try:
        async for _ in garage._stream_openai_provider("ping", "alpha", "minimax"):
            pass
    finally:
        AsyncOpenAI.__init__ = real_init  # type: ignore[method-assign]

    settings = garage.settings
    assert captured.get("api_key") == settings.minimax_api_key
    assert captured.get("base_url") == settings.minimax_base_url
    assert "minimaxi.com" in str(captured.get("base_url"))
```

**Step 3: Verify smoke tests skip without key, pass with key**

Run without key:
```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/integration/smoke/ -v
```

Expected: `2 skipped`.

Run with key (only if you have one):
```bash
cd backend/tier1 && source .venv/bin/activate && TIER1_MINIMAX_API_KEY=<key> pytest tests/integration/smoke/ -v
```

Expected: 2 passed.

**Step 4: Commit**

```bash
cd backend/tier1 && git add tests/integration/smoke/ && git commit -m "test(tier1): smoke tests for MiniMax (env-gated, live)"
```

---

## Task 6: Add cassette safety unit test

**Files:**
- Create: `backend/tier1/tests/unit/test_cassette_safety.py`

**Step 1: Write the test**

Write `backend/tier1/tests/unit/test_cassette_safety.py`:
```python
"""Safety net: detect leaked credentials in committed vcrpy cassettes.

A leaked live API key in git is a security incident. This test fails
loudly if any cassette file contains a recognizable live key pattern.

Live key patterns covered:
- OpenAI-style: `sk-` followed by 20+ alphanumeric chars (also MiniMax)
- Anthropic-style: `sk-ant-` followed by 20+ chars
- Bearer header with non-REDACTED value
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

CASSETTE_DIR = Path(__file__).parent.parent / "integration" / "behavior" / "cassettes"

# Live credential patterns (case-sensitive).
LIVE_KEY_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
]

# Bearer header that is NOT the safe "REDACTED" placeholder.
BEARER_LIVE = re.compile(r"[Aa]uthorization:\s*Bearer\s+(?!REDACTED$)[A-Za-z0-9_\-\.]{8,}")


@pytest.fixture(scope="module")
def cassette_files() -> list[Path]:
    if not CASSETTE_DIR.exists():
        return []
    return list(CASSETTE_DIR.glob("*.yaml"))


def test_no_live_keys_in_cassettes(cassette_files: list[Path]):
    """No cassette file should contain a recognizable live API key."""
    if not cassette_files:
        pytest.skip(f"no cassettes found at {CASSETTE_DIR}")
    violations: list[str] = []
    for path in cassette_files:
        text = path.read_text(encoding="utf-8")
        for pat in LIVE_KEY_PATTERNS:
            for match in pat.finditer(text):
                violations.append(f"{path.name}: live key pattern matched: {match.group(0)[:12]}…")
    assert not violations, "leaked credentials detected:\n" + "\n".join(violations)


def test_no_live_bearer_headers(cassette_files: list[Path]):
    """No cassette file should contain a Bearer header with a non-REDACTED token."""
    if not cassette_files:
        pytest.skip(f"no cassettes found at {CASSETTE_DIR}")
    violations: list[str] = []
    for path in cassette_files:
        text = path.read_text(encoding="utf-8")
        for match in BEARER_LIVE.finditer(text):
            violations.append(f"{path.name}: live bearer header: {match.group(0)[:30]}…")
    assert not violations, "leaked bearer headers detected:\n" + "\n".join(violations)
```

**Step 2: Run the test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_cassette_safety.py -v
```

Expected: 2 passed (or 2 skipped if no cassettes exist yet).

**Step 3: Commit**

```bash
cd backend/tier1 && git add tests/unit/test_cassette_safety.py && git commit -m "test(tier1): cassette safety — detect leaked live credentials"
```

---

## Task 7: Add marker leak detection unit test

**Files:**
- Create: `backend/tier1/tests/unit/test_markers.py`

**Step 1: Write the test**

Write `backend/tier1/tests/unit/test_markers.py`:
```python
"""Marker leak check: every test under tests/integration/ must be marked @pytest.mark.integration.

Without this check, an unmarked test would silently slip into PR CI and
slow it down (or hit the live API unexpectedly).
"""

from __future__ import annotations

from pathlib import Path

import pytest

INTEGRATION_DIR = Path(__file__).parent.parent / "integration"


@pytest.fixture(scope="module")
def integration_test_files() -> list[Path]:
    if not INTEGRATION_DIR.exists():
        return []
    return [p for p in INTEGRATION_DIR.rglob("test_*.py")]


def test_every_integration_test_is_marked(integration_test_files: list[Path]):
    """Every test_* function in tests/integration/ must have @pytest.mark.integration."""
    if not integration_test_files:
        pytest.skip(f"no integration tests found at {INTEGRATION_DIR}")
    unmarked: list[str] = []
    for path in integration_test_files:
        text = path.read_text(encoding="utf-8")
        # Naive AST-free scan: split into test definitions and check for marker.
        # We treat the test as "marked" if `pytest.mark.integration` appears
        # in the surrounding decorators above the `def test_` line.
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("def test_") or stripped.startswith("async def test_"):
                # Walk backwards to find decorators.
                preceding = "\n".join(lines[max(0, i - 12):i])
                if "pytest.mark.integration" not in preceding:
                    unmarked.append(f"{path.name}:{i + 1}: {stripped}")
    assert not unmarked, "unmarked integration tests found:\n" + "\n".join(unmarked)
```

**Step 2: Run the test**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_markers.py -v
```

Expected: skipped (no integration tests yet) or 1 passed (once behavior/smoke tests exist in Tasks 4 and 5).

**Step 3: Commit**

```bash
cd backend/tier1 && git add tests/unit/test_markers.py && git commit -m "test(tier1): marker leak check — all integration tests must be marked"
```

---

## Task 8: Create `tier1-integration.yml` workflow

**Files:**
- Create: `.github/workflows/tier1-integration.yml`

**Step 1: Write the workflow**

Write `.github/workflows/tier1-integration.yml`:
```yaml
name: tier1-integration
on:
  push:
    branches: [main]
    paths:
      - "backend/tier1/**"
      - ".github/workflows/tier1-integration.yml"
  workflow_dispatch:
  schedule:
    # Nightly 06:00 UTC.
    - cron: "0 6 * * *"

jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: tier1
          POSTGRES_PASSWORD: tier1
          POSTGRES_DB: tier1
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U tier1"
          --health-interval 5s --health-timeout 3s --health-retries 10
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s --health-timeout 3s --health-retries 10
      nats:
        image: nats:2.10-alpine
        ports: ["4222:4222"]

    defaults:
      run:
        working-directory: backend/tier1

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - name: Run integration tests (live MiniMax smoke + cassette replay)
        env:
          TIER1_MINIMAX_API_KEY: ${{ secrets.TIER1_MINIMAX_API_KEY }}
          TIER1_TEST_PG_DSN: postgresql://tier1:tier1@localhost:5432/tier1
          TIER1_TEST_REDIS_URL: redis://localhost:6379/0
          TIER1_TEST_NATS_URL: nats://localhost:4222
        run: pytest tests/ -v -m integration --no-cov
```

**Step 2: Verify YAML parses**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/tier1-integration.yml'))" && echo OK
```

Expected: `OK`.

**Step 3: Commit**

```bash
cd /home/john/Projects/heretek-swarm && git add .github/workflows/tier1-integration.yml && git commit -m "ci(tier1): add integration workflow (live MiniMax smoke + cassette replay)"
```

---

## Task 9: Final verification — full suite + coverage

**Files:** none

**Step 1: Run full test suite**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ -q
```

Expected: 110+ passed (current 104 + 2 smoke + 4 behavior), some skipped (smoke without key, possibly marker/safety checks if no cassettes), coverage ≥ 80%.

**Step 2: Run only integration marker**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ -v -m integration --no-cov
```

Expected: behavior tests pass (replay); smoke tests skipped (no key in local env).

**Step 3: Run only unit tests (PR CI mode)**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/ -v -m "not integration" --no-cov
```

Expected: all existing tests pass, integration tests excluded.

**Step 4: Verify cassette safety**

```bash
cd backend/tier1 && source .venv/bin/activate && pytest tests/unit/test_cassette_safety.py tests/unit/test_markers.py -v
```

Expected: 3+ passed (or skipped if no cassettes).

**Step 5: Verify clean grep for any committed live key**

```bash
cd backend/tier1 && grep -rE "(sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9_\-]{20,})" tests/integration/ || echo "OK: no live keys"
```

Expected: `OK: no live keys`.

**Step 6: Report**

If all steps pass: integration test coverage for MiniMax is in place. PR CI stays fast (no live API calls); main-merge CI runs the full integration suite with the secret.

If anything fails: fix the failing step and re-run from that step. Do not skip verifications.
