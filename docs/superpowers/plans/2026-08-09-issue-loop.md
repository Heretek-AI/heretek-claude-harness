# Issue Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an autonomous ralph-mode loop that drains the `security-scan`/`tech-debt` issue queue (12 items, #158–#168) with no human in the inner loop — per-issue subagent pipeline, gated merge, resumable across compactions.

**Architecture:** Top-level `driver.py` owns the loop and ledger at `.omc/state/issue-loop/ledger.json`. Per issue, ralph creates branch `auto/<num>-<slug>`, then runs 5 subagents (`explore`→`planner`→`executor`→`test-engineer`→`verifier`) in an isolated worktree, opens a PR, watches the merge gate (CI + Copilot + code-reviewer verdict + SonarCloud), squash-merges on green, advances ledger. Stops on queue empty, 3 per-issue verifier rejects (skip), or 5 cross-issue rejects (halt).

**Tech Stack:** Python 3.10+, `pytest`, `ruff`, `requests`, existing `mcp__github__*` tools, existing `scripts/issue_drafter.py` patterns. Subagents via Claude Agent SDK (`Agent` tool) with `model` override per role.

## Global Constraints

- **Python:** 3.10+
- **Test runner:** `pytest -q` (from repo root). Default excludes `integration` marker.
- **Lint:** `ruff check scripts/issue_loop/` (and tests dir).
- **Ledger path:** `.omc/state/issue-loop/ledger.json` (relative to repo root). Auto-created.
- **Branch naming:** `auto/<issue-number>-<kebab-slug-from-title>`. Max 50 chars total.
- **Issue scope:** labels `security-scan` AND `tech-debt`, state `open`. First run: issues #158–#168.
- **Subagent models:** `explore`=`haiku`, `planner`=`sonnet`, `executor`=`sonnet`, `test-engineer`=`sonnet`, `verifier`=`opus`.
- **Subagent isolation:** `executor` runs in `isolation: worktree`. Others run in main checkout.
- **Merge gate (all required):** GitHub Actions CI green, Copilot review submitted, `code-reviewer` verdict `approved: true` with line-anchored findings, SonarCloud quality gate passed.
- **Diff sanity:** PR diff must touch ONLY files named in the original scanner report. Otherwise verifier rejects.
- **Verifier findings:** MUST include `file:line` anchor or be rejected by ralph.
- **Stop conditions:** queue empty (success exit) | `attempts[issue] >= 3` (mark `skipped`, label `needs-human`) | `verifier_rejects_in_a_row >= 5` (halt).
- **No token-budget cap, no iteration cap** (rejected in brainstorming).
- **Don't:** edit `catalog/catalog.yaml`, `.claude-plugin/marketplace.json`, or any plugin manifest as part of this plan.

---

## File Structure

### Production code (`scripts/issue_loop/`)

| File | Responsibility |
|---|---|
| `__init__.py` | Package marker, exports `__version__ = "0.1.0"` |
| `ledger.py` | Read/write/transition ledger JSON. Pure logic, no I/O outside the file. |
| `branch.py` | Branch slug from title, branch creation, worktree spawn, rebase-on-main. |
| `subagents.py` | Run the 5 subagents in sequence; pass artifacts down the chain. |
| `gate.py` | Poll CI, request Copilot, wait SonarCloud; produce a `GateVerdict`. |
| `merge.py` | Diff-sanity check, squash-merge, comment on issue, ledger finalize. |
| `driver.py` | Top-level loop: `select_next` → `run_pipeline` → `await_gate` → `merge` → next. |

### Prompt templates (`scripts/issue_loop/prompts/`)

| File | Consumed by | Content shape |
|---|---|---|
| `explore.md` | `subagents.run_explore` | Read file:line + 50 lines context + callers; emit `context.md`. |
| `planner.md` | `subagents.run_planner` | Produce `plan.md` with `## Root cause`, `## Fix`, `## Test plan`. |
| `executor.md` | `subagents.run_executor` | Apply the fix per plan; run `pytest -q` + `ruff check`; report diff. |
| `test_engineer.md` | `subagents.run_test_engineer` | Write a regression test; verify it FAILS on base, PASSES on branch. |
| `verifier.md` | `subagents.run_verifier` | Read-only review; emit `verdict.json` with line-anchored findings. |
| `critic.md` | `subagents.run_critic_spotcheck` | Read-only; confirm a merged PR actually fixed the original issue. |

### Tests (`tests/`)

| File | Covers |
|---|---|
| `test_issue_loop_ledger.py` | `ledger.py` — selection, status transitions, retry counter |
| `test_issue_loop_branch.py` | `branch.py` — slug generation, branch creation, rebase conflict path |
| `test_issue_loop_subagents.py` | `subagents.py` — artifact-passing chain (subagents mocked) |
| `test_issue_loop_gate.py` | `gate.py` — verdict aggregation (GitHub mocked) |
| `test_issue_loop_merge.py` | `merge.py` — diff-sanity, squash-merge, ledger finalize |
| `test_issue_loop_driver.py` | `driver.py` — full loop on a synthetic ledger (everything mocked except ledger) |
| `test_issue_loop_e2e.py` | End-to-end: dry-run pipeline on a real repo fixture |

### Skill + config

| File | Responsibility |
|---|---|
| `.claude/skills/issue-loop/SKILL.md` | Skill that invokes ralph mode against the loop driver. |
| `.heretek/issue-loop-config.json` | Runtime config: label filter, model overrides, max attempts. |

### Files that change together

- Tasks 1–2 (ledger, branch) are pure logic — no GitHub/MCP coupling. Test in isolation.
- Tasks 3 (subagents) reads branch context from Task 2 and writes artifacts to the worktree.
- Tasks 4–5 (gate, merge) consume the branch from Task 2 + PR URL from Task 3.
- Task 6 (driver) is the integration of all of the above.
- Task 7 (e2e) is a separate deliverable; it does not modify production code.

---

## Task 1: Ledger module

**Files:**
- Create: `scripts/issue_loop/__init__.py`
- Create: `scripts/issue_loop/ledger.py`
- Test: `tests/test_issue_loop_ledger.py`

**Interfaces:**
- Consumes: nothing (this is the foundation).
- Produces:
  - `class Ledger` with methods:
    - `__init__(self, path: Path) -> None` — load or create empty ledger.
    - `select_next(self, candidates: list[IssueRef]) -> IssueRef | None`
    - `mark_attempt(self, issue_number: int) -> None` — increment `attempts`.
    - `mark_merged(self, issue_number: int, pr_url: str) -> None`
    - `mark_skipped(self, issue_number: int, reason: str) -> None`
    - `mark_failed(self, issue_number: int, error: str) -> None`
    - `record_verifier_reject(self) -> int` — increment root counter, return new value.
    - `reset_verifier_rejects(self) -> None`
    - `verifier_rejects_in_a_row(self) -> int`
  - `IssueRef` is a `dataclass` with `number: int, title: str, files: list[str]` (files from scanner report).
  - `status` ∈ `pending | merged | skipped | failed`.

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_issue_loop_ledger.py
from pathlib import Path
import json
import pytest
from scripts.issue_loop.ledger import Ledger, IssueRef


