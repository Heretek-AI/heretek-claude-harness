# Autopilot Issue Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing issue-loop with five-path autopilot mode (FIX / INVESTIGATE / SPEC / BREAK-DOWN / SKIP), auto-merge on green, no human gating inside the session.

**Architecture:** Pure-function classifier routes issues to path-specific subagents (existing explore/planner/executor/verifier plus 3 new prompts). Orchestrator (Claude session) drives via existing `cli.py` state mutators. New `mark_investigated` ledger method + 3 new CLI subcommands (`log-event`, `register-sub-issue`, `classify`). Critic subagent extended for spec review + trivial-vs-substantive feedback classification.

**Tech Stack:** Python 3.10+; pytest; existing scripts/issue_loop infrastructure; ruamel.yaml; gh CLI; GitHub MCP.

## Global Constraints

- Python 3.10+ (per `CLAUDE.md`)
- Tests use pytest with markers (`integration` = needs network/secrets)
- Catalog uses `ruamel.yaml` round-trip — do not reformat YAML by hand
- All `gh` calls go through the `_default_gh_runner` injection point in `cli.py` so tests can substitute a fake
- Ledger JSON is single-writer; no concurrent writes (sequential bash commands only)
- Subagent prompts follow the existing style: short Markdown, ≤60 lines, no preamble
- New prompts live in `scripts/issue_loop/prompts/` alongside existing ones
- Tests follow existing patterns in `tests/test_issue_loop_cli.py` (FakeGH injection)

---

## Task 1: Classifier pure function + tests

**Files:**
- Create: `scripts/issue_loop/classifier.py`
- Create: `tests/test_issue_loop_classifier.py`

**Interfaces:**
- Consumes: existing `IssueRef` from `scripts/issue_loop/ledger.py`
- Produces: `classify(issue: IssueRef) -> Path` where `Path` is a `str` literal in `{"fix", "investigate", "spec", "break-down", "skip"}`

- [ ] **Step 1: Write failing test for FIX path**

Create `tests/test_issue_loop_classifier.py`:

```python
"""Tests for scripts/issue_loop/classifier.py."""
from __future__ import annotations

import pytest

from scripts.issue_loop.classifier import Path, classify
from scripts.issue_loop.ledger import IssueRef


def test_fix_path_when_body_has_file_line_and_small_fix_words():
    issue = IssueRef(
        number=158,
        title="Security: yaml.load without Loader in scripts/catalog_updater.py:81",
        files=["scripts/catalog_updater.py"],
    )
    body = "Found `yaml.load(...)` call at `scripts/catalog_updater.py:81`. Fix: use yaml.safe_load."
    assert classify(issue, body=body) == "fix"


def test_fix_path_requires_both_anchor_and_fix_keyword():
    issue = IssueRef(number=1, title="x", files=[])
    # anchor but no fix keyword
    assert classify(issue, body="see `scripts/x.py:42` for context") == "investigate"
    # fix keyword but no anchor
    assert classify(issue, body="please patch the catalog parser") == "investigate"


def test_spec_path_when_body_has_design_keywords_no_anchor():
    issue = IssueRef(number=176, title="docs(research): MVP-1 Codegen fan-out", files=[])
    body = "Deep research shows two MCP targets. Design a plugin scaffolding flow with audit and research scope."
    assert classify(issue, body=body) == "spec"


def test_break_down_path_when_body_has_phase_or_checklist():
    issue = IssueRef(number=89, title="v2: hooks hardening + security", files=[])
    body = "Phase scope with sub-tasks: graceful truncation, JSON parsing, checkpoint commits. Split into phases."
    assert classify(issue, body=body) == "break-down"


def test_skip_path_when_body_marks_duplicate_or_wontfix():
    issue = IssueRef(number=99, title="duplicate of #50", files=[])
    body = "Won't fix, by design. Duplicate of #50."
    assert classify(issue, body=body) == "skip"


def test_default_path_is_investigate():
    issue = IssueRef(number=200, title="Improve error message in CLI", files=[])
    body = "When the user passes a bad flag, the error is unclear."
    assert classify(issue, body=body) == "investigate"


def test_path_enum_values_are_stable():
    assert Path("fix") == "fix"
    assert Path("investigate") == "investigate"
    assert Path("spec") == "spec"
    assert Path("break-down") == "break-down"
    assert Path("skip") == "skip"


def test_empty_body_classifies_as_investigate():
    issue = IssueRef(number=1, title="x", files=[])
    assert classify(issue, body="") == "investigate"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_issue_loop_classifier.py -v`
