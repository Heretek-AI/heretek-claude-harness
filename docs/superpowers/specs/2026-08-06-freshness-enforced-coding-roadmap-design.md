# Freshness-enforced coding — Roadmap Design Spec

> Date: 2026-08-06. Status: draft.
> Companion to parent design spec `2026-08-03-heretek-marketplace-design.md` (PLAN.md).
> Source: research conducted in the brainstorming session of 2026-08-06 — see `docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md` (follow-up: full deep-research report to be regenerated via the `refresh_pins`-style workflow before any issue is filed).

## 1. Summary

This spec defines **18 GitHub issues** to file so future sessions can pick up the work of making heretek enforce best coding practices across model classes — from local LLMs (Qwen3.6 27B-class) to frontier (deepseek-class) — without re-doing the upstream research. The full roadmap covers 24 months across four phases plus a cross-cutting track that tests the ideation methodology itself.

The motivating failure modes, surfaced in brainstorming on 2026-08-06:

1. **Stale training knowledge** — smaller models emit code that reflects outdated training data (e.g., deprecated stdlib idioms, removed APIs).
2. **Outdated dependency pinning** — smaller models suggest library versions from training-time memory, ignoring current registries.

Both are *enforcement* problems, not capability problems. Strong models know to verify; weaker models don't. This spec layers enforcement on top of every model so the gap closes at the repo level, not the model level.

The "biggest question" addressed by this spec — *how do we make an agent think up new ideas, synthesize data into new techniques instead of relying on its internal knowledge base?* — is answered operationally by §5 (the 4 ideation approaches + 4 long-term test issues that measure them).

## 2. Goals and non-goals

### Goals

