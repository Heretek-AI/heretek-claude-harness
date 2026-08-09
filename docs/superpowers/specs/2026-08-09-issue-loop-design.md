# Autonomous Issue Loop — Design

## Goal

A self-resuming, subagent-driven loop that drains the `security-scan`/`tech-debt`
issue queue with no human in the inner loop. Each iteration goes:

```
select → explore → plan → execute → test → verify → open PR → gate → merge → next
```

This is a **v1 proof**. Scope is intentionally narrow to make the loop provable
before generalizing. After v1 ships, generalization is a separate spec.

## Scope

**In scope:**
- Issues with labels `security-scan` + `tech-debt`. On first run that's #158–#168 (12 issues).
- OMC `ralph` self-loop, ledger-backed, resumable across compaction.
- One branch + one PR per issue, squash-merge on green.
- Local CI: `pytest -q`, `ruff check`, `python scripts/validate.py`,
  `python scripts/generate_marketplace.py`,
  `git diff --exit-code .claude-plugin/marketplace.json`.
- Remote CI: GitHub Actions on the PR branch.
- Copilot review, SonarCloud quality gate on the PR.
- Audit summary posted to GitHub Discussions (or issue comment fallback) after queue drains.

**Out of scope (deferred or excluded):**
- Other label sets (`enhancement`, `harness-observability`, `help wanted`, `tracking`).
- Auto-fixing PRs the verifier cannot reach a verdict on — those are labeled `needs-human` and skipped.
- Changes to `catalog/catalog.yaml`, `marketplace.json`, or any plugin manifest.
- Cross-PR coordination (no batching, no PR dependencies).
- New ADRs unless a finding surfaces a meta-decision; routine fixes use inline rationale.

## Architecture

One ralph-mode Claude session owns the loop, running in the main checkout.
Each iteration is a fixed state machine. **ralph creates the branch first**
(`auto/<num>-<slug>` off `main`), then per-issue subagent execution happens
inside an isolated git worktree that checks out that branch. The worktree is
spawned by the `executor` subagent (which is the first subagent that needs
write access) and shared by `test-engineer` and `verifier` for read access.

```
              ┌─────────────────────────────────────────┐
              │                                         │
              ▼                                         │
  ┌──────────────────┐   ┌─────────────────────────┐   │
  │ SELECT issue     │──▶│ SUBAGENT PIPELINE       │   │
  │ - label filter   │   │ 1. explore              │   │
  │ - skip closed    │   │ 2. planner              │   │
  │ - skip blocked   │   │ 3. executor (worktree)  │   │
  └──────────────────┘   │ 4. test-engineer        │   │
                         │ 5. verifier             │   │
                         └──────────┬──────────────┘   │
                                    ▼                  │
                         ┌─────────────────────────┐   │
                         │ OPEN PR (ralph)         │   │
                         └──────────┬──────────────┘   │
                                    ▼                  │
                         ┌─────────────────────────┐   │
                         │ GATE                    │   │
                         │ - CI green              │   │
                         │ - Copilot review        │   │
                         │ - code-reviewer OK      │   │
                         │ - SonarCloud quality    │   │
                         └──────┬──────────┬───────┘   │
                                │          │           │
                              pass       fail         │
                                ▼          ▼           │
                          ┌─────────┐  ┌────────────┐  │
                          │ MERGE   │  │ FEEDBACK   │──┘
                          │ squash  │  │ (re-iterate│
                          └────┬────┘  │  same issue)│
                               │       └────────────┘
                               ▼
                          advance ledger → next issue
```

### Selection

ralph itself (no subagent) reads the ledger and the open issue list filtered by
label, then picks the lowest-numbered candidate not already in a terminal state.

### Per-issue subagent pipeline

| # | Agent | Role | Model | Input | Output |
|---|---|---|---|---|---|
| 1 | `explore` | Find the flagged code: read the file:line, surrounding 50 lines, callers, related env-var sites across the repo | `haiku` | issue body + file path | `context.md` (code excerpt, callers, related sites) |
| 2 | `planner` | Draft a remediation plan: root cause, fix shape, test plan, ADR-lite rationale | `sonnet` | issue body + `context.md` | `plan.md` written to the working branch (ralph created the branch before this subagent ran) |
| 3 | `executor` | Apply the fix in an isolated worktree. Run `pytest -q` + `ruff check`. Return diff + test output | `sonnet` | `plan.md` | branch + diff + test log |
| 4 | `test-engineer` | Add a regression test that fails on the old code and passes on the new. Run it twice (against base, against fix) | `sonnet` | `plan.md` + `executor` branch | updated branch + test diff |
| 5 | `verifier` | Run `code-reviewer` (severity-rated read-only) on the final diff. Approve or reject with concrete changes | `opus` | final diff + plan.md | `verdict.json` (`approved: bool`, `severity_max`, `findings: []`) |

### ralph's own responsibilities (not delegated)

