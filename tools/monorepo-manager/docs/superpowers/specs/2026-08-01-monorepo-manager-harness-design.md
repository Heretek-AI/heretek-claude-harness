# monorepo-manager harness — design spec

**Date:** 2026-08-01
**Owner:** Heretek-AI
**Status:** Draft for review
**Plan:** `docs/superpowers/plans/2026-08-01-monorepo-manager-harness-impl.md`
**Related docs:** `Llama Ecosystem Repository Analysis.md`, `Write out a design doc for the project.md`

## 1. Purpose

`monorepo-manager` (remote: `Heretek-AI/monorepo-manager`) is the throwaway
workspace used to design, validate, and ship a contract-driven Heretek harness
that will be installed into standalone child repos. The two child repos
initialised against this spec are:

- **`Heretek-AI/llama-builds`** — CI/CD registry for llama.cpp-family builds
  (Python + YAML + shell, Linux x86_64).
- **`Heretek-AI/heretek-manager`** — local NPM CLI + WebUI runtime
  (Node.js + TypeScript, Linux x86_64).

The harness gives AI coding agents (Claude/Copilot/etc.) enough context and
tooling to work productively in either repo, and gives humans enough guardrails
that bad code rarely lands. The harness is described as four contract layers
so each child can adapt the contents to its stack without re-deriving the
shape.

This spec is the engineering source of truth for the umbrella. Per-child
products (the `llama-builds` registry design and the `heretek-manager` design
documented in `Write out a design doc for the project.md`) are separate specs.

## 2. Goals and non-goals

**Goals.**
- Make a working v1 of both child repos possible in one wave, with four fully
  wired layers per child.
- Keep the harness contract-driven (one spec, many backends per layer) so
  future children can adopt the harness without rewriting it.
- Replace ad-hoc local docs as a daily tracking surface with GitHub Issues
  + Projects v2 per child.

**Non-goals.**
- Application-level design for `llama-builds` or `heretek-manager` (covered in
  separate specs).
- ARM/macOS/Windows first-class support. Linux x86_64 only for v1.
- Containerization, release engineering, multi-org GitHub setup.
- Secrets management beyond what GitHub Actions needs.

## 3. Architecture overview

```
monorepo-manager/                        # THIS workspace (throwaway)
├── docs/superpowers/specs/
│   └── 2026-08-01-monorepo-manager-harness-design.md   # this file
├── reference/                          # reference impls (source of truth for shape)
│   ├── harness/                        # AGENTS.md, CLAUDE.md, skills, MCP, settings, hooks
│   ├── ci/                             # super-linter, pre-commit, sonarcloud, gitleaks
│   ├── tracking/                       # issue/PR templates, labels, project automation
│   ├── llama-builds-install/           # end-to-end installable copy for child A
│   └── heretek-manager-install/        # end-to-end installable copy for child B
├── scripts/
│   └── init-harness.sh                 # materialize harness into a child repo
├── README.md
└── .git/

Heretek-AI/llama-builds                 # child A (standalone repo)
Heretek-AI/heretek-manager              # child B (standalone repo)
```

**Boundary rules.**
- A child repo never references files outside its own tree. It owns its own
  `AGENTS.md`, CI workflows, Sonar project, GitHub Project.
- `monorepo-manager`’s `reference/` tree is **not** referenced from the
  children at runtime — content is copy-pasted once and edited in place.
- The spec doc is the only durable artifact; everything else in
  `monorepo-manager` is deletable once children ship v1.
- No submodules, no monorepo manager, no workspaces — children are plain
  standalone repos.

## 4. Layer 1 — Harness contract

### 4.1 Files a child must own

```
AGENTS.md
CLAUDE.md
.claude/
  skills/<skill-name>/
    SKILL.md
    [optional] scripts/
    [optional] references/
    [optional] assets/
  settings.json
  hooks/
    PreToolUse/*.sh
    PostToolUse/*.sh
    UserPromptSubmit/*.sh
    Stop/*.sh
.mcp.json
```

The harness contract states *what each file must contain and which interface
points it touches*, not literal contents — those are reference impls under
`reference/harness/`.

### 4.2 AGENTS.md / CLAUDE.md contract

A child’s `AGENTS.md` MUST contain these top-level sections in this order, each
with at least one line:

1. **Project summary** — one paragraph.
2. **Stack & runtime targets** — languages, package managers, supported
   OS/arch matrix, deployable binary outputs.
