# #47 — Counterfactual diffs spike protocol

> Date: 2026-08-06. Status: spike protocol. Type: spike. Approach: cross-domain.

## Hypothesis

Showing a side-by-side "what would change if we bumped to latest stable" annotation alongside any PR that touches a dep pin reduces the rate of "stale pin merged anyway" by ≥30% (vs. baseline), as measured by post-merge dep-bump commits in the next 90 days.

## Method

1. **Build a prototype:** `scripts/counterfactual_diffs_spike.py` reads `git diff` output for a PR, identifies dep-pin changes, queries `catalog/freshness/*.yaml` for the latest stable, and emits a markdown annotation like:

   ```diff
   - requests==2.34.0
   + requests==2.34.0  # latest stable as of 2026-08-06
   + # counterfactual: 2.35.0 is also stable; only 2 minor behind
   ```

2. **Pilot:** Run the prototype on the last 20 PRs in heretek's git history that touched `requirements.txt` or `pyproject.toml`. Generate the annotations. Manually review for accuracy.

3. **Comparison:** Would these annotations have changed reviewer behavior? (Manual judgment, not measurable.)

## Decision criteria

- **Adopt** if the prototype correctly generates annotations for ≥80% of recent PRs without false positives.
- **Adopt with follow-up pilot** if the pilot shows meaningful signal on ≥80% of in-scope files (e.g., `requirements.txt`) AND has known brittleness on out-of-scope files (e.g., `pyproject.toml` arrays). The follow-up pilot runs in M18–M20 to harden the parser.
- **Reject** if the prototype is brittle (e.g., misparses `pyproject.toml`, fails on complex version specs).

## Deliverables

- [ ] Prototype script
- [ ] Pilot run on 20 PRs
- [ ] Results document with manual review notes
- [ ] If adopted: follow-up issue filed for production integration