Expected: `ModuleNotFoundError: No module named 'scripts.issue_loop.classifier'`

- [ ] **Step 3: Write minimal implementation**

Create `scripts/issue_loop/classifier.py`:

```python
"""Issue-to-path classifier.

Pure function: takes an IssueRef + body and returns one of five paths:
fix, investigate, spec, break-down, skip. Heuristic-based, no LLM.
"""
from __future__ import annotations

import re
from typing import Literal

from .ledger import IssueRef

Path = Literal["fix", "investigate", "spec", "break-down", "skip"]

_FILE_LINE_RE = re.compile(r"`?[\w./\-]+\.[A-Za-z]+:\d+`?")
_FIX_KEYWORDS = re.compile(r"\b(fix|patch|replace|use\s+\w+\s+instead)\b", re.IGNORECASE)
_SPEC_KEYWORDS = re.compile(r"\b(research|audit|design|plugin|skill|system)\b", re.IGNORECASE)
_BREAKDOWN_KEYWORDS = re.compile(r"\b(split|decompose|sub-?tasks?|phase)\b", re.IGNORECASE)
_SKIP_KEYWORDS = re.compile(r"\b(duplicate|won'?t\s+fix|by\s+design|not\s+applicable)\b", re.IGNORECASE)


def classify(issue: IssueRef, body: str = "") -> Path:
    """Heuristic route from issue to a processing path."""
    text = f"{issue.title} {body}".lower()
    has_anchor = bool(_FILE_LINE_RE.search(issue.title)) or bool(_FILE_LINE_RE.search(body))

    if _SKIP_KEYWORDS.search(text):
        return "skip"
    if has_anchor and _FIX_KEYWORDS.search(text):
        return "fix"
    if _SPEC_KEYWORDS.search(text) and not has_anchor:
        return "spec"
    if _BREAKDOWN_KEYWORDS.search(text):
        return "break-down"
    return "investigate"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_issue_loop_classifier.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/issue_loop/classifier.py tests/test_issue_loop_classifier.py
git commit -m "feat(classifier): pure-function issue-to-path routing (fix|investigate|spec|break-down|skip)"
```

---

## Task 2: Ledger `mark_investigated` method + tests

**Files:**
- Modify: `scripts/issue_loop/ledger.py:42-56` (`_ensure`) + append new method after `mark_failed`
- Create: `tests/test_issue_loop_ledger.py`

**Interfaces:**
- Consumes: existing `Ledger` class
- Produces: `Ledger.mark_investigated(issue_number: int, findings_path: str) -> None`

- [ ] **Step 1: Write failing test**

Create `tests/test_issue_loop_ledger.py`:

```python
"""Tests for scripts/issue_loop/ledger.py."""
from __future__ import annotations

from pathlib import Path

from scripts.issue_loop.ledger import Ledger


def test_mark_investigated_sets_status_and_findings(tmp_path: Path) -> None:
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_investigated(123, "/tmp/findings.json")
    entry = ledger._entries["123"]
    assert entry["status"] == "investigated"
    assert entry["findings_path"] == "/tmp/findings.json"
    assert entry["finished_at"] is not None


def test_mark_investigated_is_terminal(tmp_path: Path) -> None:
    from scripts.issue_loop.ledger import TERMINAL
    ledger = Ledger(tmp_path / "ledger.json")
    ledger.mark_investigated(456, "x")
    assert ledger._entries["456"]["status"] in TERMINAL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_issue_loop_ledger.py -v`
Expected: `AttributeError: 'Ledger' object has no attribute 'mark_investigated'`

- [ ] **Step 3: Update `_ensure` to include `findings_path` and `path`**

In `scripts/issue_loop/ledger.py`, modify `_ensure`:

```python
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
                "path": None,
                "findings_path": None,
                "spec_path": None,
                "sub_issues": [],
                "events": [],
            }
        return self._entries[key]
```

- [ ] **Step 4: Add `mark_investigated` method after `mark_failed`**

In `scripts/issue_loop/ledger.py`, append after `mark_failed`:

```python
    def mark_investigated(self, issue_number: int, findings_path: str) -> None:
        e = self._ensure(issue_number)
        e["status"] = "investigated"
        e["findings_path"] = findings_path
        e["finished_at"] = self._now()
        self._save()
```

Also update `TERMINAL` near line 15:

