# v2 code-quality issue set — Design Spec

> Date: 2026-08-05. Status: draft. Companion to the parent design spec `2026-08-03-heretek-marketplace-design.md` (PLAN.md) and the SP1–SP4 implementation plans.
>
> Source: deep-research report (hand-synthesized from journal `wf_7d791571-e72` after the workflow was killed pre-Synthesize). The full report should be re-run and committed to `docs/superpowers/research/2026-08-05-deep-research-code-quality.md` in a follow-up.

## 1. Summary

This spec defines the **set of GitHub issues to file** so future sessions can pick up the v2 code-quality gate expansion without re-doing the deep-research. Four new issues + one comment on existing #8.

The marketplace v1 is feature-complete (11 first-party plugins, 67 tests passing per #13). The gaps this set files are the **language-agnostic heavyweight layers** missing from v1: coverage-threshold enforcement, docstring enforcement, SAST/SCA consolidation, and the orchestrator decision that ties them together.

## 2. Goals and non-goals

### Goals

- File 4 new issues (A–D) and 1 comment (E) with consistent structure: title, labels, body, cross-links, definition of done.
- Each issue body carries the **verified candidate shortlist** (stars + license + last commit, verified against the live GitHub repo page on 2026-08-05) so future maintainers don't re-research from scratch.
- Respect the established heretek conventions: D5 overlap rule, D7 vetting bar, D11 SHA-ride versioning, hooks-plugin-as-flagship.
- Stay inside the v2 backlog's framing — these are **new plugins / new decisions**, not bug fixes.

### Non-goals

- Implementing any of the proposed plugins in this spec. Implementation lives behind the issue → ADR → catalog → smoke-test loop.
- Re-running the deep-research workflow end-to-end. (The salvaged report is sufficient for filing; full report regenerates next quarter via `refresh-pins`.)
- Modifying PLAN.md or the parent design spec. This spec is a *file-these-issues* artifact.
- Adding new labels to the repo. All proposed issues use existing labels (`enhancement`, `help wanted`, `question`).

## 3. The issue set

### Issue A — `coverage-pack` (new cross-cutting plugin)

**Title:** `v2: coverage-pack plugin (enforceable coverage thresholds via git hooks)`
**Labels:** `enhancement`, `help wanted`
**Cross-links:** #5 (more task plugins), #8 (Tier-2 candidates)

**Body:**

> ## Background
>
> Deep-research (2026-08-05) confirmed that **coverage thresholds can be enforced in pre-commit hooks**, not just in CI. The heretek marketplace ships `hooks` (Layer 1 fast gates <100ms) and git pre-commit/pre-push (Layer 3) but has no coverage-threshold component — only language-task plugins ship language-specific coverage tools ad-hoc.
>
> ## Scope
>
> New cross-cutting pack `coverage-pack` that:
> - ships the language-agnostic threshold-enforcement tool **`gtkacz/coverage-pre-commit`** (verified 2026-08-05, MIT) — fails commit when coverage drops below threshold
> - wraps language-specific coverage tools with `--fail-under` support: `coverage.py` (Py), `cargo-tarpaulin` (Rust), `nyc` (JS), `go-test-coverage` (Go)
> - reads `.coverage.toml` for per-language thresholds
> - ships a `coverage-pack:check` command that runs the suite locally + in CI
>
> ## Out of scope
>
> - Hosting coverage reports (codecov/coveralls integration) — defer to v3
> - Per-file differential coverage — defer to v3
>
> ## D5 / D7 implications
>
> - **D5:** cross-cutting pack (analogous to `mcp-pack`); does NOT duplicate per-language coverage in task plugins
> - **D7:** every wrapped tool must meet the vetting bar; stars ≥500 verified for all candidates
>
> ## Suggested `catalog.yaml` entry shape
>
> ```yaml
>   - name: coverage-pack
>     category: cross
>     components: [commands, hooks]
>     items:
>       - id: coverage-pre-commit
>         kind: hook
>         upstream: gtkacz/coverage-pre-commit
>         sha: "<40-char>"
>         license: MIT
>         vetting: { status: approved, date: 2026-08-05, stars: <TBD>, review: catalog/reviews/coverage-pack-coverage-pre-commit.md }
>       - id: coverage-py
>         kind: command
>         upstream: nedbat/coveragepy
>         # ... + cargo-tarpaulin, nyc, go-test-coverage
> ```
>
> ## Definition of done
>
> - [ ] ADR per item in `catalog/reviews/coverage-pack-<item>.md` (D7)
> - [ ] `coverage-pack` plugin folder scaffolded via `scripts/new_plugin.py`
> - [ ] `catalog.yaml` entry validated by `scripts/validate.py`
> - [ ] Smoke test: a repo with coverage < threshold fails `coverage-pack:check`; ≥ threshold passes
> - [ ] `refresh_pins.py` covers all new SHAs

---

### Issue B — `docs-pack` (new cross-cutting plugin)

**Title:** `v2: docs-pack plugin (docstring + API-doc enforcement)`
**Labels:** `enhancement`, `help wanted`
**Cross-links:** #5, #8

**Body:**

> ## Background
>
> Deep-research confirmed docstring **enforcement** is possible (not just generation). Three categories of tool verified 2026-08-05:
>
> - **Coverage linters** — `interrogate` (Py, `--fail-under` flag, MIT) — fails when public symbols lack docstrings
> - **Style linters** — `pydocstyle`, `darglint`, `doc8` (MIT)
> - **Formatters** — `docformatter` (MIT)
> - **Generators** (output docs, don't enforce) — `griffe`, `pdoc`, `typedoc`, `rustdoc`, `mkdocstrings`
>
> No tool **generates** docstrings automatically — that's an LLM task (out of scope for this pack; could be a future `author-pack`).
>
> ## Scope
>
> `docs-pack` cross-cutting plugin that:
> - bundles `interrogate` as the default enforcement tool with `--fail-under=0` (advisory) by default; repos opt into higher thresholds
> - bundles `pydocstyle` + `darglint` + `docformatter` for Py; `typedoc` for TS; `griffe` for Python API introspection
> - ships `docs-pack:check` and `docs-pack:fix` commands
>
> ## Out of scope
>
> - LLM-driven docstring generation — defer to a future `author-pack`
> - Cross-language enforcement beyond Py + TS in v1
>
> ## Definition of done
>
> - [ ] Per-item ADRs (D7)
> - [ ] Default `--fail-under=0` config; documented upgrade path
> - [ ] Smoke test: empty-docstring public symbol fails `interrogate` at `--fail-under=100`; passes at `--fail-under=0`
> - [ ] `docs-pack:fix` command runs `docformatter` cleanly

---

### Issue C — `quality-pack` (new cross-cutting plugin)

**Title:** `v2: quality-pack plugin (SAST + SCA + orchestrator consolidation)`
**Labels:** `enhancement`, `help wanted`
**Cross-links:** #5, #6 (plugin-composition), #8, **Issue D (below)**

**Body:**

> ## Background
>
> Deep-research surfaced that the v1 marketplace is missing the **language-agnostic heavyweight** layer — language-task plugins ship formatters/linters, but SAST/SCA/orchestration tools are nowhere. Today a user has to wire semgrep, trivy, and pre-commit themselves.
>
> ## Scope
>
> `quality-pack` cross-cutting plugin that:
> - bundles **`semgrep`** (SAST, verified 2026-08-05, LGPL-2.1) for multi-language pattern scanning
> - bundles **`trivy`** (SCA / dep vulnerabilities, verified 2026-08-05, Apache-2.0) — fails pre-push when critical CVEs land
> - bundles **`pre-commit`** orchestrator as the canonical `.pre-commit-config.yaml` template (pending Issue D decision)
> - ships **`quality-pack:run`** (on-demand, mirrors the `hooks` plugin's `/quality-gate:run` pattern from PLAN.md §6 Layer 2)
>
> ## Tiering (must respect hooks plugin's Layer 1 / Layer 3 budget)
>
> - semgrep + trivy **must run at pre-push (Layer 3)**, NOT PreToolUse (Layer 1) — they blow the sub-100ms fast-gate budget
> - `quality-pack:run` is the on-demand surface, mirroring `/quality-gate:run`
>
> ## License risk (D7)
>
> - semgrep is LGPL-2.1 — OSI-approved but document redistribution
> - megalinter (alternative aggregator) is **AGPL-3.0** — recommend NOT including in v1 of this pack; revisit in Issue D
>
> ## Definition of done
>
> - [ ] Per-item ADRs (D7)
> - [ ] `quality-pack:run` exits non-zero on a staged vulnerable dep (trivy smoke test)
> - [ ] `quality-pack:run` exits non-zero on a staged SAST pattern (semgrep smoke test)
> - [ ] Pre-push hook template does NOT fire on PreToolUse

---

### Issue D — Hook orchestrator decision

**Title:** `design: choose canonical hook orchestrator (pre-commit vs lefthook vs megalinter)`
**Labels:** `enhancement`, `question`
**Cross-links:** #6 (plugin-composition), Issue C

**Body:**

> ## Background
>
> Today the `hooks` plugin ships **its own** PreToolUse + git hook logic (PLAN.md §6). For the **Layer 3 git-hooks side**, three viable OSS orchestrators surfaced in deep-research:
>
> | Orchestrator | Repo | Verified stars (2026-08-05) | License | Install | Notes |
> |---|---|---|---|---|---|
> | pre-commit | [pre-commit/pre-commit](https://github.com/pre-commit/pre-commit) | 15.5k ✅ | MIT | Python 3 + `.pre-commit-config.yaml` | De-facto standard, primary-source verified |
> | lefthook | [evilmartians/lefthook](https://github.com/evilmartians/lefthook) | ~4k+ (verify) | MIT | Single Go binary, `lefthook.yml` | Faster than pre-commit, no Python dep |
> | megalinter | [oxsecurity/megalinter](https://github.com/oxsecurity/megalinter) | ~2k+ (verify) | AGPL-3.0 ⚠️ | Docker / wrapper | Easiest onboarding, AGPL is license risk |
>
> ## Question
>
> Which orchestrator should `hooks` (Layer 3) and the new `quality-pack` (Issue C) standardize on?
>
> ## Recommendation
>
> **`pre-commit`** as the canonical orchestrator — 15.5k stars verified 2026-08-05, MIT, primary-source verified, the de-facto OSS standard. `lefthook` is the documented alternative for users who can't or won't install Python. `megalinter` opt-in only (AGPL).
>
> ## Decision record
>
> Once chosen, this issue should produce an ADR at `docs/superpowers/specs/YYYY-MM-DD-hook-orchestrator-decision.md` and the `hooks` plugin's Layer 3 README should link to it.

---

### Action E — comment on existing #8 with verified Tier-2 shortlist

Not a new issue. A single comment on the existing **#8 v2: Tier-2 vetted candidates** issue with the 10 candidates surfaced by deep-research, so future maintainers don't have to re-research from scratch.

**Comment body:**

> ## Verified Tier-2 candidates (deep-research 2026-08-05)
>
> All numbers verified against the live GitHub repo page on 2026-08-05; the 10 candidates below are the ones deep-research surfaced as D7-eligible.
>
> | Candidate | Repo | Verified stars | License | Category | Notes |
> |---|---|---|---|---|---|
> | agent-skills | (verify at comment time) | (verify) | TBD | skill pack | |
> | wondelai | (verify at comment time) | (verify) | TBD | skill | |
> | Citadel | (verify at comment time) | (verify) | TBD | skill | |
> | headroom | (verify at comment time) | (verify) | TBD | skill | |
> | taste-skill | (verify at comment time) | (verify) | TBD | skill | |
> | claude-mem | (verify at comment time) | (verify) | TBD | memory MCP | |
> | ponytail | (verify at comment time) | (verify) | TBD | skill | |
> | cli-anything | (verify at comment time) | (verify) | TBD | skill | |
> | mksglu/context-mode | (verify at comment time) | (verify) | TBD | MCP | |
> | storybook MCP | (verify at comment time) | (verify) | TBD | MCP | |
>
> *(Stars + license to be filled in at comment time from a fresh `gh api repos/<owner>/<repo>` lookup. Cells left blank here because the salvage didn't capture every per-candidate URL — the comment must be filled in just-in-time before posting.)*

## 4. Sequencing & dependencies

| Step | Action | Depends on |
|---|---|---|
| 1 | File Issue A (`coverage-pack`) | — |
| 2 | File Issue B (`docs-pack`) | — |
| 3 | File Issue C (`quality-pack`) | — |
| 4 | File Issue D (hook orchestrator) | — |
| 5 | Post Action E comment on #8 | Issue A,B,C,D filed (so comment can cross-link) |

A and B are independent. C depends on D's outcome for the orchestrator choice (but can be filed before D is resolved — D is referenced in C's body). All five actions can be filed in one session.

## 5. Definition of done (for this spec)

- [ ] Spec committed to git on the current branch
- [ ] User reviews the spec
- [ ] Five issues + comment filed via `gh` per §3
- [ ] Each new issue carries the body in §3 verbatim (modulo TBDs filled at filing time)
- [ ] Each new issue carries the labels in §3
- [ ] Cross-links between the new issues and existing #5/#6/#8 are intact

## 6. Open questions

1. Should the `coverage-pack` smoke-test fixture live in `tests/fixtures/` like `tests/fixtures/fast_gate/` (per #15 SP3 fix)? (Recommend: yes, mirror `fast_gate` layout.)
2. Should `quality-pack:run` also surface results via a `PostToolUse` Notification hook (PLAN.md §6 Layer 2 mention)? (Recommend: yes — opt-in.)
3. For Action E comment on #8, do we want to **also** file a tracking issue for the 10-candidate vetting queue, or is the comment sufficient? (Default: comment sufficient; revisit when #8 reaches implementation.)
