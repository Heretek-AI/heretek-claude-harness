---
date: 2026-08-10
topic: precommit-mechanical-gates
status: draft
parent: 2026-08-03-heretek-marketplace-design.md (D1–D17 inherited), 2026-08-05-security-monitoring-pipeline-design.md (D18–D22 inherited)
related_issues: [206, 207, 208]
---

# Pre-commit Mechanical Gates — Design Spec

> Date: 2026-08-10. Umbrella spec consolidating #206 + #207 + #208 and adding the catalog-tool vetting + GitHub Actions marketplace launch. Inherits D1–D22 unchanged. Adds D30–D39.

## 1. Summary

A four-piece mechanical-gate stack deployed incrementally via 7 sub-issues:

1. **Pre-commit core** — `plugins/hooks/.pre-commit-config.yaml` with hygiene + Ruff + Biome + shellcheck-py + gitleaks. Closes #206/#207/#208.
2. **Catalog-tool vetting** — 7 domain slices (Python, JS/TS, Rust, security/secret/container, polyglot, docs/lint) ship as `hooks` plugin items.
3. **GitHub Actions marketplace launch** — new sibling package `actions/` parallel to `plugins/`, with `actions-manifest.json` and ADR template. Curated entries only.
4. **CI + docs + rollout** — `pre-commit.yml` workflow (D20 SHA-pinned), CONTRIBUTING.md refresh, hooks plugin README delta.

The umbrella issue acts as a tracker linking to the 7 sub-issues. Each sub-issue merges in one PR. Pre-commit config is one file (edited incrementally, not split). Catalog vetting produces ADRs in `catalog/reviews/hooks-<tool>.md`. The `actions/` package is bootstrapped with 2 pilot entries.

## 2. Motivation

### What this fixes

- **Issue #206:** `.pre-commit-config.yaml` was scoped for repo root, but `plugins/hooks/scripts/install_git_hooks.sh` already expects `plugins/hooks/.pre-commit-config.yaml`. This spec adopts the plugin-internal location (D15 self-containment).
- **Issue #207:** No CI enforcement of pre-commit. `git commit --no-verify` lets bad code reach `main`. Adds `pre-commit/action@v3` workflow.
- **Issue #208:** CONTRIBUTING.md has shellcheck-specific instructions but no pre-commit install + `pre-commit install` step.
- **Tool sprawl:** 25+ static-analysis tools proposed across the team. No vetted matrix → drift.
- **Marketplace gap:** No curated GH Actions package — consumers of `heretek` get plugins but no first-class action bundle.

### What this does not change

- D1–D22 inherited unchanged.
- D15 strict hook ownership: only `plugins/hooks/` ships hooks; `actions/` is a separate sibling package and never ships Claude Code hooks.
- `.claude-plugin/marketplace.json` stays generated.

## 3. Locked decisions