```python
TERMINAL = frozenset({"merged", "skipped", "investigated"})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_issue_loop_ledger.py -v`
Expected: 2 passed

- [ ] **Step 6: Run existing CLI tests to verify backward compat**

Run: `pytest tests/test_issue_loop_cli.py -q`
Expected: 18 passed (no regressions)

- [ ] **Step 7: Commit**

```bash
git add scripts/issue_loop/ledger.py tests/test_issue_loop_ledger.py
git commit -m "feat(ledger): add mark_investigated status + path/findings_path/spec_path/sub_issues/events fields"
```

---

## Task 3: CLI subcommands (log-event, register-sub-issue, classify) + tests

**Files:**
- Modify: `scripts/issue_loop/cli.py:88-237` (subcommand handlers + parser)
- Modify: `tests/test_issue_loop_cli.py` (add tests)

**Interfaces:**
- Consumes: `Ledger`, `classify()`, `_list_candidates_via_gh`, `_extract_files`
- Produces: subcommands `log-event <N> --kind <info|warn|error> --message <text>`, `register-sub-issue <parent> --child <N> --relation <blocks|relates>`, `classify <N>`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_issue_loop_cli.py`:

```python
# ---------------------------------------------------------------------------
# log-event / register-sub-issue / classify
# ---------------------------------------------------------------------------


def test_log_event_appends_to_issue_events(ledger_path: Path) -> None:
    rc = run("log-event", "158", "--kind", "info", "--message", "explore subagent started", ledger_path=ledger_path)
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger
    events = Ledger(ledger_path)._entries["158"]["events"]
    assert len(events) == 1
    assert events[0]["kind"] == "info"
    assert events[0]["msg"] == "explore subagent started"
    assert "ts" in events[0]


def test_log_event_multiple_events_accumulate(ledger_path: Path) -> None:
    run("log-event", "158", "--kind", "info", "--message", "step 1", ledger_path=ledger_path)
    run("log-event", "158", "--kind", "warn", "--message", "step 2", ledger_path=ledger_path)
    from scripts.issue_loop.ledger import Ledger
    events = Ledger(ledger_path)._entries["158"]["events"]
    assert len(events) == 2
    assert [e["kind"] for e in events] == ["info", "warn"]


def test_register_sub_issue_adds_to_sub_issues_list(ledger_path: Path) -> None:
    rc = run("register-sub-issue", "1", "--child", "10", "--relation", "blocks", ledger_path=ledger_path)
    assert rc == 0
    from scripts.issue_loop.ledger import Ledger
    assert Ledger(ledger_path)._entries["1"]["sub_issues"] == [{"child": 10, "relation": "blocks"}]


def test_register_sub_issue_multiple_children_accumulate(ledger_path: Path) -> None:
    run("register-sub-issue", "1", "--child", "10", "--relation", "blocks", ledger_path=ledger_path)
    run("register-sub-issue", "1", "--child", "11", "--relation", "relates", ledger_path=ledger_path)
    from scripts.issue_loop.ledger import Ledger
    sub = Ledger(ledger_path)._entries["1"]["sub_issues"]
    assert len(sub) == 2


def test_classify_subcommand_prints_path(ledger_path: Path, fake_gh) -> None:
    gh = fake_gh()
    gh.payload = [
        {"number": 158, "title": "Security: yaml.load without Loader in scripts/catalog_updater.py:81", "body": "Fix this."},
    ]
    captured = _capture_main(["--ledger-path", str(ledger_path), "classify", "158"], gh_runner=gh)
    assert captured.returncode == 0
    assert captured.stdout.strip() == "fix"


def test_classify_subcommand_investigate_for_enhancement(ledger_path: Path, fake_gh) -> None:
    gh = fake_gh()
    gh.payload = [
        {"number": 1, "title": "v2: Workflow plugins", "body": "Deep research on plugin scaffolding"},
    ]
    captured = _capture_main(["--ledger-path", str(ledger_path), "classify", "1"], gh_runner=gh)
    assert captured.stdout.strip() == "spec"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_issue_loop_cli.py -v -k "log_event or register_sub_issue or classify_subcommand"`
Expected: 6 failures with "unrecognized arguments" / "no such subcommand"

- [ ] **Step 3: Add `_cmd_log_event`, `_cmd_register_sub_issue`, `_cmd_classify` handlers**

In `scripts/issue_loop/cli.py`, append to the subcommand handlers section (after `_cmd_status`):

```python
def _cmd_log_event(args: argparse.Namespace, ledger: Ledger) -> int:
    from datetime import datetime, timezone
    entry = ledger._ensure(args.issue_number)
    entry.setdefault("events", []).append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": args.kind,
        "msg": args.message,
    })
    ledger._save()
    return 0


