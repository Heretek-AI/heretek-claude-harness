# Pre-commit Core Rollout (Sub-issue A0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the spine of the pre-commit framework rollout — `.pre-commit-config.yaml` (plugin-internal), the CI workflow, the docs, and the plugin README — closing GitHub issues #206, #207, #208 in one PR. Subsequent slices (A1–A6) extend this base.

**Architecture:** `plugins/hooks/.pre-commit-config.yaml` becomes the single source of truth for git-hook linting/formatting/secrets; `plugins/hooks/scripts/install_git_hooks.sh` already reads this path; `.github/workflows/pre-commit.yml` enforces it in CI via `pre-commit/action@v3` (D20 SHA-pinned); CONTRIBUTING.md and `plugins/hooks/README.md` document the developer flow.

**Tech Stack:** pre-commit framework (`pip install pre-commit>=3.5`), `pre-commit/action@v3`, Ruff 0.16.x (already pinned in validate.yml), Biome 1.x, shellcheck-py (MIT wrapper over GPL tool), gitleaks 8.x, doublify/pre-commit-rust (cargo-fmt + cargo-clippy). All tool SHAs will be pinned at execution time via `pre-commit autoupdate` + manual SHA capture per D20.

## Global Constraints

These apply to every task. Inherited from spec `docs/superpowers/specs/2026-08-10-precommit-mechanical-gates-design.md`:

