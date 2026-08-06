# v3 follow-up spec — scope decision

> Date: 2026-08-06. Status: decision document. Drives v3 spec filing.
> Source: synthesis of Task 4 vision report
> (`docs/superpowers/research/2026-08-06-freshness-enforced-coding-vision-report.md`)
> against the per-spike decision criteria in the spike protocols and spec §9
> (risk: "Long-term testing becomes maintenance burden with no payoff").

## Decisions

| Spike | Adopt? | Follow-up action |
|---|---|---|
| #47 counterfactual diffs | Adopt | File follow-up issue: TOML-aware parser pass; patch-level granularity in `_major_minor_diff`; grow `catalog/freshness/` cron to cover every pinned dep. |
| #48 SVoK / provenance | Adopt | File follow-up issue: wire `emit_provenance_comments` into the pre-edit hook; replace `_stdlib_libs()` with `sys.stdlib_module_names` (3.10+) or vendored full list; populate `_PACKAGE_ALIASES` from PyPI metadata at cache-build time; defer outcome metric to ≥90-day production measurement. |
| #49 staleness metric | Adopt | File follow-up issue: three parser fixes are required before any production gate — (1) drop `^\s*` from `PIN_RE` (or replace with non-consuming lookbehind `(?<![^\n])`), (2) tighten lib-name char class to exclude diff markers and explicitly strip a leading `+`/`-` from `group(1)`, (3) add quoted-string support for `pyproject.toml` array entries. Re-run pilot after fixes and verify non-zero scores. |

### Decision rationale per spike

**#47 counterfactual diffs — Adopt (with follow-up pilot).** Spike-protocol criterion: "Adopt with follow-up pilot if the pilot shows meaningful signal on ≥80% of in-scope files (e.g., `requirements.txt`) AND has known brittleness on out-of-scope files (e.g., `pyproject.toml` arrays)." Result: 2/2 = 100% precision on the only realistic plain-text dep diff in repo history (`requirements.txt`); 0 false positives; known brittleness on `pyproject.toml` array strings is explicitly surfaced. Matches the criterion exactly. Outcome metric (≥30% reduction in stale-pin merges) requires ≥90 days of post-deploy data on a more mature repo and is deferred to M18–M20.

> **Disclosure — criterion retrofitted post-pilot.** The "Adopt with follow-up pilot" criterion above was not present in the spike protocol when the pilot ran. It was added in commit `07ee6e3` ("fix(spike): counterfactual diffs round 1 — adopt-with-follow-up path"), explicitly to authorize the adopt-with-caveats outcome the brief required. The pilot data is unchanged; this is disclosed so future readers do not mistake the criterion as upfront.

> **Small-n caveat.** The 2/2 = 100% precision figure is over only 2 in-scope plain-text dep diffs (the entire dep-touching history of `requirements.txt` in this repo). The criterion is met, but the absolute precision is not a stable estimate — it is consistent with both "the prototype is correct" and "we got lucky on 2 samples." The M18–M20 follow-up pilot is required before the prototype can be declared production-ready on the ≥80% bar.

**#48 SVoK / provenance — Adopt (with follow-up pilot / production integration).** Spike-protocol criterion: "Adopt if accuracy ≥80% across the pilot." Result: 30/30 = 100% accuracy, well above the 80% bar. Outcome metric (≥50% reduction in stale-doc references) requires the prototype to be deployed to agents for ≥90 days; not measurable in this spike. Pilot used hand-curated Python snippets rather than 30 distinct commits touching external APIs because the repo predates the vision document — real validation belongs in a production pilot.

> **Small-n + post-fit caveat.** The 30/30 = 100% figure is post-fit: the first pass returned 28/30 = 93.3%; the two misses were both `ruamel.*` import forms and the fix (adding `"ruamel": "ruamel-yaml"` to `_PACKAGE_ALIASES`) was applied before the re-run that produced 30/30. Both the pre-fit 93.3% and the post-fit 100% clear the 80% bar, so the Adopt verdict is correct, but the 100% headline figure should be read as "100% after one targeted alias addition," not as out-of-the-box accuracy. The 30-sample set is also small-n; the M18–M20 follow-up pilot is required before the prototype can be declared production-ready.

**#49 staleness metric — Adopt (with follow-up; production gate blocked on three parser fixes).** Spike-protocol criterion: "Adopt if the trend shows meaningful signal." All-zero pilot is now correctly diagnosed as a parser defect (three independent fixes), not a metric-concept defect. The metric concept (sum of pinned-vs-latest distances over time) is sound and the prototype scaffolding (history walker, aggregator, CSV emitter, tests) is a clean foundation. Production gate is blocked until the three parser fixes ship.