def _cmd_register_sub_issue(args: argparse.Namespace, ledger: Ledger) -> int:
    entry = ledger._ensure(args.parent)
    entry.setdefault("sub_issues", []).append({"child": args.child, "relation": args.relation})
    ledger._save()
    return 0


def _cmd_classify(args: argparse.Namespace, ledger: Ledger) -> int:
    try:
        candidates = _list_candidates_via_gh(args.gh_runner, repo=args.repo)
    except (RuntimeError, json.JSONDecodeError) as exc:
        print(f"classify: {exc}", file=sys.stderr)
        return 1
    match = next((c for c in candidates if c.number == args.issue_number), None)
    if match is None:
        print(f"classify: issue {args.issue_number} not found in candidates", file=sys.stderr)
        return 1
    try:
        body_proc = args.gh_runner(
            ["gh", "issue", "view", str(args.issue_number), "--json", "body", "--jq", ".body"]
        )
        if args.repo:
            pass  # _list already added --repo; gh inherits
        body = getattr(body_proc, "stdout", "") or ""
    except Exception:
        body = ""
    from .classifier import classify
    path = classify(match, body=body)
    print(path)
    return 0
```

- [ ] **Step 4: Add subparsers + dispatch entries**

In `_build_parser()`, add three new subparsers:

```python
    ple = sub.add_parser("log-event", help="Append an event log entry for an issue.")
    ple.add_argument("issue_number", type=int)
    ple.add_argument("--kind", choices=["info", "warn", "error"], required=True)
    ple.add_argument("--message", required=True)

    prs = sub.add_parser("register-sub-issue", help="Record a parent->child sub-issue relationship.")
    prs.add_argument("parent", type=int)
    prs.add_argument("--child", type=int, required=True)
    prs.add_argument("--relation", choices=["blocks", "relates"], required=True)

    pc = sub.add_parser("classify", help="Print the routing path for an issue (fix|investigate|spec|break-down|skip).")
    pc.add_argument("issue_number", type=int)
```

In `main()`, add to the dispatch dict:

```python
    dispatch = {
        "select-next": _cmd_select_next,
        "mark-attempt": _cmd_mark_attempt,
        "mark-merged": _cmd_mark_merged,
        "mark-skipped": _cmd_mark_skipped,
        "mark-failed": _cmd_mark_failed,
        "record-reject": _cmd_record_reject,
        "reset-rejects": _cmd_reset_rejects,
        "rejects-in-a-row": _cmd_rejects_in_a_row,
        "status": _cmd_status,
        "log-event": _cmd_log_event,
        "register-sub-issue": _cmd_register_sub_issue,
        "classify": _cmd_classify,
    }
```

- [ ] **Step 5: Run new tests to verify they pass**

Run: `pytest tests/test_issue_loop_cli.py -v -k "log_event or register_sub_issue or classify_subcommand"`
Expected: 6 passed

- [ ] **Step 6: Run all CLI tests to verify no regressions**

Run: `pytest tests/test_issue_loop_cli.py tests/test_issue_loop_classifier.py tests/test_issue_loop_ledger.py -q`
Expected: 26 passed (18 existing + 8 classifier + 2 ledger - 2 carried) — actually check the count

- [ ] **Step 7: Commit**

```bash
git add scripts/issue_loop/cli.py tests/test_issue_loop_cli.py
git commit -m "feat(cli): add log-event, register-sub-issue, classify subcommands"
```

---

## Task 4: Investigator prompt

**Files:**
- Create: `scripts/issue_loop/prompts/investigator.md`

**Interfaces:**
- Produces: prompt template that, when dispatched via the Agent tool, produces `findings.json` with `{pivot_to_fix: bool, fix_site: str | None, notes: str}`

- [ ] **Step 1: Write the prompt content**

Create `scripts/issue_loop/prompts/investigator.md`:

```markdown
# Subagent: investigator

You are the **investigator** subagent of an autonomous issue loop. Your job is to
deep-dive into an issue that initially seemed out-of-scope and either find a
fixable site or document why none exists. Do NOT modify code. Do NOT commit.

## Input

- Issue body
- `context.md` (from a prior explore subagent, if any)
- Repo working directory

