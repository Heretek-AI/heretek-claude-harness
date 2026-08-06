# Phase 4 vision report — counterfactual diffs + SVoK + staleness metric

> Date: 2026-08-06. Synthesizes Tasks 1, 2, 3 of Plan D.

## Summary

Three research spikes explored speculative techniques for the 24-month
horizon. Results inform the v3 follow-up spec (M23).

## Spike outcomes

| Spike | Hypothesis | Result | Decision |
|---|---|---|---|
| #47 counterfactual diffs | ≥30% reduction in stale-pin merges | 2/2 useful annotations on plain `requirements.txt` (100% precision); 3/5 `pyproject.toml` array entries missed (known brittleness); zero false positives | Adopt with follow-up pilot (M18–M20) |
| #48 SVoK / provenance | ≥50% reduction in stale-doc references | 30/30 accurate provenance comments (100% across stdlib / single-external / mixed categories); outcome metric deferred pending ≥90-day post-deploy measurement | Adopt with follow-up pilot (production integration) |
| #49 staleness metric | Useful release-quality gate signal | All commits scored 0.0 — root cause is three independent parser defects, not a metric-concept defect (anchored-regex + guard contradiction; lib-name char class includes `+`/`-`/`.` diff markers; no quoted-string support for `pyproject.toml` arrays); prototype scaffolding (history walker, aggregator, CSV emitter, tests) is sound | Adopt with follow-up (three parser fixes required before production gate) |

## Cross-spike observations

- **Pilot data scarcity is the dominant constraint.** All three spikes ran on a repo with only 5 dep-touching commits and no JS/Rust external-API samples. Each pilot adopted a "pilot on what we have; defer the real outcome metric to production" posture. This is consistent and acceptable — the spec already contemplated Phase 4 as speculative — but it means the 24-month-horizon vision rests on prototype correctness rather than empirical validation.
- **The catalog (`catalog/freshness/`) is the load-bearing seam.** Both #47 (counterfactual diffs) and #49 (staleness metric) silently skip any pin whose library does not have a `catalog/freshness/<name>.yaml` entry. Today this covers jsonschema, pyyaml, requests, ruff, ruamel-yaml — leaving pytest and any future dep unannotated. The Plan A Task 4 cron needs to grow to cover all pinned deps before either spike can be productionized.
- **Parser brittleness is the recurring theme.** #47 surfaced pyproject.toml array-string parsing; #49 surfaced three independent parser defects in `PIN_RE` (anchor/guard contradiction, lib-name char class, missing quoted-string support). Both call for regex-vs-data-shape audits at productionization time. The cleanest seam is a TOML/requirements-file-aware parser front-end instead of a single regex over diff text.
- **Outcome metrics are uniformly deferred.** #47's "stale-pin merge rate" and #48's "stale-doc citation rate" both require ≥90 days of post-deploy data. The protocol's PASS/ADOPT gates were met on prototype accuracy, not on the long-horizon hypothesis. The v3 spec must keep both metrics open as future validation rather than declaring success.
- **None of the three spikes regressed any Phase 1–3 deliverable.** Each was additive: counterfactual diffs add a pre-commit annotation, SVoK adds a pre-edit provenance comment, staleness metric adds a release-quality CSV. This is consistent with the spec's incremental posture and supports the "adopt with follow-up" pattern across all three.

## Recommended follow-up spec scope (M23)

The v3 follow-up spec should be scoped to **productionization**, not new research:

1. **Parser unification (unblocks #47 and #49).** Replace the single `PIN_RE` with a small front-end that dispatches by file type: `requirements.txt` regex pass (already works), `pyproject.toml` TOML pass (handles array-string entries), and a `_strip_diff_marker` helper that removes leading `+`/`-` from captured lib names. This addresses Defect 2 (lib-name char class) and Defect 3 (quoted strings) from #49 and the `pyproject.toml` array-string gap from #47 in one change.
2. **Anchor/guard audit (closes #49 Defect 1).** Apply the recommended fix: drop `^\s*` from `PIN_RE` (or replace with a non-consuming lookbehind `(?<![^\n])`) so `match.start()` lands on the lib name and the `diff_text[line_start] == "+"` guard is satisfiable. Add a regression test that calls `parse_pins_from_diff()` end-to-end (not the unit-test bypass).
3. **Catalog growth (unblocks #47 and #49).** Extend the Plan A Task 4 cron to auto-populate `catalog/freshness/` for every pinned dep in the repo, including pytest and any name-spelling variants (e.g., `ruamel.yaml` vs `ruamel-yaml`). Until this lands, both spikes silently skip coverage and any production validation is meaningless.
4. **SVoK integration (closes #48 follow-up).** Wire `emit_provenance_comments` into the pre-edit hook for snippet-shaped edits; replace hand-written `_stdlib_libs()` with `sys.stdlib_module_names` (3.10+) or a vendored full list; populate `_PACKAGE_ALIASES` from PyPI metadata at cache-build time so `ruamel` → `ruamel-yaml` style mappings are automatic.
5. **Outcome-metric instrumentation.** Add telemetry hooks to both counterfactual diffs (record when an annotation fires on a merged PR) and SVoK (record when an emitted citation is later found stale) so the 90-day outcome metrics can be measured without a fresh spike. Open the metrics as future-validation gates rather than declaring the 24-month hypotheses proven today.
6. **Scope cuts.** Do **not** include in M23: AST-depth provenance (out of #48 scope, low ROI), JS/Rust sample collection for SVoK (defer until heretek gains JS/Rust code in `scripts/`), trend-plot deliverable for staleness metric (intentionally manual per the spike). These are follow-on work, not v3 scope.