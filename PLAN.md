# HereTek Marketplace — Repo Plan

> Opinionated Claude Code plugin marketplace, living in the heretek-claude-harness repo.
> Public OSS from day one. Marketplace name: `heretek`. Owner: `Heretek-AI`.

---

## 1. Vision

A single-command way to turn any Claude Code install into a working, opinionated harness:

- **Task plugins** (rust, python, js-ts, web-frontend) — bundle the best *skills + MCP servers + LSP servers* curated for that language.
- **Cross-cutting plugins** (hooks, security, skills-pack, mcp-pack, lsp-pack, agents, output-styles) — generic capability packs shared across tasks.
- **3rd-party aggregation** — the marketplace directly references top external plugins (SHA-pinned, vetted) plus a docs page for recommended external marketplaces.
- **Curation pipeline** — GitHub MCP + Firecrawl + deep-research produce an auditable decision record for every item in the catalog.

Differentiator: the **hooks plugin** — layered quality gates (fast lint blocks the agent loop, slow analyzers run on demand) wired into both the Claude Code hook system and git (pre-commit/pre-push).

## 2. Locked Decisions (from grilling)

| # | Decision | Choice | Rationale / consequence |
|---|----------|--------|--------------------------|
| D1 | Repo model | Monorepo + external sources | Own plugins as `plugins/*` subdirs (relative sources); 3rd-party via `github`/`git-subdir` sources with SHA pins |
| D2 | Repo home | This harness repo (`heretek-claude-harness`) | Marketplace and harness evolve together; repo becomes public |
| D3 | Launch scope | Category-complete, candidate-curated | Every category ships ≥1 flagship plugin; only items passing the vetting bar are included; rejects → `catalog/rejected.md` |
| D4 | Audience | Public OSS day one | Needs CONTRIBUTING, SECURITY.md, written vetting bar |
| D5 | Taxonomy | Task + cross-cutting packs (all 11) | Task: rust, python, js-ts, web-frontend. Cross: hooks, security, skills-pack, mcp-pack, lsp-pack, agents, output-styles. Overlap rule: task plugins bundle only task-specific items; generic items live in packs |
| D6 | Hooks architecture | Fast-block, slow-command, pre-commit | Fast gates block PreToolUse (<100ms); slow analyzers via `/quality-gate:run`; git hooks via pre-commit framework |
| D7 | Security | SHA-pin + written vetting bar | stars ≥500, last commit ≤12mo, OSI license, source-audit of code-executing components, no critical CVEs in 24mo; quarterly refresh |
| D8 | Pipeline contract | catalog.yaml drives generation | catalog.yaml = source of truth; CI generates `marketplace.json` and validates diff empty |
| D9 | Repo hygiene | Clean sweep, repo = marketplace | Personal harness copies deleted from repo; **live global installs (~/.agents/skills, ~/.config/opencode/skills) unaffected** — delete-on-repo only |
| D10 | 3rd-party aggregation | Full aggregation | Curated external entries in-marketplace + community-tagged section + `docs/recommended-marketplaces.md` |
| D11 | Versioning | SHA-ride (no explicit versions) | Own plugins: every commit = new version. Consequence: users get updates on every `/plugin marketplace update`. Revisit if churn becomes noise |
| D12 | CI bar | Schema + generation + smoke test | JSON Schema validation of all manifests, catalog→marketplace diff check, live install smoke test with `claude` CLI |
| D13 | Identity | Marketplace name `heretek`, owner `Heretek-AI` | Public-facing: `/plugin install rust@heretek` |

## 3. Repo Layout

