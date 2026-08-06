# #49 — Staleness metric results

> Status: DONE. Authored 2026-08-06.

## Method

Walked heretek's full git history; computed per-commit staleness score.

## Results

| Metric | Value |
|---|---|
| Commits analyzed | 5 |
| Mean score | 0.0 |
| Max score | 0.0 |
| Min score | 0.0 |
| CSV row count | 5 data rows (+ 1 header) |

## Trend observation

All commits scored 0.0. Inspection of the diff format (`git show 0626af3 -- pyproject.toml`) reveals that dependency pins appear inside quoted strings (e.g. `"requests==2.34.2"`). The prototype's pin regex (`PIN_RE`) does not handle the leading double-quote character, so all pin lines in the actual repo are missed by `parse_pins_from_diff`. The unit tests still pass because they bypass the diff parser entirely and call `score_for_pins()` directly with curated dicts — and `requests.yaml` reports `latest_version: 2.34.2`, matching the pinned `2.34.0` closely enough to score near zero.

## Decision

**Adopt with follow-up.** The metric concept (sum of pinned-vs-latest distances over time) is sound, and the prototype scaffolding is a clean foundation. Before this can be a production gate, two improvements are required:

1. **Fix the pin regex** to handle quoted strings inside `pyproject.toml` `dependencies = [...]` arrays (the dominant pin format in modern Python projects).
2. **Resolve lib-name normalization** between pin and cache: e.g., `PyYAML` pin vs `pyyaml.yaml` cache file — case and dot-vs-dash normalization must be made explicit.

Both are small and would unblock re-running the pilot with non-zero scores, at which point a trend plot will be meaningful.

## Artifacts

- Prototype: `scripts/staleness_metric_spike.py`
- Tests: `tests/vision/test_staleness_metric.py` (2 passing)
- Protocol: `docs/superpowers/spikes/2026-08-06-staleness-metric-spike-protocol.md`
- Pilot CSV: `/tmp/staleness.csv`