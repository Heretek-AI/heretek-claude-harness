# #48 — Semantic Version-of-Knowledge (SVoK) / provenance comments spike

> Date: 2026-08-06. Status: spike protocol. Type: spike. Approach: cross-domain.

## Hypothesis

Adding `# generated against <lib> docs v<X.Y.Z> fetched <date>` provenance
comments to code that uses external APIs lets a code reviewer (human or
agent) verify the agent's knowledge is current, and reduces the rate of
"agent cited docs that no longer exist" by ≥50% (measured by stale-doc
references in subsequent PRs).

## Method

1. **Prototype:** `scripts/svok_provenance_spike.py` takes a code snippet
   and the freshness cache as input; identifies which external APIs are
   used; emits provenance comments for each.

2. **Pilot:** Run the prototype on 30 generated code samples (mix of
   Python/JS/Rust from heretek's own history). Verify each emitted
   provenance comment is accurate.

3. **Decision:** adopt if accuracy ≥80% across the pilot.

## Deliverables

- [ ] Prototype script
- [ ] 30-sample pilot run
- [ ] Results document with accuracy metrics
- [ ] If adopted: follow-up issue for production integration