- Issue selection from ledger
- Branch creation (`auto/<num>-<slug>`)
- PR creation via `mcp__github__github-create_pull_request`
- Gate watching: poll CI, request Copilot review, wait for SonarCloud
- Squash-merge + close iteration
- Ledger updates

### Skipped subagents

`architect`, `critic` (except as post-merge spot-checker), `debugger`, `designer`,
`qa-tester`, `writer`, `document-specialist`, `analyst`, `scientist`,
`security-reviewer` (security is already in the issue scope; `code-reviewer` covers
the per-PR check), `code-simplifier`. The pipeline is mechanical and the
`code-reviewer` already covers the review lens.

## Data flow

### Issue selection (ralph, top of each iteration)

```python
# pseudocode
def select_next():
    ledger = read(".omc/state/issue-loop/ledger.json")
    done   = {n for n, row in ledger.items() if row.status in ("merged", "skipped")}
    issues = github_list_issues(
        labels=["security-scan", "tech-debt"], state="open"
    )
    candidates = [
        i for i in issues
        if i.number not in done
        and ledger.get(str(i.number), {}).get("attempts", 0) < 3
    ]
    candidates.sort(key=lambda i: i.number)
    return candidates[0] if candidates else None
```

If `select_next` returns `None`, ralph exits cleanly with a summary.

### Per-issue handoff (subagent → subagent)

Each subagent writes one artifact to the worktree. The next subagent reads it.
No state in agent memory — everything survives compaction.

```
branch: auto/<num>-<slug>
  ├── context.md          ← explore
  ├── plan.md             ← planner
  ├── <code fix>          ← executor
  ├── <regression test>   ← test-engineer
  └── verdict.json        ← verifier  (NOT committed; consumed by ralph)
```

### Ledger schema

`.omc/state/issue-loop/ledger.json`:

```json
{
  "<issue_number>": {
    "title": "Security: yaml.load without Loader in scripts/refresh_pins.py",
    "branch": "auto/157-yaml-loader",
    "pr_url": null,
    "attempts": 0,
    "last_gate_state": "pending",
    "status": "pending",
    "last_error": null,
    "started_at": null,
    "finished_at": null
  }
}
```

`status` ∈ `pending | merged | skipped | failed`.

- `merged` — terminal, success.
- `skipped` — terminal, needs human (3 verifier rejections exhausted).
- `failed` — non-terminal, subagent crashed; retryable on next tick.

### Resume semantics

On every ralph tick: read ledger first. If last entry is `pending` and
`last_gate_state != "merged"`, resume that iteration from where it stopped
(gate-wait, retry verifier, etc.). Never re-execute merged or skipped entries.

## Error handling

Three failure classes, each with a deterministic recovery path. The loop must
be resumable across every failure type without losing work.

### Subagent crashes (LLM error, tool timeout, context overflow)

- Re-run the same subagent. If twice in a row the same subagent fails on the
  same artifact, re-spawn it once. If the third attempt also fails, mark the
  iteration `failed`, log the artifact, advance to the next issue.
- A `failed` entry does NOT count toward the consecutive-failure skip counter.
  Crashes are infrastructure noise, not a sign of bad fixes.

### Test failures (`pytest` red, `ruff check` dirty)

- `executor`'s job is to land green. First attempt red → `executor` re-runs with
  the failure attached (one self-correction loop, max 2 attempts). Still red →
  iteration `failed`, next issue.
- Never open a PR with red tests. The branch exists for forensic review but
  no PR URL is recorded.

### Verifier rejection (consecutive-failure path)

Track `verifier_rejects_in_a_row` in the ledger root. On `reject`:

1. Append verifier's `findings[]` to the next planner's input (re-plan, don't
   re-execute blindly).
2. Increment `attempts[issue]` and `verifier_rejects_in_a_row`.
3. If `attempts[issue] >= 3` → mark `skipped`, add a `needs-human` comment via
   `mcp__github__github-add_issue_comment` describing what blocked it. Reset
   `verifier_rejects_in_a_row` to 0.
4. Else → re-enter pipeline from `planner` (skip `explore`; reuse `context.md`).

If verifier approves after ≤2 retries, reset the counter on success.

### Gate failures (CI red, Copilot REQUEST_CHANGES, SonarCloud failed)

`pr_url` exists but gate didn't pass. Hold the iteration open, poll for 10 min.
If still failing:

- **CI red** → treat as test failure; re-enter from `test-engineer`.
- **Copilot REQUEST_CHANGES** → treat as verifier rejection; re-enter from
  `planner` with the bot's comments attached.
- **SonarCloud failed** → re-enter from `executor` with the finding attached.

### Branch staleness

Before re-entering the pipeline after a gate failure, ralph does
`git fetch origin main` in the main checkout, then `cd`s into the executor's
worktree and rebases the working branch onto `origin/main`. If the rebase
conflicts, mark iteration `skipped` with comment "main moved out from under
us, needs human rebase."