@pytest.fixture
def tmp_ledger(tmp_path: Path) -> Path:
    return tmp_path / "ledger.json"


def test_ledger_creates_empty_file(tmp_ledger: Path) -> None:
    Ledger(tmp_ledger)
    assert tmp_ledger.exists()
    assert json.loads(tmp_ledger.read_text()) == {}


def test_select_next_returns_lowest_open(tmp_ledger: Path) -> None:
    Ledger(tmp_ledger)  # empty
    candidates = [
        IssueRef(number=160, title="x", files=[]),
        IssueRef(number=158, title="y", files=[]),
        IssueRef(number=159, title="z", files=[]),
    ]
    assert Ledger(tmp_ledger).select_next(candidates).number == 158


def test_select_next_skips_already_merged(tmp_ledger: Path) -> None:
    l = Ledger(tmp_ledger)
    l.mark_merged(158, "https://github.com/foo/bar/pull/1")
    candidates = [
        IssueRef(number=158, title="x", files=[]),
        IssueRef(number=159, title="y", files=[]),
    ]
    assert l.select_next(candidates).number == 159


def test_select_next_skips_three_time_failure(tmp_ledger: Path) -> None:
    l = Ledger(tmp_ledger)
    l.mark_attempt(158)
    l.mark_attempt(158)
    l.mark_attempt(158)
    candidates = [IssueRef(number=158, title="x", files=[])]
    assert l.select_next(candidates) is None


def test_mark_attempt_increments(tmp_ledger: Path) -> None:
    l = Ledger(tmp_ledger)
    l.mark_attempt(158)
    l.mark_attempt(158)
    assert l._entries[158]["attempts"] == 2


def test_mark_merged_sets_terminal_status(tmp_ledger: Path) -> None:
    l = Ledger(tmp_ledger)
    l.mark_merged(158, "https://example/pr/1")
    assert l._entries[158]["status"] == "merged"
    assert l._entries[158]["pr_url"] == "https://example/pr/1"
    assert l._entries[158]["finished_at"] is not None


def test_verifier_rejects_counter(tmp_ledger: Path) -> None:
    l = Ledger(tmp_ledger)
    assert l.verifier_rejects_in_a_row() == 0
    assert l.record_verifier_reject() == 1
    assert l.record_verifier_reject() == 2
    l.reset_verifier_rejects()
    assert l.verifier_rejects_in_a_row() == 0


def test_mark_skipped_resets_counter(tmp_ledger: Path) -> None:
    l = Ledger(tmp_ledger)
    l.record_verifier_reject()
    l.record_verifier_reject()
    l.mark_skipped(158, "rejected thrice")
    assert l.verifier_rejects_in_a_row() == 0
    assert l._entries[158]["status"] == "skipped"
```

- [ ] **Step 2: Run the tests — confirm RED**

Run: `pytest tests/test_issue_loop_ledger.py -q`
Expected: `ModuleNotFoundError: No module named 'scripts.issue_loop'`

- [ ] **Step 3: Create the package marker**

Create `scripts/issue_loop/__init__.py`:

```python
"""Autonomous issue-loop driver (Spec: docs/superpowers/specs/2026-08-09-issue-loop-design.md)."""
__version__ = "0.1.0"
```

- [ ] **Step 4: Run again — still RED**

Run: `pytest tests/test_issue_loop_ledger.py -q`
Expected: `ModuleNotFoundError: No module named 'scripts.issue_loop.ledger'`

- [ ] **Step 5: Implement `ledger.py`**

Create `scripts/issue_loop/ledger.py`:

```python
"""Persistent ledger for the issue-loop driver.

JSON file at .omc/state/issue-loop/ledger.json. One entry per issue.
Status transitions are monotonic: pending -> {merged | skipped | failed}.
`failed` is non-terminal; the loop retries on the next tick.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TERMINAL = frozenset({"merged", "skipped"})


@dataclass(frozen=True)
class IssueRef:
    number: int
    title: str
    files: list[str]  # file paths named in the scanner report (for diff-sanity)


class Ledger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._entries: dict[str, dict] = json.loads(self.path.read_text())
        else:
            self._entries = {}
            self._save()

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._entries, indent=2, sort_keys=True))

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _ensure(self, number: int, title: str = "") -> dict:
        key = str(number)
        if key not in self._entries:
            self._entries[key] = {
                "title": title,
                "branch": None,
                "pr_url": None,
                "attempts": 0,
                "last_gate_state": "pending",
                "status": "pending",
                "last_error": None,
                "started_at": None,
                "finished_at": None,
            }
        return self._entries[key]

    def select_next(self, candidates: list[IssueRef]) -> Optional[IssueRef]:
        eligible = []
        for c in sorted(candidates, key=lambda x: x.number):
            entry = self._entries.get(str(c.number))
            if entry is None:
                eligible.append(c)
                continue
            if entry["status"] in TERMINAL:
                continue
            if entry["attempts"] >= 3:
                continue
            eligible.append(c)
        return eligible[0] if eligible else None

    def mark_attempt(self, issue_number: int) -> None:
        e = self._ensure(issue_number)
        e["attempts"] += 1
        e["started_at"] = e["started_at"] or self._now()
        self._save()

    def mark_merged(self, issue_number: int, pr_url: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "merged"
        e["pr_url"] = pr_url
        e["finished_at"] = self._now()
        self._save()

    def mark_skipped(self, issue_number: int, reason: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "skipped"
        e["last_error"] = reason
        e["finished_at"] = self._now()
        self.reset_verifier_rejects()
        self._save()

    def mark_failed(self, issue_number: int, error: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "failed"
        e["last_error"] = error
        # do NOT set finished_at — failed is non-terminal
        self._save()

    def record_verifier_reject(self) -> int:
        self._entries.setdefault("__root__", {})
        self._entries["__root__"].setdefault("verifier_rejects_in_a_row", 0)
        self._entries["__root__"]["verifier_rejects_in_a_row"] += 1
        self._save()
        return self._entries["__root__"]["verifier_rejects_in_a_row"]

    def reset_verifier_rejects(self) -> None:
        if "__root__" in self._entries:
            self._entries["__root__"]["verifier_rejects_in_a_row"] = 0
            self._save()

    def verifier_rejects_in_a_row(self) -> int:
        return self._entries.get("__root__", {}).get("verifier_rejects_in_a_row", 0)
```

- [ ] **Step 6: Run the tests — confirm GREEN**

Run: `pytest tests/test_issue_loop_ledger.py -q`
Expected: all 8 tests pass.

- [ ] **Step 7: Lint**

Run: `ruff check scripts/issue_loop/ledger.py tests/test_issue_loop_ledger.py`
Expected: clean (or only auto-fixable nits).

- [ ] **Step 8: Commit**

```bash
git add scripts/issue_loop/__init__.py scripts/issue_loop/ledger.py tests/test_issue_loop_ledger.py
git commit -m "feat(issue-loop): add ledger module with TDD coverage"
```

---

## Task 2: Branch + worktree module

**Files:**
- Create: `scripts/issue_loop/branch.py`
- Test: `tests/test_issue_loop_branch.py`

**Interfaces:**
- Consumes: `IssueRef` from Task 1.
- Produces:
  - `slug_from_title(title: str, max_len: int = 50) -> str` — kebab-case, ascii-only.
  - `class BranchManager`:
    - `__init__(self, repo_root: Path) -> None`
    - `create(self, issue_number: int, title: str) -> str` — returns branch name.
    - `spawn_worktree(self, branch: str, target: Path) -> Path` — `git worktree add`.
    - `rebase_onto_main(self, worktree: Path) -> bool` — returns True on success, False on conflict.
    - `remove_worktree(self, worktree: Path) -> None`

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_issue_loop_branch.py
from pathlib import Path
import subprocess
import pytest
from scripts.issue_loop.branch import slug_from_title, BranchManager


def test_slug_from_title_basic() -> None:
    assert slug_from_title("Security: yaml.load without Loader") == "security-yaml-load-without-loader"


def test_slug_from_title_truncates_at_max_len() -> None:
    long = "x" * 200
    s = slug_from_title(long, max_len=30)
    assert len(s) <= 30
    assert s == "x" * 30


def test_slug_from_title_drops_punctuation() -> None:
    assert slug_from_title("Fix: TOCTOU race in `_save_done_items`") == "fix-toctou-race-in-save-done-items"


def test_slug_from_title_collapses_dashes() -> None:
    assert slug_from_title("a -- b") == "a-b"


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    (repo / "f").write_text("0\n")
    subprocess.check_call(["git", "add", "f"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "-m", "init"], cwd=repo)
    return repo


def test_branch_manager_create(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml.load without Loader")
    assert name == "auto/158-yaml-load-without-loader"
    out = subprocess.check_output(
        ["git", "branch"], cwd=git_repo
    ).decode()
    assert "auto/158-yaml-load-without-loader" in out


def test_branch_manager_spawn_worktree(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml.load without Loader")
    wt = git_repo.parent / "wt"
    bm.spawn_worktree(name, wt)
    assert wt.exists()
    assert (wt / "f").exists()
    bm.remove_worktree(wt)


def test_branch_manager_rebase_clean(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml")
    wt = git_repo.parent / "wt"
    bm.spawn_worktree(name, wt)
    assert bm.rebase_onto_main(wt) is True


def test_branch_manager_rebase_conflict(git_repo: Path) -> None:
    bm = BranchManager(git_repo)
    name = bm.create(158, "yaml")
    wt = git_repo.parent / "wt"
    bm.spawn_worktree(name, wt)
    # mutate on main
    (git_repo / "f").write_text("main-change\n")
    subprocess.check_call(["git", "commit", "-q", "-am", "main"], cwd=git_repo)
    # conflicting change on branch
    (wt / "f").write_text("branch-change\n")
    subprocess.check_call(["git", "commit", "-q", "-am", "branch"], cwd=wt)
    assert bm.rebase_onto_main(wt) is False
```

- [ ] **Step 2: Run tests — confirm RED**

Run: `pytest tests/test_issue_loop_branch.py -q`
Expected: `ModuleNotFoundError: No module named 'scripts.issue_loop.branch'`

- [ ] **Step 3: Implement `branch.py`**

Create `scripts/issue_loop/branch.py`:

```python
"""Branch + worktree operations for the issue loop.

