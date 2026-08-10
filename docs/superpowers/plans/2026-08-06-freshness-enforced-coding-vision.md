# Freshness-enforced Coding — Vision Plan (Plan D)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three 24-month-horizon research spikes — counterfactual diffs (#47), SVoK / provenance comments (#48), cumulative codebase-staleness metric (#49). Each produces a decision document with measured evidence; not shipped code. Builds on Plans A, B, C artifacts (freshness cache, pattern registry, profile loader).

**Architecture:** Three independent research artifacts. Each spike has its own evaluation protocol and produces a `*-results.md` document. The synthesis task (Task 4) aggregates results into a "vision report" that informs the M24 follow-up spec (per spec §9).

**Tech Stack:** Python 3.10+, git CLI (for `git log`/`git blame`), PyYAML 6.0.3, pytest 9.1.1. No new runtime deps.

## Global Constraints

Same as Plans A, B, C. Key constraints for Plan D:

- **D5 / D7 / D11 / D15** — still apply, though spikes are not subject to D15 (no hooks).
- **Spike discipline:** each spike defines hypothesis + method + decision criteria upfront (per spec §9 risk table).
- **No silent scope expansion:** if a spike produces a SHIP-able artifact, it gets a separate issue + ADR; spikes themselves do not ship code.
- **Cite the research report:** every spike's results document must reference `docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md` and the brainstorm sources it draws on.

## Prerequisite

Plans A, B, C must be complete: `catalog/freshness/*.yaml` populated; `catalog/forbidden_patterns.yaml` exists; `catalog/model_profiles/*.yaml` exist; `scripts/freshness_index.py` runs successfully.

---

## File Structure (Plan D)

**New files:**
- `scripts/counterfactual_diffs_spike.py` — #47 prototype
- `scripts/svok_provenance_spike.py` — #48 prototype
- `scripts/staleness_metric_spike.py` — #49 prototype
- `docs/superpowers/spikes/2026-08-06-counterfactual-diffs-spike-protocol.md`
- `docs/superpowers/spikes/2026-08-06-counterfactual-diffs-results.md`
- `docs/superpowers/spikes/2026-08-06-svok-provenance-spike-protocol.md`
- `docs/superpowers/spikes/2026-08-06-svok-provenance-results.md`
- `docs/superpowers/spikes/2026-08-06-staleness-metric-spike-protocol.md`
- `docs/superpowers/spikes/2026-08-06-staleness-metric-results.md`
- `tests/vision/__init__.py`
- `tests/vision/conftest.py`
- `tests/vision/test_counterfactual_diffs.py`
- `tests/vision/test_svok_provenance.py`
- `tests/vision/test_staleness_metric.py`

**Modified files:**
- `docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md` — append Phase 4 results section in Task 4

---

### Task 1: Spike #47 — Counterfactual diffs prototype

**Files:**
- Create: `scripts/counterfactual_diffs_spike.py`
- Create: `docs/superpowers/spikes/2026-08-06-counterfactual-diffs-spike-protocol.md`
- Create: `docs/superpowers/spikes/2026-08-06-counterfactual-diffs-results.md`
- Create: `tests/vision/test_counterfactual_diffs.py`

**Interfaces:**
- Consumes: git history (commit SHAs) + `catalog/freshness/*.yaml`
- Produces: a side-by-side diff that, given a PR touching a dep pin, shows "what would change if you bumped to latest"

- [ ] **Step 1: Write the spike protocol**

File: `docs/superpowers/spikes/2026-08-06-counterfactual-diffs-spike-protocol.md`

```markdown
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
- **Reject** if the prototype is brittle (e.g., misparses `pyproject.toml`, fails on complex version specs).

## Deliverables

- [ ] Prototype script
- [ ] Pilot run on 20 PRs
- [ ] Results document with manual review notes
- [ ] If adopted: follow-up issue filed for production integration
```

- [ ] **Step 2: Write the failing test**

File: `tests/vision/test_counterfactual_diffs.py`