| # | Decision | Choice |
|---|---|---|
| D1–D17 (parent) | Marketplace D-rules | Inherited unchanged |
| D18–D22 (parent) | Security monitoring D-rules | Inherited unchanged (D20 SHA-pinning applies to all new workflows in this spec) |
| D23–D29 (harness observability) | Telemetry rules | Inherited unchanged |
| **D30** | **Pre-commit config location** | **`plugins/hooks/.pre-commit-config.yaml` (plugin-internal). Aligns with the existing `install_git_hooks.sh` path. The hooks plugin stays a self-contained installable unit.** |
| **D31** | **Umbrella scope** | **One GitHub issue that links to 7 sub-issues. Each sub-issue is one PR. Umbrella closes when all 7 sub-issues are merged + linked.** |
| **D32** | **Language coverage** | **Forward-looking. Pre-commit config covers Python, JS/TS, Rust, Shell, Markdown, YAML, TOML, Dockerfile, PHP, Java, Kotlin, Go, C/C++. Hooks gate on `types_or` / `files:` regex so non-applicable languages are zero-cost no-ops until files appear. AST-grep ships as polyglot fallback.** |
| **D33** | **Vetting scope** | **All 25 candidate tools get a D7 decision (approved / needs-triage / rejected) in this spec. Approved tools get ADRs at `catalog/reviews/hooks-<tool>.md`. Rejected tools land in `catalog/rejected.md`. The matrix in §6 is authoritative.** |
| **D34** | **GitHub Actions package shape** | **New sibling directory `actions/` parallel to `plugins/`. Each curated action lives at `actions/<name>/` with `action.yml` + ADR. `catalog/catalog.yaml` gains a new top-level `actions:` block. Generator emits `actions-manifest.json` alongside `.claude-plugin/marketplace.json`. Schema in `tests/schemas/actions-manifest.schema.json`.** |
| **D35** | **Actions distribution** | **ADR-gated curation only. Pilot launches: `trivy-action` (security/container) + `reviewdog-action` (code review). Both already pass D7. Phase 2 adds semgrep, gitleaks, zizmor after pilot validates the package contract.** |
| **D36** | **CI strategy** | **New `.github/workflows/pre-commit.yml` runs `pre-commit/action@v3` on PR + push to main. `shellcheck.yml` retained (already D20-pinned, read-only). `validate.yml` retains schema + catalog checks. Workflows do not duplicate coverage.** |
| **D37** | **fail_fast + skip policy** | **`fail_fast: true` at the root of `plugins/hooks/.pre-commit-config.yaml` (developer-time optimization per #206 acceptance). CI uses `pre-commit/action@v3` defaults (fail-fast off) so PRs surface every violation at once. Long-running hooks (semgrep full-repo, trivy) use `stages: [manual]` so they run only on `pre-commit run --hook-stage manual` (CI weekly + on-demand), never on `git commit`.** |
| **D38** | **D15 strict hooks ownership** | **The 25 vetted tools either (a) ship as pre-commit hooks via `plugins/hooks/.pre-commit-config.yaml` (Layer 3) or (b) ship as catalog `items[].kind: hook` for Claude Code `PreToolUse` consumers (Layer 1). Neither path adds hooks to non-`hooks` plugins.** |
| **D39** | **Spec lifecycle** | **This spec is an umbrella. Each sub-issue has its own ADR cluster; the spec stays thin. New tools post-merge open follow-up sub-issues (e.g. "A7: re-evaluate rejected candidates quarterly via refresh-pins").** |

## 4. Architecture

```
                ┌────────────────────────────────────────────────────────┐
                │  heretek-claude-harness repo (this spec's primary site)│
                │  Python + JS/TS + Rust + Shell + Markdown + YAML + ... │
                └────────────────────────────────────────────────────────┘
                                   │
                ┌──────────────────┴──────────────────┐
                │                                     │
                ▼                                     ▼
   plugins/hooks/.pre-commit-config.yaml   .github/workflows/pre-commit.yml
   - hygiene, ruff, biome, shellcheck-py,   - pre-commit/action@v3 (D20 SHA)
     gitleaks (core, A0)                    - matrix: [core, python, security,
   - fawltydeps, yamale, ruff-pre-commit      polyglot, ci] (slice-aware)
     (Python, A1)                            - schedule: weekly Monday 06:00 UTC
   - biome-pre-commit, semgrep-js (JS, A2)
   - cargo-machete, cargo-clippy (Rust, A3)
   - tirith, trivy-pre-commit, syft-pre-
     commit, checkov (security, A4)
   - ast-grep, semgrep (polyglot, A5)
                │
                │ + ADRs in catalog/reviews/hooks-<tool>.md
                ▼
   catalog/catalog.yaml  ──►  catalog/actions.yaml  ──►  generator
                                                       │
                                                       ├► .claude-plugin/marketplace.json (existing)
                                                       └► actions-manifest.json (new)
   actions/                                                ▲
     trivy-action/action.yml + ADR ── curated entry ──────┘
     reviewdog-action/action.yml + ADR
     (phase 2: semgrep, gitleaks, zizmor)
```

## 5. Interface contracts

| From → To | Contract |
|---|---|
| Umbrella issue → sub-issues | One parent issue with checklist linking to 7 numbered sub-issues. Body references this spec. |
| Sub-issue A0 → this repo | `plugins/hooks/.pre-commit-config.yaml` (hygiene + ruff + biome + shellcheck-py + gitleaks) + `.github/workflows/pre-commit.yml` + CONTRIBUTING.md edit + `plugins/hooks/README.md` edit. |
| Sub-issues A1–A5 → `plugins/hooks/.pre-commit-config.yaml` | Each adds a top-level `- repo: ...` entry. No file split, no override chain. |
| Pre-commit hooks → catalog | Each approved tool gets one ADR + one catalog `items[]` entry under the `hooks` plugin (kind: `hook`). |
| Catalog → generator | `catalog/catalog.yaml` gains `actions:` block (list). Generator emits `actions-manifest.json` at the same path as `marketplace.json`. |
| `actions/<name>/action.yml` → consumer | Each action is a standard GH Action — `action.yml` with `runs.using`, `inputs`, `outputs`. Pinned via `uses:` SHA in consumer workflows per D20. |
| `.github/workflows/pre-commit.yml` → runner | `pre-commit/action@v3` with explicit SHA. Caching enabled. Matrix runs slice subsets so per-PR latency stays bounded. |

## 6. Vetting matrix (D33)

Authoritative for the 25+ candidate tools. Each row is a real D7 decision based on current public facts; the team must re-verify at merge time using `refresh_pins.py`.

| Tool | Repo | Category | D7 stars | D7 license | D7 last-commit | D7 CVE | Verdict | Target |
|---|---|---|---|---|---|---|---|---|
| `pre-commit/pre-commit-hooks` | pre-commit/pre-commit | hygiene | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (Layer 3 core) |
| `gitleaks/gitleaks` | gitleaks/gitleaks | secrets | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (Layer 3 + Layer 1 hook) |
| `astral-sh/ruff-pre-commit` | astral-sh/ruff | Python | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (Layer 3 core) |
| `biomejs/pre-commit` | biomejs/biome | JS/TS | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (Layer 3 core) |
| `shellcheck-py/shellcheck-py` | shellcheck-py/shellcheck-py | Shell | ✓ | GPL-3 → MIT (wrapper) | ✓ | ✓ | **Approved** (wrapper MIT, scans GPL tool) | hooks plugin (Layer 3 core) |
| `doublify/pre-commit-rust` | doublify/pre-commit-rust | Rust | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (Layer 3 core) |
| `tweag/FawltyDeps` | tweag/FawltyDeps | Python deps | ✓ | BSD-3 | ✓ | ✓ | **Approved** | hooks plugin (A1) |
| `23andMe/Yamale` | 23andMe/Yamale | YAML schema | borderline (~600) | Apache-2.0 | ✓ | ✓ | **Needs triage** — verify stars at merge | hooks plugin (A1) |
| `ast-grep/ast-grep` | ast-grep/ast-grep | polyglot | ✓ | MIT | ✓ | ✓ | **Approved** (already used in validate.yml) | hooks plugin (A5) |
| `returntocorp/semgrep` | semgrep/semgrep | polyglot | ✓ | LGPL-2.1 | ✓ | ✓ | **Approved** | hooks plugin (A5) |
| `sheeki03/tirith` | sheeki03/tirith | security policy | ✗ (<500 stars) | MIT | ✓ | ✓ | **Rejected** — D7 stars fail. Note rationale. | n/a — see `catalog/rejected.md` |
| `croc100/pytest-mrt` | croc100/pytest-mrt | test reporter | ✗ (low stars, niche) | MIT | borderline | n/a | **Rejected** — niche, low stars | n/a |
| `bnjbvr/cargo-machete` | bnjbvr/cargo-machete | Rust deps | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A3) |
| `analysis-tools-dev/static-analysis` | analysis-tools-dev/static-analysis | aggregator | ✓ | MIT | ✓ | n/a (docs only) | **Approved** as reference doc only (no code execution) | README link, not a catalog item |
| `quay/clair` | quay/clair | container vuln | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** for GH Actions package only (heavy, not pre-commit-friendly) | actions package (phase 2) |
| `koalaman/shellcheck` | koalaman/shellcheck | Shell | ✓ | GPL-3 | ✓ | ✓ | **Approved** — already in `shellcheck.yml` (D20 pinned) | hooks plugin (Layer 3 core) |
| `woodruffw/zizmor` | woodruffw/zizmor | YAML/GHA | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A4) |
| `nikic/PHP-Parser` | nikic/PHP-Parser | PHP parser | ✓ | BSD-3 | ✓ | ✓ | **Approved** (library; downstream tools use it) | pre-commit config hook (A2) |
| `phpstan/phpstan` | phpstan/phpstan | PHP static | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `PHP-CS-Fixer/PHP-CS-Fixer` | PHP-CS-Fixer/PHP-CS-Fixer | PHP format | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `bridgecrewio/checkov` | bridgecrewio/checkov | IaC | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** | actions package (phase 2) |
| `anchore/syft` | anchore/syft | SBOM | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** | actions package (phase 2) |
| `checkstyle/checkstyle` | checkstyle/checkstyle | Java lint | ✓ | LGPL-2.1 | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `reviewdog/reviewdog` | reviewdog/reviewdog | review bot | ✓ | MIT | ✓ | ✓ | **Approved** | actions package (pilot) |
| `SonarSource/sonarqube` | SonarSource/sonarqube | SAST | ✓ | LGPL-2.1 | ✓ | ✓ | **Approved** (self-hosted option) — already referenced in hooks plugin Layer 2 | hooks plugin (Layer 2 quality_gate) |
| `securego/gosec` | securego/gosec | Go lint | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `presidentbeef/brakeman` | presidentbeef/brakeman | Rails SAST | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `google/error-prone` | google/error-prone | Java SAST | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `facebook/pyrefly` | facebook/pyrefly | Python type | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A1) |
| `facebook/Pysa` | facebook/Pysa | Python SAST | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A1) |
| `sverweij/dependency-cruiser` | sverweij/dependency-cruiser | JS deps | ✓ | MIT | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `aquasecurity/trivy` | aquasecurity/trivy | vuln scan | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** | actions package (pilot) |
| `detekt/detekt` | detekt/detekt | Kotlin lint | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `dominikh/go-tools` | dominikh/go-tools | Go lint | ✓ | BSD-3 | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `danmar/cppcheck` | danmar/cppcheck | C/C++ lint | ✓ | GPL-3 | ✓ | ✓ | **Approved** | hooks plugin (A2) |
| `fallow-rs/fallow` | fallow-rs/fallow | Rust deps | ✓ | Apache-2.0 | ✓ | ✓ | **Approved** | hooks plugin (A3) |

