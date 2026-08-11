---
date: 2026-08-03
topic: heretek-marketplace
status: draft
parent: PLAN.md (the original repo plan — this spec is the refined, locked v1 design)
---

# HereTek Marketplace v1 — Design Spec

> Opinionated Claude Code plugin marketplace, living in the `heretek-claude-harness` repo.
> Public OSS from day one. Marketplace name: `heretek`. Owner: `Heretek-AI`.

---

## 1. Vision

A single-command install that turns any Claude Code into an opinionated harness. The `heretek` marketplace ships 11 first-party plugins (4 task: `rust`, `python`, `js-ts`, `web-frontend`; 7 cross-cutting: `hooks`, `security`, `skills-pack`, `mcp-pack`, `lsp-pack`, `agents`, `output-styles`) plus curated SHA-pinned 3rd-party aggregation.

The **`hooks` plugin is the differentiator**: layered quality gates — fast blocking (<100ms), slow on-demand, git pre-commit — wired into both the Claude Code hook system and git. Public OSS day one, every item vetted.

---

## 2. Locked decisions

Inherits D1–D13 from `PLAN.md`. Adds D14–D17 from this spec's brainstorming session.

| # | Decision | Choice |
|---|---|---|
| D1 | Repo model | Monorepo + external sources. Own plugins as relative sources (`pluginRoot=./plugins`); 3rd-party via `git-subdir`/`github` with SHA pins |
| D2 | Repo home | This repo (`heretek-claude-harness`) |
| D3 | Launch scope | Category-complete, candidate-curated. Every category ships ≥1 flagship; only items passing the vetting bar ship; rejects → `catalog/rejected.md` |
| D4 | Audience | Public OSS day one. Needs `CONTRIBUTING.md`, `SECURITY.md`, written vetting bar |
| D5 | Taxonomy | 4 task + 7 cross-cutting plugins. Overlap rule: task plugins bundle only task-specific items; generic items live in packs |
| D6 | Hooks architecture | Fast-block (<100ms), slow-command (`/quality-gate:run`), pre-commit framework (Layer 3) |
| D7 | Security / vetting bar | SHA-pin + written bar: stars ≥ 500, last commit ≤ 12mo, OSI license, source-audit of code-executing components, no critical CVEs in 24mo. Quarterly refresh |
| D8 | Pipeline contract | `catalog.yaml` is source of truth. CI generates `marketplace.json`; `git diff --exit-code` enforced |
| D9 | Repo hygiene | Repo = marketplace. Personal harness copies deleted from repo. Live global installs (`~/.agents/skills`, `~/.config/opencode/skills`) untouched |
| D10 | 3rd-party aggregation | Full: curated in-marketplace + community-tagged section + `docs/recommended-marketplaces.md` |
| D11 | Versioning (own) | SHA-ride — no explicit version. Every marketplace commit = new version. Updates flow on `/plugin marketplace update` |
| D12 | CI bar | Schema validation + generation diff + live install smoke test |
| D13 | Identity | Marketplace `heretek`, owner `Heretek-AI`. Public-facing: `/plugin install rust@heretek` |
| **D14** | **License** | **MIT for own code. Vendored 3rd-party components retain their upstream license + NOTICE** |
| **D15** | **Hooks overlap (strict)** | **`hooks` plugin owns ALL hooks firing on `Edit`/`Write`/`PreToolUse`/`PostToolUse`/`Notification`. No other plugin ships such hooks — including security-scoped hooks** |
| **D16** | **Versioning re-confirm** | **SHA-ride confirmed for own plugins. Revisit with explicit versions + `renames` map only if update churn becomes a user-visible problem** |
| **D17** | **Heretek-AI org** | **Must exist before public launch (Phase 6 / SP4). Repo transfer to the org required as part of launch** |

---

## 3. Architecture overview

```
catalog.yaml (source of truth — every item, every plugin)
   │  scripts/generate-marketplace
   ▼
.claude-plugin/marketplace.json (generated, never hand-edited)
   │  claude plugin marketplace add heretek <repo-url>
   ▼
user installs: /plugin install <name>@heretek
   │
   ├─ relative source  → plugins/<name>/                       (first-party)
   └─ git-subdir/github SHA-pinned → upstream repo             (3rd-party)
```