3. **Build, test, lint, run commands** — exact commands a fresh agent runs.
4. **Project structure** — top-level tree with one-line annotations.
5. **Conventions** — code style, naming, commit message format, branch/PR
   conventions.
6. **Do / Don’t list** — non-obvious constraints (e.g. `ttm.pages_limit`
   checks are Linux-only; symlink swaps must use the atomic temp-link +
   rename pattern).
7. **Pointer block** — links to issue templates, the GitHub Project URL,
   the SonarCloud project key, super-linter config path, and the
   `.claude/skills/` index.

`CLAUDE.md` is short. It MUST reference `AGENTS.md` for substance and add
Claude-specific notes (which skills to use for which task, model tier
guidance, hook expectations).

### 4.3 `.claude/skills/` contract

Each skill is a folder `skills/<skill-name>/` with:

- `SKILL.md` — markdown body describing when to use the skill, the
  procedure, expected outputs. **Required frontmatter:**
  `name`, `description`, optional `allowed-tools`.
- Optional `scripts/`, `references/`, `assets/`.

**Required canon skills (every child ships):**

- `superpowers:brainstorming`
- `superpowers:writing-plans`
- `superpowers:executing-plans`
- `superpowers:test-driven-development`
- `superpowers:systematic-debugging`
- `superpowers:verification-before-completion`
- `superpowers:requesting-code-review`
- `superpowers:receiving-code-review`
- `superpowers:using-git-worktrees`
- `superpowers:finishing-a-development-branch`
- `superpowers:subagent-driven-development`
- `superpowers:dispatching-parallel-agents`

These are pinned to a specific `superpowers` release in the umbrella spec;
the reference impl hard-codes the version via `skills/manifest.json`.

**Required per-repo skills (examples; children may add others):**

- **`llama-builds`** — `heretek-manifest-codegen` (generate `manifest.json`
  from `targets/*/build.sh`), `heretek-upstream-sync` (test a new
  llama.cpp upstream SHA before promoting to a release).
- **`heretek-manager`** — `heretek-strix-halo-audit` (interpret
  `nvidia-smi` / `rocminfo` / `vulkaninfo` and recommend a backend),
  `heretek-symlink-swap` (apply atomic symlink swap recipe with safety
  checks), `heretek-manifest-fetch` (call the `llama-builds` manifest
  safely with retries).

A skill that depends on an MCP server MUST declare the dependency in its
`requiredSkills` array. If the server is unavailable, the skill fails
fast with a clear message instead of silently skipping.

### 4.4 `.mcp.json` contract

JSON file declaring MCP servers under a single `mcpServers` key. Each
entry:

```json
{
  "name": {
    "description": "One-sentence purpose.",
    "transport": "stdio",
    "command": "...",
    "args": ["..."],
    "env": { "ENV_VAR": null },
    "timeoutSeconds": 15,
    "retry": 0,
    "requiredSkills": ["skill-name"]
  }
}
```

**Validation rules (enforced by `scripts/init-harness.sh`):**

- `name` matches `^[a-z][a-z0-9-]{2,32}$`.
- `description` is non-empty, ≤ 200 chars.
- `transport` is `stdio` (with `command`+`args`) or `http` (with `url`,
  optional `headers`).
- `env` keys match `^[A-Z][A-Z0-9_]{2,32}$`; values are looked up from the
  process environment at startup. No plaintext secrets in `.mcp.json`.
- `timeoutSeconds` default is 15.
- `retry` default is 0 (fail loud).

**Required servers for every child:**

- **`github`** — official GitHub MCP, scoped to the child repo.

**Optional / per-child:**

- **`sonarqube`** — for direct SonarCloud queries from agents
  (`mcp__sonarqube__*` tools).
- **`codebase-memory-mcp`** — cross-session continuity via knowledge graph.
- **`heretek-registry`** (custom, `llama-builds` side) — read-only wrapper
  around the static `manifest.json` registered against
  `https://heretek-ai.github.io/llama-builds/`.
- **`heretek-audit`** (custom, `heretek-manager` side) — wraps
  `nvidia-smi` / `rocminfo` / `vulkaninfo` with a uniform
  `hardware_profile` schema and a `recommend` tool.

No skill ever calls an MCP server owned by a different child. Cross-child
coupling goes through published registry/HTTP, never MCP.