```
heretek-claude-harness/
├── .claude-plugin/
│   └── marketplace.json          # generated from catalog.yaml — DO NOT hand-edit
├── plugins/                      # first-party plugins (relative sources, pluginRoot "./plugins")
│   ├── rust/
│   │   ├── .claude-plugin/plugin.json
│   │   ├── skills/               # rust-specific skills
│   │   ├── .mcp.json             # task-specific MCP servers
│   │   ├── .lsp.json             # rust-analyzer etc.
│   │   └── README.md
│   ├── python/
│   ├── js-ts/
│   ├── web-frontend/
│   ├── hooks/                    # flagship: quality gates + git hooks
│   │   ├── .claude-plugin/plugin.json
│   │   ├── hooks/hooks.json      # PreToolUse fast gates + Notification hooks
│   │   ├── commands/quality-gate.md
│   │   ├── git-hooks/            # pre-commit framework config (YAML) + installer command
│   │   └── README.md
│   ├── security/
│   ├── skills-pack/
│   ├── mcp-pack/
│   ├── lsp-pack/
│   ├── agents/
│   └── output-styles/
├── catalog/
│   ├── catalog.yaml              # source of truth — every item, every plugin
│   ├── reviews/                  # ADR-style review per item: <slug>.md
│   │   └── 0000-template.md
│   └── rejected.md               # items that failed vetting + why
├── scripts/
│   ├── generate-marketplace      # catalog.yaml → .claude-plugin/marketplace.json
│   ├── validate                  # JSON Schema check of all manifests
│   ├── new-plugin                # scaffold a plugin from template
│   ├── new-item                  # start the curation workflow for a candidate
│   └── refresh-pins              # quarterly: check external SHA pins + vetting freshness
├── docs/
│   ├── curation-policy.md        # the written vetting bar (D7) + pipeline how-to
│   ├── recommended-marketplaces.md  # external marketplaces to add manually
│   ├── CONTRIBUTING.md
│   └── SECURITY.md
├── .github/workflows/
│   ├── validate.yml              # schema + generation diff
│   └── smoke-test.yml            # live install test with claude CLI
├── .gitignore                    # excludes .harness/, local state, secrets
└── README.md                     # marketplace identity + one-command install
```

## 4. Marketplace Manifest

`.claude-plugin/marketplace.json` (generated):

```jsonc
{
  "name": "heretek",
  "description": "Opinionated Claude Code harness: task plugins, quality-gate hooks, curated MCP/LSP/skills.",
  "owner": { "name": "Heretek-AI", "url": "https://github.com/Heretek-AI" },
  "metadata": { "pluginRoot": "./plugins" },
  "allowCrossMarketplaceDependenciesOn": ["claude-plugins-official"],
  "plugins": [
    // first-party, relative sources:
    { "name": "rust", "source": "rust", "category": "task", "tags": ["rust", "language"] },
    // ... python, js-ts, web-frontend, hooks, security, skills-pack, mcp-pack, lsp-pack, agents, output-styles
    // curated 3rd-party, SHA-pinned (full aggregation, D10):
    { "name": "superpowers", "source": { "type": "git-subdir", "url": "obra/superpowers", "path": "superpowers", "sha": "<full-40-char>" }, "category": "community", "tags": ["3rd-party"] }
    // ...
  ]
}
```

Notes:
- Relative sources use `pluginRoot`, so `"source": "rust"` → `plugins/rust`. No `../` paths.
- External entries (community/3rd-party) always carry a **full 40-char `sha`**, never a bare `ref`. `sha` is the effective pin when both are set.
- `git-subdir` sparse-clones external monorepos (e.g. `anthropics/claude-code` plugins dir) — only fetch the plugin subdir.

## 5. Plugin Catalog (v1 — all 11)

| Plugin | Category | Bundles | Flagship content (first cut) |
|--------|----------|---------|------------------------------|
| `rust` | task | skills + mcp + lsp | rust-analyzer (lsp), cargo-check skill, task-scoped skills |
| `python` | task | skills + mcp + lsp | basedpyright/pyright (lsp), ruff-driven skill, task-scoped MCP |
| `js-ts` | task | skills + mcp + lsp | biome/oxc tooling (lsp+skill), tsconfig-aware skills |
| `web-frontend` | task | skills + mcp + lsp | lighthouse skill, chrome-devtools-mcp (external, vetted), design-review skills |
| `hooks` | cross (flagship) | hooks + commands + git-hooks | See §6 |
| `security` | cross | skills + hooks + commands | security-research/skills, audit commands |
| `skills-pack` | cross | skills only | the harness's curated general skills (caveman suite, find-skills, review-work) re-packaged |
| `mcp-pack` | cross | mcp only | context7, github-mcp-server, codebase-memory-mcp, serena (all external, SHA-pinned, vetted) |
| `lsp-pack` | cross | lsp only | LSP configs for common languages (binaries must be user-installed — stated in README) |
| `agents` | cross | agents only | reusable sub-agent definitions |
| `output-styles` | cross | output styles | curated output-style presets |

**Overlap rule (D5):** task plugins ship *only* task-specific components. Any component useful across ≥2 tasks lives in its pack. The hooks plugin owns *all* quality-gate hooks; no other plugin ships hooks that fire on Edit/Write.

**Backlog (v2):** workflow plugins, monitors, templates pack, marketplace-branded agent suite.