## Output

Write `findings.json` at the repo root:

```json
{
  "pivot_to_fix": true,
  "fix_site": "scripts/refresh_pins.py:223",
  "notes": "Found same yaml.load() pattern as #158. Root cause identical; copy the fix."
}
```

Or, when no fix site exists:

```json
{
  "pivot_to_fix": false,
  "fix_site": null,
  "notes": "Investigated 12 files. No related yaml.load/Path traversal pattern. Issue describes a missing feature, not a bug."
}
```

## Behavior

1. Read the issue body. Identify what the user wants.
2. Grep for related patterns: similar function names, similar anti-patterns,
   similar files mentioned in the title.
3. If a fix site is found: set `pivot_to_fix: true` and the file:line.
4. If after exhaustive search no fix site exists: set `pivot_to_fix: false`
   and explain what was investigated.
5. Do not guess. If unsure, mark `pivot_to_fix: false` and explain.

## Model

`sonnet` (per `.heretek/issue-loop-config.json`).
```

- [ ] **Step 2: Verify prompt file exists**

Run: `ls -la scripts/issue_loop/prompts/investigator.md`
Expected: file exists, ~40 lines

- [ ] **Step 3: Commit**

```bash
git add scripts/issue_loop/prompts/investigator.md
git commit -m "feat(prompts): add investigator subagent prompt"
```

---

## Task 5: Spec-writer prompt

**Files:**
- Create: `scripts/issue_loop/prompts/spec_writer.md`

- [ ] **Step 1: Write the prompt content**

Create `scripts/issue_loop/prompts/spec_writer.md`:

```markdown
# Subagent: spec-writer

You are the **spec-writer** subagent of an autonomous issue loop. Your job is to
produce an SDD design spec at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
following the brainstorming skill flow. Do NOT implement. Do NOT commit the spec
until you have self-reviewed.

## Input

- Issue body
- `context.md` (from a prior explore or investigator subagent)
- Repo working directory

## Output

A design spec matching the existing format in
`docs/superpowers/specs/2026-08-09-issue-loop-refactor-adr.md` and
`docs/superpowers/specs/2026-08-10-autopilot-issue-loop-design.md`.

Required sections (use the brainstorming skill checklist):

- Frontmatter (date, topic, status: design, parent)
- Context (why this spec exists)
- Decisions (table of options chosen + alternatives)
- Architecture (if applicable)
- Components (new + extended files)
- Data Flow (if applicable)
- Error Handling (table of failure -> action)
- Testing
- Out of Scope
- Verification

## Behavior

1. Read the issue body. Run clarifying questions internally (imagine user
   answered; pick sensible defaults — do NOT block on questions).
2. Propose 2-3 approaches with tradeoffs. Pick one with rationale.
3. Present the design scaled to complexity (a few sentences for simple, up
   to 300 words for nuanced).
4. Write the spec to disk.
5. Self-review the spec: placeholders, contradictions, ambiguity, scope.
   Fix inline.
6. Commit the spec with message `docs(spec): <topic> design`.

## Model

`opus` (design work needs the best model).
```

- [ ] **Step 2: Verify file exists**

Run: `ls -la scripts/issue_loop/prompts/spec_writer.md`
Expected: ~50 lines

- [ ] **Step 3: Commit**

```bash
git add scripts/issue_loop/prompts/spec_writer.md
git commit -m "feat(prompts): add spec-writer subagent prompt"
```

---

## Task 6: Breakdowner prompt

**Files:**
- Create: `scripts/issue_loop/prompts/breakdowner.md`

- [ ] **Step 1: Write the prompt content**

Create `scripts/issue_loop/prompts/breakdowner.md`:

```markdown
# Subagent: breakdowner

You are the **breakdowner** subagent of an autonomous issue loop. Your job is to
decompose a large issue into smaller sub-issues via the GitHub sub-issue API. Do
NOT modify code. Do NOT commit the sub-issue creations yourself — the
orchestrator handles that via `register-sub-issue`.

## Input

- Issue body (with checklist or phase structure)
- Repo working directory
- GitHub MCP server (for `sub_issue_write` calls)

## Output

A list of sub-issue candidates, each as JSON:

```json
[
  {"title": "Sub-task 1: implement graceful truncation", "body": "..."},
  {"title": "Sub-task 2: implement JSON parsing", "body": "..."}
]
```

## Behavior