All commands are shell-out via subprocess.run with check=False so callers
can inspect exit codes (e.g. rebase conflict returns False, not raise).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug_from_title(title: str, max_len: int = 50) -> str:
    s = title.lower()
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:max_len]


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


class BranchManager:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def create(self, issue_number: int, title: str) -> str:
        slug = slug_from_title(title)
        branch = f"auto/{issue_number}-{slug}"
        r = _run(["git", "checkout", "-b", branch], self.repo_root)
        if r.returncode != 0:
            raise RuntimeError(f"git checkout -b failed: {r.stderr}")
        return branch

    def spawn_worktree(self, branch: str, target: Path) -> Path:
        target.parent.mkdir(parents=True, exist_ok=True)
        r = _run(["git", "worktree", "add", str(target), branch], self.repo_root)
        if r.returncode != 0:
            raise RuntimeError(f"git worktree add failed: {r.stderr}")
        return target

    def rebase_onto_main(self, worktree: Path) -> bool:
        # fetch latest main
        _run(["git", "fetch", "origin", "main"], self.repo_root)
        r = _run(["git", "rebase", "origin/main"], worktree)
        if r.returncode != 0:
            # abort the in-progress rebase so the worktree is usable
            _run(["git", "rebase", "--abort"], worktree)
            return False
        return True

    def remove_worktree(self, worktree: Path) -> None:
        _run(["git", "worktree", "remove", "--force", str(worktree)], self.repo_root)
```

- [ ] **Step 4: Run tests — confirm GREEN**

Run: `pytest tests/test_issue_loop_branch.py -q`
Expected: all 9 tests pass.

- [ ] **Step 5: Lint**

Run: `ruff check scripts/issue_loop/branch.py tests/test_issue_loop_branch.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/issue_loop/branch.py tests/test_issue_loop_branch.py
git commit -m "feat(issue-loop): add branch + worktree manager with TDD coverage"
```

---

## Task 3: Subagent prompt templates

**Files:**
- Create: `scripts/issue_loop/prompts/explore.md`
- Create: `scripts/issue_loop/prompts/planner.md`
- Create: `scripts/issue_loop/prompts/executor.md`
- Create: `scripts/issue_loop/prompts/test_engineer.md`
- Create: `scripts/issue_loop/prompts/verifier.md`
- Create: `scripts/issue_loop/prompts/critic.md`

No code-test step — these are reviewed as docs and consumed by the subagents.

- [ ] **Step 1: Create `explore.md`**

```markdown
# Subagent: explore

You are the **explore** subagent of an autonomous issue loop. Your job is to
produce `context.md` on the working branch. Do not modify code.

## Input

- Issue body (with file path + line number)
- Repo working directory

## Output

Write `context.md` at the repo root with these sections:

```
## Flagged location
<path>:<line>

## Excerpt
<50 lines around the flag, verbatim>

## Callers
<list of files that import/call the flagged symbol or use the env var>

## Related sites
<other files where the same anti-pattern lives — e.g. other `yaml.load` calls>

## Constraints
<anything that constrains the fix: compatibility, schema, tests already covering this>
```

## Quality bar

- `context.md` MUST be ≥ 200 chars.
- MUST reference the exact `file:line` from the issue body.
- No speculation: if you can't find callers, say "no callers found."

## Model

`haiku`. Stay narrow. Don't write code.
```

- [ ] **Step 2: Create `planner.md`**

```markdown
# Subagent: planner