## 6. Hooks Plugin Architecture (the differentiator)

Three layers, both hook worlds:

**Layer 1 — Fast gates (blocking, sub-100ms).** `PreToolUse` on `Edit`/`Write`/`MultiEdit`. Lint only staged/new content:
- python → `ruff` (targeted)
- rust → `rustfmt --check` (targeted; `cargo-clippy` is too slow to block — demoted to Layer 2)
- js-ts → `biome` (targeted)

**Layer 2 — Slow analyzers (on-demand + optional notify).**
- `/quality-gate:run` command: full suite — clippy, megalinter, tdd-guard, jscpd, sonarqube (scanner if configured).
- Optional `PostToolUse` **Notification** hooks (non-blocking) that surface analyzer output without stalling the agent loop.

**Layer 3 — Git hooks.** Ships a pre-commit framework config (`pre-commit` YAML) + an installer command (`/hooks:install-git-hooks`) that runs `pre-commit install` for pre-commit/pre-push. Independent of Claude Code's hook system.

**Conflict policy:** hooks plugin is the single owner of quality-gate hooks. If a user enables another hooks plugin, ordering/override is resolved at the manifest level (strict mode, `plugin.json` as authority). Documented in the plugin README.

## 7. Curation Pipeline

New-item workflow (scripted as `scripts/new-item`, executed by maintainer or delegated to the research stack):

```
1. Discover   — Firecrawl: scrape candidate repo/README/agg list (ref.text, awesome-lists, topics)
2. Verify     — GitHub MCP: stars, last commit, license, open issues, CVE scan
3. Review     — deep-research skill: tool quality, alternatives, opinionated verdict
4. Record     — write catalog/reviews/<slug>.md (ADR) — template: what / why / alternatives / verdict / target plugin
5. Catalog    — add entry to catalog.yaml (or rejected.md if it fails the bar)
6. Generate   — scripts/generate-marketplace → marketplace.json
7. Gate       — CI: schema validate + generation diff + smoke test
```

**catalog.yaml entry contract (D8):**

```yaml
plugins:
  - name: rust
    category: task
    tags: [rust, language]
    source: { type: relative, path: rust }
    components: [skills, mcp, lsp]
    items:                      # curated inside the plugin
      - id: rust-analyzer
        kind: lsp
        upstream: rust-lang/rust-analyzer
        sha: <40-char>
        license: MIT
        vetting: { status: approved, date: 2026-08-03, stars: 10000, review: catalog/reviews/rust-analyzer.md }
```

Every `items` entry carries vetting status + review link. Nothing ships unvetted.

## 8. Vetting Policy (written bar — D7)

A candidate is included **only if**:
- stars ≥ **500**
- last commit ≤ **12 months**
- OSI-approved license (MIT/Apache-2.0/BSD) — explicitly checked
- **source-audit pass** for any code-executing component (hooks, `bin/`, MCP servers, pre-commit hooks) — human review recorded in the ADR
- no **critical** CVEs in last 24 months (GitHub advisory check via GitHub MCP)

**Refresh loop (quarterly):** `scripts/refresh-pins` enumerates all external SHA pins + vetting dates, flags stale ones via GitHub MCP; maintainer either bumps the SHA (re-vetting the delta) or moves the item to `rejected.md` with reason. Standing chore with an owner (maintainer). A `renames` entry in marketplace.json handles removals gracefully.

## 9. Versioning & Distribution

- **Own plugins:** no explicit `version` (D11) — version = marketplace repo commit SHA. Every push propagates on `/plugin marketplace update`. Consequence: changes ship fast, no stable channels. Revisit with explicit versions + `renames` if update churn annoys users.
- **External plugins:** SHA-pinned (D7). No auto-update — updates only when the maintainer bumps the pin during quarterly refresh.
- **Marketplace itself:** `metadata.version` bumped per release; `renames` map maintained for renames/removals.

## 10. CI / CD

`.github/workflows/validate.yml` (on PR + push to main):
1. `scripts/validate` — JSON Schema check: `marketplace.json` + every `plugin.json` (+ `hooks.json`, `.mcp.json`, `.lsp.json` shape).
2. `scripts/generate-marketplace` → assert `git diff --exit-code` (catalog.yaml and marketplace.json never drift).
3. Vetting lint: catalog entries without `vetting.status: approved` + review link fail CI.