### 4.5 `.claude/settings.json` + hooks contract

`settings.json` declares permissions, model defaults, and hook bindings.
Required contents:

- **`permissions.allow`** — curated allowlist per repo (NEVER `*`). Covers
  the build/test/lint commands enumerated in `AGENTS.md`.
- **`permissions.deny`** — includes destructive shell patterns
  (`rm -rf`, `git push --force`, `git reset --hard` against protected
  branches).
- **Hook blocks** for `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, `Stop`.
  Each block references files in `.claude/hooks/` that MUST exist.
- **`model`** — per-task default (e.g. `opus` / `sonnet` / `haiku` tier). Set
  per child in `settings.json`; not declared in `.mcp.json`.

**Required hooks for every child:**

- **`PreToolUse` Bash hooks** — block the destructive patterns above by
  parsing the proposed command string.
- **`Stop` hook** — runs a lightweight verification step (lint-only by
  default) and rejects completion if it failed.

`.claude/hooks/.lockfile` stores a SHA-256 over every hook file. The
harness loader computes this hash at agent startup; a mismatch (a hook
file was edited outside the init script) refuses to load the agent
manifest and surfaces a clear remediation message: "hook files drift
detected; run `scripts/init-harness.sh --refresh-hooks`".

## 5. Layer 2 — Quality-gate contract

### 5.1 Required CI workflows

Each child ships four GitHub Actions workflows with exact filenames:

| Workflow file | Trigger | Required check name |
| --- | --- | --- |
| `.github/workflows/super-linter.yml` | `pull_request`, `push` to `main` | `super-linter` |
| `.github/workflows/pre-commit.yml` | `pull_request`, `push` to `main` | `pre-commit` |
| `.github/workflows/sonarcloud.yml` | `pull_request`, `push` to `main` | `sonarcloud` |
| `.github/workflows/secret-scan.yml` | `pull_request`, `push` to `main` | `gitleaks` |

All four are required status checks on the protected branch. The umbrella
spec documents the `gh api` incantation to set them.

### 5.2 Super-linter contract

Pinned to `github/super-linter/super-linter@v6` (or whatever version the
umbrella locks at spec time).

- `.github/linters/` contains language-specific configs:
  `eslintrc.yml`, `python-ruff.yml`, `shellcheck.yml`, `yamllint.yml`,
  `markdownlint.yml`, `prettierrc.yml`. (Add `sqlfluff.yml` if a child uses
  SQL.) Default super-linter flavor unless overridden.
- Workflow `env` declares linters to enable; minimum set:
  `VALIDATE_PYTHON`, `VALIDATE_YAML`, `VALIDATE_JSON`, `VALIDATE_SHELL`,
  `VALIDATE_MARKDOWN`, `VALIDATE_JAVASCRIPT`, `VALIDATE_TYPESCRIPT`,
  `VALIDATE_GITHUB_ACTIONS`. Per-child enablement lives in the env block,
  not the configs.
- `DISABLE_ERRORS=false`. Super-linter failures fail the workflow.
- `DEFAULT_BRANCH=main` and `GITHUB_TOKEN` are wired.

### 5.3 Pre-commit contract

Top-level `.pre-commit-config.yaml` with revs pinned (no `latest`).
Required hooks (chosen from pre-commit.com/hooks.html):

- **Pre-commit/pre-commit-hooks** pinned at `v5.0.0` (or the latest 5.x
  tag at spec time) — `trailing-whitespace`,
  `end-of-file-fixer`, `check-yaml`, `check-json`,
  `check-added-large-files` (with `max-size: 500KiB`),
  `check-merge-conflict`, `check-case-conflict`, `detect-private-key`.
- **astral-sh/ruff-pre-commit** — `ruff` + `ruff-format` (replaces
  black/flake8/isort where applicable).
- **adrienverge/yamllint**, **shellcheck-py**, **prettier**, **eslint**
  shims as applicable per child.
- **gitleaks/gitleaks** with `types: [file]` (cheap local layer; the
  GitHub workflow is the authoritative one).
- **commitlint** if conventional commits are used (`llama-builds` yes;
  `heretek-manager` tbd per child spec).

`PostToolUse` hook on `Edit`/`Write` runs `pre-commit run --files
<changed>` against the diff. Failures annotate the tool result and
hard-fail the agent step.

### 5.4 SonarCloud contract

`sonar-project.properties` at repo root with required keys:

```properties
sonar.projectKey=Heretek-AI_<repo-name>
sonar.organization=heretek-ai
sonar.projectName=<repo-name>
sonar.sources=src
sonar.tests=tests
sonar.javascript.lcov.reportPaths=coverage/lcov.info
sonar.python.coverage.reportPaths=coverage.xml
sonar.sourceEncoding=UTF-8
```

Workflow uses `SonarSource/sonarqube-scan-action@v2` and
`SonarSource/sonarqube-quality-gate-action@v1`. Secrets:

- `SONAR_TOKEN` (repo-level).
- `SONAR_HOST_URL=https://sonarcloud.io` (default; overridable).