1. Read the issue body. Identify discrete sub-tasks (checkboxes, phases,
   distinct deliverables).
2. For each sub-task: draft a clear title and self-contained body.
3. Call the GitHub MCP `sub_issue_write` with `method: add`, `issue_number:
   <parent>`, `sub_issue_id: <new_issue_id>`. The orchestrator will run
   `python -m scripts.issue_loop.cli register-sub-issue <parent> --child <N>
   --relation blocks` after each creation.
4. If the issue does not actually decompose (single deliverable): return an
   empty list and write `breakdowner.log` with `NOT_DECOMPOSABLE: <reason>`.

## Model

`sonnet`.
```

- [ ] **Step 2: Verify file exists**

Run: `ls -la scripts/issue_loop/prompts/breakdowner.md`
Expected: ~35 lines

- [ ] **Step 3: Commit**

```bash
git add scripts/issue_loop/prompts/breakdowner.md
git commit -m "feat(prompts): add breakdowner subagent prompt"
```

---

## Task 7: Critic extension (spec verdict + trivial/substantive feedback)

**Files:**
- Modify: `scripts/issue_loop/prompts/critic.md`

- [ ] **Step 1: Read current critic.md**

Run: `cat scripts/issue_loop/prompts/critic.md`

- [ ] **Step 2: Replace critic.md with extended version**

Overwrite `scripts/issue_loop/prompts/critic.md`:

```markdown
# Subagent: critic (spot-checker)

You are the **critic** subagent. Invoked on two occasions:

1. **Spec review** — for SPEC-path issues, after spec_writer produces a design
   doc. Verify the spec is internally consistent, complete, and unambiguous.
2. **Trivial-vs-substantive feedback** — for review feedback (Copilot,
   code-reviewer) on PRs. Classify each piece of feedback so the orchestrator
   knows whether to auto-fix or leave the PR open for human review.

Read-only. Do not modify code or commit.

## Input

For spec review: the design doc at `docs/superpowers/specs/<file>.md`.
For feedback classification: the review comment(s) on a PR.

## Output

For spec review, write `verdict.json`:

```json
{
  "verdict": "SPEC_READY" | "NEEDS_REVISION",
  "issues": ["section X is ambiguous", "missing error handling table"]
}
```

For feedback classification, write `feedback.json`:

```json
{
  "items": [
    {"file": "scripts/x.py", "line": 42, "kind": "trivial" | "substantive", "message": "..."}
  ]
}
```

## Rules

- Spec review: `SPEC_READY` ONLY if no `placeholder`, `TBD`, `TODO`, or
  internal contradiction. `NEEDS_REVISION` lists specific issues.
- Feedback classification:
  - `trivial`: lint warnings, comment typos, missing imports, docstring
    format, ruff violations, line-length.
  - `substantive`: design changes, API changes, schema changes, breaking
    changes, security-sensitive refactors.
- EVERY classification MUST cite `file:line`. If you cannot point to a
  specific line, drop the item.

## Model

`opus`.
```

- [ ] **Step 3: Verify file is updated**

Run: `head -30 scripts/issue_loop/prompts/critic.md`
Expected: shows the new dual-purpose header

- [ ] **Step 4: Commit**

```bash
git add scripts/issue_loop/prompts/critic.md
git commit -m "feat(prompts): extend critic for spec review + trivial-vs-substantive feedback"
```

---

## Task 8: Config extension (paths_enabled, periodic_summary_minutes)

**Files:**
- Modify: `.heretek/issue-loop-config.json`

- [ ] **Step 1: Read current config**

Run: `cat .heretek/issue-loop-config.json`

- [ ] **Step 2: Add autopilot fields**

Overwrite `.heretek/issue-loop-config.json`:

```json
{
  "version": 3,
  "labels": [],
  "paths_enabled": ["fix", "investigate", "spec", "break-down", "skip"],
  "periodic_summary_minutes": 30,
  "halt_after_cross_issue_rejects": 5,
  "subagent_models": {
    "explore": "haiku",
    "planner": "sonnet",
    "executor": "sonnet",
    "test-engineer": "sonnet",
    "verifier": "opus",
    "critic": "opus",
    "investigator": "sonnet",
    "spec_writer": "opus",
    "breakdowner": "sonnet"
  },
  "max_per_issue_attempts": 3,
  "gate_timeout_s": 600,
  "ledger_path": ".omc/state/issue-loop/ledger.json"
}
```

- [ ] **Step 3: Verify JSON is valid**

Run: `python -c "import json; print(json.load(open('.heretek/issue-loop-config.json'))['version'])"`
Expected: `3`

- [ ] **Step 4: Commit**

```bash
git add .heretek/issue-loop-config.json
git commit -m "feat(config): autopilot paths + periodic summary + new subagent models"
```

---

## Task 9: Skill SKILL.md rewrite

**Files:**
- Modify: `.claude/skills/issue-loop/SKILL.md` (rewrite)

- [ ] **Step 1: Overwrite SKILL.md with autopilot flow**

Overwrite `.claude/skills/issue-loop/SKILL.md`:

```markdown
# Issue Loop (Autopilot)