### Systemic-failure guard

If `verifier_rejects_in_a_row` reaches 5 across issues, halt and ask for human
review via terminal output. The verifier or scanner may have drifted; this is
not a per-issue problem.

## Testing / verification

The loop must verify itself before opening a PR against a real issue. Three
layers, in order.

### Pre-flight (before ralph starts)

A dry-run mode picks issue #158 (yaml.load in `refresh_pins.py`), runs the full
subagent pipeline against `main`, and stops at "branch ready, PR not yet
created." Inspect:

- All 5 artifacts present on the branch
- `pytest -q` green
- `ruff check` clean
- `verdict.json` has `approved: true`

If any check fails, ralph does not proceed to issue #159. #158 is chosen because
it's a one-line fix (`yaml.load → yaml.safe_load`), has an existing test file,
and is the smallest possible surface for verifying the pipeline shape.

### Per-iteration verification (during the loop)

Each subagent must pass its own gate before handing off:

- `explore`: produces `context.md` ≥ 200 chars, references real `file:line`
- `planner`: `plan.md` contains `## Root cause`, `## Fix`, `## Test plan` headers
- `executor`: `pytest -q` exits 0 on the branch, `ruff check` exits 0
- `test-engineer`: the new test FAILS on `main` (run it once rebased onto base,
  confirm red) and PASSES on the branch
- `verifier`: `verdict.json.approved == true` AND `severity_max ≤ "MEDIUM"`

ralph reads each artifact before spawning the next subagent. A malformed
handoff fails the iteration (per Error handling) rather than silently
propagating bad state.

### Per-PR verification (before merge)

The merge gate IS the verification step, plus one extra: **diff sanity** — the
branch's diff must be strictly contained within the file(s) the original
scanner report named. If `executor` touches anything else (even formatting),
`verifier` rejects. This catches the "agent went off-script" failure mode,
which is the most common silent-bug source in autonomous loops.

### Post-loop verification (after queue drains)

After the last issue closes, ralph:

1. Re-runs the full local CI on `main` with all merged branches included
2. Prints a summary: merged / skipped / failed counts, total wall time, total
   token spend, list of issue numbers
3. Posts that summary as a GitHub Discussion (or issue comment, if Discussion
   isn't enabled) — this becomes the human-readable audit trail

### Verifier-of-the-verifier

Catch-22 risk: what if `verifier` starts rubber-stamping?

- `verifier` is `opus` (most expensive model — appropriate for a security review).
- `verifier` MUST cite specific lines for any `findings[]` it returns; ralph
  rejects findings with no `file:line` anchor.
- After every merge, a `critic` agent (read-only) spot-checks 1 in 4 merged PRs
  against the original issue body. If `critic` says a merge didn't actually
  fix the issue, the loop halts and a human is paged.

This is "verification before completion" applied recursively — the loop is
only as trustworthy as its verifier, so we put a second pair of eyes on the
verifier's outputs.

## Stop conditions

- **Queue empty** — no label-matching issues in `pending` or `in-progress`
  state. Loop exits with summary.
- **3 consecutive `verifier` rejections on the same issue** — mark `skipped`,
  `needs-human`, advance. Resets the consecutive counter on success.
- **5 cross-issue `verifier` rejections in a row** — halt; possible systemic
  verifier/scanner drift. Human review.

No hard iteration cap, no token-budget cap. The queue-empty sentinel plus
the consecutive-failure paths are sufficient for the v1 scope.

## Out-of-band signals

Ralph listens for these mid-iteration and acts deterministically:

- `stop` typed at the terminal → graceful halt at the next ledger write
- `ctrl-c` twice → emergency halt; ledger preserved at last write
- GitHub rate-limit error → sleep 60s, retry; if persistent, halt
- Verifier/scanner drift signal (`verifier_rejects_in_a_row >= 5`) → halt, print
  last 5 issue numbers and rejection summaries to terminal, exit with non-zero
  so the loop is visibly broken

## Non-goals

- Generalizing beyond `security-scan`/`tech-debt` (separate spec after v1 ships)
- Multi-repo loops (separate spec)
- Concurrent processing of multiple issues (single-stream is enough for 12 items)
- Replacing the existing `scripts/issue_drafter.py` (it stays for scanner output;
  this loop drains the queue it creates)

## Risks

| Risk | Mitigation |
|---|---|
| `verifier` rubber-stamps | `opus` model + line-anchored findings + 1-in-4 `critic` spot-check |
| `executor` touches out-of-scope files | Diff-sanity gate in `verifier` |
| Loop burns budget on a stuck issue | 3-attempt skip + cross-issue halt at 5 |
| Main moves while working | `git fetch origin main` + rebase before retry |
| Subagent context overflow on long fix | Per-subagent narrow context; artifacts persisted on branch |
| Quality gate failures cascade | Each gate failure routes to a specific re-entry point, not full re-run |