`.github/workflows/smoke-test.yml` (on merge, and nightly):
1. Fresh temp dir, `claude plugin marketplace add heretek <repo-url>`.
2. Install all 11 plugins; assert skills/hooks/mcp/lsp components present.
3. Trigger one fast-gate hook on a staged bad file; assert non-zero exit.
4. Requires `claude` CLI + auth token in CI secrets (design note: token scoped, `--dangerously-skip-permissions` only in isolated runner).

## 11. Repo Hygiene / Migration (D9)

- `.gitignore` gains: `.harness/`, `*.local.*`, any remaining personal state, symlinked `.codegraph` if not intended public.
- **Delete from repo:** `.agents/` skill copies, `.omc/`, `.serena/` state, `ref.text` (absorbed into `catalog/`), `skills-lock.json` (absorbed into catalog.yaml), this session's config artifacts.
- **Live global installs are untouched** (`~/.agents/skills`, `~/.config/opencode/skills`) — the harness keeps working locally; the repo just stops duplicating it.
- Re-packaged as plugins: general skills that *do* ship → `skills-pack` (caveman suite, find-skills, review-work, etc.).
- **Before going public:** run a secret scan (`gh secret scan` / `github-run_secret_scanning`) over the tree; scrub history if anything leaked.

## 12. Phases

| Phase | Deliverable | Exit criteria |
|-------|-------------|---------------|
| 0 — Bootstrap | Repo hygiene: .gitignore, secret scan, delete non-shipping files, first commit | Clean public-safe tree |
| 1 — Scaffold | `.claude-plugin/marketplace.json` (generator), 11 plugin skeletons via `new-plugin`, CI validate.yml | `validate` passes, marketplace installs with zero plugins failing |
| 2 — Flagship | `hooks` plugin fully built (fast gates + `/quality-gate:run` + pre-commit + tests) | Smoke test: fast gate blocks, git hooks install |
| 3 — Task plugins | rust + python curated end-to-end via pipeline (ADRs, catalog entries) | 2 task plugins pass smoke test |
| 4 — Packs | skills-pack, mcp-pack, lsp-pack, security, agents, output-styles | All 11 plugins green in smoke test |
| 5 — Aggregation | Curated 3rd-party entries (SHA-pinned, vetted) + `recommended-marketplaces.md` + community tags | Full aggregation live, quarterly refresh scripted |
| 6 — Public | README (one-command install), CONTRIBUTING, SECURITY.md, repo rename to public-facing name | `/plugin install rust@heretek` works for a stranger |

## 13. Risks

1. **Pin treadmill** — 40+ external SHA pins to re-verify quarterly. Mitigated: scripted refresh, low bar for demoting stale items to rejected.md.
2. **SHA-ride update surprise** — every marketplace commit is a new version for all own plugins. Mitigated: discipline on main-branch pushes; revisit with explicit versions if users complain.
3. **Hook conflicts** — multiple hooks plugins colliding on the same events. Mitigated: hooks plugin is sole owner; strict mode; documented ordering.
4. **LSP binary dependency** — `.lsp.json` configs need binaries the user must install. Mitigated: per-plugin README install instructions + `/plugin` Errors tab guidance.
5. **Supply-chain compromise** — a vetted external repo turns malicious between refreshes. Mitigated: SHA pins make drift impossible; quarterly re-audit; SECURITY.md reporting path.
6. **Public = permanent** — anything shipped is endorsable forever. Mitigated: rejected.md + renames + careful PR review.

## 14. Open Items

1. ~~Confirm the D9 reading: global skill installs are the live ones; repo deletion is safe.~~ ✅ **CONFIRMED** — repo copies are duplicates; live global installs at `~/.agents/skills` and `~/.config/opencode/skills` are unaffected by repo deletion.
2. ~~Repo rename: `heretek-claude-harness` → `heretek-marketplace` (or keep name, marketplace stays `heretek`).~~ ✅ **RESOLVED** — keep repo name `heretek-claude-harness`; marketplace name stays `heretek` (repo name ≠ marketplace name).
3. First commit — repo currently has no commits; Phase 0 creates history from a clean base. (pending)
4. ~~`claude` CLI availability + CI auth token for the smoke test.~~ ✅ **RESOLVED** — `claude` CLI installed. CI auth token still needed when smoke-test workflow is built (Phase 6).
5. ~~Script language for `scripts/`~~ ✅ **RESOLVED** — Python 3 + PyYAML (single dep; stdlib handles JSON/glob/subprocess; no node_modules in a marketplace repo).