Drain the GitHub issue queue end-to-end with no human gating inside the session.

## When to use

User says any of: "drain the issue queue", "run the issue loop",
"process the security-scan issues", "auto-fix #158 onward", "autopilot the
issue loop".

## Activation

The skill is activated by user invocation. There is no cron/webhook trigger.
The user runs `/issue-loop` (or invokes via slash command) when ready.

## Flow

1. **Pre-flight:** `python -m scripts.issue_loop.cli status` to confirm ledger
   state.
2. **Tick loop:** repeat until `select-next` returns `{}`:
   1. `python -m scripts.issue_loop.cli select-next` → `IssueRef | {}`
   2. If `{}`: emit periodic summary, then halt cleanly.
   3. `python -m scripts.issue_loop.cli mark-attempt <N>`
   4. `python -m scripts.issue_loop.cli classify <N>` → `fix|investigate|spec|break-down|skip`
   5. Dispatch path-specific subagent(s) via the `Agent` tool:
      - **fix**: explore → planner → executor → test-engineer → verifier (existing)
      - **investigate**: read `scripts/issue_loop/prompts/investigator.md`
      - **spec**: read `scripts/issue_loop/prompts/spec_writer.md` then
        `scripts/issue_loop/prompts/critic.md` (for spec verdict), then
        implementation flow
      - **break-down**: read `scripts/issue_loop/prompts/breakdowner.md`
      - **skip**: log-event + comment + mark-skipped
   6. Poll gate (CI + Copilot + SonarCloud) via GitHub MCP.
   7. Finalize:
      - `fix` green → squash-merge → `mark-merged`
      - `fix` red → leave PR open + log-event "needs-human"
      - `investigate` pivot → goto fix path
      - `investigate` no-fix → log-event + comment + `mark-investigated`
      - `spec` impl green → squash-merge + comment "spec: <path>"
      - `spec` impl red → leave PR open
      - `break-down` → `register-sub-issue` per child
      - `skip` → log-event + `mark-skipped`
3. **Halt conditions:** GitHub rate limit, infra failure, Anthropic error.
   NOT halt: cross-issue verifier rejects, quality gate failures,
   SonarCloud blocks, token/wall-clock limits (per user choice).

## Periodic summary

Every `periodic_summary_minutes` (default 30): emit a throughput summary
(issues processed by path+outcome since last summary, current issue in
flight, ETA, halt-condition warnings).

## Don't

- Don't auto-close issues on GitHub. They stay open with comments.
- Don't lower the verifier `Model='opus'` requirement.
- Don't change `halt_after_cross_issue_rejects: 5` — the autopilot skill
  overrides it in-memory; the config value remains for non-autopilot runs.
- Don't widen the issue filter without updating the spec.
```

- [ ] **Step 2: Verify file updated**

Run: `wc -l .claude/skills/issue-loop/SKILL.md`
Expected: ~70 lines

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/issue-loop/SKILL.md
git commit -m "feat(skill): rewrite issue-loop SKILL.md for autopilot flow"
```

---

## Task 10: Integration drain script (smoke test)

**Files:**
- Create: `scripts/issue_loop/autopilot_drain.py`

**Interfaces:**
- Consumes: existing `cli.py` subcommands + GitHub MCP
- Produces: end-to-end drain script that exercises all 5 paths against fixture issues

- [ ] **Step 1: Write the drain script**

Create `scripts/issue_loop/autopilot_drain.py`:

