---
date: 2026-08-08
topic: harness-observability-test-pipeline
status: draft
parent: 2026-08-08-harness-observability-design.md (D23–D29 inherited)
---

# Harness Observability — Test Pipeline (sub-spec 2)

> Date: 2026-08-08. Sub-spec 2 of 3 under the parent harness-observability spec. Inherits D23–D29 unchanged.

## 1. Summary

Adds `.github/workflows/harness-test.yml` — a weekly-cron GitHub Action that runs Claude Code with heretek plugins against curated OSS fixtures, captures per-run artifacts (patch.diff, telemetry.jsonl, claude-session.log, eval_input.json), and uploads them as workflow artifacts. Sub-spec 3 (eval harness) consumes those artifacts.

## 2. Components

### 2.1 `.github/workflows/harness-test.yml`

```yaml
on:
  schedule:
    - cron: '0 2 * * 0'        # Sunday 02:00 UTC
  workflow_dispatch:
  pull_request:
    types: [labeled]
permissions:
  contents: write
  pull-requests: write
jobs:
  harness-test:
    if: github.event.label.name == 'harness-test' || github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'
    strategy:
      matrix:
        fixture: [fixture-1-ruff-lint, fixture-2-fast-gate-block, fixture-3-ast-grep-block, fixture-4-drift-detector-warn, fixture-5-telemetry-export]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<SHA>          # D20 SHA-pinned
      - uses: actions/setup-python@<SHA>      # D20 SHA-pinned
      - uses: actions/setup-node@<SHA>        # D20 SHA-pinned
      - run: pip install -r tests/fixtures/harness/requirements.txt
      - run: python scripts/harness_test.py --fixture ${{ matrix.fixture }} --output artifacts/
      - uses: actions/upload-artifact@<SHA>   # D20 SHA-pinned
        with: { name: harness-${{ matrix.fixture }}, path: artifacts/ }
```

D20 compliance: every `uses:` pinned to 40-char commit SHA. Enforced by `tests/test_action_pinning.py` (existing).

### 2.2 `tests/fixtures/harness/fixture-N-*` — one directory per fixture

```
fixture-1-ruff-lint/
  task.md                  ← task prompt given to Claude Code
  setup.sh                 ← pre-task setup (clone target repo, install deps)
  expected.json            ← ground truth: pass conditions, diff hints, rubric
  requirements.txt         ← Python deps for the harness runner
  ground-truth.patch       ← the expected patch (for diff similarity)
```

**`task.md`** — markdown. The harness reads this verbatim.

**`expected.json`** — JSON. Defines the auto-grade criteria + rubric for LLM-judge + human review.

### 2.3 `scripts/harness_test.py` — entrypoint

Runs one fixture end-to-end. Spawns `claude` CLI in the fixture's task repo with the heretek plugins installed. Captures everything.

```bash
python scripts/harness_test.py --fixture fixture-1-ruff-lint --output artifacts/
```

**Artifact bundle per run:**
```
artifacts/harness-<fixture>/
  patch.diff                    ← git diff of harness's changes
  telemetry.jsonl               ← copied from collector (sub-spec 1)
  claude-session.log            ← full Claude Code stdout/stderr
  eval_input.json               ← task.md + expected.json + diff + telemetry
  metadata.json                 ← run_id, start_time, end_time, model, plugins
  result.json                   ← auto-grade output (sub-spec 3 phase 1)
```

**`eval_input.json`** includes `sha256(patch.diff)` and `sha256(telemetry.jsonl)`. Sub-spec 3 refuses mismatched inputs.

### 2.4 `tests/fixtures/harness/fixture-meta-meta/` — the fixture for testing the fixture system

A meta-fixture whose task is "write a fixture." Used in `tests/test_harness_test.py` to test the runner without needing real Claude Code.

## 3. Data flow

```
[harness-test.yml scheduled trigger Sunday 02:00 UTC]
   └─▶ matrix job per fixture
         ├─▶ checkout @ pinned SHA
         ├─▶ setup-python + setup-node
         ├─▶ pip install deps
         ├─▶ python scripts/harness_test.py --fixture <fixture>
         │     ├─▶ cd tests/fixtures/harness/<fixture>/
         │     ├─▶ bash setup.sh (clone target repo, etc.)
         │     ├─▶ claude --plugin-dir plugins/hooks/ ... < task.md
         │     │     └─▶ collector (sub-spec 1) captures events to JSONL
         │     ├─▶ git diff > patch.diff
         │     ├─▶ copy telemetry.jsonl
         │     ├─▶ write metadata.json
         │     └─▶ invoke sub-spec 3 phase-1 (auto-grade)
         │           └─▶ writes result.json
         └─▶ upload-artifact artifacts/harness-<fixture>/
```

## 4. Error handling

| Failure | Response |
|---|---|
| Fixture repo clone fails | matrix entry failed; alert maintainer; skip phase |
| Claude Code exits non-zero | artifact still uploaded; `result.json` records `claude_exit_code`; auto-grade skipped |
| Telemetry JSONL missing/empty | `result.json` records `telemetry_collector_installed: false`; eval can still grade patch + reasoning |
| `harness-test.yml` itself fails | `if: failure()` step opens issue with full traceback |
| 3+ consecutive matrix entries fail | workflow halts, opens emergency issue |

## 5. Testing

- `tests/test_harness_test.py` — uses `fixture-meta-meta`. Mocks `subprocess.run` to invoke a deterministic script.
- `tests/test_workflows.py` (extend existing) — `harness-test.yml` runs against `fixture-meta-meta` via `act`. Asserts artifact bundle shape.
- Integration: real Claude Code runs marked `@pytest.mark.integration`, skipped in CI by default.

**Coverage target:** ≥90% on `scripts/harness_test.py`.

## 6. Phases

| Phase | Deliverable | Exit |
|---|---|---|
| 2.1 | `fixture-meta-meta` + `scripts/harness_test.py` + `tests/test_harness_test.py` | meta-fixture runs end-to-end; bundle shape correct |
| 2.2 | `harness-test.yml` workflow + D20 SHA-pinning | workflow runs on `pull_request` labeled `harness-test` |
| 2.3 | 5 curated fixtures (fixture-1 through fixture-5) | each fixture has task.md, setup.sh, expected.json, ground-truth.patch |
| 2.4 | Weekly cron + emergency-issue step | Sunday 02:00 UTC cron active; emergency issue opens on workflow failure |

## 7. References

- `docs/superpowers/specs/2026-08-08-harness-observability-design.md` — parent spec
- `docs/superpowers/specs/2026-08-08-harness-observability-collector.md` — sub-spec 1
- `scripts/security_scan.py` — pattern for `harness_test.py` (entrypoint + CLI)
- `.github/workflows/security-scan.yml` — pattern for `harness-test.yml` (matrix + cron)
- `tests/test_workflows.py` — existing workflow test infrastructure
- Issue #2 — v2 Monitor plugins (consumer of this output)
