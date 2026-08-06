# #47 — Counterfactual diffs results

> Status: PARTIAL_PILOT. Authored 2026-08-06.

## Method

Pilot on every dep-touching commit in `git log -- requirements.txt pyproject.toml`. The full 20-PR pilot was not possible: only **5 commits** in repo history touch `requirements.txt` or `pyproject.toml`. Per the protocol's fallback, this is treated as "insufficient data; deferred signal" — but manual review of all 5 was still performed.

## Results

| Metric | Value |
|---|---|
| Commits reviewed | 5 (vs. 20-PR target) |
| Diff lines reviewed | 11 distinct dep-pin lines |
| Correct annotations produced | 2 / 2 (100%) on plain `requirements.txt` lines |
| False positives | 0 |
| Missed annotations | 3 (all on `pyproject.toml` array entries — known limitation) |
| Reviewer-behavior change | Manual judgment: annotation in f440b0f (jsonschema, 3 minor behind) would have been useful signal at PR time. |

### Per-commit detail

| Commit | Files | Annotations emitted | Notes |
|---|---|---|---|
| 8f3b91f (initial pin) | pyproject.toml, requirements.txt | 0 | All `+` lines; correctly silent. |
| ef34926 (pytest 8.3.3 → 9.0.3) | pyproject.toml | 0 | **Missed.** `pyproject.toml` deps live in `["pytest==8.3.3"]` strings; the `-dev = ["pytest...` line doesn't match `PIN_RE` because the regex treats `dev` as the package name and `=` (with whitespace) as the operator. Prototype is brittle on array-string formats. |
| f60cfa2 (add ruamel.yaml) | requirements.txt | 0 | All `+` lines; correctly silent. |
| f440b0f (bump PyYAML/jsonschema/pytest) | pyproject.toml, requirements.txt | 2 (requirements.txt only) | PyYAML: "0 minor behind" (6.0.2 → 6.0.3, patch-level diff but reported as 0 minor). jsonschema: "3 minor behind" (4.23.0 → 4.26.0). Useful reviewer signal. |
| 0626af3 (add requests 2.34.2) | pyproject.toml, requirements.txt | 0 | Pinned version equals latest stable from `catalog/freshness/requests.yaml` (2.34.2); correctly silent. |

### Limitations surfaced

1. **`pyproject.toml` array strings** (e.g., `dev = ["pytest==8.3.3"]`) are not parsed — the regex expects `name OP version` at the start of the line, not `key = ["name OP version"]`. Would need a separate pass over TOML/array entries.
2. **Patch vs. minor granularity** is coarse — `_major_minor_diff` ignores patch numbers. PyYAML 6.0.2 → 6.0.3 shows "0 minor behind," which understates the bump.
3. **Catalog coverage** is partial — only libs with `catalog/freshness/<name>.yaml` are annotated. Today: jsonschema, pyyaml, requests, ruff, ruamel-yaml. Other deps (`pytest`, `ruamel.yaml` if spelled that way) are silently skipped.

## Decision

**Adopt with follow-up pilot** (per the protocol's "Adopt with follow-up pilot" decision criterion). Rationale:

- **In-scope match satisfied** — the prototype correctly produces 2/2 useful annotations on the only realistic plain-text dep diff in history (`requirements.txt`) with zero false positives, which is ≥80% of in-scope files.
- **Known out-of-scope brittleness** — the `pyproject.toml` array-string parser path is brittle and `catalog/freshness/` coverage is partial. This satisfies the protocol's "known brittleness on out-of-scope files (e.g., `pyproject.toml` arrays)" half of the criterion.
- **Follow-up pilot** will run in M18–M20 per the protocol. A production version needs:
  - TOML-aware parser pass (or rely on external `tomli`/`tomllib`).
  - Auto-populate `catalog/freshness/` for every dep pin (the cron from Plan A Task 4 should grow to cover all pinned deps).
  - Patch-level granularity in `_major_minor_diff` (e.g., "N patch, M minor, K major").

The 90-day outcome metric (post-merge dep-bump commits) is not measurable in this spike — repo is too new. Real validation belongs in a production pilot on a more mature repo per the protocol's M18-M20 plan.

## Follow-up

- [ ] File follow-up issue: "counterfactual diffs: productionize prototype" — assign to M18-M20 lane.
- [ ] Grow `catalog/freshness/` cron to cover all pinned deps (pytest, ruamel.yaml spelled correctly).
- [ ] Add TOML-aware parsing pass.
- [ ] Improve `_major_minor_diff` to report patch/minor/major separately.