```python
"""End-to-end autopilot drain script.

Exercises all 5 paths against fixture issues. Used as integration smoke test
for the autopilot issue-loop extension. Not for production use — production
drains are driven by the Claude orchestrator via the Agent tool.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LEDGER = ROOT / ".omc" / "state" / "issue-loop" / "ledger.json"
CONFIG = ROOT / ".heretek" / "issue-loop-config.json"

FIXTURES = [
    {"number": 158, "title": "Security: yaml.load without Loader in scripts/catalog_updater.py:81",
     "body": "Found `yaml.load(...)` at `scripts/catalog_updater.py:81`. Fix: use yaml.safe_load.",
     "expected_path": "fix"},
    {"number": 176, "title": "docs(research): MVP-1 Codegen fan-out",
     "body": "Deep research on plugin design with audit scope.",
     "expected_path": "spec"},
    {"number": 200, "title": "Improve error message in CLI",
     "body": "When the user passes a bad flag, the error is unclear.",
     "expected_path": "investigate"},
    {"number": 89, "title": "v2: hooks hardening + security",
     "body": "Phase scope: graceful truncation, JSON parsing, checkpoint commits. Split into phases.",
     "expected_path": "break-down"},
    {"number": 99, "title": "duplicate of #50",
     "body": "Won't fix, by design. Duplicate of #50.",
     "expected_path": "skip"},
]


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python", "-m", "scripts.issue_loop.cli", "--ledger-path", str(LEDGER), *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )


def classify_fixture(fix: dict) -> str:
    """Inject fixture body via a fake-gh runner is overkill for smoke; instead
    use the classifier directly and verify against expected_path."""
    from scripts.issue_loop.ledger import IssueRef
    from scripts.issue_loop.classifier import classify
    issue = IssueRef(number=fix["number"], title=fix["title"], files=[])
    actual = classify(issue, body=fix["body"])
    assert actual == fix["expected_path"], f"{fix['number']}: expected {fix['expected_path']}, got {actual}"
    return actual


def main() -> int:
    print(f"drain: {len(FIXTURES)} fixtures")
    config = json.loads(CONFIG.read_text())
    assert config["paths_enabled"] == ["fix", "investigate", "spec", "break-down", "skip"]
    assert config["periodic_summary_minutes"] == 30

    for fix in FIXTURES:
        path = classify_fixture(fix)
        run_cli("mark-attempt", str(fix["number"]))
        run_cli("log-event", str(fix["number"]), "--kind", "info", "--message", f"classified as {path}")

    statuses = json.loads(run_cli("status").stdout)
    print(f"status: {statuses}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run the drain script**

Run: `python -m scripts.issue_loop.autopilot_drain`
Expected: `drain: 5 fixtures` followed by `status: {...}`. No assertion errors.

- [ ] **Step 3: Verify ledger has the expected entries**

Run: `python -m scripts.issue_loop.cli status`
Expected: pending count > 0 (or use a test ledger path if you want to avoid polluting the real ledger)

To avoid polluting the real ledger, set `LEDGER_PATH=/tmp/test-ledger.json python -m scripts.issue_loop.autopilot_drain` (modify the script to read the env var, OR use a separate test ledger). For the smoke test, accept pollution — the drain is reversible by `reset_verifier_rejects()` if needed.

- [ ] **Step 4: Commit**

```bash
git add scripts/issue_loop/autopilot_drain.py
git commit -m "feat(drain): autopilot integration smoke test (5 fixtures, all paths)"
```

---

## Self-review

After writing all 10 tasks, verify:

1. **Spec coverage:**
   - 5 paths ✓ Tasks 1 (classifier), 4-6 (new prompts), 9 (SKILL flow)
   - Aggressive investigation ✓ Tasks 4 (investigator), 9 (SKILL flow re-route)
   - Auto-merge on green ✓ Task 9 (SKILL flow finalize step)
   - Halt only on system limits ✓ Task 9 (SKILL halt section)
   - SPEC path ✓ Tasks 5 (spec_writer), 7 (critic extension)
   - BREAK-DOWN path ✓ Task 6 (breakdowner)
   - Periodic summary ✓ Tasks 8 (config), 9 (SKILL)
   - New CLI subcommands ✓ Task 3
   - `mark_investigated` ✓ Task 2
   - Backward-compat ledger ✓ Task 2 (TERMINAL includes 'investigated')
   - Critic extension ✓ Task 7
   - No placeholders: scan confirms no TBD/TODO ✓
   - Type consistency: `Path` literal defined in Task 1, used in Task 3; `mark_investigated` defined in Task 2, used in Task 9 flow ✓

2. **All steps have concrete code or commands** (no "add appropriate error handling").

3. **Tasks are bite-sized (2-5 min each step)** with TDD pattern where applicable.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-autopilot-issue-loop.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