```python
"""Tests for counterfactual_diffs_spike.py (#47)."""
import pytest
from pathlib import Path

from scripts.counterfactual_diffs_spike import annotate_diff


def test_annotate_diff_flags_stale_pin():
    """#47: diff pinning requests==2.34.0 produces annotation when 2.35+ exists."""
    diff = "-requests==2.34.0\n"
    if not (Path("catalog/freshness") / "requests.yaml").exists():
        pytest.skip("populate catalog/freshness/requests.yaml first")

    annotated = annotate_diff(diff)
    # Annotation should mention a newer version exists
    assert "latest stable" in annotated.lower() or "counterfactual" in annotated.lower(), \
        f"expected counterfactual annotation, got: {annotated}"


def test_annotate_diff_passes_through_unrelated_changes():
    """#47: diff that doesn't touch deps is passed through unchanged."""
    diff = "+# new comment\n+def foo(): pass\n"
    annotated = annotate_diff(diff)
    assert annotated == diff, "non-dep diff should be passed through unchanged"
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `pytest tests/vision/test_counterfactual_diffs.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement the prototype**

File: `scripts/counterfactual_diffs_spike.py`

```python
"""Counterfactual diffs spike (#47) — prototype.

Given a unified diff touching dep pins, emits a side-by-side annotation
showing "what would change if you bumped to latest stable."

This is research code. Production integration is a follow-up issue if
the prototype proves out.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
# Match `name==X.Y.Z` etc.
PIN_RE = re.compile(r"^([+-])([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*([0-9][^,;\s]*)", re.MULTILINE)


def _latest_for(lib: str) -> str | None:
    cache_file = CACHE_DIR / f"{lib.lower().replace('.', '-')}.yaml"
    if not cache_file.exists():
        return None
    try:
        data = yaml.safe_load(cache_file.read_text())
    except yaml.YAMLError:
        return None
    return data.get("latest_version")


def annotate_diff(diff: str) -> str:
    """Annotate a diff with counterfactual "bump to latest" hints."""
    today = datetime.now(timezone.utc).date().isoformat()
    annotated_lines = []

    for line in diff.splitlines():
        match = PIN_RE.match(line)
        if not match:
            annotated_lines.append(line)
            continue

        sign, name, op, version = match.groups()
        latest = _latest_for(name)

        if not latest or latest == version:
            annotated_lines.append(line)
            continue

        annotated_lines.append(line)
        if sign == "-":
            annotated_lines.append(
                f"+# counterfactual: {name}=={latest} is also stable as of {today} "
                f"({_major_minor_diff(version, latest)} behind)"
            )

    return "\n".join(annotated_lines)


def _major_minor_diff(pinned: str, latest: str) -> str:
    """Render 'N minor' or 'N major' diff between pinned and latest."""
    try:
        p = tuple(int(x) for x in pinned.split(".")[:2])
        l = tuple(int(x) for x in latest.split(".")[:2])
    except ValueError:
        return "version diff"
    if len(p) < 2 or len(l) < 2:
        return "version diff"
    if p[0] != l[0]:
        return f"{l[0] - p[0]} major"
    return f"{l[1] - p[1]} minor"


if __name__ == "__main__":
    import sys
    print(annotate_diff(sys.stdin.read()))
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest tests/vision/test_counterfactual_diffs.py -v`
Expected: 2 tests PASS (with cache populated; skip if cache empty)

- [ ] **Step 6: Run pilot on last 20 dep-touching PRs**

Run:
```bash
git log --oneline -20 -- requirements.txt pyproject.toml | head -20
# Manual: feed each diff to the prototype and review output.
```

If no PR history touches deps, mark pilot as "insufficient data; defer to M18-M20 production pilot."

- [ ] **Step 7: Write the results document**

File: `docs/superpowers/spikes/2026-08-06-counterfactual-diffs-results.md`

```markdown
# #47 — Counterfactual diffs results

> Status: PENDING. Authored 2026-08-06.

## Method

20-PR pilot using `git log -- requirements.txt pyproject.toml`.

## Results (PENDING)

| Metric | Value |
|---|---|
| PRs reviewed | (fill from pilot) |
| Correct annotations | (fill from pilot) |
| False positives | (fill from pilot) |
| Reviewer-behavior change | (manual judgment) |

## Decision

_To be filled after pilot review._
```

- [ ] **Step 8: Commit**