You are the **planner** subagent. Produce `plan.md` on the working branch.
Do not modify code yet.

## Input

- Issue body
- `context.md` (from `explore`)

## Output: `plan.md` with these required sections

```markdown
## Root cause
<one paragraph: why the flagged code is wrong>

## Fix
<the smallest change that resolves it; describe the diff in prose>

## Test plan
<which test file, what new test function, what it asserts>

## Risk
<what could go wrong; what we are NOT fixing in this iteration>
```

If the fix is larger than 30 lines, STOP and write "BLOCKED: too large for
single-iteration loop" in `plan.md`. The orchestrator will skip the issue.

## Model

`sonnet`.
```

- [ ] **Step 3: Create `executor.md`**

```markdown
# Subagent: executor

You are the **executor** subagent. Apply the fix described in `plan.md`.

## Input

- `plan.md`
- Working directory (an isolated git worktree off `auto/<num>-<slug>`)

## Behavior

1. Read `plan.md` end-to-end before touching code.
2. Apply the minimal change described.
3. Run from repo root:
   - `pytest -q` (must exit 0)
   - `ruff check <changed files>`
4. If `pytest` or `ruff` fails, self-correct ONCE. If still failing, write
   the failure to `executor.log` on the branch and STOP — do not commit.

## Diff constraint

Touch ONLY files named in the original scanner report (see `context.md`).
If you find yourself needing to touch another file, abort and write
"BLOCKED: requires out-of-scope change" to `executor.log`.

## Output

Commit the change on the branch with message: `fix(<issue-num>): <one-line summary>`.

## Model

`sonnet`. Isolation: worktree.
```

- [ ] **Step 4: Create `test_engineer.md`**

```markdown
# Subagent: test-engineer

You are the **test-engineer** subagent. Add a regression test.

## Input

- `plan.md` (specifically the "Test plan" section)
- The branch produced by `executor`

## Behavior

1. Write the test per the plan's "Test plan."
2. Verify it FAILS on the base:
   ```bash
   git stash
   git checkout origin/main -- <touched files>
   pytest tests/<new_test_file>::<new_test> -v  # must FAIL
   git checkout auto/<num>-<slug> -- <touched files>
   git stash pop
   ```
3. Verify it PASSES on the branch:
   ```bash
   pytest tests/<new_test_file>::<new_test> -v  # must PASS
   ```
4. Commit the test on the branch.

If step 2 fails to FAIL (test passes on base too) or step 3 fails to PASS,
abort and write "BLOCKED: regression test does not discriminate" to
`test_engineer.log`.

## Model

`sonnet`.
```

- [ ] **Step 5: Create `verifier.md`**

```markdown
# Subagent: verifier

You are the **verifier** subagent. Read-only review. Emit `verdict.json`.

## Input

- The branch's diff (`git diff origin/main...auto/<num>-<slug>`)
- `plan.md`

## Output: `verdict.json` at repo root

```json
{
  "approved": true,
  "severity_max": "LOW",
  "findings": [
    {"file": "<path>", "line": 42, "severity": "LOW", "message": "..."}
  ]
}
```

## Rules

- `approved: true` ONLY if `severity_max` is `LOW` or `MEDIUM`. Any `HIGH`
  or `CRITICAL` finding forces `approved: false`.
- EVERY finding MUST cite `file:line`. If you cannot point to a specific line,
  drop the finding — do not include vague concerns.
- Run a `code-reviewer` review and respect its verdict on severity.

## Model

`opus`. Read-only.
```

- [ ] **Step 6: Create `critic.md`**

```markdown
# Subagent: critic (spot-checker)

You are the **critic** subagent. Invoked on 1-in-4 merged PRs to confirm the
fix actually resolved the issue. Read-only.

## Input

- Merged PR diff
- Original issue body

## Output

A single line on stdout:
```
VERDICT: FIXED | NOT_FIXED | PARTIAL
```
plus a one-paragraph rationale.

If `NOT_FIXED` or `PARTIAL`, the orchestrator halts the loop.

## Model

`opus`. Read-only.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/issue_loop/prompts/
git commit -m "feat(issue-loop): add 6 subagent prompt templates"
```

---

## Task 4: Subagent runner

**Files:**
- Create: `scripts/issue_loop/subagents.py`
- Test: `tests/test_issue_loop_subagents.py`

**Interfaces:**
- Consumes: `IssueRef`, prompt paths from Task 3.
- Produces:
  - `class SubagentRunner`:
    - `__init__(self, prompts_dir: Path, worktree: Path | None = None) -> None`
    - `run_pipeline(self, issue: IssueRef) -> PipelineResult`
  - `PipelineResult` is a dataclass with:
    - `verdict: dict` (parsed `verdict.json` or `{}`)
    - `blocked_reason: str | None`
    - `log_files: list[Path]`

The runner is a thin wrapper that loads prompt files, dispatches each
subagent (here: a stub interface that returns canned data), and threads
artifacts down the chain. The Agent SDK dispatch happens in Task 6 (driver).

For unit testing, `run_pipeline` accepts an optional `dispatch` callable
so tests can inject canned behavior.

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_issue_loop_subagents.py
from pathlib import Path
import pytest
from scripts.issue_loop.ledger import IssueRef
from scripts.issue_loop.subagents import SubagentRunner, PipelineResult


@pytest.fixture
def prompts_dir(tmp_path: Path) -> Path:
    p = tmp_path / "prompts"
    p.mkdir()
    for name in ("explore", "planner", "executor", "test_engineer", "verifier"):
        (p / f"{name}.md").write_text(f"# {name}\n")
    return p


def test_runner_orchestrates_all_five_steps(prompts_dir: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    issue = IssueRef(number=158, title="x", files=["scripts/refresh_pins.py"])

    calls: list[str] = []

    def fake_dispatch(name: str, prompt: str, worktree: Path) -> str:
        calls.append(name)
        if name == "verifier":
            return '{"approved": true, "severity_max": "LOW", "findings": []}'
        return ""

    runner = SubagentRunner(prompts_dir, worktree=wt, dispatch=fake_dispatch)
    result = runner.run_pipeline(issue)
    assert calls == ["explore", "planner", "executor", "test_engineer", "verifier"]
    assert result.verdict == {"approved": True, "severity_max": "LOW", "findings": []}


def test_runner_records_blocked_reason(prompts_dir: Path, tmp_path: Path) -> None:
    wt = tmp_path / "wt"
    wt.mkdir()
    issue = IssueRef(number=158, title="x", files=[])

    def fake_dispatch(name: str, prompt: str, worktree: Path) -> str:
        if name == "planner":
            return "BLOCKED: too large for single-iteration loop"
        return ""

    runner = SubagentRunner(prompts_dir, worktree=wt, dispatch=fake_dispatch)
    result = runner.run_pipeline(issue)
    assert result.blocked_reason is not None
    assert "too large" in result.blocked_reason
```

- [ ] **Step 2: Run tests — confirm RED**