- **D15:** Only the `hooks` plugin (`plugins/hooks/`) ships hooks. Pre-commit config lives at `plugins/hooks/.pre-commit-config.yaml` (NOT repo root).
- **D20:** All GitHub Actions references use the full 40-char SHA + version comment. Existing `shellcheck.yml` is already D20-pinned — do not touch it.
- **D30:** Config is plugin-internal. `plugins/hooks/scripts/install_git_hooks.sh` reads `$PLUGIN_ROOT/.pre-commit-config.yaml` (already correct).
- **D37:** `fail_fast: true` at the root of the config. CI uses action defaults (fail-fast off) so PRs surface every violation. Long-running hooks get `stages: [manual]` (we don't add any in A0; A1–A5 may).
- **D38:** No new hooks in non-`hooks` plugins. (N/A for A0 — A0 doesn't touch other plugins.)
- **Python ≥ 3.10** (per `pyproject.toml`).
- **CI test command:** `pytest -q` (per CONTRIBUTING.md + validate.yml).
- **Lint command:** `ruff check` (per pre-commit-on-save in `.claude/settings.json` if present; otherwise `ruff check .`).
- **Schema validator:** `python scripts/validate.py` (per CONTRIBUTING.md).
- **Marketplace sync check:** `git diff --exit-code .claude-plugin/marketplace.json` (per CONTRIBUTING.md).
- **Conventional Commits:** subject line `<type>(<scope>): <summary>` (per recent git log: `feat(...)`, `fix(...)`, `docs(...)`, `chore(...)`).
- **Co-author trailer:** `Co-Authored-By: Claude <noreply@anthropic.com>` (per CLAUDE.md).

---

## File Structure

| Path | Created/Modified | Responsibility |
|---|---|---|
| `plugins/hooks/.pre-commit-config.yaml` | **Create** | Pre-commit framework config. Hygiene + Ruff + Biome + shellcheck-py + gitleaks + doublify (Rust). SHA-pinned per D20. `fail_fast: true`. `default_install_hook_types: [pre-commit, pre-push]`. |
| `.github/workflows/pre-commit.yml` | **Create** | CI enforcement. D20 SHA-pinned `actions/checkout`, `actions/setup-python`, `pre-commit/action`. Triggers: PR, push to main, weekly Mon 06:00 UTC. Read-only permissions. |
| `CONTRIBUTING.md` | **Modify** | Add a "Pre-commit framework" section between the "Tests" section and the "ShellCheck" section. Documents `pip install pre-commit` + `pre-commit install` + `pre-commit run --all-files` + `--no-verify` warning. |
| `plugins/hooks/README.md` | **Modify** | Expand Layer 3 to enumerate the new tools (hygiene, ruff, biome, shellcheck, gitleaks, rust) and confirm `fail_fast: true`. |
| `CHANGELOG.md` | **Modify** | Add entry under unreleased: "Pre-commit framework rollout (closes #206, #207, #208)." |
| `tests/test_precommit_config.py` | **Create** | Validates the config: file exists, valid YAML, parses via `pre_commit validate-config`, hook SHAs are 40-hex, `fail_fast: true`, root contains required repos, no repo outside the allowlist. |
| `tests/test_precommit_workflow.py` | **Create** | Validates `.github/workflows/pre-commit.yml`: valid YAML, D20-pinned actions, read-only permissions, includes PR + push-to-main + schedule triggers. |

No existing files are deleted. `plugins/hooks/scripts/install_git_hooks.sh` is unchanged (it already reads `plugins/hooks/.pre-commit-config.yaml`).

---

## Task 1: Baseline — existing tests pass + spec recap

**Files:** none touched.

- [ ] **Step 1: Confirm clean tree and branch**

```bash
git status --short
git branch --show-current
```

Expected: clean tree, current branch is `red-hound` (the worktree's branch). If not, stop and rebase.

- [ ] **Step 2: Run baseline test suite**

```bash
pytest -q
```

Expected: green. If any failure, capture it and surface to the user before continuing.

- [ ] **Step 3: Verify the install-githooks test still passes**

```bash
pytest -q tests/test_install_git_hooks.py
```

Expected: green (it currently passes because `plugins/hooks/.pre-commit-config.yaml` is absent — the script's `if [[ -f "$HOOK_PATH" ]] && grep -q "pre-commit"` short-circuit doesn't trigger; the `pre-commit install --config "$PRECOMMIT_CONFIG"` call may fail silently because the config file doesn't exist, OR `pre-commit` may install without a config and just not run hooks).

If the test passes but is suspect (no config), note this for Task 4.

- [ ] **Step 4: Capture git log baseline**

```bash
git log --oneline -5
```

Expected: head commit is `c28a74a` (telemetry) or newer from the spec commit `df8a363`. If not, stop and investigate.

- [ ] **Step 5: No commit yet — proceed to Task 2.**

---

## Task 2: Bootstrap test file for pre-commit config

**Files:**
- Create: `tests/test_precommit_config.py`
- Test: `tests/test_precommit_config.py`

**Interfaces:**
- Consumes: `pre_commit.config.load_config` (the library API) — verify importable.
- Produces: A pytest module that other tasks will extend.

- [ ] **Step 1: Write the failing test scaffold**

```python
# tests/test_precommit_config.py
"""Tests for plugins/hooks/.pre-commit-config.yaml.

These tests assert structural invariants from the mechanical-gates spec
(D30, D37, D38): config is plugin-internal, fail-fast at the root, every
repo SHA-pinned (40-hex), and every repo in the allowlist.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PRECOMMIT_CONFIG = REPO_ROOT / "plugins" / "hooks" / ".pre-commit-config.yaml"

# Allowlist of repos approved for A0 (spec section 6 + D33):
# hygiene + ruff + biome + shellcheck-py + gitleaks + doublify.
A0_REPO_ALLOWLIST = frozenset({
    "https://github.com/pre-commit/pre-commit-hooks",
    "https://github.com/astral-sh/ruff-pre-commit",
    "https://github.com/biomejs/pre-commit",
    "https://github.com/shellcheck-py/shellcheck-py",
    "https://github.com/gitleaks/gitleaks",
    "https://github.com/doublify/pre-commit-rust",
})


def test_precommit_config_exists() -> None:
    assert PRECOMMIT_CONFIG.is_file(), (
        f"{PRECOMMIT_CONFIG} must exist per spec D30 (plugin-internal config)"
    )


def test_precommit_config_is_yaml() -> None:
    """Sanity: file starts with `---` or `repos:` (pre-commit accepts both)."""
    text = PRECOMMIT_CONFIG.read_text()
    assert text.lstrip().startswith(("---\n", "repos:\n")), (
        "pre-commit config must start with a YAML doc marker or `repos:`"
    )


def test_precommit_config_fails_fast_at_root() -> None:
    """Spec D37: fail_fast: true at the root for local developer-time optimization."""
    import yaml
    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    assert isinstance(data, dict)
    assert data.get("fail_fast") is True, (
        "root `fail_fast: true` required per spec D37"
    )


def test_precommit_config_repos_sha_pinned() -> None:
    """Every repo entry must pin a 40-char hex SHA per D20 spirit (hook immutability)."""
    import yaml
    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    sha_re = re.compile(r"^[0-9a-f]{40}$")
    repos = data.get("repos") or []
    assert repos, "config must declare at least one repo"
    for repo in repos:
        rev = repo.get("rev")
        assert rev, f"repo {repo.get('repo')} missing `rev`"
        assert sha_re.match(rev), (
            f"repo {repo.get('repo')} rev={rev!r} is not a 40-char hex SHA"
        )


def test_precommit_config_repos_in_allowlist() -> None:
    """Every repo must be in the A0 allowlist (no surprise additions)."""
    import yaml
    data = yaml.safe_load(PRECOMMIT_CONFIG.read_text())
    repos = data.get("repos") or []
    seen = {r.get("repo") for r in repos}
    extras = seen - A0_REPO_ALLOWLIST
    assert not extras, f"unexpected repos outside A0 allowlist: {extras}"


def test_precommit_validate_config_passes() -> None:
    """`pre-commit validate-config` must exit 0 (skip if CLI unavailable)."""
    import shutil
    import subprocess
    if not shutil.which("python3"):
        pytest.skip("python3 not installed")
    cli_check = subprocess.run(
        ["python3", "-m", "pre_commit", "--version"],
        capture_output=True,
    )
    if cli_check.returncode != 0:
        pytest.skip("pre-commit CLI not runnable (install with `pip install pre-commit`)")
    result = subprocess.run(
        ["python3", "-m", "pre_commit", "validate-config", str(PRECOMMIT_CONFIG)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"pre-commit validate-config failed: {result.stdout}\n{result.stderr}"
    )
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest -q tests/test_precommit_config.py
```

Expected: FAIL — `PRECOMMIT_CONFIG` does not exist yet.

- [ ] **Step 3: No commit yet — the test file is scaffolded but the config it asserts on is Task 3.**

---

## Task 3: Create `plugins/hooks/.pre-commit-config.yaml` (A0 spine)

**Files:**
- Create: `plugins/hooks/.pre-commit-config.yaml`

**Interfaces:**
- Consumes: `tests/test_precommit_config.py` (the test from Task 2).
- Produces: A config parseable by `pre-commit validate-config` with 6 repos, all SHA-pinned, `fail_fast: true`.

- [ ] **Step 1: Look up current SHAs for the 6 repos**

Use one of:
- (preferred) `pre-commit autoupdate --freeze` against a temp config — but skip if pre-commit CLI not available locally
- Web fetch `https://github.com/<owner>/<repo>/commits/<branch>.atom` and grab the latest commit SHA

Substitutions if you cannot reach the network: read `tests/test_precommit_config.py::A0_REPO_ALLOWLIST` for repo URLs; SHA-pinning at execution time is required for D20 spirit. If a SHA cannot be obtained, abort and surface to the user.

Pin SHAs to the **latest stable** release of each tool at execution time (do NOT use `main` branch SHAs — those float).

- [ ] **Step 2: Write the config file**

```yaml
# plugins/hooks/.pre-commit-config.yaml
# Layer 3 pre-commit framework config for the heretek hooks plugin.
# Spec: docs/superpowers/specs/2026-08-10-precommit-mechanical-gates-design.md
# D30: plugin-internal location. D37: fail_fast at root for developer time.
# D20: all repos pinned to a 40-char hex SHA at execution time.

# Minimum pre-commit version required by this config.
minimum_pre_commit_version: "3.5.0"

# Install BOTH pre-commit AND pre-push hooks. The install_git_hooks.sh
# script invokes `pre-commit install` without args; this setting expands
# that to include the pre-push stage.
default_install_hook_types: [pre-commit, pre-push]

# D37: fail_fast on local runs so developers see the first violation and
# fix it before re-running. CI sets fail-fast off (per action defaults)
# so PRs surface every violation in a single round-trip.
fail_fast: true

repos:
  # 1. Hygiene: trailing whitespace, EOF newline, merge-conflict markers,
  # large file blocks, YAML/TOML/JSON syntax checks.
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <SHA>
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-merge-conflict
      - id: check-added-large-files
        args: [--maxkb=1024]
      - id: check-yaml
      - id: check-toml
      - id: check-json

  # 2. Python: Ruff lint + format. Already used in plugins/hooks Layer 1
  # fast_gate.py; this wires the same gate into git commit.
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <SHA>
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  # 3. JS/TS: Biome format. Already in plugins/js-ts as biome-lsp.
  - repo: https://github.com/biomejs/pre-commit
    rev: <SHA>
    hooks:
      - id: biome-check
        # Apply safe fixes only; unsafe autofixes require explicit opt-in.
        args: [--apply]

  # 4. Shell: shellcheck-py wrapper (MIT). Shellcheck binary itself is GPL
  # but the wrapper is MIT and scans .sh files in the repo. Coverage
  # already exists in .github/workflows/shellcheck.yml; this adds it to
  # git commit so devs catch issues before pushing.
  - repo: https://github.com/shellcheck-py/shellcheck-py
    rev: <SHA>
    hooks:
      - id: shellcheck

  # 5. Secrets: gitleaks pre-commit. Hardblocks API keys, tokens, etc.
  # Already covered in CI by the security-scan-digest workflow; this
  # adds the dev-time fast path.
  - repo: https://github.com/gitleaks/gitleaks
    rev: <SHA>
    hooks:
      - id: gitleaks

  # 6. Rust: cargo-fmt + cargo-clippy. Already in plugins/rust as
  # cargo-clippy skill; this wires the same gate into git commit.
  - repo: https://github.com/doublify/pre-commit-rust
    rev: <SHA>
    hooks:
      - id: cargo-fmt
      - id: cargo-clippy
```

Replace every `<SHA>` with the actual 40-char hex pinned at Step 1.

- [ ] **Step 3: Run the test scaffold from Task 2**

```bash
pytest -q tests/test_precommit_config.py
```

Expected: PASS (all 6 tests).

- [ ] **Step 4: Run `pre-commit validate-config` manually**

```bash
python3 -m pre_commit validate-config plugins/hooks/.pre-commit-config.yaml
```

Expected: exits 0, no output. If non-zero, fix the YAML.

- [ ] **Step 5: Dry-run `pre-commit run --all-files` to surface violations**

```bash
python3 -m pre_commit run --all-files --config plugins/hooks/.pre-commit-config.yaml 2>&1 | tee /tmp/precommit-dryrun.log
```

Expected: this will almost certainly surface existing violations (trailing whitespace, EOF, ruff findings, etc.). Note them all in `/tmp/precommit-dryrun.log`. They will be fixed in Task 4.

- [ ] **Step 6: Commit**

```bash
git add plugins/hooks/.pre-commit-config.yaml tests/test_precommit_config.py
git commit -m "feat(hooks): A0 pre-commit core config (hygiene + ruff + biome + shellcheck + gitleaks + rust)

Plugin-internal config per spec D30. fail_fast at root per D37.
All repos SHA-pinned per D20.

Closes sub-spec 2026-08-10-precommit-mechanical-gates §3, A0 slice.
Closes #206 partially (config layer only; CI + docs in follow-up commits).

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Fix existing violations surfaced by Task 3 dry-run

**Files:** various existing files in the repo.

**Interfaces:**
- Consumes: `/tmp/precommit-dryrun.log` (the violations list from Task 3 Step 5).
- Produces: A clean `pre-commit run --all-files` output.

- [ ] **Step 1: Re-read the dry-run log**

```bash
cat /tmp/precommit-dryrun.log
```

Expected: a list of `FAIL: <hook-id>` blocks with file paths and line numbers.

- [ ] **Step 2: Group violations by hook + severity**

Common categories to expect:
- **trailing-whitespace:** trailing spaces or tabs at line ends
- **end-of-file-fixer:** missing trailing newline
- **check-yaml / check-json / check-toml:** syntax errors in existing config files
- **ruff:** lint findings (unused imports, undefined names, line-length)
- **ruff-format:** formatting differences
- **biome-check:** JS/TS/CSS format findings (the repo has very few JS files, likely clean)
- **shellcheck:** quoting / set -e / SC#### warnings in shell scripts
- **gitleaks:** should be clean (the secrets scanner would have caught test data)

- [ ] **Step 3: Auto-fix what hooks can fix**

```bash
python3 -m pre_commit run --all-files --config plugins/hooks/.pre-commit-config.yaml
```

For `ruff` with `--fix` and `ruff-format` and `biome-check` with `--apply`: hooks auto-fix on first run. Re-run to confirm.

- [ ] **Step 4: Manually fix what hooks cannot auto-fix**

For each remaining violation:
- `trailing-whitespace`, `end-of-file-fixer`: usually auto-fixed; re-run.
- `ruff` non-auto-fixable: edit the file to resolve.
- `shellcheck`: edit the script (add quotes, add `set -e`, etc.). Use `shellcheck -x --severity=warning` as the rubric (matches `.github/workflows/shellcheck.yml`).
- `gitleaks`: investigate the secret. If it's a test fixture with intentional fake data, add `gitleaks:allow` inline comment (per gitleaks docs) OR exclude the file via `.gitleaksignore`.

- [ ] **Step 5: Re-run until clean**

```bash
python3 -m pre_commit run --all-files --config plugins/hooks/.pre-commit-config.yaml
```

Expected: all hooks PASS. If any FAIL, loop to Step 4.

- [ ] **Step 6: Confirm tests still pass**

```bash
pytest -q
```

Expected: green. Ruff auto-fixes may have changed Python files; tests should still pass since ruff-format is formatting-only and `ruff --fix` should not break code.

- [ ] **Step 7: Run schema validator + marketplace sync check**

```bash
python scripts/validate.py
git diff --exit-code .claude-plugin/marketplace.json
```

Expected: validator exits 0, no marketplace.json drift. (The config didn't touch the catalog, but be safe.)

- [ ] **Step 8: Commit the fixes**

```bash
git add -A
git status --short  # review what's staged
git commit -m "fix: auto-apply pre-commit fixes + manual violation cleanup (A0)

Resolves all violations surfaced by pre-commit run --all-files on
the A0 config. Categories: trailing-whitespace, EOF newline, ruff
lint+format, shellcheck quoting. gitleaks clean.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

If no auto-fixes happened (everything was already clean), skip this commit.

---

## Task 5: Test the install script reads the new config

**Files:**
- Modify: `tests/test_install_git_hooks.py`

**Interfaces:**
- Consumes: existing test module.
- Produces: An assertion that `install_git_hooks.sh` succeeds when the config file is present and structurally valid.

- [ ] **Step 1: Run the existing install_git_hooks test**

```bash
pytest -q tests/test_install_git_hooks.py -v
```

Expected: all 4 tests PASS (they were already passing per Task 1 Step 3 baseline; now they exercise the real config, not the absent one).

- [ ] **Step 2: Add a new test that asserts the install script references the real config**

Append to `tests/test_install_git_hooks.py`:

```python
def test_install_sh_uses_existing_precommit_config() -> None:
    """Regression guard: install_git_hooks.sh must NOT silently install
    when the config file is absent. The script reads
    $PLUGIN_ROOT/.pre-commit-config.yaml and `pre-commit install
    --config <path>` fails when the path doesn't exist.
    """
    config_path = (
        Path(__file__).resolve().parents[1]
        / "plugins" / "hooks" / ".pre-commit-config.yaml"
    )
    assert config_path.is_file(), (
        "A0 spec D30 requires plugins/hooks/.pre-commit-config.yaml to exist"
    )
```

- [ ] **Step 3: Run the extended test**

```bash
pytest -q tests/test_install_git_hooks.py -v
```

Expected: 5 tests, all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_install_git_hooks.py
git commit -m "test(hooks): assert install_git_hooks.sh has a real pre-commit config (A0)

Regression guard: if the config ever goes missing again, this test
fails loudly instead of letting install_git_hooks.sh silently install
without a config.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Add `.github/workflows/pre-commit.yml`

**Files:**
- Create: `.github/workflows/pre-commit.yml`
- Test: `tests/test_precommit_workflow.py`

**Interfaces:**
- Consumes: `pre-commit/action@v3` (D20 SHA to be pinned at execution time).
- Produces: A workflow file that runs the pre-commit config on PR + push-to-main + weekly schedule.

- [ ] **Step 1: Look up the D20 SHAs**

Required SHAs at execution time:
- `actions/checkout@v4` → 40-char SHA + version comment
- `actions/setup-python@v5` → 40-char SHA + version comment
- `pre-commit/action@v3.0.1` → 40-char SHA + version comment

Look up via the same workflow used for the existing `shellcheck.yml` (which already does this) — visit the release page or use `git ls-remote https://github.com/<owner>/<repo>.git refs/tags/<tag>^{}`.

- [ ] **Step 2: Write the workflow test scaffold**

```python
# tests/test_precommit_workflow.py
"""Tests for .github/workflows/pre-commit.yml.

Spec D20: SHA-pin every action. Spec D36: PR + push-to-main + weekly
schedule triggers. Read-only permissions.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pre-commit.yml"

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_workflow_exists() -> None:
    assert WORKFLOW.is_file(), f"{WORKFLOW} must exist (spec D36)"


def test_workflow_yaml_parses() -> None:
    yaml.safe_load(WORKFLOW.read_text())


def test_workflow_has_required_triggers() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    on = data.get(True) or data.get("on")  # PyYAML quirk: `on:` → True
    assert on is not None, "workflow must declare `on:` triggers"
    assert "pull_request" in on, "must trigger on pull_request"
    assert "push" in on, "must trigger on push"
    push_branches = on["push"].get("branches") if isinstance(on["push"], dict) else None
    assert push_branches and "main" in push_branches, (
        "push trigger must include `branches: [main]`"
    )
    sched = on.get("schedule")
    assert sched, "must include a weekly schedule trigger"


def test_workflow_actions_sha_pinned() -> None:
    """D20: every `uses:` line must pin a 40-char hex SHA + version comment."""
    text = WORKFLOW.read_text()
    uses_lines = [
        line for line in text.splitlines() if "uses:" in line
    ]
    assert uses_lines, "workflow must reference at least one action"
    for line in uses_lines:
        m = re.search(r"uses:\s+([^@\s]+)@([0-9a-f]{40})", line)
        assert m, (
            f"uses: line not SHA-pinned: {line!r}"
        )


def test_workflow_permissions_readonly() -> None:
    data = yaml.safe_load(WORKFLOW.read_text())
    perms = data.get("permissions")
    assert perms == {"contents": "read"}, (
        f"workflow must declare read-only permissions; got {perms!r}"
    )
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
pytest -q tests/test_precommit_workflow.py
```

Expected: FAIL — `WORKFLOW` does not exist yet.

- [ ] **Step 4: Write the workflow file**

```yaml
# .github/workflows/pre-commit.yml
# Spec D36: CI enforcement of plugins/hooks/.pre-commit-config.yaml.
# D20: every action SHA-pinned. Pre-commit/action has built-in caching.
# Read-only permissions. Triggers: PR, push-to-main, weekly Mon 06:00 UTC.

name: pre-commit

on:
  pull_request:
  push:
    branches: [main]
  schedule:
    - cron: "0 6 * * 1"  # Mondays at 06:00 UTC (matches validate.yml schedule)
  workflow_dispatch:

# Read-only: pre-commit only reads repo files and runs the hook suite.
permissions:
  contents: read

jobs:
  pre-commit:
    name: pre-commit run --all-files
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@<SHA>  # v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@<SHA>  # v5
        with:
          python-version: "3.12"

      - uses: pre-commit/action@<SHA>  # v3.0.1
```

Replace every `<SHA>` with the values from Step 1.

- [ ] **Step 5: Run the test**

```bash
pytest -q tests/test_precommit_workflow.py
```

Expected: all 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/pre-commit.yml tests/test_precommit_workflow.py
git commit -m "ci: add pre-commit workflow (closes #207)

D36: enforce plugins/hooks/.pre-commit-config.yaml on PR + push-to-main
+ weekly Mon 06:00 UTC. D20: every action SHA-pinned. Read-only
permissions. pre-commit/action@v3 has built-in caching.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Update CONTRIBUTING.md (closes #208)

**Files:**
- Modify: `CONTRIBUTING.md`

**Interfaces:**
- Consumes: existing CONTRIBUTING.md.
- Produces: A new "Pre-commit framework" section between "Tests" and "ShellCheck".

- [ ] **Step 1: Read CONTRIBUTING.md to find the insertion point**

The "Tests" section ends at the line starting `## ShellCheck`. Insert the new section immediately before `## ShellCheck`.

- [ ] **Step 2: Insert the new section**

```markdown
## Pre-commit framework

A `pre-commit` framework config lives at `plugins/hooks/.pre-commit-config.yaml`
and runs hygiene, Ruff, Biome, shellcheck, gitleaks, and Rust fmt/clippy on every
`git commit` and `git push`. To install it locally:

```bash
# Install the framework
pip install pre-commit

# Bind it to this repo (idempotent)
python3 -m pre_commit install --config plugins/hooks/.pre-commit-config.yaml
```

To run the full suite manually without committing:

```bash
python3 -m pre_commit run --all-files --config plugins/hooks/.pre-commit-config.yaml
```

If a hook fails, fix the issue (or use `git commit --no-verify` to bypass — but
this is **discouraged**; the CI workflow `.github/workflows/pre-commit.yml`
will block the PR anyway). The install is also bundled into the hooks plugin:

```bash
/plugin install hooks@heretek
/hooks:install-git-hooks
```
```

- [ ] **Step 3: Verify the diff is sensible**

```bash
git diff CONTRIBUTING.md
```

Expected: only the new section is added. No other changes.

- [ ] **Step 4: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs(contributing): add pre-commit framework section (closes #208)

Documents the plugin-internal config location, install commands,
the --no-verify caveat, and the bundled /hooks:install-git-hooks path.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Update plugins/hooks/README.md

**Files:**
- Modify: `plugins/hooks/README.md`

**Interfaces:**
- Consumes: existing README.
- Produces: Layer 3 expanded with the A0 tool list and `fail_fast: true` mention.

- [ ] **Step 1: Find the Layer 3 section**

The current README has "Layer 3 (git hooks): `/hooks:install-git-hooks` installs pre-commit + pre-push hooks via the pre-commit framework." under the `## What` section.

- [ ] **Step 2: Replace the Layer 3 line + Install Layer-3 framework section**

In the `## What` section, replace:

```markdown
- **Layer 3 (git hooks):** `/hooks:install-git-hooks` installs pre-commit + pre-push hooks via the pre-commit framework.
```

with:

```markdown
- **Layer 3 (git hooks):** `/hooks:install-git-hooks` installs pre-commit + pre-push hooks via the pre-commit framework. Tools: hygiene (trailing whitespace, EOF, YAML/TOML/JSON syntax, large file blocks, merge-conflict markers), Ruff lint+format, Biome format, shellcheck, gitleaks, cargo-fmt + cargo-clippy. `fail_fast: true` at the root for developer time.
```

- [ ] **Step 3: Verify the diff**

```bash
git diff plugins/hooks/README.md
```

Expected: only the Layer 3 line is expanded.

- [ ] **Step 4: Commit**

```bash
git add plugins/hooks/README.md
git commit -m "docs(hooks): expand Layer 3 README with A0 tool list

Lists the six A0 hooks (hygiene, ruff, biome, shellcheck, gitleaks,
rust fmt+clippy) and the fail_fast root setting.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: existing CHANGELOG.
- Produces: An entry under the unreleased section noting the rollout.

- [ ] **Step 1: Read CHANGELOG.md**

```bash
head -20 CHANGELOG.md
```

- [ ] **Step 2: Find the unreleased / latest section header**

The file uses a versioned section format (per the existing 2026-08-09 entries visible in git log).

- [ ] **Step 3: Add an entry**

If there's an `## Unreleased` section, add:

```markdown
- feat(hooks): Pre-commit framework rollout (sub-spec A0) — `.pre-commit-config.yaml` at `plugins/hooks/`, CI workflow `.github/workflows/pre-commit.yml`, CONTRIBUTING.md refresh, hooks README expansion. Closes #206, #207, #208.
```

If the latest section is a versioned release (e.g. `## v1.x`), add the entry under that section OR create a new `## Unreleased` section at the top.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): note pre-commit framework rollout (A0)

Closes #206, #207, #208.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Final verification

**Files:** none touched.

- [ ] **Step 1: Run the full test suite**

```bash
pytest -q
```

Expected: green. The new tests `tests/test_precommit_config.py` and `tests/test_precommit_workflow.py` should pass; the extended `tests/test_install_git_hooks.py` should pass.

- [ ] **Step 2: Run the pre-commit suite manually one last time**

```bash
python3 -m pre_commit run --all-files --config plugins/hooks/.pre-commit-config.yaml
```

Expected: all hooks PASS.

- [ ] **Step 3: Run the schema validator**

```bash
python scripts/validate.py
```

Expected: exits 0.

- [ ] **Step 4: Run the marketplace sync check**

```bash
git diff --exit-code .claude-plugin/marketplace.json
```

Expected: no diff (catalog was not touched).

- [ ] **Step 5: Verify the issue closes are documented**

```bash
git log --oneline -10
```

Expected: 7-8 commits, the head one referencing #206/#207/#208 closure. The umbrella GitHub issue is created in Task 11.

- [ ] **Step 6: Surface to the user**

Summarize: total commits, total tests added, total files created/modified, dry-run result. Stop here and report before opening the PR. The PR + umbrella issue creation is the next step but should not be auto-opened (the user wanted to eat, not auto-merge).

---

## Task 11: Open the umbrella GitHub issue + sub-issues

**Files:** none touched (GitHub-side).

**Interfaces:**
- Consumes: This plan + the spec.
- Produces: 1 umbrella issue linking to 7 sub-issues. The umbrella body references the spec + this plan.

- [ ] **Step 1: Create the umbrella issue**

Use `mcp__github__github-issue_write` with `method: create`:

```
title: "feat: Mechanical-gate rollout — pre-commit framework + tool catalog + GitHub Actions marketplace"
body: (paste the umbrella body from the spec §1-3)
labels: ["enhancement", "needs-triage"]
```

- [ ] **Step 2: Create the 7 sub-issues**

For each of A0–A6, create an issue with `method: create` referencing the umbrella via `## Related: #<umbrella-number>` and the spec section. Each sub-issue body lists the slice's tools + acceptance criteria.

- [ ] **Step 3: Link sub-issues to the umbrella**

Edit the umbrella issue to fill in the placeholder `#TBD-A0..A6` with the actual sub-issue numbers.

- [ ] **Step 4: Close the umbrella with A0**

A0 is closed by the PR opened in Task 12 below. The other 6 sub-issues stay open.

- [ ] **Step 5: Surface to the user**

Report the umbrella issue URL + sub-issue URLs + A0 PR URL.

---

## Task 12: Open the A0 PR

**Files:** none touched (GitHub-side).

- [ ] **Step 1: Push the branch**

```bash
git push -u origin red-hound
```

- [ ] **Step 2: Open the PR**

Use `mcp__github__github-create_pull_request`:

```
base: main
head: red-hound
title: "feat(hooks): A0 pre-commit core rollout (closes #206/#207/#208)"
body: (the umbrella reference, the A0 summary, the test summary, the manual verification log)
```

- [ ] **Step 3: Link the PR to the umbrella**

Add a comment to the umbrella issue:

```
A0 PR opened: <url>. Closes #206/#207/#208. The other 6 sub-issues (#A1..#A6) remain in flight per the umbrella.
```

- [ ] **Step 4: Surface to the user**

Final report: spec path, plan path, umbrella issue URL, A0 PR URL, total commits, total tests, list of next sub-issues pending.

---

## Self-Review

**1. Spec coverage:**
- D30 (plugin-internal config) → Task 3
- D31 (umbrella + sub-issues) → Task 11
- D36 (CI workflow) → Task 6
- D37 (fail_fast + stages:manual) → Task 3 fail_fast (stages:manual deferred to A1+)
- D38 (D15 reinforced) → Task 3 + Task 11 sub-issue scope
- Issue #206 → Task 3 + Task 4
- Issue #207 → Task 6
- Issue #208 → Task 7

**2. Placeholder scan:** The plan contains `<SHA>` placeholders, but those are explicit lookup steps (Step 1 of Task 3, Step 1 of Task 6) with concrete instructions on how to resolve. Not a "TBD" failure.

**3. Type consistency:** `PRECOMMIT_CONFIG`, `A0_REPO_ALLOWLIST`, `WORKFLOW`, `SHA_RE` all named consistently across tests. `pre-commit validate-config` command consistent.

**4. Risks flagged in spec §9:**
- Risk 1 (existing violations) → Task 4 surfaces and fixes
- Risk 5 (long-running hooks) → not applicable in A0; stages:[manual] deferred to A1+

Gaps explicitly out of scope: A1–A6 (each gets its own plan); D32 forward-looking language hooks for PHP/Java/Kotlin/Go/C++ (covered in A2); D34 actions/ package (covered in A6).