```bash
git add scripts/counterfactual_diffs_spike.py tests/vision/test_counterfactual_diffs.py
git add docs/superpowers/spikes/2026-08-06-counterfactual-diffs-spike-protocol.md
git add docs/superpowers/spikes/2026-08-06-counterfactual-diffs-results.md
git commit -m "spike(counterfactual): #47 prototype + pilot"
```

---

### Task 2: Spike #48 — SVoK / provenance comments research

**Files:**
- Create: `scripts/svok_provenance_spike.py`
- Create: `docs/superpowers/spikes/2026-08-06-svok-provenance-spike-protocol.md`
- Create: `docs/superpowers/spikes/2026-08-06-svok-provenance-results.md`
- Create: `tests/vision/test_svok_provenance.py`

**Interfaces:**
- Consumes: Edit events + `catalog/freshness/*.yaml` (for doc-version tokens) + active model profile
- Produces: a Python AST visitor that, given a generated code snippet using external APIs, emits a provenance comment naming the doc-version consulted

- [ ] **Step 1: Write the spike protocol**

File: `docs/superpowers/spikes/2026-08-06-svok-provenance-spike-protocol.md`

```markdown
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
```

- [ ] **Step 2: Write the failing test**

File: `tests/vision/test_svok_provenance.py`

```python
"""Tests for svok_provenance_spike.py (#48)."""
import pytest
from pathlib import Path

from scripts.svok_provenance_spike import emit_provenance_comments


def test_emit_provenance_for_yaml_safe_load():
    """#48: code using yaml.safe_load gets provenance comment for pyyaml."""
    code = "import yaml\ndata = yaml.safe_load(f)\n"
    if not (Path("catalog/freshness") / "pyyaml.yaml").exists():
        pytest.skip("populate catalog/freshness/pyyaml.yaml first")

    annotated = emit_provenance_comments(code)
    assert "pyyaml" in annotated
    assert "generated against" in annotated or "docs v" in annotated.lower()


def test_emit_provenance_unchanged_for_pure_stdlib():
    """#48: code with no external API gets passed through (no provenance comments)."""
    code = "x = [1, 2, 3]\nprint(sum(x))\n"
    annotated = emit_provenance_comments(code)
    # Either identical, or only minor formatting
    assert annotated == code or "generated against" not in annotated
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `pytest tests/vision/test_svok_provenance.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement the prototype**

File: `scripts/svok_provenance_spike.py`

```python
"""SVoK / provenance comments spike (#48) — prototype.

Given a code snippet, identifies external-API usages and emits provenance
comments naming the doc-version consulted (from the freshness cache).

This is research code. Production integration is a follow-up issue if
the prototype proves out.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
# Match `import X` / `from X import Y` for top-level imports + common usage forms
IMPORT_RE = re.compile(r"^(?:from|import)\s+([a-zA-Z_][a-zA-Z0-9_.]*)", re.MULTILINE)
USAGE_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_.]*)\.")


def _doc_version_for(lib: str) -> str | None:
    cache_file = CACHE_DIR / f"{lib.lower().replace('.', '-')}.yaml"
    if not cache_file.exists():
        return None
    try:
        data = yaml.safe_load(cache_file.read_text())
    except yaml.YAMLError:
        return None
    return data.get("latest_version")


def _stdlib_libs() -> set[str]:
    """Approximation — Python stdlib modules (limited set; production would be complete)."""
    return {
        "os", "sys", "json", "re", "pathlib", "collections", "typing",
        "datetime", "time", "itertools", "functools", "subprocess",
        "math", "random", "hashlib", "logging", "unittest", "io",
    }


def emit_provenance_comments(code: str) -> str:
    """Emit provenance comments naming doc-version for external APIs used."""
    imports = set()
    for match in IMPORT_RE.finditer(code):
        imports.add(match.group(1).split(".")[0])

    external = imports - _stdlib_libs()
    today = datetime.now(timezone.utc).date().isoformat()
    provenance_lines = []

    for lib in sorted(external):
        version = _doc_version_for(lib)
        if version:
            provenance_lines.append(
                f"# generated against {lib} docs v{version} (fetched {today})"
            )

    if not provenance_lines:
        return code

    # Insert provenance block after the first import line (or at top if no imports)
    lines = code.splitlines()
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("import ") or line.startswith("from "):
            insert_idx = i + 1
            break

    return "\n".join(lines[:insert_idx] + [""] + provenance_lines + [""] + lines[insert_idx:])


if __name__ == "__main__":
    import sys
    print(emit_provenance_comments(sys.stdin.read()))
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest tests/vision/test_svok_provenance.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Run pilot on 30 samples**

Gather 30 generated code samples from heretek's git history (or fixtures in `tests/fixtures/` if insufficient history). Run the prototype on each. Record accuracy.

- [ ] **Step 7: Write the results document**

File: `docs/superpowers/spikes/2026-08-06-svok-provenance-results.md`

```markdown
# #48 — SVoK / provenance results