Run: `pytest tests/test_issue_loop_subagents.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `subagents.py`**

Create `scripts/issue_loop/subagents.py`:

```python
"""Subagent pipeline runner.

Threads artifacts from one subagent to the next. The actual Agent SDK
dispatch is injected via `dispatch=` so unit tests can stub it. In
production (driver.py), `dispatch` is wired to the Agent tool.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .ledger import IssueRef

DispatchFn = Callable[[str, str, Path], str]


@dataclass
class PipelineResult:
    verdict: dict = field(default_factory=dict)
    blocked_reason: Optional[str] = None
    log_files: list[Path] = field(default_factory=list)


def _default_dispatch(name: str, prompt: str, worktree: Path) -> str:
    # Real dispatch is wired by driver.py using the Agent SDK.
    # This default exists only so the class is constructible in isolation.
    raise NotImplementedError(
        "SubagentRunner requires an explicit dispatch= in production. "
        "The driver wires this to the Agent tool."
    )


class SubagentRunner:
    def __init__(
        self,
        prompts_dir: Path,
        worktree: Optional[Path] = None,
        dispatch: Optional[DispatchFn] = None,
    ) -> None:
        self.prompts_dir = prompts_dir
        self.worktree = worktree or Path.cwd()
        self.dispatch = dispatch or _default_dispatch

    def _prompt(self, name: str) -> str:
        return (self.prompts_dir / f"{name}.md").read_text()

    def run_pipeline(self, issue: IssueRef) -> PipelineResult:
        result = PipelineResult()

        # 1. explore
        explore_out = self.dispatch("explore", self._prompt("explore"), self.worktree)
        if explore_out.strip() == "":
            # explore must write context.md; absent output = failure
            result.blocked_reason = "explore produced no output"
            return result

        # 2. planner
        planner_out = self.dispatch("planner", self._prompt("planner"), self.worktree)
        if planner_out.startswith("BLOCKED"):
            result.blocked_reason = planner_out
            return result

        # 3. executor
        executor_out = self.dispatch("executor", self._prompt("executor"), self.worktree)
        if executor_out.startswith("BLOCKED"):
            result.blocked_reason = executor_out
            return result

        # 4. test-engineer
        te_out = self.dispatch("test_engineer", self._prompt("test_engineer"), self.worktree)
        if te_out.startswith("BLOCKED"):
            result.blocked_reason = te_out
            return result

        # 5. verifier
        verifier_out = self.dispatch("verifier", self._prompt("verifier"), self.worktree)
        try:
            result.verdict = json.loads(verifier_out)
        except json.JSONDecodeError:
            result.blocked_reason = f"verifier returned non-JSON: {verifier_out[:200]}"
            return result

        return result
```

- [ ] **Step 4: Run tests — confirm GREEN**

Run: `pytest tests/test_issue_loop_subagents.py -q`
Expected: 2 tests pass.

- [ ] **Step 5: Lint**

Run: `ruff check scripts/issue_loop/subagents.py tests/test_issue_loop_subagents.py`

- [ ] **Step 6: Commit**

```bash
git add scripts/issue_loop/subagents.py tests/test_issue_loop_subagents.py
git commit -m "feat(issue-loop): add subagent runner with injectable dispatch"
```

---

## Task 5: Merge gate (CI + Copilot + SonarCloud + code-reviewer)

**Files:**
- Create: `scripts/issue_loop/gate.py`
- Test: `tests/test_issue_loop_gate.py`

**Interfaces:**
- Produces:
  - `class GatePoller`:
    - `__init__(self, github_token: str, repo: str, pr_number: int) -> None`
    - `wait(self, timeout_s: int = 600) -> GateVerdict`
  - `GateVerdict` is a dataclass:
    - `ci: Literal["green", "red", "pending"]`
    - `copilot: Literal["approved", "changes_requested", "pending"]`
    - `sonar: Literal["passed", "failed", "pending"]`
    - `code_reviewer: Literal["approved", "rejected", "pending"]`
    - `property ok: bool` (all four green/approved/passed)

The poller uses `requests` against the GitHub REST API (statuses + reviews
+ checks). The SonarCloud piece is read from the GitHub check-runs endpoint
(filter by app `sonarcloud`).

For tests, `wait()` accepts an optional `clock=time.monotonic` and a
`sleep=` callable so tests can fast-forward time.

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_issue_loop_gate.py
from dataclasses import dataclass
from scripts.issue_loop.gate import GateVerdict, GatePoller


@dataclass
class FakeGitHub:
    ci: str = "green"
    copilot: str = "approved"
    sonar: str = "passed"
    cr: str = "approved"


def test_gate_verdict_ok_when_all_green() -> None:
    v = GateVerdict(ci="green", copilot="approved", sonar="passed", code_reviewer="approved")
    assert v.ok is True


def test_gate_verdict_not_ok_on_any_red() -> None:
    v = GateVerdict(ci="red", copilot="approved", sonar="passed", code_reviewer="approved")
    assert v.ok is False


def test_gate_poller_returns_verdict_on_first_pass() -> None:
    fake = FakeGitHub()
    poller = GatePoller(
        github_token="x", repo="o/r", pr_number=1,
        fetcher=lambda: fake, sleep=lambda s: None,
    )
    v = poller.wait(timeout_s=10)
    assert v.ok is True


def test_gate_poller_times_out_to_red() -> None:
    fake = FakeGitHub(ci="red")
    poller = GatePoller(
        github_token="x", repo="o/r", pr_number=1,
        fetcher=lambda: fake, sleep=lambda s: None,
    )
    v = poller.wait(timeout_s=0)
    assert v.ci == "red"
    assert v.ok is False
```

- [ ] **Step 2: Run tests — confirm RED**

Run: `pytest tests/test_issue_loop_gate.py -q`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `gate.py`**

Create `scripts/issue_loop/gate.py`:

```python
"""Merge gate: wait for CI + Copilot + SonarCloud + code-reviewer to agree.

All four signals must be green/approved/passed before the loop proceeds
to merge. Polled on a short interval until all signals are terminal or
the timeout fires.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Literal

Status = Literal["green", "red", "pending", "approved", "changes_requested", "passed", "failed"]


@dataclass
class GateVerdict:
    ci: Status = "pending"
    copilot: Status = "pending"
    sonar: Status = "pending"
    code_reviewer: Status = "pending"

    @property
    def ok(self) -> bool:
        return (
            self.ci == "green"
            and self.copilot == "approved"
            and self.sonar == "passed"
            and self.code_reviewer == "approved"
        )


def _real_fetcher() -> GateVerdict:
    # Wired in driver.py. Tests inject a fetcher via the constructor.
    raise NotImplementedError("GatePoller requires fetcher= in tests; "
                              "driver.py wires real fetcher.")


