# SonarCloud Remediation — Design Spec

> Date: 2026-08-08. Status: in-flight.
> Source data: SonarCloud API (`Heretek-AI_heretek-claude-harness`, statuses=OPEN) pulled 2026-08-08.
> Epic: (linked once filed)

## 1. Goal

Resolve all **71 open SonarCloud issues** on `Heretek-AI/heretek-claude-harness` via a sequence of
focused, reviewable PRs. Land BLOCKERs first, then CRITICAL, then area-grouped MAJOR/MINOR.

## 2. Counts at snapshot

| Severity | Count | Type | Count |
|---|---|---|---|
| BLOCKER | 7 | VULNERABILITY | 36 |
| CRITICAL | 5 | CODE_SMELL | 34 |
| MAJOR | 50 | BUG | 1 |
| MINOR | 9 | | |

Effort: 1768min total per SonarCloud.

Top rules: `githubactions:S8544`×11, `pythonsecurity:S8707`×9, `githubactions:S8541`×8,
`python:S3516`×6, `python:S3776`×5, `python:S6353`×4, `python:S1481`×4, `shelldre:S7688`×4.

## 3. Sequencing — 7 PRs

| PR | Scope | Sev | Count | Est. lines |
|----|-------|-----|-------|-----------|
| 1 | BLOCKER (all 7) — S2083 real fix + 6×S3516 verify/suppress | B | 7 | ~80 |
| 2 | CRITICAL cognitive complexity (5 functions; security_scan.py:236 is the beast at CC=57) | C | 5 | ~400 |
| 3 | GitHub Actions hardening (S8544/S8541/S8233/S6505/S8543 across 5 workflows) | M | 22 | ~60 |
| 4 | Python security rules S8707/S8705/S2083-style | M | 10 | ~80 |
| 5 | Python code smells (S1481, S1172, S5958, S3358, S1656, S9073, S8997, S8513, S5778, S5713, S6353, S108) | M+M | ~14 | ~40 |
| 6 | Shell script issues (S7688×4, S7677×1) | M | 5 | ~20 |
| 7 | Remaining MAJOR/MINOR catch-all (text:S8565 pyproject, leftover rules) | M+m | ~8 | ~20 |

Total ~71 fixes across 7 PRs. Each PR <500 lines diff.

## 4. Approach to likely false positives

**S3516 "always returns same value"** (6 BLOCKER hits) — read each site, confirm by inspection +
behavior-preserving test, then either:
- Real refactor: extract the side-effect and have the function return None intentionally (still
  valid Python idiom; suppress with `# noqa: S3516` only if Sonar still flags after refactor)
- Confirmed false positive: `# noqa: S3516` annotation with rationale comment

**S3776 cognitive complexity > 15** — real refactors. Extract helper functions. security_scan.py:236
at CC=57 will need a `RefactorPlan` with private helpers.

