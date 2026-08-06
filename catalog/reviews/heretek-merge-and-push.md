# heretek:merge-and-push

> First-party item. Reviewed against D7 spirit (self-pin, internal review only — no upstream).
> Date: 2026-08-05

## What

`heretek:merge-and-push` is the post-SDD merge skill. After a sub-project
implementation (SP1–SP4 pattern) completes and the final review returns
"Ready to merge", the skill performs the deterministic dance: verify a
clean working tree, fast-forward `main` from the feature branch, run the
full local gate on the merged result, push to `origin`, and clean up the
worktree + branch. It lives in the `skills-pack` plugin and is the only
allowed path to push a finished SP slice in this harness.

## Why first-party

The merge-and-push dance is a hard-gate workflow specific to heretek's
SDD pattern: clean tree check, fast-forwardability check, full local
gate on merged result, push, cleanup. The order and the "STOP on any
failure" rules are part of heretek's process discipline — there is no
upstream equivalent and a generic git alias would skip half the safety
properties.

## Alternatives considered

- **`gh pr merge --squash` + manual cleanup**: rejected because the
  workflow's value is the pre-flight checks (clean tree, named branch,
  fast-forwardable) and the post-merge test run before push; `gh`
  shortcuts skip those.
- **Plain `git` aliases**: rejected because they don't enforce the
  "STOP on test failure, do NOT push" invariant.
- **CI-driven merge queue**: rejected because heretek is a single-repo
  marketplace and the human-in-the-loop rebase / fix-up cadence is the
  whole point of the SDD pattern.
- **`heretek:merge-and-push` skill**: chosen — encodes the pre-flight
  checks, the user confirmation prompt, the test-on-merged-result gate,
  and the worktree + branch cleanup in one place.

## Verdict

- [x] Approved (first-party)
- [ ] Rejected

## Target plugin

`skills-pack`

## Vetting checklist (D7 spirit)

- [x] Internal review by maintainer recorded (date: 2026-08-05)
- [x] No external code execution surface beyond documented SKILL.md / hooks.json
- [x] No external network calls beyond declared MCP
- [x] License: MIT