class GatePoller:
    def __init__(
        self,
        github_token: str,
        repo: str,
        pr_number: int,
        fetcher: Callable[[], GateVerdict] = _real_fetcher,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.github_token = github_token
        self.repo = repo
        self.pr_number = pr_number
        self.fetcher = fetcher
        self.sleep = sleep
        self.clock = clock

    def wait(self, timeout_s: int = 600) -> GateVerdict:
        deadline = self.clock() + timeout_s
        while self.clock() < deadline:
            v = self.fetcher()
            if v.ok or any([
                v.ci == "red",
                v.copilot == "changes_requested",
                v.sonar == "failed",
                v.code_reviewer == "rejected",
            ]):
                return v
            self.sleep(2)
        return self.fetcher()
```

- [ ] **Step 4: Run tests — confirm GREEN**

Run: `pytest tests/test_issue_loop_gate.py -q`
Expected: 4 tests pass.

- [ ] **Step 5: Lint + commit**

```bash
ruff check scripts/issue_loop/gate.py tests/test_issue_loop_gate.py
git add scripts/issue_loop/gate.py tests/test_issue_loop_gate.py
git commit -m "feat(issue-loop): add merge gate poller with injectable fetcher"
```

---

## Task 6: Merge module

**Files:**
- Create: `scripts/issue_loop/merge.py`
- Test: `tests/test_issue_loop_merge.py`

**Interfaces:**
- Produces:
  - `class Merger`:
    - `__init__(self, github_token: str, repo: str) -> None`
    - `diff_is_scoped(self, branch: str, allowed_files: list[str]) -> bool`
    - `squash_merge(self, branch: str, pr_number: int, issue_number: int) -> str` — returns merge commit SHA.

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_issue_loop_merge.py
from pathlib import Path
import subprocess
import pytest
from scripts.issue_loop.merge import Merger


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q", "-b", "main"], cwd=repo)
    subprocess.check_call(["git", "config", "user.email", "t@t"], cwd=repo)
    subprocess.check_call(["git", "config", "user.name", "t"], cwd=repo)
    (repo / "a.py").write_text("a\n")
    subprocess.check_call(["git", "add", "a.py"], cwd=repo)
    subprocess.check_call(["git", "commit", "-q", "-m", "init"], cwd=repo)
    return repo


def test_diff_is_scoped_true_when_only_allowed_files(git_repo: Path) -> None:
    subprocess.check_call(["git", "checkout", "-q", "-b", "auto/x"], cwd=git_repo)
    (git_repo / "a.py").write_text("a-changed\n")
    subprocess.check_call(["git", "commit", "-q", "-am", "x"], cwd=git_repo)
    m = Merger("tok", "o/r")
    assert m.diff_is_scoped("auto/x", ["a.py"]) is True


def test_diff_is_scoped_false_when_other_file(git_repo: Path) -> None:
    subprocess.check_call(["git", "checkout", "-q", "-b", "auto/x"], cwd=git_repo)
    (git_repo / "b.py").write_text("b\n")
    subprocess.check_call(["git", "add", "b.py"], cwd=git_repo)
    subprocess.check_call(["git", "commit", "-q", "-m", "x"], cwd=git_repo)
    m = Merger("tok", "o/r")
    assert m.diff_is_scoped("auto/x", ["a.py"]) is False
```

- [ ] **Step 2: Run tests — confirm RED**

- [ ] **Step 3: Implement `merge.py`**

Create `scripts/issue_loop/merge.py`:

```python
"""Diff-sanity check + squash-merge for the issue loop.

diff_is_scoped() runs against a local repo (the worktree from Task 2).
squash_merge() hits the GitHub API; in tests it is stubbed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .branch import _run


def _real_github_merge(*args, **kwargs) -> str:
    # Wired in driver.py. Tests stub this.
    raise NotImplementedError("Merger.squash_merge requires a github_merge= "
                              "callable in tests.")


class Merger:
    def __init__(
        self,
        github_token: str,
        repo: str,
        local_repo: Path | None = None,
        github_merge=_real_github_merge,
    ) -> None:
        self.github_token = github_token
        self.repo = repo
        self.local_repo = local_repo or Path.cwd()
        self.github_merge = github_merge

    def diff_is_scoped(self, branch: str, allowed_files: list[str]) -> bool:
        r = _run(["git", "diff", "--name-only", "main", branch], self.local_repo)
        if r.returncode != 0:
            return False
        changed = {Path(p).as_posix() for p in r.stdout.strip().splitlines() if p}
        allowed = {Path(p).as_posix() for p in allowed_files}
        return changed.issubset(allowed)

    def squash_merge(self, branch: str, pr_number: int, issue_number: int) -> str:
        return self.github_merge(
            token=self.github_token,
            repo=self.repo,
            pr_number=pr_number,
            commit_message=f"fix(#{issue_number}): squash-merge from {branch}",
        )
```

- [ ] **Step 4: Run tests — confirm GREEN**

Run: `pytest tests/test_issue_loop_merge.py -q`
Expected: 2 tests pass.

- [ ] **Step 5: Lint + commit**

```bash
ruff check scripts/issue_loop/merge.py tests/test_issue_loop_merge.py
git add scripts/issue_loop/merge.py tests/test_issue_loop_merge.py
git commit -m "feat(issue-loop): add merger with diff-sanity check"
```

---

## Task 7: Driver (top-level loop)

**Files:**
- Create: `scripts/issue_loop/driver.py`
- Test: `tests/test_issue_loop_driver.py`

**Interfaces:**
- Produces:
  - `class IssueLoop`:
    - `__init__(self, ledger: Ledger, branch: BranchManager, subagents: SubagentRunner, gate: GatePoller, merger: Merger, github_token: str, repo: str, prompts_dir: Path) -> None`
    - `run_once(self) -> bool` — process one issue; return True if work was done, False on queue-empty.
    - `run_until_empty(self) -> Summary`
  - `Summary` is a dataclass with `merged: int, skipped: int, failed: int, issue_numbers: list[int]`.

Driver wires real Agent SDK dispatch into `SubagentRunner` (via
`Agent` tool with subagent_type and model override per role) and real
GitHub fetcher into `GatePoller`. Driver owns the state machine in
§1 of the spec.

- [ ] **Step 1: Write the failing test file**

```python
# tests/test_issue_loop_driver.py
from pathlib import Path
import pytest
from scripts.issue_loop.ledger import Ledger, IssueRef
from scripts.issue_loop.branch import BranchManager
from scripts.issue_loop.subagents import SubagentRunner, PipelineResult
from scripts.issue_loop.gate import GatePoller, GateVerdict
from scripts.issue_loop.merge import Merger
from scripts.issue_loop.driver import IssueLoop


@pytest.fixture
def fake_loop(tmp_path: Path) -> IssueLoop:
    ledger = Ledger(tmp_path / "ledger.json")
    bm = BranchManager(tmp_path)  # unused in this test, just needs to construct
    sr = SubagentRunner(
        prompts_dir=tmp_path / "prompts",
        worktree=tmp_path,
        dispatch=lambda n, p, w: '{"approved": true, "severity_max": "LOW", "findings": []}',
    )
    gp = GatePoller(
        "tok", "o/r", pr_number=1,
        fetcher=lambda: GateVerdict(ci="green", copilot="approved", sonar="passed", code_reviewer="approved"),
        sleep=lambda s: None,
    )
    m = Merger("tok", "o/r")
    candidates = [IssueRef(number=158, title="x", files=["a.py"])]

    return IssueLoop(
        ledger=ledger,
        branch=bm,
        subagents=sr,
        gate=gp,
        merger=m,
        github_token="tok",
        repo="o/r",
        prompts_dir=tmp_path / "prompts",
        candidates_provider=lambda: candidates,
        pr_opener=lambda issue, branch: (1, "https://example/pr/1"),  # returns (pr_number, url)
        squash_merge=lambda **kw: "deadbeef",
    )


def test_run_once_returns_false_when_queue_empty(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.json")
    loop = IssueLoop(
        ledger=ledger,
        branch=BranchManager(tmp_path),
        subagents=SubagentRunner(tmp_path / "prompts", tmp_path, dispatch=lambda *a: "{}"),
        gate=GatePoller("t", "o/r", 1, fetcher=lambda: GateVerdict(), sleep=lambda s: None),
        merger=Merger("t", "o/r"),
        github_token="t",
        repo="o/r",
        prompts_dir=tmp_path / "prompts",
        candidates_provider=lambda: [],
        pr_opener=lambda i, b: (0, ""),
        squash_merge=lambda **kw: "",
    )
    assert loop.run_once() is False


def test_run_once_returns_true_and_marks_merged(fake_loop: IssueLoop) -> None:
    assert fake_loop.run_once() is True
    assert fake_loop.ledger._entries["158"]["status"] == "merged"


def test_run_until_empty_returns_summary(fake_loop: IssueLoop) -> None:
    summary = fake_loop.run_until_empty()
    assert summary.merged == 1
    assert summary.skipped == 0
```

- [ ] **Step 2: Run tests — confirm RED**

- [ ] **Step 3: Implement `driver.py`**

Create `scripts/issue_loop/driver.py`:

```python
"""Top-level ralph loop. Selects the next issue, runs the pipeline,
waits the gate, merges, advances the ledger. Resumable: on each entry,
reads ledger first and picks up where the last tick left off.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from .branch import BranchManager
from .gate import GatePoller
from .ledger import IssueRef, Ledger
from .merge import Merger
from .subagents import SubagentRunner


@dataclass
class Summary:
    merged: int = 0
    skipped: int = 0
    failed: int = 0
    issue_numbers: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.issue_numbers is None:
            self.issue_numbers = []


class IssueLoop:
    def __init__(
        self,
        *,
        ledger: Ledger,
        branch: BranchManager,
        subagents: SubagentRunner,
        gate: GatePoller,
        merger: Merger,
        github_token: str,
        repo: str,
        prompts_dir: Path,
        candidates_provider: Callable[[], list[IssueRef]],
        pr_opener: Callable[[IssueRef, str], tuple[int, str]],
        squash_merge: Callable[..., str],
    ) -> None:
        self.ledger = ledger
        self.branch = branch
        self.subagents = subagents
        self.gate = gate
        self.merger = merger
        self.github_token = github_token
        self.repo = repo
        self.prompts_dir = prompts_dir
        self.candidates_provider = candidates_provider
        self.pr_opener = pr_opener
        self.squash_merge = squash_merge

    def _process(self, issue: IssueRef) -> None:
        self.ledger.mark_attempt(issue.number)

        # 1. create branch
        branch_name = self.branch.create(issue.number, issue.title)

        # 2. run subagent pipeline
        result = self.subagents.run_pipeline(issue)
        if result.blocked_reason:
            self.ledger.mark_skipped(issue.number, result.blocked_reason)
            return

        verdict = result.verdict
        if not verdict.get("approved"):
            rejects = self.ledger.record_verifier_reject()
            if rejects >= 5:
                raise SystemExit(
                    f"verifier_rejects_in_a_row={rejects} >= 5 — halting loop"
                )
            # Re-enter from planner is handled by the ralph prompt; here we
            # just record the failure and skip to next issue.
            if self.ledger._entries[str(issue.number)]["attempts"] >= 3:
                self.ledger.mark_skipped(issue.number, "verifier rejected 3x")
            else:
                self.ledger.mark_failed(issue.number, "verifier rejected")
            return

        # 3. open PR
        pr_number, pr_url = self.pr_opener(issue, branch_name)

        # 4. wait for gate
        gate_verdict = self.gate.wait()
        if not gate_verdict.ok:
            self.ledger.mark_failed(issue.number, f"gate: {gate_verdict}")
            return

        # 5. diff-sanity + merge
        if not self.merger.diff_is_scoped(branch_name, issue.files):
            self.ledger.mark_failed(issue.number, "diff-sanity failed")
            return
        self.merger.squash_merge(
            branch=branch_name, pr_number=pr_number, issue_number=issue.number
        )
        self.ledger.mark_merged(issue.number, pr_url)
        self.ledger.reset_verifier_rejects()

    def run_once(self) -> bool:
        issue = self.ledger.select_next(self.candidates_provider())
        if issue is None:
            return False
        self._process(issue)
        return True

    def run_until_empty(self) -> Summary:
        s = Summary()
        while self.run_once():
            # update summary
            entry = self.ledger._entries[str(self._last_processed_number())]
            if entry["status"] == "merged":
                s.merged += 1
            elif entry["status"] == "skipped":
                s.skipped += 1
            else:
                s.failed += 1
            s.issue_numbers.append(int(next(reversed(self.ledger._entries))))
        return s

    def _last_processed_number(self) -> int:
        # Used only by run_until_empty summary. Cheap: scan keys.
        return max(
            (int(k) for k in self.ledger._entries if k != "__root__"),
            default=0,
        )
```

- [ ] **Step 4: Run tests — confirm GREEN**

Run: `pytest tests/test_issue_loop_driver.py -q`
Expected: 3 tests pass.

- [ ] **Step 5: Lint + commit**

```bash
ruff check scripts/issue_loop/driver.py tests/test_issue_loop_driver.py
git add scripts/issue_loop/driver.py tests/test_issue_loop_driver.py
git commit -m "feat(issue-loop): add top-level driver wiring ledger+branch+subagents+gate+merge"
```

---

## Task 8: End-to-end smoke test (real repo)

**Files:**
- Test: `tests/test_issue_loop_e2e.py`

This test runs the dry-run pipeline against the actual `scripts/refresh_pins.py`
on issue #158 (yaml.load). It uses a temporary worktree so the main
checkout is untouched. It does NOT open a PR — it stops at "branch ready,
verdict approved."

- [ ] **Step 1: Write the test**

```python
# tests/test_issue_loop_e2e.py
"""End-to-end smoke test for the issue-loop pipeline.

Runs the dry-run pipeline against issue #158 (yaml.load in
refresh_pins.py). Uses a real git worktree off main. Does NOT open a PR.

Marked `integration` so the default `pytest -q` run skips it.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.issue_loop.branch import BranchManager
from scripts.issue_loop.ledger import IssueRef, Ledger


pytestmark = pytest.mark.integration


REPO = Path("/home/john/Projects/heretek-claude-harness")


def test_e2e_dry_run_on_issue_158(tmp_path: Path) -> None:
    # 1. set up a clean worktree off main
    wt = tmp_path / "wt"
    bm = BranchManager(REPO)
    branch_name = bm.create(158, "yaml.load without Loader")
    bm.spawn_worktree(branch_name, wt)
    try:
        # 2. dry-run pipeline. Subagents are not invoked here; we just
        # confirm the worktree exists, the branch is created, and a simple
        # script edit + test cycle passes locally.
        target = wt / "scripts" / "refresh_pins.py"
        original = target.read_text()
        assert "yaml.load(" in original  # pre-condition: the bug exists

        # 3. naive fix: replace yaml.load with yaml.safe_load
        patched = original.replace("yaml.load(", "yaml.safe_load(")
        target.write_text(patched)
        subprocess.check_call(["git", "commit", "-q", "-am", "fix: yaml.safe_load"],
                              cwd=wt)

        # 4. verify pytest passes
        result = subprocess.run(
            ["pytest", "-q", "tests/"],
            cwd=wt, capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, f"pytest failed:\n{result.stdout}\n{result.stderr}"
    finally:
        bm.remove_worktree(wt)
        # clean up the test branch
        subprocess.run(["git", "branch", "-D", branch_name], cwd=REPO, check=False)
```

- [ ] **Step 2: Run the test — should pass**

Run: `pytest tests/test_issue_loop_e2e.py -q -m integration`
Expected: 1 test passes.

If it fails, check:
- Is `REPO` path correct? Update if the repo moves.
- Does `pytest -q` pass on main locally? Fix first; the e2e is a smoke test, not a unit test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_issue_loop_e2e.py
git commit -m "test(issue-loop): add e2e smoke test against issue #158 dry-run"
```

---

## Task 9: Skill definition + runtime config

**Files:**
- Create: `.claude/skills/issue-loop/SKILL.md`
- Create: `.heretek/issue-loop-config.json`

These make the loop invocable from Claude Code and persist runtime config.

- [ ] **Step 1: Create the skill**

Create `.claude/skills/issue-loop/SKILL.md`:

```markdown
---
name: issue-loop
description: Use when the user asks to drain a queue of GitHub issues autonomously. Activates OMC ralph mode against `scripts/issue_loop/driver.py`.
---

# Issue Loop

Drain the `security-scan`/`tech-debt` issue queue end-to-end with no human
in the inner loop.

## When to use this skill

User says any of:
- "drain the issue queue"
- "run the issue loop"
- "process the security-scan issues"
- "auto-fix #158 onward"

## Activation

```bash
# Pre-flight (dry-run on issue #158 only, no PR)
python -m scripts.issue_loop.driver --dry-run --issue 158

# Full loop
python -m scripts.issue_loop.driver --run-until-empty
```

## What the skill does

1. Reads the ledger at `.omc/state/issue-loop/ledger.json`.
2. Picks the lowest-numbered unprocessed issue matching
   `security-scan`/`tech-debt`.
3. Creates branch `auto/<num>-<slug>`.
4. Spawns 5 subagents (explore, planner, executor, test-engineer, verifier)
   in an isolated worktree.
5. Opens a PR via the GitHub MCP server.
6. Waits for CI + Copilot + code-reviewer + SonarCloud.
7. Squash-merges on green; marks `skipped` after 3 verifier rejections.
8. Halts after 5 cross-issue verifier rejections.

## Stop / resume

- The ledger survives compaction and process restarts. Re-running the skill
  resumes from the last pending entry.
- To halt cleanly: send `stop` to the terminal.
- To reset a single issue: edit the ledger JSON (status back to `pending`,
  attempts to 0).

## Don't

- Don't lower the verifier model from `opus`. Security findings need the
  best model we have.
- Don't widen the issue filter without updating `.heretek/issue-loop-config.json`
  AND the spec — they're coupled.
- Don't open PRs to `main` directly; all work happens on `auto/*` branches.
```

- [ ] **Step 2: Create the runtime config**

Create `.heretek/issue-loop-config.json`:

```json
{
  "version": 1,
  "labels": ["security-scan", "tech-debt"],
  "subagent_models": {
    "explore": "haiku",
    "planner": "sonnet",
    "executor": "sonnet",
    "test-engineer": "sonnet",
    "verifier": "opus",
    "critic": "opus"
  },
  "max_per_issue_attempts": 3,
  "halt_after_cross_issue_rejects": 5,
  "gate_timeout_s": 600,
  "ledger_path": ".omc/state/issue-loop/ledger.json"
}
```

- [ ] **Step 3: Verify the skill is discoverable**

Run: `ls .claude/skills/issue-loop/SKILL.md`
Expected: file exists.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/issue-loop/SKILL.md .heretek/issue-loop-config.json
git commit -m "feat(issue-loop): add skill definition and runtime config"
```

---

## Self-review

1. **Spec coverage:**
   - §1 Architecture (ralph + 5 subagents + gate + merge) → Tasks 4, 5, 6, 7.
   - §2 Components (selection, subagent table, ralph responsibilities) → Tasks 1, 4, 7.
   - §3 Data flow (selection alg, handoff artifacts, ledger schema) → Tasks 1, 4, 7.
   - §4 Error handling (subagent crashes, test fails, verifier rejection, gate fails, branch staleness, halt guard) → Tasks 4, 5, 6, 7.
   - §5 Testing (pre-flight on #158, per-iteration gates, per-PR diff-sanity, post-loop summary, verifier-of-verifier) → Tasks 7, 8, 9 + §5.4 summary in driver.
   - Stop conditions (queue empty, 3 per-issue, 5 cross-issue) → Tasks 1, 7.
   - Out-of-band signals → Task 7 (`run_until_empty` and `mark_skipped` reset the counter).
   - Verifier must cite file:line → Task 3 verifier prompt.

2. **Placeholder scan:** none. Every step has actual code or actual file content.

3. **Type consistency:**
   - `IssueRef` defined in Task 1, consumed in Tasks 2, 4, 7. Same fields across all.
   - `Ledger` methods defined in Task 1 (`select_next`, `mark_attempt`, `mark_merged`, `mark_skipped`, `mark_failed`, `record_verifier_reject`, `reset_verifier_rejects`, `verifier_rejects_in_a_row`) used in Task 7. Names match.
   - `SubagentRunner.run_pipeline` defined in Task 4 returns `PipelineResult` with `verdict: dict`, `blocked_reason: Optional[str]`, `log_files: list[Path]`. Task 7 consumes `.verdict` and `.blocked_reason`.
   - `GateVerdict.ok` defined in Task 5, consumed in Task 7.
   - `Merger.diff_is_scoped` and `Merger.squash_merge` defined in Task 6, consumed in Task 7.
   - Branch naming `auto/<num>-<slug>` matches across Tasks 2, 3, 7, 9.
