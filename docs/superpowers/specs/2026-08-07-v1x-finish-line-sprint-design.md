---
date: 2026-08-07
topic: v1x-finish-line-sprint
status: proposed
parent: docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md
related_issues: [32, 34, 33, 31, 12]
---

# v1.x Finish-Line Sprint — Design Spec

> Date: 2026-08-07. One-week sprint closing out v1.x phase-1 hardening: #32 (GITHUB_REPOSITORY env) → #34 (shallow-clone portability). Triggers #33 (spec §8 features) by end. Triage-only spec; implementation lives behind per-issue branch → PR.

## 1. Summary

The v1.x phase-track (#88) holds seven open issues. Two are already closed (#30, #46). Of the remaining five, three (#31 coverage, #33 spec §8, #12 mailbox) are larger work that should wait for the post-sprint batch. This sprint lands **#32 and #34** — two small, independent hardening items whose combined diff is ~30 LOC + ~6 tests + a README version note. Both unblock #33 (spec §8 features) and tighten the v1.1 release bar before declaring phase-1 closed.

Scope is intentionally tight. Sprint owner works sequentially (single-thread), ships one PR per issue, runs CI on each before merging.

## 2. Goals and non-goals

### Goals

- Land #32: replace hardcoded `"Heretek-AI/heretek-claude-harness"` in `scripts/security_scan.py:194` with `os.environ.get("GITHUB_REPOSITORY", "<fallback>")`. Add 2 tests covering both branches (env present, env absent → fallback).
- Land #34: replace `git clone --depth 1` in `scripts/security_scan.py:_shallow_clone` with `git clone --no-checkout <url>` so the subsequent `git checkout <sha>` never triggers an auto-fetch round-trip. Add 1 test mocking `subprocess.run` to assert the `--no-checkout` invocation shape.
- Each PR passes `pytest -q` and `python scripts/validate.py` on push.
- Both issues auto-close via PR body reference (`Closes #N`).

### Non-goals

- #31 (90% coverage on 4 modules) — deferred. ~25-40 test cases; not a one-week item.
- #33 (spec §8 features) — deferred. Depends on #32 + #31 landing; opens next sprint.
- #12 (security@heretek.ai mailbox) — deferred. Admin work, not engineering; parked.
- Refactor of `scripts/security_scan.py` beyond the two pinpoint edits.
- New CI workflow or coverage gate. Existing CI is sufficient.

## 3. Sequence and dependency map

```
PR #32  ──→  CI green  ──→  merge  ──→  PR #34  ──→  CI green  ──→  merge  ──→  close sprint
```

Sole dependency between the two PRs: PR #34's branch is rebased onto `main` *after* PR #32 lands, so its test fixtures see the env-var path being exercised. No code-level coupling — could be parallelized with a worktree, but sequential keeps review simple and surfaces CI regressions in order.

## 4. Per-issue design

### 4.1 #32 — GITHUB_REPOSITORY env var

**Files touched (3):**
- `scripts/security_scan.py` — read env at function entry, thread through to `draft_issue_and_pr(repo=...)`. Local CLI invocations keep upstream as the fallback default.
- `tests/test_security_scan.py` — add 2 tests. Use `monkeypatch.setenv("GITHUB_REPOSITORY", "fork/repo")` for the present case; `monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)` for the absent case. Mock `draft_issue_and_pr` to capture the `repo=` kwarg.
- No spec change. §5.4 already calls for "configurable repo"; this is the implementation.

**Acceptance check:**
- `pytest tests/test_security_scan.py -k "repo"` exits clean (2 new tests).
- Local `python scripts/security_scan.py --help` still references upstream.
- A fork's CI run with `GITHUB_REPOSITORY=fork/repo` opens issues against the fork (verified manually or in a fork-PR CI run).

### 4.2 #34 — `_shallow_clone` portability (Option A)

**Files touched (3):**
- `scripts/security_scan.py:_shallow_clone` — swap `git clone --depth 1 <url> .` for `git clone --no-checkout <url> <target>`. The `git checkout <sha>` that follows is unchanged. Cloning into `<target>` (not `.`) keeps the working-tree layout identical to before.
- `tests/test_security_scan.py` — add 1 test. Mock `subprocess.run`, invoke `_shallow_clone("owner/repo", "abc123", tmp_path)`, assert the first `subprocess.run` call has args `["git", "clone", "--no-checkout", "https://github.com/owner/repo.git", str(target)]` and the second is `["git", "checkout", "abc123"]` with `cwd=str(target)`.
- `README.md` — under the "Common commands" section, add a one-line prerequisite: `requires git >= 2.30 (auto-fetch safe-checkout was added in 2.30)`. Belt-and-suspenders for any future flag like `--depth` that might re-introduce the fragility.

**Acceptance check:**
- `pytest tests/test_security_scan.py -k "shallow_clone"` exits clean (1 new test).
- Local manual run on a system with git 2.43: `python -c "from scripts.security_scan import _shallow_clone; ..."` clones a test repo and checks out the requested SHA without network round-trip during checkout (verified by capturing `strace` or `git trace` — out of scope for this issue's PR, documented as follow-up if desired).

## 5. Risk and rollback

| Risk | Likelihood | Mitigation |
|---|---|---|
| PR #32 breaks a CI workflow that depends on the hardcoded repo | low | One workflow reads this code path (`security-scan.yml` daily cron). PR run surfaces it before merge. |
| PR #34 clone layout change breaks a downstream consumer | low | `_shallow_clone` is private to the module; only caller is `main()` in the same file. |
| Sprint owner context-switches mid-issue | medium | Single-thread, no parallel work. PR review happens after each lands. |
| `--no-checkout` clone still triggers a fetch in some git versions | low | `--no-checkout` skips the working-tree fetch; `checkout <sha>` against a complete object database is local. No network call expected. |

Rollback: each PR reverts independently via `git revert <merge-sha>`. No schema or catalog change, so no follow-up cleanup.

## 6. Testing strategy

- All tests hermetic (no network, no real subprocess). Use `monkeypatch`, `unittest.mock`, `tmp_path`.
- Coverage delta: `scripts/security_scan.py` rises from 63% → ~67% on this sprint. #31 drives the push to 90%.
- No new CI gate added. Existing `.github/workflows/validate.yml` runs `pytest -q` + `scripts/validate.py`; that's the merge bar.

## 7. Definition of done (sprint)

- [ ] PR #32 merged; #32 closed via PR body reference.
- [ ] PR #34 merged; #34 closed via PR body reference.
- [ ] `pytest -q` green on `main` after both merges.
- [ ] `python scripts/validate.py` green on `main` after both merges.
- [ ] No new untracked files in working tree.
- [ ] Sprint retro recorded as a 1-paragraph comment on #88.

## 8. Out-of-scope follow-ups (next sprint candidate)

- #31 (coverage 90% on 4 modules)
- #33 (spec §8 features — VT cap, state-recovery, emergency issue, suppression)
- #12 (security@heretek.ai mailbox wiring)
- #20 (hook orchestrator ADR — v2 phase but low coordination cost)

## 9. References

- Issue #88 (v1.x phase-track)
- Issue #87 (roadmap index)
- Spec: `docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md` §5.1, §5.4, §8
- Plan: `docs/superpowers/plans/2026-08-05-security-monitoring-pipeline.md` Task 13
- Final review verdict: "I3" (#32), "I5" (#34)
- Recent commits for pattern reference: `b10daa4` (#30), `bdab24e` (#46)
