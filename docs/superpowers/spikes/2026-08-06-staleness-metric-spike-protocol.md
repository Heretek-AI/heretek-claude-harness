# #49 — Cumulative codebase-staleness metric spike protocol

> Date: 2026-08-06. Status: spike protocol. Type: spike. Approach: external-data.

## Hypothesis

A per-commit "staleness score" — sum of (pinned-version-distance-from-latest) over all deps in the repo — is a useful release-quality gate: when the score increases by >X% between two consecutive releases, the release should be flagged for review.

## Method

1. **Prototype:** `scripts/staleness_metric_spike.py` walks git history commit-by-commit, parses dep pins from each commit, computes per-commit staleness score, and emits a CSV with columns `(commit_sha, score)`.

2. **Pilot:** Run on heretek's full git history; produce the CSV. Plot the trend (manual visualization, not automated).

3. **Decision:** adopt if the trend shows meaningful signal (e.g., score correlates with known release-quality events like #44/#45 work).

## Deliverables

- [x] Prototype script (`scripts/staleness_metric_spike.py`)
- [x] Pilot CSV (`/tmp/staleness.csv`, 5 data rows + 1 header)
- [ ] Trend plot (manual) — explicitly deferred: pilot scores are all 0.0 due to a parser defect (see results doc); a trend plot of a flat-zero series conveys no signal and would be misleading. Plot will be produced after the follow-up parser fix lands and the pilot re-runs.
- [x] Results document (`docs/superpowers/spikes/2026-08-06-staleness-metric-results.md`)