**S8707 / S8705** ("LLMs running this code with faulty CLI arguments...") — Python security AI/LLM
pattern. Likely false-positive in our context (we don't pass these scripts to LLMs). Verify, then
`# noqa: S8707` with rationale if confirmed.

## 5. Verification (per PR)

```bash
python scripts/validate.py        # schema OK
python scripts/generate_marketplace.py
git diff --exit-code .claude-plugin/marketplace.json
pytest -q                        # 270 baseline + new tests pass
```

GitHub Actions workflows: pin `pip install` deps with `--require-hashes` or set
`actions/setup-python@v5` `cache: 'pip'` + lockfile. Verify each workflow manually after the YAML
change with `act` or by reading carefully.

## 6. PR status (filled in as each merges)

| PR | Branch | Status | Merged at | Notes |
|----|--------|--------|-----------|-------|
| 1 | `fix/sonar-blocker` | ✅ merged (#142) | 2026-08-09 | |
| 2 | `refactor/cognitive-complexity` | ✅ merged (#143) | 2026-08-09 | |
| 3 | `ci/github-actions-hardening` | ✅ merged (#144) | 2026-08-09 | |
| 4 | `fix/python-security-rules` | ✅ merged (#145) | 2026-08-09 | |
| 5 | `chore/python-code-smells` | ✅ merged (#146) | 2026-08-09 | |
| 6 | `fix/shell-script-issues` | ✅ merged (#147) | 2026-08-09 | |
| 7 | `chore/sonar-remaining` | ✅ merged (#148) | 2026-08-09 | |
| — | `fix/nosonar-same-line` | ✅ merged (#149) | 2026-08-09 | Marker-relocation follow-up |

## 7. Non-goals

- No Quality Gate wiring (deferred per user decision; quarterly `refresh_pins.py` already re-verifies).
- No new lint tools added.
- No performance optimizations (orthogonal to Sonar findings).
- No changes to `plugins/hooks/scripts/fast_gate*` (sub-100ms budget).

## 8. Risks

- **Refactor regressions**: especially `security_scan.py:236` refactor. Mitigation: run full pytest
  + dry-run `python scripts/security_scan.py --help` after refactor.
- **Workflow YAML breaks**: pinned-version changes can break CI. Mitigation: keep diffs minimal,
  preserve comment markers like `# D20`.
- **`pyproject.toml` lockfile change** (text:S8565): if uv/poetry aren't the actual tool, leave it.
- **Token/context exhaustion mid-sequence**: commit + push + merge after each PR so state persists.

## 9. Out of scope

- D7 catalog changes (this is a code-quality sweep, not a catalog decision).
- Documentation rewrites.
- Plugin component additions or removals.

## 10. Issue list (full)

```
[BLOCKER ] scripts/drift_detector.py:57  pythonsecurity:S2083            Change this code to not construct the path from user-controlled data.
[BLOCKER ] scripts/drift_detector.py:176  python:S3516                    Refactor this method to not always return the same value.
[BLOCKER ] scripts/lookup_gate.py:60  python:S3516                        Refactor this method to not always return the same value.
[BLOCKER ] scripts/rlm_fast_gate_spike.py:22  python:S3516                Refactor this method to not always return the same value.
[BLOCKER ] scripts/scanners/ast_grep_scanner.py:68  python:S3516          Refactor this method to not always return the same value.
[BLOCKER ] scripts/scanners/forbidden_pattern_scanner.py:89  python:S3516 Refactor this method to not always return the same value.
[BLOCKER ] scripts/stale_dep_intercept.py:104  python:S3516               Refactor this method to not always return the same value.
[CRITICAL] scripts/catalog_updater.py:22  python:S3776                    Refactor this function to reduce its Cognitive Complexity from 17 to the 15 allowed.
[CRITICAL] scripts/refresh_pins.py:79  python:S3776                       Refactor this function to reduce its Cognitive Complexity from 17 to the 15 allowed.
[CRITICAL] scripts/refresh_pins.py:139  python:S3776                      Refactor this function to reduce its Cognitive Complexity from 17 to the 15 allowed.
[CRITICAL] scripts/scanners/lsp.py:80  python:S3776                       Refactor this function to reduce its Cognitive Complexity from 16 to the 15 allowed.
[CRITICAL] scripts/security_scan.py:236  python:S3776                     Refactor this function to reduce its Cognitive Complexity from 57 to the 15 allowed.
[MAJOR   ] .claude/skills/catalog/tests/smoke_test.sh:104  shelldre:S7688  Use '[[' instead of 'test' command for conditional tests.
[MAJOR   ] .github/workflows/security-scan-pr.yml:30  githubactions:S8541  Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/security-scan-pr.yml:30  githubactions:S8544  Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/security-scan.yml:11  githubactions:S8233    Move this write permission from workflow level to job level.
[MAJOR   ] .github/workflows/security-scan.yml:12  githubactions:S8233    Move this write permission from workflow level to job level.
[MAJOR   ] .github/workflows/security-scan.yml:13  githubactions:S8233    Move this write permission from workflow level to job level.
[MAJOR   ] .github/workflows/security-scan.yml:33  githubactions:S8544    Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/security-scan.yml:34  githubactions:S8541    Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/security-scan.yml:34  githubactions:S8544    Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/security-scan.yml:106  githubactions:S8541   Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/security-scan.yml:106  githubactions:S8544   Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/smoke-test.yml:43  githubactions:S8541      Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/smoke-test.yml:43  githubactions:S8544      Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/smoke-test.yml:64  githubactions:S6505      Omitting "--ignore-scripts" allows lifecycle scripts to run during package installation.
[MAJOR   ] .github/workflows/smoke-test.yml:64  githubactions:S8543      Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/smoke-test.yml:67  githubactions:S8541      Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/smoke-test.yml:67  githubactions:S8544      Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/smoke-test.yml:150  githubactions:S8541     Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/smoke-test.yml:150  githubactions:S8544     Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/validate.yml:34  githubactions:S8544        Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/validate.yml:35  githubactions:S8544        Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/validate.yml:129  githubactions:S8541       Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/validate.yml:129  githubactions:S8544       Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] .github/workflows/validate.yml:154  githubactions:S8541       Omitting "--only-binary :all:" can lead to the execution of setup scripts.
[MAJOR   ] .github/workflows/validate.yml:154  githubactions:S8544       Using dependencies without locking resolved versions is security-sensitive.
[MAJOR   ] plugins/hooks/scripts/install_git_hooks.sh:32  shelldre:S7688  Use '[[' instead of '[' for conditional tests.
[MAJOR   ] pyproject.toml:None  text:S8565                              Dependency versions are not predictable if the lock file (uv.lock, poetry.lock, pdm.lock or pylock.t
[MAJOR   ] scripts/catalog_updater.py:38  pythonsecurity:S8707            LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/catalog_updater.py:66  pythonsecurity:S8707            LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/generate_marketplace.py:92  pythonsecurity:S8707       LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/generate_marketplace.py:111  pythonsecurity:S8707      LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/refresh_pins.py:119  pythonsecurity:S8707             LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/refresh_pins.py:153  pythonsecurity:S8707             LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/refresh_pins.py:176  pythonsecurity:S8707             LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/refresh_pins.py:201  python:S1656                     Remove or correct this useless self-assignment.
[MAJOR   ] scripts/refresh_pins.py:203  python:S108                      Either remove or fill this block of code.
[MAJOR   ] scripts/scanners/lsp.py:183  python:S3358                     Extract this nested conditional expression into an independent statement.
[MAJOR   ] scripts/security_scan.py:191  pythonsecurity:S8705             LLMs running this code with faulty CLI arguments can escape from shell sandboxes.
[MAJOR   ] scripts/security_scan.py:265  pythonsecurity:S8707             LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/security_scan.py:266  pythonsecurity:S8707             LLMs running this code with faulty CLI arguments can escape file system restrictions.
[MAJOR   ] scripts/stale_dep_intercept.py:58  python:S1172                Remove the unused function parameter "file_path".
[MAJOR   ] scripts/svok_provenance_spike.py:73  python:S8513              Replace chained "startswith" calls with a single call using a tuple argument.
[MAJOR   ] tests/enforcement/test_profile_aware_enforcement.py:43  python:S9073  Split this composite assertion into separate assertions.
[MAJOR   ] tests/smoke/fast_gate_smoke.sh:24  shelldre:S7688              Use '[[' instead of '[' for conditional tests.
[MAJOR   ] tests/smoke/fast_gate_smoke.sh:31  shelldre:S7677              Redirect this error message to stderr (>&2).
[MAJOR   ] tests/smoke/fast_gate_smoke.sh:35  shelldre:S7688              Use '[[' instead of '[' for conditional tests.
[MAJOR   ] tests/test_fast_gate.py:44  python:S5778                       Refactor this exception test to have only one invocation possibly throwing an exception.
[MAJOR   ] tests/test_quality_gate.py:39  python:S8997                    Use the "monkeypatch" fixture for temporary modifications.
[MAJOR   ] tests/test_quality_gate.py:42  python:S8997                    Use the "monkeypatch" fixture for temporary modifications.
[MAJOR   ] tests/test_scanner_base.py:18  python:S5958                    This assertion is too broad; use a more specific exception type or check the exception message.
[MINOR   ] scripts/counterfactual_diffs_spike.py:19  python:S6353         Use concise character class syntax '\d' instead of '[0-9]'.
[MINOR   ] scripts/counterfactual_diffs_spike.py:45  python:S1481         Replace the unused local variable "op" with "_".
[MINOR   ] scripts/generate_marketplace.py:127  python:S5713             Remove this redundant Exception class; it derives from another which is already caught.
[MINOR   ] scripts/lookup_gate.py:31  python:S6353                        Use concise character class syntax '\d' instead of '[0-9]'.
[MINOR   ] scripts/rlm_fast_gate_spike.py:32  python:S1481                Remove the unused local variable "file_path".
[MINOR   ] scripts/rlm_fast_gate_spike.py:33  python:S1481                Remove the unused local variable "new_string".
[MINOR   ] scripts/stale_dep_intercept.py:27  python:S6353                Use concise character class syntax '\d' instead of '[0-9]'.
[MINOR   ] scripts/stale_dep_intercept.py:62  python:S1481                Replace the unused local variable "op" with "_".
[MINOR   ] scripts/staleness_metric_spike.py:18  python:S6353            Use concise character class syntax '\d' instead of '[0-9]'.
```
