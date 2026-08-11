---
date: 2026-08-09
topic: issue-loop-architecture
status: accepted
parent: docs/superpowers/plans/2026-08-09-issue-loop.md
closes: skill-activation-bug
---

# Issue Loop Architecture — Decision

> Date: 2026-08-09. Reframes the activation model for the issue-loop
> pipeline shipped via PR #192 (commits `6a08cd3`, `8859dc4`).
> Author: agent-led per `2026-08-09-issue-loop.md` follow-up.

## Context

The original implementation plan (`2026-08-09-issue-loop.md`) defines
the driver (`scripts/issue_loop/driver.py`) as a library with all
collaborators injected. The skill at
`.claude/skills/issue-loop/SKILL.md` activates the loop via:

```bash
python -m scripts.issue_loop.driver --dry-run --issue 158
python -m scripts.issue_loop.driver --run-until-empty
```

Neither command works:

1. `driver.py` has no `__main__` block; the package has no `__main__.py`.
   Both commands exit 0 with no side effects.
2. `candidates_provider`, `pr_opener`, `squash_merge` are constructor
   parameters with no production wiring.
3. `_default_dispatch`, `_real_fetcher`, `_real_github_merge` all raise
   `NotImplementedError`.
4. The `Agent` tool that runs subagents only exists inside the Claude
   orchestrator — a Python CLI cannot dispatch subagents. A fully
   autonomous Python CLI is architecturally impossible.

The plan's Task 7 reads: "Driver wires real Agent SDK dispatch into
`SubagentRunner` (via `Agent` tool with subagent_type and model override
per role)". The `Agent` tool is an in-process Claude tool. The plan
implicitly assumes Claude **is** the orchestrator. The CLI activation
in SKILL.md is therefore aspirational, not wired.

## Decision

Reframe the architecture:

- **Python = state.** `scripts/issue_loop/cli.py` (new) exposes thin
  argparse subcommands that wrap the existing `Ledger` methods:
  `select-next`, `mark-attempt`, `mark-merged`, `mark-skipped`,
  `mark-failed`, `record-reject`, `reset-rejects`, `rejects-in-a-row`,
  `status`. No subagent dispatch, no GitHub API calls, no gate polling.
- **Claude = orchestrator.** `.claude/skills/issue-loop/SKILL.md`
  (rewritten) is now a ralph-mode prompt that Claude executes against
  itself: read the ledger via CLI, dispatch subagents via the `Agent`
  tool, open/merge PRs via the GitHub MCP, poll the gate via MCP, mark
  state via CLI. Halt on `rejects-in-a-row >= 5` or queue empty.
- **Driver library kept.** `scripts/issue_loop/{driver,subagents,gate,merge}.py`
  stay as unit-testable library code. They are not invoked in the new
  flow but remain for future re-wiring (e.g., if the Agent SDK ever
  becomes callable from a non-Claude process).

## Why this shape

- **Matches the plan's intent.** Task 7 says the driver "wires real
  Agent SDK dispatch". The `Agent` tool is a Claude tool — the plan
  already assumed Claude drives.
- **Reuses everything that already works.** All 7 existing
  `scripts/issue_loop/` modules stay as-is. Only `__init__.py` is
  unchanged; `cli.py` is additive.
- **TDD-able.** Each CLI subcommand is a 5–15 line wrapper around an
  existing tested method. `tests/test_issue_loop_cli.py` adds 18 tests
  covering each subcommand plus the cross-issue reject-reset edge case.
- **Resumable.** Ledger is unchanged. Process restart or skill
  re-invocation picks up where the last successful tick left off.
- **Honest.** No `NotImplementedError` paths in production. The CLI
  either works or fails loudly. No hidden coupling to a future PR.

## Consequences

- The activation line in any external docs (`CATALOG.md`, README,
  runbook) must change from `python -m scripts.issue_loop.driver ...`
  to "invoke the `issue-loop` skill and let Claude orchestrate".
- `SubagentRunner.run_pipeline` becomes a library artifact; the new
  flow calls the `Agent` tool directly per role, with
  `scripts/issue_loop/prompts/<role>.md` as the prompt body.
- `GatePoller._real_fetcher` stays unimplemented; the new flow polls
  the GitHub MCP from the orchestrator instead. If `GatePoller` ever
  needs a non-Claude caller, that fetcher will need to be wired.
- 1 pre-existing test flake (`test_install_sh_exists_and_executable`)
  is unrelated and not addressed here.

## Verification

Drain #158 end-to-end via the rewritten skill. Expected ledger state
after:

```json
{"158": {"status": "merged", "pr_url": "https://.../pull/N", "attempts": 1}}
```

`pytest tests/test_issue_loop_cli.py -v` covers all subcommands + edge
cases. Spot-check: kill Claude mid-drain, re-invoke the skill, confirm
no duplicate processing (terminal entries skipped).

## Followups (not in this ADR)

- Lower the verifier `Model='opus'` requirement? **No** — security
  findings need the best model we have (existing constraint, unchanged).
- ~~Widen the label filter beyond `security-scan`/`tech-debt`? Requires
  updating `.heretek/issue-loop-config.json` AND this spec — coupled.~~
  **Resolved 2026-08-10:** filter widened to all open issues per
  user-requested full-queue drain starting from issue #1. See
  *Filter widening* section below.
- Wire real subagent dispatch into `SubagentRunner.run_pipeline` for
  callers that aren't Claude? Deferred until a non-Claude caller exists.

## Filter widening (2026-08-10)

User-requested: drain the entire open issue queue starting from #1,
not just `security-scan`/`tech-debt`. Subagent roles and prompt bodies
stay unchanged; only the candidate filter widens.

**Changes:**

- `.heretek/issue-loop-config.json`: `labels: []` (was `["security-scan",
  "tech-debt"]`). Bumped `version: 1 → 2`.
- `scripts/issue_loop/cli.py`: `DEFAULT_LABELS = []`. `_list_candidates_via_gh`
  now passes zero `--label` flags to `gh issue list`, so all open issues
  are returned. `Ledger.select_next` already picks the lowest-numbered
  unprocessed candidate, so the queue drains #1 → top by default.

**Expected behavior on enhancement / tracking issues:**

The existing prompts are tuned for security findings with scanner
reports (`explore.md` expects a flagged file:line, `executor.md` enforces
"touch only files named in the original scanner report"). For enhancement
or tracking issues without a scanner report, the executor will likely
abort with `BLOCKED: requires out-of-scope change` or the planner will
write `BLOCKED: too large for single-iteration loop`. These outcomes
land in the ledger as `failed` (non-terminal) or `skipped` (terminal),
so the queue still drains — those issues just don't get auto-implemented.

**Pause conditions:**

- Cross-issue verifier rejects in a row ≥ 5 (config
  `halt_after_cross_issue_rejects`): loop halts.
- Per-issue attempts ≥ 3 (config `max_per_issue_attempts`): issue
  marked `failed`, loop moves on.
- Queue empty: loop halts.
