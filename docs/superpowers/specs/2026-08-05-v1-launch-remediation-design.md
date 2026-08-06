# v1 Launch Remediation — Design Spec

> Date: 2026-08-05. Status: design (awaiting user review). Companion to the canonical design spec `2026-08-03-heretek-marketplace-design.md` (PLAN.md) and the SP1–SP4 implementation plans.

## 1. Summary

Close all 9 v1 launch-blocker issues (Themes2, 3, 5) and produce a v1.0 release artifact, so the `heretek` marketplace can ship publicly with no known gap between catalog state and shipped state.

The marketplace v1 is feature-complete (11 first-party plugins, 67 tests passing per #13 body, security monitoring pipeline live per D18–D22). The gaps this spec targets are **the residual content drift, the partial refresh-pins deliverable, the missing public-facing mailbox wiring, the unposted v1.0 announcement, and the unblock-released maintenance-skills review** — every one of which gates a clean public launch.

This spec is **ship-strict**: no v1.0 ships until every one of the 9 issues is closed and the v1.0 release artifact is posted.

## 2. Goals and non-goals

### Goals

- Close 9 specific GitHub issues with merged PRs (#9, #10, #11, #12, #13, #14, #15, #16, #21).
- File 1 tracking issue that links all 9 sub-issues + this spec + the implementation plan.
- Produce 1 release artifact (CHANGELOG.md entry + draft release notes + `v1.0.0` tag + `gh release create` invocation).
- Honor the project invariants: D7 vetting bar, D11 SHA-ride, D15 hooks ownership, D17 catalog source-of-truth, `mem:task_completion` local gate.
- Stay inside the v1-launch framing — these are **blockers to ship**, not new features.

### Non-goals

- Issues #30–#34 (security pipeline Task 13 hardening) — separate v1.1 effort.
- Issues #1–#8, #17–#20 (v2 expansion backlog) — post-v1.0.
- Any change to the SP1–SP4 plan docs themselves — they're historical records.
- Any change to PLAN.md §14 (already marked ✅ RESOLVED for the items it lists).
- Adding new labels to the repo. Existing labels (`bug`, `enhancement`, `tech-debt`, `help wanted`, `documentation`, `question`, `testing`, `v1.1`, `security-scan`, `portability`) suffice.

## 3. Scope — the 9 issues

| # | Title | Theme | Mode |
|---|-------|-------|------|
| 9  | web-frontend + lsp-pack plugin.json missing `"dependencies": []` field (consistency) | 2 (drift) | agent-only |
| 10 | First-party items use SP1 ADR template; need per-item ADRs for self-pin items | 2 (drift) | agent-only |
| 11 | refresh_pins.py `--update-shas` flag is parsed but never acts | 2 (partial deliverable) | agent-only |
| 12 | ops — wire `security@heretek.ai` mailbox (currently SECURITY.md uses GitHub Advisories) | 5 (release readiness) | hard-gate |
| 13 | release — heretek marketplace v1.0 announcement (changelog, tag, GitHub release) | 5 (release readiness) | hard-gate (terminal) |
| 14 | design — should the heretek marketplace itself have a version? | 5 (release readiness) | agent-only |
| 15 | SP3: rust-clippy skill file missing (catalog/state drift) | 3 (bug) | agent-only |
| 16 | security: Dependabot flagged 2 moderate vulnerabilities on origin/main | 3 (bug) | agent-only |
| 21 | review: 3 heretek maintenance skills shipped to `.claude/skills/` + `.agents/skills/` | 5 (release readiness) | hard-gate |

## 4. Constraints (from clarifying questions)

- **Ship-strict.** All 9 closed before v1.0 ships.
- **Agent does all 9 end-to-end.** Hard-gates only at the 3 human-action points (#12 mailbox wiring, #21 skills review, #13 release post). Agent produces runbook / review packet / release draft; human executes the external action; agent merges and closes the issue.
- **One issue, one PR.** Branched from `main`. Conventional commits. PR trailer `Closes #N`. Matches SP3/SP4 per-plugin pattern.
- **Strict dependency order.** 9 steps in sequence (see §6); no parallel fan-out.

## 5. Architecture & artifacts

### Artifact map

```
docs/superpowers/specs/2026-08-05-v1-launch-remediation-design.md   ← this file
docs/superpowers/plans/2026-08-05-v1-launch-remediation.md          ← from writing-plans skill

GitHub:
  + 1 tracking issue on Heretek-AI/heretek-claude-harness
      title: "v1.0 launch remediation: ship-strict closure of 9 blockers"
      body: lists 9 sub-issues + links to spec + plan
  + 9 branches, 9 PRs (one per sub-issue), all branched from main
  + 1 release tag: v1.0.0 (pushed by human after #13 PR merges)

Local:
  + CHANGELOG.md (new, at repo root) — first entry is v1.0.0
  + docs/v1.0-release-notes.md (drafted by agent for #13, human posts via gh release create)
  + docs/ops/security-mailbox-runbook.md (produced by agent for #12, human executes)
  + catalog/reviews/heretek-{catalog,refresh-pins,merge-and-push}.md (produced by agent for #21)
```

### Components

- **Spec** (this file) = source of truth for *what* and *why*. Stable post-approval.
- **Plan** (next step, from `writing-plans`) = TDD task list per issue. Source of truth for *how* and *in what order*. Gets `progress:` lines added as issues close.
- **Tracking issue** = coordination hub. Status dashboard; updated after each PR merge; closes when #13 merges.
- **Per-issue branches** = the 9 atomic units of work. Each branch carries one issue's commits + a `Closes #N` trailer.
- **CHANGELOG.md** = running log. Each PR adds an entry under `## Unreleased`; the final step converts `## Unreleased` → `## v1.0.0` (date).

### Data flow

```
spec (this doc) ──► plan (writing-plans) ──► 9 issues × {branch, PR, merge}
                                              │
                                              ▼ tracking issue updated per merge
                                              │
                                              ▼
                                  #13 release prep → human posts
```

### Boundaries

- Plan doc owns per-issue work order.
- Tracking issue owns status dashboard.
- Spec stays stable (no edits after approval); plan gets `progress:` lines added as issues close.

## 6. Sequencing — 9 steps in dependency order

| Step | Issue | Depends on | Why this position |
|------|-------|------------|-------------------|
| 1 | **#14** marketplace-version design | — | Design decision gates the release-tag format used in #13. If marketplace needs a `metadata.version`, that's a code change; if not, #13 stays simple. |
| 2 | **#11** refresh_pins `--update-shas` fix | — (sequenced after #14 for context, not because of code overlap) | Closes a partial SP4 deliverable. Gives downstream catalog-drift items a working SHA-bump tool. |
| 3 | **#9** plugin.json `dependencies: []` | #11 | Smallest content-drift fix. Tests the schema before tackling heavier drift items. |
| 4 | **#10** per-item ADRs | #9, #11 | After tooling + schema consistency are green, ADRs slot in cleanly. |
| 5 | **#15** rust-clippy skill | #10 | Catalog/state drift. Likely surfaces from `#11 refresh_pins` re-audit; sequence after so test infra is up to date. |
| 6 | **#16** Dependabot moderate CVEs | — (independent) | Dep bumps may touch `requirements*.txt`. Doing before release-prep means v1.0 ships with green Dependabot dashboard. |
| 7 | **#12** `security@heretek.ai` mailbox runbook | — (external system) | Agent produces runbook. Human executes. **Hard gate.** |
| 8 | **#21** skills review packet | — (human review) | Agent produces review packet. Human signs off on PR #22. **Hard gate.** |
| 9 | **#13** v1.0 announcement | #14, #12, #21 (all closed) | Terminal step. CHANGELOG.md + release notes + tag command. Human posts via `gh release create`. **Hard gate.** |

### Sequencing rationale

- **#14 first** — it's a design decision, not a code change — cheap to do and unblocks #13's release-tag format.
- **#11 second** — it underpins catalog hygiene for steps3–5. The other content-drift fixes are easier when the refresh loop works.
- **#9, #10, #15 cluster** — pure content drift. Order is smallest-first (#9) → ADR scaffolding (#10) → largest known gap (#15).
- **#16 standalone** — dep bumps don't depend on or block anything else but should land before release-prep so the changelog captures them.
- **#12, #21 buffer the terminal** — both are external/human-gated. Sequencing them as steps7–8 gives the human time to act on the runbooks while the agent finishes catalog work.
- **#13 last** — gates on all of the above.

### Hard-gate semantics

When the agent reaches a hard-gate step (#12, #21, #13), it stops after producing the artifact (runbook / review packet / changelog + tag command) and waits for human confirmation before the next step starts. No PR for a hard-gate step merges without explicit human go-ahead.

## 7. Per-issue execution pattern

### Branch + PR template (every issue follows this)

```
Branch name:  fix/<num>-<slug>    e.g. fix/11-refresh-pins-update-shas
Base:         main
Commit style: conventional commits  e.g. fix(refresh-pins): implement --update-shas (closes #11)
PR trailer:   Closes #N            links PR to issue; auto-closes on merge
```

### Mode 1 — agent-only (steps1–6: #14, #11, #9, #10, #15, #16)

1. Read issue body for acceptance criteria.
2. Implement + extend or add tests (see §8 test matrix).
3. Run local gate (§9).
4. Conventional-commit + push + open PR.
5. Wait for CI green; fix failures; merge (squash per repo default).
6. Update tracking issue (checkbox → done).

### Mode 2 — hard-gate (steps7–9: #12, #21, #13)

1. Same branch setup.
2. Produce the artifact (runbook / review packet / changelog + release notes + tag command).
3. Run local gate where applicable (#13 changelog touches marketplace generation; #12 and #21 don't).
4. Open PR with `human-action-required` label and an artifact-handoff comment.
5. **Stop.** Wait for human confirmation before merging.
6. After human confirms: merge, update tracking issue, advance to next step.

## 8. Test matrix

| Issue | Test additions |
|-------|----------------|
| #9  | `tests/test_plugin_components.py`: parameterized check that every `plugins/*/plugin.json` carries `dependencies: []`. |
| #10 | `tests/test_catalog_vetting.py`: ADR-file-exists assertion per first-party item (per `vetting.review` link). |
| #11 | `tests/test_refresh_pins.py`: end-to-end `--update-shas` against a fixture repo (mocked GitHub API). |
| #15 | New `tests/test_rust_clippy_skill.py`: skill file exists + matches catalog entry. |
| #16 | Extend `tests/test_action_pinning.py` or new `tests/test_dependencies.py`: regression for bumped versions + lockfile check. |
| #12, #21, #13 | No tests (external / human / release artifacts). |

## 9. Verification (every PR runs all four, hard-fail per `mem:task_completion`)

```bash
python scripts/validate.py # schema validation
python scripts/generate_marketplace.py                # regenerate marketplace.json
git diff --exit-code .claude-plugin/marketplace.json   # idempotency
pytest -q                                             # full suite
```

**Additional gate for #11 / #16** (pipeline modules per security spec §8): coverage ≥ 90% on `scripts/refresh_pins.py` and any dep-bump helper.

**Coverage reporting.** `.coverage` is currently untracked and stale (Aug 5). Step1 (or the first PR that touches `pyproject.toml` / `requirements*.txt`) adds `.coverage` to `.gitignore` if not already, and configures `pyproject.toml` `tool.coverage` to write `coverage.xml` for CI consumption.

## 10. Hard gates — detailed

### #12 — `security@heretek.ai` mailbox

**Agent produces.** `docs/ops/security-mailbox-runbook.md` (DNS A/MX records, Google Workspace alias wiring, GitHub Advisory email config, `docs/SECURITY.md` pointer edit). PR with `human-action-required` label.

**Human executes.** Adds DNS records, sets up the alias, updates GitHub repo settings, flips SECURITY.md link live. Confirms in PR thread.

**Resolution.** Human comments "mailbox live" on PR; agent merges, closes #12.

### #21 — 3 heretek maintenance skills review

**Agent produces.** Review packet: `pytest -q` summary, file-diff shortlist (3 SKILL.md files + `tests/smoke/`), smoke-test run output, ADR cross-references for the 3 skills. Posted as PR comment on PR #22.

**Human executes.** Reviews skills against D7 / D11 / D15 / D17 invariants; approves or requests changes.

**Resolution.** Human approves PR #22; agent merges, closes #21.

### #13 — v1.0 announcement (terminal)

**Agent produces.** `CHANGELOG.md` with `## v1.0.0 (date)` entry (entries from each closed issue), `docs/v1.0-release-notes.md` (drafted), local tag invocation `git tag -a v1.0.0 -m "heretek marketplace v1.0.0"` (committed in PR but tag push deferred), `gh release create v1.0.0 --notes-file docs/v1.0-release-notes.md` command printed in PR comment.

**Human executes.** Reviews changelog + notes, runs `gh release create`, copies notes into the GitHub Release body, marks PR #13 as the release PR.

**Resolution.** Release live on GitHub; agent closes #13.

## 11. Success criteria

1. All 9 GitHub issues closed with PRs that merged.
2. Tracking issue closed with all 9 sub-issues linked + each marked done.
3. `CHANGELOG.md` carries a `## v1.0.0` entry; `## Unreleased` is empty.
4. Local `v1.0.0` tag exists and is pushed to origin.
5. GitHub Release `v1.0.0` exists with `docs/v1.0-release-notes.md` body.
6. `mem:task_completion` local gate exits 0 from `main`:
   - `validate.py` OK
   - `generate_marketplace.py` exits 0
   - `git diff --exit-code .claude-plugin/marketplace.json` clean
   - `pytest -q` green
7. Dependabot dashboard clean for `main` (no open moderate+ alerts).
8. `.coverage` either ignored or regenerated as part of CI; no stale untracked file in working tree.

## 12. Out of scope (deferred)

| Issue(s) | Deferred to | Why |
|----------|-------------|-----|
| #30–#34 | v1.1 (security pipeline Task 13) | Post-merge hardening; not launch-blocking. |
| #1–#8 | v2 | Expansion backlog; speculative. |
| #17–#20 | v2 | Code-quality pack backlog. |
| #22 | — | Already merged (PR #22 merged into main per git log); #21 review is the open thread. |

## 13. Open questions

None at design time. Decisions made during clarifying Q&A:

1. Scope = v1 launch blockers (Themes 2 + 3 + 5).
2. Priority = ship-strict (all 9 in one push).
3. Boundary = agent does all, hard-gates at human-action points.
4. PR cadence = one issue, one PR.
5. Approach = A (strict dependency order), no parallel fan-out.

If new questions arise during implementation, surface them via PR comments on the tracking issue; do not amend this spec.

## 14. References

- Canonical design spec: `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` (PLAN.md)
- v2 code-quality backlog spec: `docs/superpowers/specs/2026-08-05-v2-code-quality-issue-set-design.md`
- Security monitoring pipeline spec: `docs/superpowers/specs/2026-08-05-security-monitoring-pipeline-design.md`
- Implementation plans: SP1–SP4 (`docs/superpowers/plans/2026-08-03-sp{1,2,3}.md`, `docs/superpowers/plans/2026-08-05-sp4-aggregation-launch.md`), maintenance skills (`docs/superpowers/plans/2026-08-05-heretek-maintenance-skills.md`), security pipeline (`docs/superpowers/plans/2026-08-05-security-monitoring-pipeline.md`)
- Project memories: `mem:core`, `mem:conventions`, `mem:tech_stack`, `mem:task_completion`, `mem:suggested_commands`