**Quality gate defaults** (overridable per child):

- New code coverage ≥ 80%.
- New code duplication < 3%.
- No new reliability issues ≥ blocker.
- No new security hotspots ≥ high.

Branch analysis on PRs is enabled via `sonar.pullrequest.branch` and
`sonar.pullrequest.key` action inputs.

### 5.5 Secret-scan contract

`gitleaks/gitleaks-action@v2` with:

- `CONFIG_PATH` defaults to `.github/gitleaks-config.yml` (minimal default
  ruleset committed to each child).
- `.gitleaks-baseline.json` committed at day one to silence historical
  findings until triaged.
- Real findings block the PR. False positives are tracked exceptions in
  the baseline with a justification comment.

### 5.6 Branch-protection contract

`main` branch protection on every child:

- Required status checks = the four above + per-child build/test checks.
- Required linear history.
- No force pushes.
- Dismiss stale approvals on push.
- Required conversation resolution.
- Restrict who can push (no direct push to `main` — PRs only).

## 6. Layer 3 — Tracking contract

### 6.1 Issue templates

Each child ships these under `.github/ISSUE_TEMPLATE/`:

| Template | Required fields |
| --- | --- |
| `bug.md` | repro steps, expected vs actual, environment (OS, hardware, llama.cpp backend, manifest version captured by `heretek-manifest-fetch` for `heretek-manager` issues; build SHA for `llama-builds` issues), logs |
| `feature.md` | problem statement, proposed solution, alternatives, files touched, backwards-compat impact |
| `security.md` | disclosure policy link, severity guess, repro, impact; auto-routes to `security` label |
| `refactor.md` | motivation, scope (files/modules), test plan, risk |
| `infra-tooling.md` | scope (skill, MCP server, lint gap), expected behavior, actual behavior; tagged `area/infra` |
| `spec.md` | long-form design proposal that wraps an external `docs/superpowers/specs/*.md` by URL |

Templates are `config.yml`-driven forms; the spec lists the required-field
set per template.

### 6.2 PR template

`.github/PULL_REQUEST_TEMPLATE.md` with required sections:

- Linked Issue ID (`Closes #` / `Issue:` prefix).
- Scope / approach.
- Screenshots or test output if relevant.
- Breaking-change note.
- Checklist: lint / sonar / pre-commit / tests / docs / skills added.

### 6.3 Label taxonomy

Two layers of labels, contract-defined so Projects v2 filters are stable:

- **Area:** `area/build`, `area/client`, `area/infra`, `area/docs`,
  `area/security`.
- **Type:** `type/bug`, `type/feature`, `type/refactor`, `type/spec`,
  `type/tooling`, `type/discussion`.
- **Status:** `status/needs-triage`, `status/in-progress`,
  `status/in-review`, `status/blocked`, `status/done`.
- **Priority:** `priority/p0`–`priority/p3`.
- **Severity** (security/bugs): `severity/low`, `severity/medium`,
  `severity/high`, `severity/critical`.
- **Special:** `security`, `good-first-issue`, `help-wanted`, `keep-open`.
- **Per-child room:** children can add child-specific labels provided they
  nest under the contract namespace (e.g. `area/build/backend`).

### 6.4 GitHub Projects v2 schema

Each child creates a single Project with:

| Field | Type | Options |
| --- | --- | --- |
| Title | text | (auto) |
| Status | single-select | Backlog, Triage, In Progress, In Review, Done, Won’t Fix |
| Priority | single-select | P0, P1, P2, P3 |
| Area | single-select | Build, Client, Infra, Docs, Security |
| Type | single-select | Bug, Feature, Refactor, Spec, Tooling, Discussion |
| Owner | assignee | (auto from issue assignees) |
| Iteration | iteration | optional, two-week cycles |
| Linked PRs | text | (auto from PR body regex `Issue: #\d+`) |
| Severity | single-select | Low, Medium, High, Critical |
| Effort | number | (story points) |