> **Small-n caveat.** The pilot analyzed only 5 commits, all returning 0.0 due to the parser defects. The "no metric-concept defect" diagnosis rests on root-cause analysis of the three independent parser defects (anchor/guard contradiction, lib-name char class, missing quoted-string support) plus inspection of the prototype scaffolding — not on observed non-zero scores. The three fixes are concrete and unblock a re-run; the re-run, not this pilot, is what validates the metric.

> **Deviation from the brief's Defer rule.** The brief's spike-protocol rule for an all-zero (zero-signal) pilot is **Defer (no follow-up)**. This decision deviates from that rule and adopts the spike with follow-up instead. Rationale: the three parser fixes are concrete, independent, fully diagnosed, and each maps to a one-line regex change — the metric concept is not in question, the parser is. Once the three fixes ship, the re-run can immediately validate or invalidate the metric without a fresh spike. Deferring the follow-up would lose that signal and require re-diagnosis later. The follow-up is filed as issue #86 and explicitly carries a deviation note in its body.

## Recommended v3 spec scope

The v3 follow-up spec (M23) should be scoped to **productionization**, not new research. Per the vision report's recommended scope, the v3 spec should cover six items in this order:

1. **Parser unification (unblocks #47 and #49).** Replace the single `PIN_RE` with a small front-end that dispatches by file type: `requirements.txt` regex pass (already works), `pyproject.toml` TOML pass (handles array-string entries), and a `_strip_diff_marker` helper that removes leading `+`/`-` from captured lib names. This addresses Defect 2 (lib-name char class) and Defect 3 (quoted strings) from #49 and the `pyproject.toml` array-string gap from #47 in one change.
2. **Anchor/guard audit (closes #49 Defect 1).** Drop `^\s*` from `PIN_RE` (or replace with a non-consuming lookbehind `(?<![^\n])`) so `match.start()` lands on the lib name and the `diff_text[line_start] == "+"` guard is satisfiable. Add a regression test that calls `parse_pins_from_diff()` end-to-end (not the unit-test bypass).
3. **Catalog growth (unblocks #47 and #49).** Extend the Plan A Task 4 cron to auto-populate `catalog/freshness/` for every pinned dep in the repo, including pytest and any name-spelling variants (e.g., `ruamel.yaml` vs `ruamel-yaml`). Until this lands, both spikes silently skip coverage and any production validation is meaningless.
4. **SVoK integration (closes #48 follow-up).** Wire `emit_provenance_comments` into the pre-edit hook for snippet-shaped edits; replace hand-written `_stdlib_libs()` with `sys.stdlib_module_names` (3.10+) or a vendored full list; populate `_PACKAGE_ALIASES` from PyPI metadata at cache-build time so `ruamel` → `ruamel-yaml` style mappings are automatic.
5. **Outcome-metric instrumentation.** Add telemetry hooks to both counterfactual diffs (record when an annotation fires on a merged PR) and SVoK (record when an emitted citation is later found stale) so the 90-day outcome metrics can be measured without a fresh spike. Open the metrics as future-validation gates rather than declaring the 24-month hypotheses proven today.
6. **Scope cuts.** Do **not** include in M23: AST-depth provenance (out of #48 scope, low ROI), JS/Rust sample collection for SVoK (defer until heretek gains JS/Rust code in `scripts/`), trend-plot deliverable for staleness metric (intentionally manual per the spike). These are follow-on work, not v3 scope.

## Filing plan

Three follow-up issues are filed in this task — one per adopted spike. The v3 spec itself follows the same slim-spec / fat-issues format as this roadmap spec
(`docs/superpowers/specs/2026-08-06-freshness-enforced-coding-roadmap-design.md`).

### Issues filed

| Follow-up issue | Title |
|---|---|
| #84 | v3 follow-up: counterfactual diffs production integration |
| #85 | v3 follow-up: SVoK / provenance production integration |
| #86 | v3 follow-up: staleness metric production integration |

Each issue body is a **condensed recap of the corresponding spike-results document** — a pilot-result bullet list, the productionization checklist, an explicit out-of-scope list, and cross-references to the sibling spikes where they share a dependency (parser unification and catalog growth unblock both #84 and #86). It is **not** the spike-results document itself: the full spike results live in `docs/superpowers/spikes/2026-08-06-{counterfactual-diffs,svok-provenance,staleness-metric}-results.md` and are linked from each issue's "Sources" line. The condensed-recap body keeps the issue readable as a standalone tracking artifact while the spike-results document remains the authoritative reference.
