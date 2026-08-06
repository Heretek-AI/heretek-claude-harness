# #49 — Cumulative codebase-staleness metric spike protocol

> Date: 2026-08-06. Status: spike protocol. Type: spike. Approach: external-data.

## Hypothesis

A per-commit "staleness score" — sum of (pinned-version-distance-from-latest) over all deps in the repo — is a useful release-quality gate: when the score increases by >X% between two consecutive releases, the release should be flagged for review.

## Method

1. **Prototype:** `scripts/staleness_metric_spike.py` walks git history commit-by-commit, parses dep pins from each commit, computes per-commit staleness score, and emits a CSV with columns `(commit_sha, score)`.

2. **Pilot:** Run on heretek's full git history; produce the CSV. Plot the trend (manual visualization, not automated).

3. **Decision:** adopt if the trend shows meaningful signal (e.g., score correlates with known release-quality events like #44/#45 work).

## Deliverables

- [ ] Prototype script
- [ ] Pilot CSV
- [ ] Trend plot (manual)
- [ ] Results document