- File 18 GitHub issues with consistent structure: each carries **Research Summary** (with inline URL evidence) and **Ideation Notes** (which of 4 approaches produced it, what was combined, why novel).
- Respect established heretek conventions: D5 overlap rule, D7 vetting bar, D11 SHA-ride versioning, D15 hooks-plugin-as-flagship.
- Cross-reference the existing v1.1 hardening issues (#30–#34), v2 quality-pack backlog (#17–#20), and the security-monitoring-pipeline spec that already ships.
- Bake in a falsifiable methodology for agent ideation: 4 approaches, each tested long-term across the 14 roadmap items that use it.

### Non-goals

- Implementing any of the proposed items in this spec. Implementation flows through the standard issue → ADR → catalog → smoke-test loop.
- Modifying PLAN.md or the security-monitoring-pipeline-design.md. This spec is *additive*.
- Adding new labels to the repo. All proposed issues use existing labels (`enhancement`, `security-scan`, `tech-debt`, `testing`, `help-wanted`, `question`).
- Re-running the full deep-research workflow end-to-end. (The research conducted in brainstorming is sufficient for filing; full reports regenerate next quarter via `refresh_pins`.)

## 3. The item set

18 items total. **8 SHIP** (#36–38, 40, 43–46; concrete catalog/plugin deliverables) + **6 SPIKE** (#39, 41, 42, 47–49; research artifacts producing decisions/findings, not shipped code) + **4 TEST** (#50–53; long-term measurement instruments for the 4 ideation approaches — themselves the spec's answer to the meta-question on agent ideation).

| # | Title | Phase | Type | Approach |
|---|-------|-------|------|----------|
| 36 | Freshness index prototype (`scripts/freshness_index.py` + `catalog/freshness/`) | 1 | ship | external-data |
| 37 | Stale-dep intercept hook (`scripts/stale_dep_intercept.py`) | 1 | ship | failure-mode |
| 38 | Freshness eval harness (`tests/freshness_eval/`) | 1 | ship | external-data |
| 39 | Directive-docs system-prompt augmentation experiment | 1 | spike | failure-mode |
| 40 | Forbidden-pattern registry (`catalog/forbidden_patterns.yaml`) | 2 | ship | external-data |
| 41 | Drift detector prototype (`scripts/drift_detector.py`) | 2 | spike | cross-domain |
| 42 | RLM fast-gate research spike | 2 | spike | cross-domain |
| 43 | AST-grep fast-gate integration | 2 | ship | external-data |
| 44 | Model-card profile catalog (`catalog/model_profiles/`) | 3 | ship | external-data |
| 45 | Lookup-gate hook (`scripts/lookup_gate.py`) | 3 | ship | failure-mode |
| 46 | Freshness tokens system (`scripts/freshness_tokens.py`) | 3 | ship | external-data |
| 47 | Counterfactual diffs prototype | 4 | spike | cross-domain |
| 48 | SVoK / provenance comments research | 4 | spike | cross-domain |
| 49 | Cumulative codebase-staleness metric | 4 | spike | external-data |
| 50 | Test: external-data triangulation (long-term measurement) | cross | test | (itself) |
| 51 | Test: adversarial ideation (long-term measurement) | cross | test | (itself) |
| 52 | Test: failure-mode-driven ideation (long-term measurement) | cross | test | (itself) |
| 53 | Test: cross-domain transfer ideation (long-term measurement) | cross | test | (itself) |

## 4. Issue body template

Each GitHub issue body follows this template. Type-specific sections are filled per item type.

```markdown
# [Item title]

> Phase: [N]. Type: [ship|spike|test]. Ideation approach: [name].
> Filed: YYYY-MM-DD. Sources verified: YYYY-MM-DD.

## Background
[Why this item exists; what gap it fills; parent spec section]

## Research Summary
[Synthesized findings. Inline URL citations with verification dates:
"claim ([source](url), verified YYYY-MM-DD)."]

## Ideation Notes
[Which of 4 approaches produced this. What external sources inspired it.
What was combined. Why this synthesis is novel vs each component alone.]

## Scope
[What's in.]

## Out of scope
[What's deferred.]

## [SHIP-only] D5 / D7 implications
[Cross-cutting vs task plugin check; vetting bar; SHA-ride; hooks-ownership check]

## [SHIP-only] Suggested catalog.yaml entry shape
[YAML sketch per v2-code-quality-issue-set convention]

## [SPIKE-only] Hypothesis + method
[Testable hypothesis; method to validate; success criteria; deliverables]

## [TEST-only] Measurement framework
[What "effective ideation" means for this approach; how to measure across
roadmap items that used it; success thresholds; data collection protocol]

## Per-item Definition of Done
- [ ] [concrete acceptance criteria]

## Cross-references
[Other items in this spec; existing heretek issues; ADRs; spec docs]
```

**Type-specific sections:**

| Section | SHIP (#36–38, 40, 43–46) | SPIKE (#39, 41, 42, 47–49) | TEST (#50–53) |
|---|---|---|---|
| D5/D7 + Catalog shape | ✅ | ❌ | ❌ |
| Hypothesis + method | ❌ | ✅ | ❌ |
| Measurement framework | ❌ | ❌ | ✅ (centerpiece) |
| Research Summary | ✅ | ✅ | ✅ (lighter — defines the approach itself) |
| Ideation Notes | ✅ | ✅ | ✅ (definitional — "this test IS approach X") |

### Worked example — #36 Freshness index

> **Background:** heretek's existing security-monitoring pipeline (`security-monitoring-pipeline-design.md` §6) tracks installed dep vulnerabilities post-hoc. It has no forward-looking "what's the latest stable version" data source. Models emitting code today rely on their training-time memory of dep versions, producing stale pins.
>
> **Research Summary:** Context7 MCP prevents hallucinated-deprecated-method output ([bswen blog](https://docs.bswen.com/blog/2026-03-17-prevent-ai-hallucinations-outdated-docs/), verified 2026-08-06). Google DeepMind shipped Gemini API Docs MCP for the same problem ([techbuzz](https://techbuzz.ai/articles/google-fixes-ai-coding-agents-outdated-code-problem), verified 2026-08-06). CodeRabbit's December 2025 analysis found AI-generated code produces ~1.7× more issues than human-written code, 2.74× for XSS ([propelcode.ai](https://www.propelcode.ai/blog/emergent-code-review-patterns-ai-generated-code), verified 2026-08-06).
>
> **Ideation Notes:** *external-data triangulation*. Three independent observations triangulated: (a) Context7 covers docs but not runtime deps; (b) Gemini API Docs MCP pulls docs nightly but isn't cross-vendor; (c) Dependabot queries runtime registries but doesn't cover API freshness. Synthesized as a nightly Python script (`scripts/freshness_index.py`) that materializes a local cache of both doc + registry state, queryable in <5ms by edit-time hooks. Novel because no existing tool unifies the doc + dep layers into a single forward-looking cache.

## 5. Methodology: how agents generate new ideas

This section answers the spec's "biggest question."

The spec commits to a **four-approach framework** for agent ideation. Each roadmap item names which approach produced it (in `Ideation Notes`); the four cross-cutting TEST items (#50–53) measure approach effectiveness over 24 months.

| Approach | Definition | Best for |
|---|---|---|
| **External-data triangulation** | Agent searches external sources (Firecrawl, GitHub MCP, arXiv), finds where multiple sources agree on a problem, synthesizes new techniques by combining existing ones. | Concrete deliverables backed by prior art; defends against "internal knowledge" failure mode |
| **Adversarial ideation** | Generate candidate ideas, critique with a second agent pass, refine. Classic LLM-as-critic loop. | Quality-bar elevation; de-risking obvious-bad ideas |
| **Failure-mode-driven** | Start from observed failure modes (e.g., "Qwen3.6 27B emits outdated deps"), design targeted interventions. | High-relevance items; tightest match to user-stated pain |
| **Cross-domain transfer** | Borrow techniques from unrelated fields (biology, type theory, dynamical systems) and apply to coding agents. | High novelty potential; high validation cost |

**Why all four instead of one.** Each approach has a different failure mode. Picking one would bake in that approach's blind spots. The TEST items (#50–53) measure whether the synthesis actually produces useful artifacts — and feed back into future spec design.

**Why this answers "don't rely on internal knowledge."** External-data triangulation is *required* by the approach definition — there is no synthesis without external sources. Failure-mode-driven and cross-domain transfer also require external observation. Only adversarial ideation operates purely within model internals, which is why it's one of four approaches, not the dominant one.

## 6. Cross-references (matrix)

How new items connect to existing heretek assets.

| New item | Connects to | Why |
|---|---|---|
| #36 Freshness index | `security-monitoring-pipeline-design.md` §6 | Pipeline is the substrate; freshness index is a new data source the pipeline can consume |
| #37 Stale-dep intercept | `security-monitoring-pipeline-design.md` §6 + D15 hooks | Hooks-plugin-as-flagship constraint; intercept lives as D15 hook |
| #38 Freshness eval | #36 + #37 | Eval harness measures both; ship together |
| #39 Directive-docs experiment | (no heretek substrate — pure prompt experiment) | n/a |
| #40 Forbidden-pattern registry | `security-monitoring-pipeline-design.md` (extends scanner base) + #19 (quality-pack ortho) | Pipeline scanners consume the registry; quality-pack is parallel track |
| #41 Drift detector | D15 hooks (new hook type) | Hooks plugin owns all quality gates per D15 |
| #42 RLM fast-gate | D15 hooks + #43 AST-grep (parallel) | Spike that competes with/extends AST approach |
| #43 AST-grep fast-gate | D15 hooks + #42 RLM (parallel) | Spike that competes with RLM approach; picks one to ship |
| #44 Model-card profiles | `v2-code-quality-issue-set-design.md` (Issue C: quality-pack) | Both address model-aware enforcement; orthogonal layers |
| #45 Lookup gate | #36 + #37 + D15 | Builds on freshness substrate; new D15 hook |
| #46 Freshness tokens | #36 + Phase 4 items (SVoK) | Tokens are a foundation for provenance ideas |
| #47 Counterfactual diffs | (vision — no current substrate) | n/a |
| #48 SVoK / provenance | #46 (tokens) | Tokens enable provenance comments |
| #49 Cumulative staleness | #36 + `security-monitoring-pipeline-design.md` | Pipeline tracks per-issue staleness; metric aggregates over time |
| #50–#53 Ideation-test issues | (every item with that approach column populated) | Aggregate measurement across roadmap items |

**Idempotency rules** (per heretek convention):
- No two items produce the same plugin. If a proposed item duplicates `quality-pack` (#19), deprioritize it.
- Hooks ownership per D15: only #37, #41, #42, #43, #45 may declare hooks. All others must not.
- Catalog entries must respect D7 vetting bar; SHIP items only.

## 7. Sequencing & dependencies

All 18 issues filed in one batch (matching v2-code-quality-issue-set precedent). Shipping follows dependencies:

| Window | Item | Depends on | Notes |
|---|---|---|---|
| M0 | #50–53 (test framework) | — | Filed first to establish measurement baseline |
| M0 | #36–39 (Phase 1) | — | Filed alongside test framework |
| M0–1 | Ship #36 (freshness index) | #50 | Data source for downstream items |
| M1–2 | Ship #37 (stale-dep intercept) | #36 | Hooks plugin, sub-100ms |
| M1–2 | Ship #38 (eval harness) | #36 | Measures Phase 1 effectiveness |
| M1–3 | Spike #39 (directive-docs) | — | Independent prompt experiment |
| M3 | #40–43 (Phase 2) | #36, #37 | Filed when foundation stable |
| M3–4 | Ship #40 (forbidden-pattern registry) | #50 | First pattern registry in repo |
| M3–6 | Spike #41 (drift detector) | — | Parallel with #42, #43 |
| M3–6 | Spike #42 (RLM fast-gate) | — | Competes with #43 |
| M4–6 | Ship #43 (AST-grep fast-gate) | #42 (decides winner) | Pick one of #42/#43 to ship |
| M6 | #44–46 (Phase 3) | #36 | Filed when freshness proven |
| M6–9 | Ship #44 (model-card profiles) | #50 | Independent of #45/#46 |
| M7–10 | Ship #45 (lookup gate) | #36, #37 | Mandatory-lookup enforcement |
| M8–12 | Ship #46 (freshness tokens) | #36 | Foundation for #48 |
| M12 | #47–49 (Phase 4) | — | Filed when Phase 1–3 stable |
| M12–18 | Spike #47 (counterfactual diffs) | — | Pure research |
| M14–20 | Spike #48 (SVoK) | #46 | Builds on token substrate |
| M16–24 | Spike #49 (staleness metric) | #36, #40 | Aggregates Phase 1+2 data |
| M24 | Aggregate #50–53 results | All items | Final measurement report |

**Key dependency rules:**
- Phase 2 filing blocked by Phase 1 ship (#36, #37) so the foundation exists.
- Phase 3 filing blocked by #36 (freshness) so profile enforcement has data.
- Phase 4 unblocked — pure research.
- #42 vs #43: pick one to ship based on Phase 2 spike results.
- Test items (#50–53) co-evolve with roadmap — their `Measurement framework` sections get refined as roadmap items actually ship, capturing real data.

## 8. Definition of done (for this spec)

- [ ] Spec committed to git on current branch
- [ ] User reviews the spec before any issues are filed
- [ ] All 18 issues filed via `gh issue create` per §3 (item list) — numbered #36–#53
- [ ] Each new issue body carries all required sections per §4 (template)
- [ ] Each new issue carries type-appropriate sections (D5/D7 + catalog shape for SHIP; hypothesis + method for SPIKE; measurement framework for TEST)
- [ ] Each new issue carries cross-references per §6
- [ ] Each new issue's `## Per-item Definition of Done` references its position in §7 sequencing table
- [ ] Labels applied per item type:
  - SHIP: `enhancement` + domain (`security-scan`, `tech-debt`, `testing`)
  - SPIKE: `enhancement` (no second label — `research` is not in heretek's existing label set per §2 non-goals)
  - TEST: `enhancement` + `question` + `testing`
- [ ] Each ideation-test issue (#50–53) links from its `Measurement framework` to every roadmap item with the matching approach column populated
- [ ] Final check: `gh issue list --label freshness-roadmap` returns all 18 with no duplicates

## 9. Open questions & risks

### Open questions

1. **"Long-term" horizon for test items** — 24 months (matches full roadmap) or 6 months (one quick cycle)? *Recommendation: 24 months, matching the spec horizon. Could be 6 with renewal.*
2. **Multi-approach items** — Some items may draw from more than one approach (e.g., #41 drift detector is failure-mode + cross-domain). How to label? *Recommendation: pick the primary approach; note the secondary in Ideation Notes.*
3. **Evaluation budget** — #38 eval harness adds CI minutes. Approximate: 30 tasks × N models × fresh/dated docs lookup = ?. *Recommendation: budget 5–10 min per CI run, opt-in via `INTEGRATION` marker.*
4. **Spec filing shape** — One PR with 18 issues, or 4 PRs (one per phase + cross-cutting)? *Recommendation: one PR matching v2-code-quality-issue-set precedent; smaller follow-up PRs as items ship.*
5. **Test item aggregation** — How does the M24 measurement roll-up actually get written up? New spec? ADR? *Recommendation: a follow-up spec at M23 that synthesizes results.*

### Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Spike items produce negative results (RLM doesn't help; forbidden-pattern registry has too many false positives) | Medium | Medium | Each spike defines success criteria upfront; negative results still produce a "do not ship" decision + ADR |
| External source URLs rot (blogs deleted, repos archived) | High over 24mo | Low | Verification dates stamped; quarterly `refresh_pins`-style URL validation |
| Test items produce incomparable data because roadmap items don't follow consistent methodology | Medium | High | Per-item "Ideation Notes" enforces methodology documentation; spec self-review catches drift |
| CI budget overrun from eval harness + drift detector | Medium | Medium | Drift detector is opt-in; eval harness is a separate workflow with its own concurrency budget |
| The 4 ideation approaches turn out not to be meaningfully distinct | Low | Medium | Define each approach's distinctive criteria in its TEST item's Measurement framework; if too similar, collapse |
| "Long-term testing" becomes maintenance burden with no payoff | Medium | Medium | Test items define explicit decision criteria at M6 and M12; if data is uninformative, can shut down early |