Population rules:

- **Status** auto-set by automation rules: opening a PR linked to an Issue
  moves it to `In Review`; merging the PR moves it to `Done`. Closing
  without merge routes to `Won’t Fix` only via maintainer comment + label.
- **Priority** is human-set.
- **Owner** is the issue assignee; if none, a maintainer must assign
  during triage.

### 6.5 Automation rules

Reference impls live in `reference/tracking/projects-automation.graphql`
per child. Required rules:

1. New Issue opened → `Status = Triage`.
2. `area/build` → `Area = Build`; `area/client` → `Client`;
   `area/infra` → `Infra`; `area/docs` → `Docs`; `area/security` →
   `Security`. (This is also the rule that satisfies "infer Area from
   labels.") Multiple area labels: prefer the most specific.
3. `priority/p0`–`p3` → set `Priority`.
4. PR referencing `Closes #\d+` or `Issue: #\d+` → linked issue
   `Status = In Review` if the PR targets `main`; else no change.
5. PR merged → linked issue `Status = Done`.
6. Issue closed without merge and `status/needs-triage` cleared → leave
   `Status` alone; trust the closer.

### 6.6 Spec/Issue binding

Each spec doc adds a footer block in its own file:

```markdown
## Tracking
- Spec tracking Issue: #<id> (<child-repo>)
- Roadmap project: https://github.com/orgs/<org>/projects/<n>
- Sonar project: https://sonarcloud.io/project/overview?id=...
```

The footer is read by a Project automation that pins it to the Project
item. Reference impl: `reference/tracking/spec-footer.md`.

### 6.7 Tracking policy (contributors)

Each child’s `CONTRIBUTING.md` has a `Tracking` section that says:

- Long-lived design debates, decision logs, and progress notes live as
  Issues/Project items — not as separate Markdown files.
- `docs/superpowers/specs/*.md` is the engineering source of truth only
  for *in-flight* designs (spec → plan → implementation). Once an
  implementation lands, the design lives in the issue/PR conversation and
  in the code.
- An exception list (release notes, ADRs needing cross-repo visibility) is
  explicitly small and recorded in the same Project.

## 7. Reference implementations

Reference impls in `monorepo-manager/reference/` are the canonical examples
for each layer. On the *first* init of a child repo, `init-harness.sh`
*generates* the reference impls from this spec. On subsequent inits,
`init-harness.sh` refuses to overwrite a reference impl that has drifted
from the contract (it computes a contract-hash from this spec section and
compares it against the hash baked into the reference impl header); the
operator must explicitly run `init-harness.sh --force` to regenerate.

- `reference/harness/llama-builds/` — full harness tree for child A.
- `reference/harness/heretek-manager/` — full harness tree for child B.
- `reference/ci/llama-builds/` — workflows + linter/pre-commit/Sonar/gitleaks
  configs for child A.
- `reference/ci/heretek-manager/` — same for child B.
- `reference/tracking/llama-builds/` — templates + label config + project
  automation for child A.
- `reference/tracking/heretek-manager/` — same for child B.
- `reference/llama-builds-install/` and `reference/heretek-manager-install/` —
  end-to-end installable copies show how a single `init-harness.sh` call
  materialises the harness into a fresh repo.

## 8. Workflow

Daily flow inside a child repo:

1. Read `AGENTS.md`. Note commands, conventions, don’ts, the pointer block.
2. Pick an Issue from the GitHub Project. Required gates before code:
   Status ≠ `Backlog`, Priority set, Owner set.
3. Non-trivial changes run `superpowers:brainstorming`. Output is a spec
   under `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` carrying the
   tracking Issue footer.
4. `superpowers:writing-plans` produces the implementation plan as a
   series of dependent tasks.
5. Implementation follows TDD (`superpowers:test-driven-development`); CI
   runs the four required checks plus per-child build/test checks.
6. The `Stop` hook runs a lint-only verification before allowing the agent
   to end its turn.
7. PR closes the issue and auto-moves the Project item to `Done`.

## 9. Error handling

- **Pre-commit hook failure on agent save.** `PostToolUse` hook runs
  `pre-commit run --files <changed>`; failures annotate the tool result
  and hard-fail.
- **Super-linter failure on PR.** Required check blocks merge; PR template
  checklist requires acknowledgement of the failure mode in the PR body.
- **SonarCloud quality gate fail.** Required check blocks merge. Coverage
  gap on new code, or any new blocker, blocks the PR.
- **Gitleaks real finding.** Block merge. False positives are tracked
  exceptions in the baseline with a justification comment.
- **MCP server outage during an agent run.** Servers declare
  `timeoutSeconds` (default 15) and `retry=0` (fail loud). Tools calling
  MCP must surface errors verbatim.
- **Skill misfire.** Skills that depend on MCP declare the dependency in
  `requiredSkills`; if the server is unavailable, the skill fails fast.
- **Hook bypass attempt.** Hook files have a `.lockfile` SHA-256 hash.
  Mismatch refuses to load the agent manifest.

## 10. Testing

- **Harness layer.** Unit tests for each skill’s procedure (shell harness
  parses the steps and asserts each step is invoked). Integration test
  boots Claude with the harness config and runs `npx claude -p` against a
  curated prompt set; asserts expected MCP calls happen.
- **CI workflows.** Each workflow is a reusable workflow (`workflow_call`);
  `reference/workflows/tests/` runs each against `act` (or a stub) and
  verifies required outputs and required-check names match the contract.
- **Sonar wiring.** Smoke test in `reference/sonar-smoke/` creates a tiny
  repo with intentional issues and confirms the gate fails on them.
- **Gitleaks.** Fixture with intentional secrets confirms the action
  blocks the PR.
- **Issue/Project automations.** `gh api` replay test loads each
  automation rule and dry-runs it against fixture events.
- **Per-child tests are out of scope for the umbrella.** Each child’s spec
  defines its own test strategy.

## 11. Rollout

Single-wave v1:

1. Spec committed at
   `monorepo-manager/docs/superpowers/specs/2026-08-01-monorepo-manager-harness-design.md`.
2. Reference impls built under `monorepo-manager/reference/{harness,ci,tracking}/`
   plus `reference/llama-builds-install/` and `reference/heretek-manager-install/`.
3. Tests pass under `monorepo-manager/reference/workflows/tests/`.
4. Init script at `monorepo-manager/scripts/init-harness.sh` materialises
   the harness into a child repo given a name + stack choice.
5. Child repos run init scripts during their own brainstorm-implementation
   cycles; subsequent child specs reference this umbrella spec.
6. Each child opts into GitHub Insights sharing for 60 days post-launch
   so PR throughput and required-check fail rate are observable.

## 12. Open questions (for follow-up specs)

- **WebUI framework.** Original `heretek-manager` design mentions
  React/Vue. Umbrella does not dictate; child spec chooses and notes the
  extra CI burden (browser matrix, accessibility, Storybook).
- **MCP server runtime.** Heretek custom MCPs are contract-level here.
  Implementations, packaging (`npx`-published vs bundled), and version
  pinning land in per-child specs.
- **Secrets strategy.** Are org-level secrets used for shared values like
  `SONAR_HOST_URL`? Defer to per-child implementation.
- **Spec archive.** When an implementation lands, where does the
  superseded spec live? Recommended: mirrored into
  `docs/superpowers/specs/archive/` inside each child repo, with a Project
  pointer.
- **Coverage thresholds.** 80% on new code is the default. Concrete
  numbers set per-child during child specs.

## 13. Risks

- **Spec coverage is broad; missing any one of the four layers leaves
  holes.** Mitigated by the init script + contract tests in
  `reference/workflows/tests/`.
- **Drift between reference impls and the contract.** Mitigated by the
  init script failing on mismatch.
- **External service outages** (super-linter, SonarCloud) can stall
  merges. Branch-protection allows maintainers to bypass with `admin`
  overrides; automation does not.

## 14. Tracking

- Spec tracking Issue: N/A (umbrella is throwaway; the spec is the engineering source of truth for the in-flight design).
- Roadmap project: N/A (umbrella has no project; tracking lives in each child repo per the GitHub Issues + Projects v2 contract in section 6).
- Sonar project: N/A (umbrella has no app code; the contract is satisfied per-child by the `render_configs` template from Task 13's render path).