**Totals:** 36 entries — 33 approved (1 docs-only), 2 rejected, 1 needs triage. Rejected tools: `sheeki03/tirith` (D7 stars fail — record rationale in `catalog/rejected.md`), `croc100/pytest-mrt` (D7 stars fail + niche). Needs-triage: `23andMe/Yamale` (verify stars ≥ 500 at merge).

## 7. Phasing (7 sub-issues)

| Sub-issue | Slice | Tools (sample) | PR scope |
|---|---|---|---|
| **A0** | Pre-commit core (closes #206/#207/#208) | hygiene, ruff-pre-commit, biome-pre-commit, shellcheck-py, gitleaks, doublify/pre-commit-rust | One PR: `.pre-commit-config.yaml` + `.github/workflows/pre-commit.yml` + CONTRIBUTING.md + `plugins/hooks/README.md` |
| **A1** | Python ecosystem | FawltyDeps, Yamale (if stars pass), pyrefly, Pysa, ruff-pre-commit | One PR: catalog items + ADR cluster + config delta |
| **A2** | JS/TS + Java + Kotlin + Go + PHP + C/C++ | biome-pre-commit (deeper), semgrep-js, gosec, brakeman, error-prone, phpstan, php-cs-fixer, checkstyle, detekt, dominikh/go-tools, dependency-cruiser, cppcheck | One PR |
| **A3** | Rust ecosystem | cargo-machete, fallow, cargo-clippy deepen, cargo-fmt tighten | One PR |
| **A4** | Security/secret/container | zizmor, gitleaks (deeper), checkov, syft (action only) | One PR |
| **A5** | Polyglot static analysis | ast-grep (rules), semgrep rules, tirith (if rejection overturned) | One PR |
| **A6** | GitHub Actions marketplace launch | scaffold `actions/`, schema, ADR template, pilot entries (`trivy-action`, `reviewdog-action`) | One PR |

Merge order: A0 first (the spine). Then A1–A5 in parallel-friendly batches. A6 lands last because it touches the generator.

## 8. CI + docs

- **`.github/workflows/pre-commit.yml`** — D20 SHA-pinned `actions/checkout`, `actions/setup-python@v5`, `pre-commit/action@v3`. PR + push-to-main + weekly Monday 06:00 UTC. `fail-fast: false` (CI surface every violation). Read-only permissions.
- **Existing `shellcheck.yml`** — retained. Already D20-pinned. No edit.
- **`CONTRIBUTING.md`** — new section "Pre-commit framework": install (`pip install pre-commit`), bind (`pre-commit install`), run (`pre-commit run --all-files`), skip (`git commit --no-verify` rationale).
- **`plugins/hooks/README.md`** — Layer 3 section expanded with the new tool list and `fail_fast: true` mention.
- **`docs/recommended-github-actions.md`** — pointer file for `actions/` discoverability (no schema, no catalog coupling).
- **CLAUDE.md** — one-line addition pointing to this spec under "Common commands".

## 9. Open risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Pre-commit on the full repo surfaces >100 existing violations | A0 PR either fixes them in the same PR (preferred) OR adds `--baseline` exclusions scoped to legacy files only. No blanket suppression. |
| 2 | 25 ADRs inflate `catalog/reviews/` | ADRs are short (per D6 template). Batched reviews per slice reduce churn. |
| 3 | Yamale stars drift below D7 at merge time | Sub-issue A1 is gated on a re-check. If fails, the entry is removed before merge, no orphan hook in config. |
| 4 | `actions/` generator duplicates `marketplace.json` codegen | Generator uses shared helpers (`scripts/_marketplace_common.py`); DRY via single emitter. |
| 5 | Long-running hooks (semgrep full, trivy) blow the 5-min CI budget | Tagged `stages: [manual]` so they run on `pre-commit run --hook-stage manual` only — weekly schedule + `workflow_dispatch`, never on PR. |
| 6 | D15 violations sneak in via new `actions/` | CI lint: `python scripts/validate.py` rejects any plugin entry other than `hooks` declaring `hooks` in `components`. Same rule applies to `actions/` — `actions/<name>/action.yml` is `runs.using: composite|docker|node20`, never a Claude Code hook manifest. |

## 10. Acceptance criteria (umbrella)

- [ ] A0 PR merged; `pre-commit run --all-files` exits 0; CI workflow live; CONTRIBUTING.md updated.
- [ ] A1–A5 PRs merged; all approved tools have ADRs + catalog items.
- [ ] A6 PR merged; `actions/` package bootstrapped; pilot entries live; `actions-manifest.json` regenerates.
- [ ] `python scripts/validate.py` exits 0.
- [ ] `pytest -q` exits 0.
- [ ] `python scripts/generate_marketplace.py` produces no `.claude-plugin/marketplace.json` drift.
- [ ] Umbrella issue closes when all 7 sub-issues close + links resolve.