> Status: PENDING. Authored 2026-08-06.

## Method

30-sample pilot across Python/JS/Rust from heretek's git history.

## Results (PENDING)

| Metric | Value |
|---|---|
| Samples tested | (fill from pilot) |
| Accurate provenance comments | (fill from pilot) |
| Accuracy rate | (fill from pilot) |

## Decision

_To be filled after pilot review._
```

- [ ] **Step 8: Commit**

```bash
git add scripts/svok_provenance_spike.py tests/vision/test_svok_provenance.py
git add docs/superpowers/spikes/2026-08-06-svok-provenance-spike-protocol.md
git add docs/superpowers/spikes/2026-08-06-svok-provenance-results.md
git commit -m "spike(svok): #48 prototype + pilot"
```

---

### Task 3: Spike #49 — Cumulative codebase-staleness metric

**Files:**
- Create: `scripts/staleness_metric_spike.py`
- Create: `docs/superpowers/spikes/2026-08-06-staleness-metric-spike-protocol.md`
- Create: `docs/superpowers/spikes/2026-08-06-staleness-metric-results.md`
- Create: `tests/vision/test_staleness_metric.py`

**Interfaces:**
- Consumes: git history (commit SHAs) + `catalog/freshness/*.yaml`
- Produces: a per-commit staleness score + an aggregate trend over the repo's history

- [ ] **Step 1: Write the spike protocol**

File: `docs/superpowers/spikes/2026-08-06-staleness-metric-spike-protocol.md`

```markdown
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
```

- [ ] **Step 2: Write the failing test**

File: `tests/vision/test_staleness_metric.py`

```python
"""Tests for staleness_metric_spike.py (#49)."""
import pytest
from pathlib import Path

from scripts.staleness_metric_spike import score_for_pins


def test_score_for_pins_with_fresh_pins_is_low():
    """#49: fresh pins score near 0."""
    if not list(Path("catalog/freshness").glob("*.yaml")):
        pytest.skip("populate catalog/freshness/ first")

    pins = {"requests": "2.34.0"}  # assume latest is 2.34+
    score = score_for_pins(pins)
    assert score < 1.0, f"fresh pin should score low, got {score}"


def test_score_for_pins_with_stale_pins_is_high():
    """#49: stale pins score higher than fresh pins."""
    if not list(Path("catalog/freshness").glob("*.yaml")):
        pytest.skip("populate catalog/freshness/ first")

    fresh = score_for_pins({"requests": "2.34.0"})
    stale = score_for_pins({"requests": "2.20.0"})  # 14 minor behind
    assert stale > fresh, f"stale pin should score higher than fresh: {stale} vs {fresh}"
```

- [ ] **Step 3: Run tests and verify they fail**

Run: `pytest tests/vision/test_staleness_metric.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Implement the prototype**

File: `scripts/staleness_metric_spike.py`

```python
"""Cumulative codebase-staleness metric spike (#49) — prototype.

Walks git history, computes per-commit staleness score based on
dep-pin-vs-latest-version distance.

This is research code. Production integration is a follow-up issue if
the prototype proves out.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
PIN_RE = re.compile(r"^\s*([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*([0-9][^,;\s]*)", re.MULTILINE)


def _latest_for(lib: str) -> str | None:
    cache_file = CACHE_DIR / f"{lib.lower().replace('.', '-')}.yaml"
    if not cache_file.exists():
        return None
    try:
        return yaml.safe_load(cache_file.read_text()).get("latest_version")
    except yaml.YAMLError:
        return None


def _version_distance(pinned: str, latest: str) -> int:
    """Compute approximate major+minor distance between pinned and latest."""
    try:
        p = tuple(int(x) for x in pinned.split(".")[:2])
        l = tuple(int(x) for x in latest.split(".")[:2])
    except ValueError:
        return 0
    if len(p) < 2 or len(l) < 2:
        return 0
    return max(0, (l[0] - p[0]) * 100 + (l[1] - p[1]))


def score_for_pins(pins: dict[str, str]) -> float:
    """Compute staleness score for a dict of {lib: pinned_version}.

    Returns a sum of distance scores. Lower is fresher.
    """
    total = 0.0
    for lib, pinned in pins.items():
        latest = _latest_for(lib)
        if not latest:
            continue
        total += _version_distance(pinned, latest)
    return total


def parse_pins_from_diff(diff_text: str) -> dict[str, str]:
    """Extract dep pins from a unified diff (added lines only)."""
    pins = {}
    for match in PIN_RE.finditer(diff_text):
        # Only consider added lines (+ prefix)
        # Find the line's leading char
        start = match.start()
        # The line starts at the previous \n (or 0)
        line_start = diff_text.rfind("\n", 0, start) + 1
        if line_start < start and diff_text[line_start] == "+":
            lib, _, version = match.group(1), match.group(2), match.group(3)
            pins[lib] = version
    return pins


def compute_history_scores(repo_dir: str = ".") -> list[tuple[str, float]]:
    """Walk git history, return list of (commit_sha, staleness_score)."""
    result = subprocess.run(
        ["git", "log", "--pretty=format:%H", "--", "requirements.txt", "pyproject.toml"],
        cwd=repo_dir, capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        return []

    scores = []
    for sha in result.stdout.strip().splitlines():
        diff_result = subprocess.run(
            ["git", "show", sha, "--", "requirements.txt", "pyproject.toml"],
            cwd=repo_dir, capture_output=True, text=True, timeout=30,
        )
        if diff_result.returncode != 0:
            continue
        pins = parse_pins_from_diff(diff_result.stdout)
        scores.append((sha, score_for_pins(pins)))

    return scores


if __name__ == "__main__":
    import csv
    import sys

    scores = compute_history_scores()
    writer = csv.writer(sys.stdout)
    writer.writerow(["commit_sha", "staleness_score"])
    for sha, score in scores:
        writer.writerow([sha, score])
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest tests/vision/test_staleness_metric.py -v`
Expected: 2 tests PASS

- [ ] **Step 6: Run pilot on heretek's git history**

Run:
```bash
cd /home/john/Projects/heretek-claude-harness
python -c "from scripts.staleness_metric_spike import compute_history_scores; print(len(compute_history_scores()), 'commits')"
```

Expected: at least 5 commits (heretek's history has more than that).

Then:
Run:
```bash
python -m scripts.staleness_metric_spike > /tmp/staleness.csv
wc -l /tmp/staleness.csv
```

Expected: ≥ 5 rows in CSV.

- [ ] **Step 7: Write the results document**

File: `docs/superpowers/spikes/2026-08-06-staleness-metric-results.md`

```markdown
# #49 — Staleness metric results

> Status: PENDING. Authored 2026-08-06.

## Method

Walked heretek's full git history; computed per-commit staleness score.

## Results (PENDING)

| Metric | Value |
|---|---|
| Commits analyzed | (fill from CSV) |
| Mean score | (fill from CSV) |
| Score trend | (manual judgment from CSV plot) |

## Decision

_To be filled after pilot review._
```

- [ ] **Step 8: Commit**

```bash
git add scripts/staleness_metric_spike.py tests/vision/test_staleness_metric.py
git add docs/superpowers/spikes/2026-08-06-staleness-metric-spike-protocol.md
git add docs/superpowers/spikes/2026-08-06-staleness-metric-results.md
git commit -m "spike(staleness): #49 prototype + pilot"
```

---

### Task 4: Synthesize all three spikes into "vision report"

**Files:**
- Modify: `docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md` (append Phase 4 results section)
- Create: `docs/superpowers/research/2026-08-06-freshness-enforced-coding-vision-report.md`

**Interfaces:**
- Consumes: results documents from Tasks 1, 2, 3
- Produces: a single aggregated vision report

- [ ] **Step 1: Read all three results documents**

Run: `cat docs/superpowers/spikes/2026-08-06-counterfactual-diffs-results.md docs/superpowers/spikes/2026-08-06-svok-provenance-results.md docs/superpowers/spikes/2026-08-06-staleness-metric-results.md`

- [ ] **Step 2: Write the vision report**

File: `docs/superpowers/research/2026-08-06-freshness-enforced-coding-vision-report.md`

```markdown
# Phase 4 vision report — counterfactual diffs + SVoK + staleness metric

> Date: 2026-08-06. Synthesizes Tasks 1, 2, 3 of Plan D.

## Summary

Three research spikes explored speculative techniques for the 24-month
horizon. Results inform the v3 follow-up spec (M23).

## Spike outcomes

| Spike | Hypothesis | Result | Decision |
|---|---|---|---|
| #47 counterfactual diffs | ≥30% reduction in stale-pin merges | (fill from results) | |
| #48 SVoK / provenance | ≥50% reduction in stale-doc references | (fill from results) | |
| #49 staleness metric | Useful release-quality gate signal | (fill from results) | |

## Cross-spike observations

_To be filled after all three pilots complete._

## Recommended follow-up spec scope (M23)

_To be filled after cross-spoke synthesis._
```

- [ ] **Step 3: Append a Phase 4 section to the research report**

Append to `docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md`:

```markdown

## Phase 4 results (added 2026-08-06)

The three Phase 4 spikes (#47, #48, #49) ran as Plan D tasks. Full results:
see `docs/superpowers/research/2026-08-06-freshness-enforced-coding-vision-report.md`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/research/2026-08-06-freshness-enforced-coding-vision-report.md
git add docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md
git commit -m "docs(research): vision report aggregating #47, #48, #49 spike results"
```

---

### Task 5: Decision gate — which spikes to promote

**Files:**
- Create: `docs/superpowers/specs/2026-08-06-v3-follow-up-spec-scope.md` (decision document, not a full spec yet)

**Interfaces:**
- Consumes: vision report (Task 4)
- Produces: a decision document listing which spikes are adopted as v3 follow-up issues

- [ ] **Step 1: Apply decision rules per spec §9**

Per spec §9 risk table: "Long-term testing becomes maintenance burden with no payoff" — if a spike produces uninformative data, shut it down.

For each spike, apply:

- **Adopt (file follow-up issue):** spike succeeded per its decision criteria, follow-up work is meaningful
- **Defer (no follow-up issue, retain prototype):** spike showed promise but needs more data
- **Reject (no follow-up):** spike produced negative results

- [ ] **Step 2: Write the decision document**

File: `docs/superpowers/specs/2026-08-06-v3-follow-up-spec-scope.md`

```markdown
# v3 follow-up spec — scope decision

> Date: 2026-08-06. Status: decision document. Drives v3 spec filing.

## Decisions

| Spike | Adopt? | Follow-up action |
|---|---|---|
| #47 counterfactual diffs | (fill from results) | |
| #48 SVoK / provenance | (fill from results) | |
| #49 staleness metric | (fill from results) | |

## Recommended v3 spec scope

_To be filled based on the decision table above._

## Filing plan

(Each adopted spike gets filed as a follow-up issue; the v3 spec itself
follows the same slim-spec / fat-issues format as this roadmap spec.)
```

- [ ] **Step 3: File follow-up issues for any adopted spikes**

For each adopted spike, run `gh issue create` with the spike-results document
attached as the body. Title format: `v3 follow-up: <spike-id> production integration`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-06-v3-follow-up-spec-scope.md
git commit -m "docs(spec): v3 follow-up scope decision (drives future spec)"
```

---

**Plan D ends here. The 24-month roadmap from spec `2026-08-06-freshness-enforced-coding-roadmap-design.md` is fully planned across Plans A–D.**
