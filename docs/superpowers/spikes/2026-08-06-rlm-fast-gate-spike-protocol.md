# #42 — RLM fast-gate research spike

> Date: 2026-08-06. Status: spike protocol. Type: spike. Approach: cross-domain.

## Hypothesis

An RLM-style scaffold (Python REPL + recursive LM calls) running on a single Edit event can match the precision of ast-grep (#43) while achieving **higher recall** on subtle deprecated patterns — at acceptable latency (<2s p95) — when running on frontier models.

## Method

1. **Corpus:** 50 edits sampled from heretek's recent git history; 25 contain known-deprecated APIs, 25 are clean.
2. **Treatment (RLM):** Run `scripts/rlm_fast_gate_spike.py` on each edit. Measure precision (true positives / flagged), recall (true positives / actual deprecated), latency p50/p95.
3. **Baseline (ast-grep):** Run #43 scanner on the same corpus. Same metrics.
4. **Comparison:** Per-corpus precision/recall/latency. Adopt RLM if precision ≥ ast-grep AND recall > ast-grep × 1.5 AND latency p95 ≤ 2s.

## Eval set

The 50-edit corpus lives at `tests/detection/fixtures/rlm_corpus/` (created in Task 4 Step 2). Each entry is `{file_path, new_string, expected_verdict: "deprecated"|"clean"}`.

## Decision criteria

- **Adopt RLM (#42)** if it satisfies the comparison rule above.
- **Adopt AST-grep (#43)** otherwise.
- **Reject both** if neither meets precision ≥70% AND recall ≥50% — escalate to #49 staleness metric research instead.

## Deliverables

- [ ] 50-edit corpus authored (with ground truth)
- [ ] RLM treatment + ast-grep baseline both run
- [ ] Results documented in `docs/superpowers/spikes/2026-08-06-rlm-fast-gate-results.md`
- [ ] Decision recorded + ADR if non-trivial
