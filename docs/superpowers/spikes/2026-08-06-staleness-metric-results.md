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

All commits scored 0.0 because `parse_pins_from_diff()` returns `{}` for every diff it sees — the function is unconditionally dead code, regardless of the input format. This is the primary defect; the previously-suspected quoting issue is a secondary, independent problem.

### Defect 1 (primary): `^`-anchor guard contradiction makes the parser return `{}` always

`PIN_RE` begins with `^\s*` under `re.MULTILINE`, so every match necessarily begins at the start of a line — `match.start()` equals the position of the first non-whitespace character on the line, and the previous-`\n`-plus-one (`line_start`) equals `match.start()` minus the consumed whitespace. The guard on line 158:

```python
if line_start < start and diff_text[line_start] == "+":
```

is therefore never satisfiable for any line that starts at the line's leading position. To make matters worse, the diff-marker character (`+` or `-` or ` `) lives *before* the match, not after the previous `\n`'s whitespace — so even if `line_start == start`, the marker character at `line_start` could be `+`, but the `line_start < start` half of the AND fails first.

Net effect: the parser contributes zero pins on every input, including plain unquoted `requirements.txt` lines like `+requests==2.34.0` (which `PIN_RE` *does* match). The unit tests still pass because they call `score_for_pins()` directly and bypass `parse_pins_from_diff()` entirely. This is the same root-cause family as a recent line-anchor-vs-guard contradiction fixed in a prior plan: the regex and the post-filter were specified as if independent, but the anchor makes the filter vacuous.

### Defect 2 (secondary, independent): diff-marker contamination of the captured lib name

`PIN_RE`'s lib-name char class `[a-zA-Z0-9_.+-]` includes `+`, `-`, and `.`. On an unindented added line `+requests==2.34.0`, the captured `group(1)` is `+requests` — not `requests` — because `+` is a permitted first character. Even if Defect 1 is fixed, `_latest_for("+requests")` would then compute the cache path as `+requests.yaml` (after `.lower().replace('.', '-')` → `+requests.yaml`) and miss every cache file. The same issue affects `-` removal-context lines (less important because we filter those out, but the regex doesn't know that yet) and any leading-`.` packages (none in practice, but the bug is structural).

This defect is independent of Defect 1: fixing the guard without tightening the char class would still produce zero scores. Conversely, tightening the char class without fixing the guard would still produce zero scores.

### Defect 3 (tertiary, was previously misidentified as primary): quoted strings in `pyproject.toml`

The heretek repo's `pyproject.toml` pins appear as `"requests==2.34.2"` inside a `dependencies = [...]` array. The current `PIN_RE` would not match these even if Defects 1 and 2 were fixed, because the leading `"` is not a comparator. This is the third independent defect. It was previously identified as the primary cause of the all-zero pilot; the parser analysis above shows it is actually the least impactful of the three for this pilot (the pilot produces zero scores regardless of whether quoting is supported).

### Lib-name normalization note (was overstated in the first cut)

`_latest_for()` does `.lower().replace('.', '-')` to map a pin name to its cache filename. For pins like `PyYAML` and `ruamel.yaml`, this correctly produces `pyyaml.yaml` and `ruamel-yaml.yaml` respectively, matching the cache-file naming convention used elsewhere in this repo. The reverse direction (PEP 503: dash → dot canonicalization) is a real gap for any future cache that uses dot-separated names, but it does **not** affect the current pilot — every pin the current repo touches is in the case-insensitive `.lower().replace('.', '-')` direction. Framing updated accordingly; the original report's concern #2 was overstated.

## Decision

**Adopt with follow-up.** The metric concept (sum of pinned-vs-latest distances over time) is sound, and the prototype scaffolding (history walker, score aggregator, CSV emitter, tests) is a clean foundation. The all-zero pilot is now correctly diagnosed as a parser defect, not a metric-concept defect. Three independent fixes are required before this can be a production gate:

1. **Fix the `^`-anchor guard contradiction in `parse_pins_from_diff()`** (Defect 1). Recommended concrete fix: drop `^\s*` from `PIN_RE` (or replace it with a non-consuming lookbehind `(?<![^\n])` so the match still anchors at line start but `match.start()` lands on the first character of the lib name rather than after whitespace). With the leading whitespace removed, `line_start < start` becomes satisfiable for any line whose first character is the lib name, and the existing `diff_text[line_start] == "+"` check works as written.
2. **Tighten the lib-name char class to exclude diff markers** (Defect 2). Recommended concrete fix: change `[a-zA-Z0-9_.+-]` to `[a-zA-Z0-9_.]` and explicitly strip a leading `+` or `-` from `group(1)` before the cache lookup (defense-in-depth: the regex should not capture it in the first place, but the strip guards against future regex drift).
3. **Add quoted-string support for `pyproject.toml` `dependencies = [...]` arrays** (Defect 3). Recommended concrete fix: change `PIN_RE` to also accept an optional leading `"` and a required `"` (or `'`) closing the version literal — e.g., `^\s*["']?([a-zA-Z0-9_.+-]+)["']?\s*([=<>~!]=)\s*["']?([0-9][^"';,\s]*)`. Combined with the Defect-1 regex change (drop the `^\s*`), this becomes `(?<![^\n])["']?([a-zA-Z0-9_.]+)["']?\s*...`.

After all three fixes, re-run the pilot on heretek's history and verify non-zero scores before declaring the metric production-ready. The trend plot deliverable remains manual (intentional — not part of the prototype scope).

## Artifacts

- Prototype: `scripts/staleness_metric_spike.py`
- Tests: `tests/vision/test_staleness_metric.py` (2 passing; bypass `parse_pins_from_diff()` by design)
- Protocol: `docs/superpowers/spikes/2026-08-06-staleness-metric-spike-protocol.md`
- Pilot CSV: `/tmp/staleness.csv`