**Curation loop** (`scripts/new-item`, run by maintainer or delegated to research stack):

1. **Discover** — Firecrawl: scrape candidate repo/README/agg list (`ref.text`, awesome-lists, GitHub topics)
2. **Verify** — GitHub MCP: stars, last commit, license, open issues, CVE scan
3. **Review** — deep-research skill: tool quality, alternatives, opinionated verdict
4. **Record** — write `catalog/reviews/<slug>.md` (ADR template: what / why / alternatives / verdict / target plugin)
5. **Catalog** — add entry to `catalog.yaml`, or move to `catalog/rejected.md` if it fails the bar
6. **Generate** — `scripts/generate-marketplace` → `marketplace.json`
7. **Gate** — CI: schema validate + generation diff + smoke test

CI: `.github/workflows/validate.yml` on PR + push to main. `.github/workflows/smoke-test.yml` on merge + nightly.

---

## 4. Hooks architecture (D6 + D15)

Three layers, both hook worlds:

### Layer 1 — Fast gates (blocking, <100ms)

`PreToolUse` on `Edit`/`Write`/`MultiEdit`. Lint only staged/new content:

- python → `ruff` (targeted)
- rust → `rustfmt --check` (targeted; `cargo-clippy` is too slow to block — demoted to Layer 2)
- js-ts → `biome` (targeted)

Exit non-zero → blocks the tool call. **Hard 100ms timeout; fail-open with warning if exceeded** (don't stall the agent loop).

### Layer 2 — Slow analyzers (on-demand + optional notify)

- `/quality-gate:run` command: full suite — clippy, megalinter, tdd-guard, jscpd, sonarqube (when configured)
- Optional `PostToolUse` Notification hooks (non-blocking) that surface analyzer output without stalling the agent loop

### Layer 3 — Git hooks

- Ships a pre-commit framework config (YAML) + an installer command (`/hooks:install-git-hooks`) that runs `pre-commit install` for pre-commit + pre-push
- Independent of Claude Code's hook system
- Requires Python (pre-commit is Python); README documents both Claude Code install (`/plugin install hooks@heretek`) and git hook install (via the command)

### Conflict policy (D15, strict)

The `hooks` plugin is the sole owner of all hooks firing on `Edit`/`Write`/`PreToolUse`/`PostToolUse`/`Notification`. **No other plugin ships such hooks** — including security-scoped hooks. If a user enables another hooks plugin, ordering is resolved at the manifest level (strict mode, `plugin.json` is authority). Documented in plugin README.

### Aitmpl.com hooks

The 6 aitmpl.com hooks listed in `ref.text` (security-scanner, dependency-checker, smart-formatting, run-tests-after-changes, change-tracker, plus a duplicate) are vetted per D7. **Any that pass land in `plugins/hooks/hooks/hooks.json` with an ADR.** Per the strict reading of D5/D15, they belong in the `hooks` plugin, not split across plugins.

---

## 5. `catalog.yaml` schema (D8)

```yaml
plugins:
  - name: rust
    category: task                 # task | cross | community
    tags: [rust, language]
    source: { type: relative, path: rust }   # first-party
    # 3rd-party example:
    # source: { type: git-subdir, url: obra/superpowers, path: superpowers, sha: <40-char> }
    components: [skills, mcp, lsp]           # what this plugin bundles
    items:                                   # curated items inside the plugin
      - id: rust-analyzer
        kind: lsp                            # skills | mcp | lsp | hook | agent | output-style
        upstream: rust-lang/rust-analyzer    # for 3rd-party items; omit for first-party
        sha: <40-char>                       # required for 3rd-party; omit for first-party
        license: MIT                         # SPDX
        vetting:
          status: approved                   # approved | pending | rejected
          date: 2026-08-03
          stars: 10000
          last_commit: 2026-07-15
          cve_scan: 2026-08-03               # date of last GitHub-advisory CVE check
          review: catalog/reviews/rust-analyzer.md   # required when status=approved
```

**CI lint:** entries with `vetting.status: approved` must have a `review:` link. Rejected items live in `catalog/rejected.md` with reason (license, stars, CVE, etc.). Re-vetting permitted by re-running the new-item flow.

**Generation contract:** `scripts/generate-marketplace` reads `catalog.yaml`, writes `.claude-plugin/marketplace.json`. The JSON Schema for `marketplace.json` is the Claude Code plugin marketplace schema (verify exact shape in SP1 against current docs at <https://code.claude.com/docs/en/plugin-marketplaces>). The schema is treated as authoritative; any divergence is a bug.

---

## 6. Vetting bar (D7)

A candidate is included **only if all** are true:

- stars ≥ 500
- last commit ≤ 12 months
- OSI-approved license (MIT / Apache-2.0 / BSD etc.) — explicitly checked
- **source-audit pass** for any code-executing component (hooks, `bin/`, MCP servers, pre-commit hooks) — human review recorded in the ADR
- no **critical** CVEs in last 24 months (GitHub advisory check via GitHub MCP)

### Refresh loop (quarterly)

`scripts/refresh-pins` enumerates all external SHA pins + vetting dates, flags stale ones via GitHub MCP. Maintainer either bumps the SHA (re-vetting the delta) or moves the item to `rejected.md` with reason. Standing chore with an owner. A `renames` entry in `marketplace.json` handles removals gracefully.

---

## 7. CI / CD

### `.github/workflows/validate.yml` (PR + push to main)

1. `scripts/validate` — JSON Schema check of `marketplace.json` + every plugin manifest (`plugin.json`, `hooks.json`, `.mcp.json`, `.lsp.json`)
2. `scripts/generate-marketplace` + assert `git diff --exit-code` (catalog.yaml and marketplace.json never drift)
3. Vetting lint — entries with `vetting.status: approved` without a `review:` link fail CI

### `.github/workflows/smoke-test.yml` (merge + nightly)

1. Fresh temp dir, `claude plugin marketplace add heretek <repo-url>`
2. Install all 11 plugins; assert skills/hooks/mcp/lsp components present
3. Trigger one fast-gate hook on a staged bad file; assert non-zero exit
4. Requires `claude` CLI + scoped auth token in CI secrets; `--dangerously-skip-permissions` only in isolated runner

### Error handling

- Schema-invalid `catalog.yaml` → CI red, error to stderr
- Schema validation runs first; generation only on schema-clean input
- Vetting failure path: rejected items → `catalog/rejected.md` with reason; re-vetting via new-item flow
- Smoke test captures stderr; one retry tolerated (flaky-network tolerance)

---

## 8. First-party plugins (11 cards)

| # | Plugin | Category | Components | Bundle (v1 first cut) | Vetting notes |
|---|---|---|---|---|---|
| 1 | **`rust`** | task | skills + mcp + lsp | rust-analyzer (lsp; user-installed via rustup), cargo-check skill, task-scoped MCP. No hooks (D15). | rust-analyzer is rust-lang official; well-known. |
| 2 | **`python`** | task | skills + mcp + lsp | basedpyright or pyright (lsp; user-installed), ruff-driven skill, pytest patterns skill. No hooks. | pyright/basedpyright OSI-approved, ≥500★. |
| 3 | **`js-ts`** | task | skills + mcp + lsp | biome or oxc (lsp + formatter), tsconfig-aware skills. No hooks. | biome/oxc both MIT, ≥500★. |
| 4 | **`web-frontend`** | task | skills + mcp | chrome-devtools-mcp (mcp; source-audit required), lighthouse-driven skill, design-review skill, storybook integration. No hooks. | chrome-devtools-mcp code-executing → D7 source-audit. |
| 5 | **`hooks`** | cross (flagship) | hooks + commands + git-hooks | Layer 1 fast gates (ruff/rustfmt/biome PreToolUse, <100ms); Layer 2 `/quality-gate:run` (clippy/megalinter/tdd-guard/jscpd/sonarqube); Layer 3 pre-commit framework installer `/hooks:install-git-hooks`. **Sole owner of all hooks (D15).** Aitmpl.com hooks vetted per D7; if any pass, they land here. | Tools are vetted upstream; aitmpl.com hooks need re-pinning to upstream before inclusion. |
| 6 | **`security`** | cross | skills + commands | Security-research skill, audit checklists, audit commands. **No hooks** (D15). | Code-execution paths (if any) need D7 source-audit. |
| 7 | **`skills-pack`** | cross | skills only | v1 candidates: caveman (JuliusBrussee/caveman), superpowers (obra/superpowers), find-skills, review-work. Tier-2 candidates (defer to v2 unless vetted): agent-skills, wondelai/skills, Citadel, headroom, taste-skill, claude-mem, ponytail, cli-anything. Each gets an ADR. | Vetting bar likely keeps 3-5 for v1; rest deferred. |
| 8 | **`mcp-pack`** | cross | mcp only | context7, github-mcp-server, codebase-memory-mcp, serena. chrome-devtools-mcp lives in `web-frontend` (task-specific). mksglu/context-mode under consideration; not in v1 unless vetted. | All MCP servers are code-executing → D7 source-audit mandatory. |
| 9 | **`lsp-pack`** | cross | lsp only | LSP configs for common languages: rust-analyzer, basedpyright/oxc, gopls, clangd, etc. Binaries are user-installed (per-plugin README + `/plugin` Errors tab guidance). | No SHA-pinned binaries — configs are JSON pointers. |
| 10 | **`agents`** | cross | agents only | Reusable sub-agent definitions: code-reviewer, security-reviewer, test-engineer, etc. Mostly first-party markdown + prompts. | External agent definitions go through D7. |
| 11 | **`output-styles`** | cross | output-styles only | Curated presets: terse, detailed, tabular, explanatory, etc. First-party markdown + prompts. Candidates from claudepluginhub.com/output-styles only if vetted. | No hooks/MCP/LSP — style presets only. |

**Overlap rule recap (D5):** task plugins ship *only* task-specific components. Anything useful across ≥2 tasks lives in its pack. The `hooks` plugin owns *all* hooks.

---

## 9. Repo layout

```
heretek-claude-harness/
├── .claude-plugin/
│   └── marketplace.json          # generated from catalog.yaml — DO NOT hand-edit
├── plugins/                      # first-party plugins (relative sources, pluginRoot "./plugins")
│   ├── rust/
│   ├── python/
│   ├── js-ts/
│   ├── web-frontend/
│   ├── hooks/                    # flagship: quality gates + git hooks
│   ├── security/
│   ├── skills-pack/
│   ├── mcp-pack/
│   ├── lsp-pack/
│   ├── agents/
│   └── output-styles/
├── catalog/
│   ├── catalog.yaml              # source of truth
│   ├── reviews/                  # ADR per item
│   └── rejected.md               # items that failed vetting + why
├── scripts/
│   ├── generate-marketplace      # catalog.yaml → marketplace.json
│   ├── validate                  # JSON Schema check
│   ├── new-plugin                # scaffold a plugin from template
│   ├── new-item                  # curation workflow
│   └── refresh-pins              # quarterly: check external SHA pins + vetting freshness
├── docs/
│   ├── curation-policy.md        # written vetting bar (D7) + pipeline how-to
│   ├── recommended-marketplaces.md
│   ├── CONTRIBUTING.md
│   ├── SECURITY.md
│   └── superpowers/
│       └── specs/                # this spec lives here
├── .github/workflows/
│   ├── validate.yml
│   └── smoke-test.yml
├── LICENSE                       # MIT (D14)
├── .gitignore
└── README.md                     # one-command install
```

---

## 10. Phases → sub-project mapping

| Phase | Deliverable | Sub-project | Exit criteria |
|---|---|---|---|
| 0 — Bootstrap | Repo hygiene, first public-safe commit | **SP1 Foundation** | Clean public-safe tree; LICENSE=MIT committed; `ref.text` deleted; personal dirs removed; `.gitignore` covers them; secret-scan clean |
| 1 — Scaffold | `marketplace.json` generator, 11 plugin skeletons, CI `validate.yml` | **SP1 Foundation** | `scripts/validate` passes; marketplace installs with zero plugins failing; `catalog.yaml` → `marketplace.json` diff = 0 |
| 2 — Flagship | `hooks` plugin fully built | **SP2 Hooks flagship** | Smoke test: Layer 1 fast gate blocks bad file; `/quality-gate:run` runs full suite; `/hooks:install-git-hooks` installs pre-commit framework |
| 3 — Task plugins | rust + python curated end-to-end | **SP3 First-party plugins** | 2 task plugins pass smoke test; ADRs written; catalog entries vetted |
| 4 — Packs | skills-pack, mcp-pack, lsp-pack, security, agents, output-styles, js-ts, web-frontend | **SP3 First-party plugins** | All 11 plugins green in smoke test |
| 5 — Aggregation | Curated 3rd-party entries; `recommended-marketplaces.md`; community tags | **SP4 Aggregation + Launch** | Full aggregation live; `scripts/refresh-pins` working; SHA pins in place |
| 6 — Public | README, CONTRIBUTING.md, SECURITY.md, Heretek-AI org + repo transfer | **SP4 Aggregation + Launch** | A stranger can `/plugin install rust@heretek` from a clean machine |

---

## 11. Sub-project decomposition (4 sub-projects)

Each sub-project gets its own design spec + implementation plan (via writing-plans). This top-level spec is the parent.

### SP1 — Foundation (Phases 0 + 1)

**Scope:** finish Phase 0 cleanup. Build Phase 1 scaffold.
- Delete `.agents/`, `.omc/`, `.serena/`, `ref.text`, `.harness/` from repo (live global installs untouched per D9)
- Add `LICENSE` (MIT, D14)
- Scrub `.gitignore`; secret-scan; scrub history if anything leaked
- Define `catalog.yaml` schema (this spec §5); verify against current Claude Code marketplace schema
- Build `scripts/generate-marketplace` (catalog.yaml → marketplace.json)
- Build `scripts/validate` (JSON Schema check on all manifests)
- Build `scripts/new-plugin` (scaffold a plugin from template)
- Scaffold all 11 plugin directories with minimal `plugin.json` + READMEs
- Add CI `validate.yml`

**Exit:** marketplace installs with zero plugins failing; `catalog.yaml` → `marketplace.json` diff = 0; CI `validate` green on a clean tree.

**Why first:** every later sub-project depends on the catalog schema and generator. A wrong schema is the most expensive rework in the project.

### SP2 — Hooks flagship (Phase 2)

**Scope:** full hooks plugin; three-layer architecture; conflict policy; aitmpl.com hooks vetted and landed.
- Layer 1 fast gates: ruff (python), rustfmt (rust), biome (js-ts). PreToolUse on Edit/Write/MultiEdit, hard 100ms timeout, fail-open with warning
- Layer 2 `/quality-gate:run`: clippy, megalinter, tdd-guard, jscpd, sonarqube (when configured). Optional non-blocking PostToolUse Notification hooks
- Layer 3 pre-commit framework: YAML config + `/hooks:install-git-hooks` installer command
- Strict conflict policy (D15) implemented; documented in plugin README
- Vet the 6 aitmpl.com hooks against D7; any that pass land in `plugins/hooks/hooks/hooks.json` with ADR

**Exit:** smoke test green; Layer 1 fast gate blocks a staged bad file; Layer 3 git hooks install and run; Layer 2 on-demand command works.

**Why separate:** largest single deliverable; the differentiator; ships alone once the foundation is in place.

### SP3 — First-party plugins (Phases 3 + 4)

**Scope:** task plugins + packs.
- **Phase 3 first:** rust, python curated end-to-end via the curation pipeline. ADRs per item, catalog entries vetted.
- **Phase 4:** js-ts, web-frontend (rest of task plugins); skills-pack, mcp-pack, lsp-pack, security, agents, output-styles (packs).
- Every `items` entry has an ADR in `catalog/reviews/`.

**Exit:** all 11 plugins green in smoke test; full catalog vetted.

**Why combined:** Phases 3 and 4 share the catalog-pipeline + smoke-test infrastructure from SP1; they're parallel tracks, not sequential.

### SP4 — Aggregation + Launch (Phases 5 + 6)

**Scope:** curated 3rd-party aggregation + public launch.
- **Phase 5:** curated 3rd-party entries (SHA-pinned, vetted, ADRs); `docs/recommended-marketplaces.md`; community-tagged section in marketplace.json; `scripts/refresh-pins` for quarterly SHA + vetting refresh
- **Phase 6:** README (one-command install); CONTRIBUTING.md; SECURITY.md (including supply-chain reporting path); Heretek-AI org creation + repo transfer (D17); CI auth token for smoke test (open item §14.4 from PLAN.md); repo rename if decided

**Exit:** a stranger can `/plugin install rust@heretek` from a clean machine; aggregation live; quarterly refresh scripted; org + repo public; SECURITY.md reporting path established.

**Why combined:** aggregation and launch are tightly coupled — third-party entries need public docs (README, SECURITY) to be useful; launch is meaningless without aggregation live.

---

## 12. Risks

| # | Risk | Mitigation |
|---|---|---|
| 1 | Pin treadmill — 40+ external SHA pins to re-verify quarterly | Scripted refresh (`scripts/refresh-pins`); low bar for demoting stale items to `rejected.md` |
| 2 | SHA-ride update surprise — every marketplace commit = new version (D11) | Discipline on main-branch pushes; revisit with explicit versions + `renames` only if users complain (D16) |
| 3 | Hook conflicts — multiple hooks plugins colliding on same events | `hooks` plugin is sole owner of all hooks (D15); strict mode; documented ordering |
| 4 | LSP binary dependency — `.lsp.json` configs need binaries the user installs | Per-plugin README + `/plugin` Errors tab guidance |
| 5 | Supply-chain compromise — vetted external repo turns malicious between refreshes | SHA pins make drift impossible; quarterly re-audit; SECURITY.md reporting path |
| 6 | Public = permanent — anything shipped is endorsable forever | `rejected.md` + `renames` + careful PR review |
| 7 | Heretek-AI org doesn't exist yet (D17) — public launch blocked until org + repo transfer | Tracked in SP4 exit criteria; one-time pre-launch task |
| 8 | CI auth token for smoke test (open item PLAN.md §14.4) | Tracked in SP4 exit criteria; token scoped, isolated runner only |
| 9 | Scope creep across 4 sub-projects | YAGNI in every sub-project spec; deferred items go to v2 backlog |
| 10 | Marketplace schema drift — Claude Code docs change after SP1 locks the schema | Re-validate against current docs in SP4 (Phase 6 pre-launch); treat schema as authoritative |

---

## 13. v2 backlog (explicitly out of v1)

- Workflow plugins, monitors, templates pack, marketplace-branded agent suite
- Explicit-version + `renames` migration (only if D11 SHA-ride becomes a problem)
- Deferred 3rd-party candidates (only if they pass D7): agent-skills, wondelai/skills, Citadel, headroom, taste-skill, claude-mem, ponytail, cli-anything, mksglu/context-mode
- More task plugins (go, c/cpp, ruby, etc.)
- Plugin-composition tooling (combine hooks + mcp + skills without re-bundling)

---

## 14. Open items (resolved this session)

| # | Item | Resolution |
|---|---|---|
| 1 | License | D14: MIT for own code; vendored components retain upstream license + NOTICE |
| 2 | Hooks overlap (D5/D15) | Strict: all hooks in `hooks` plugin, including security-scoped |
| 3 | Versioning (D11) | Re-confirmed: SHA-ride |
| 4 | Marketplace schema details | Verified plan shape; full Schema verification deferred to SP1 (Foundation) against current Claude Code docs |
| 5 | Aitmpl.com hooks | Vetting per D7; if any pass, all land in `hooks` plugin |
| 6 | Sub-project decomposition | 4 sub-projects (Foundation, Hooks flagship, First-party plugins, Aggregation+Launch) |
| 7 | Spec organization | Hybrid: vision/decisions/arch + cross-cutting foundations + 11 plugin cards + phases/sub-projects/risks |

---

## 15. References

- `PLAN.md` — original repo plan (this spec is the refined, locked v1 design)
- `ref.text` — initial candidate pool (absorbed into `catalog/reviews/*` ADRs by SP3/SP4; deleted from repo in SP1)
- <https://code.claude.com/docs/en/plugin-marketplaces> — Claude Code plugin marketplace format (schema reference; verify in SP1)
- <https://code.claude.com/docs/en/plugins> — Claude Code plugins format (per-plugin manifest reference)
- D7 vetting sources: GitHub MCP (stars, last commit, license, CVEs), Firecrawl (README/agg scrape), deep-research skill (qualitative review)
