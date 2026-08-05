# heretek-claude-harness maintenance skills — Design Spec

> Date: 2026-08-05. Status: draft. Companion to the parent design spec `2026-08-03-heretek-marketplace-design.md` and the SP1–SP4 implementation plans.

## 1. Summary

This spec defines three Claude Code / opencode maintenance skills for the heretek-claude-harness repo. The skills capture the recurring workflows that emerged during the SP1–SP4 implementation:

1. **`/heretek:catalog`** — research and add vetted items to the marketplace (either as new items in an existing plugin, or as a brand-new plugin with its first items). Two modes, one skill.
2. **`/heretek:refresh-pins`** — quarterly D7-bar verification (thin wrapper around `scripts/refresh_pins.py`).
3. **`/heretek:merge-and-push`** — post-SDD merge dance (fast-forward → test on merged result → push → cleanup worktree + branch).

These are **repo-specific maintenance skills**, not generic superpowers skills. They live under `.claude/skills/` and `.agents/skills/` so both Claude Code and opencode can invoke them.

The general superpowers workflow patterns (subagent-driven-development, fix loops, scoped re-review) are already captured by existing skills (`superpowers:subagent-driven-development`, `superpowers:writing-plans`, etc.). What was *missing* was repo-specific runbooks for the workflows we used repeatedly — those become these three skills.

## 2. Goals and non-goals

### Goals

- Capture the research + ADR + catalog + content + validate + commit workflow as a single invokable skill (currently 6+ manual steps).
- Make quarterly D7 re-vetting a one-command operation rather than a script invocation that requires reading docs.
- Make the post-SDD merge → push → cleanup dance safe and consistent (currently a multi-command sequence that risks forgetting a step).

### Non-goals

- Generalizing to superpowers skills (those already exist).
- Cross-repository coordination (heretek has only one repo).
- Auto-creating PRs (merge-and-push stops at local push; PR creation is a separate concern).
- Implementing `--update-shas` in refresh-pins.py (tracked as Issue #11).
- Catalog schema changes (the catalog schema is already settled per SP1).

## 3. File layout

```
.claude/skills/
  catalog/
    SKILL.md              # the catalog skill's instruction file
    tests/
      smoke_test.sh      # mock-mode smoke test (research in temp dir, validate, rollback)
  refresh-pins/
    SKILL.md              # thin wrapper around scripts/refresh_pins.py
  merge-and-push/
    SKILL.md              # git merge → test → push → cleanup dance

.agents/skills/            # mirror of .claude/skills/ — opencode reads this
  catalog/SKILL.md
  refresh-pins/SKILL.md
  merge-and-push/SKILL.md
```

Each `SKILL.md` is the instruction file the Skill tool loads when invoked. The mirror to `.agents/skills/` is intentional: Claude Code reads `.claude/skills/`, opencode reads `.agents/skills/`. Both will resolve the same skill.

## 4. Skill 1 — `/heretek:catalog`

### 4.1 Invocation

```
/heretek:catalog                  # prompts for mode
/heretek:catalog add-item         # explicit add-item mode
/heretek:catalog add-plugin       # explicit add-plugin mode
```

If invoked without a subcommand, the skill prompts:
> "This skill has two modes: `add-item` (add a vetted third-party item to an existing plugin) or `add-plugin` (scaffold a new plugin with its first vetted items). Which mode? (or describe what you want to add and I'll infer)."

### 4.2 Shared steps (both modes)

These run in both `add-item` and `add-plugin` modes. Each step has explicit acceptance criteria.

#### Step 1: Research

For each candidate item:
- `gh api repos/{owner}/{repo}` → extract `stargazers_count`, `pushed_at`, `license.spdx_id`.
- `gh api repos/{owner}/{repo}/security-advisories` → count critical CVEs (severity == "CRITICAL" → fail D7).
- `WebFetch` the upstream README to confirm scope matches the catalog intent.

Apply the D7 bar (per `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` §7):
- stars ≥ 500 → PASS or fail
- last_commit ≤ 12 months → PASS or fail
- license is OSI-approved (MIT / Apache-2.0 / BSD / etc.) → PASS or fail
- source-audit pass for code-executing components → human review documented in ADR
- 0 critical CVEs (CVSS ≥ 9.0) in 24 months → PASS or fail

If any D7 criterion fails, mark item `rejected` in catalog and stop.

#### Step 2: ADR

Write `catalog/reviews/<plugin>-<item>.md` using the SP1 template at `catalog/reviews/0000-template.md`. Fill in real research data — no placeholders. The ADR is the audit trail.

#### Step 3: Catalog update

Update `catalog/catalog.yaml`:

- **`add-item` mode**: append a new entry to the existing plugin's `items[]` with the full vetting block.
- **`add-plugin` mode**: add a new top-level plugin entry with `components: [...]` and `items: [...]`.

#### Step 4: Content files

- **`add-item` mode**: write or update the corresponding content file based on `kind`:
  - `kind: skill` → `plugins/<plugin>/skills/<name>/SKILL.md`
  - `kind: mcp` → `plugins/<plugin>/.mcp.json` (single file with multiple servers) or `plugins/<plugin>/mcp/<name>/.mcp.json` per server
  - `kind: lsp` → `plugins/<plugin>/.lsp.json` (single file with multiple language servers)
  - `kind: agent` → `plugins/<plugin>/agents/<name>.md`
  - `kind: output-style` → `plugins/<plugin>/output-styles/<name>.md`
- **`add-plugin` mode**: create the directory tree `plugins/<plugin>/.claude-plugin/plugin.json` + the first content files.

#### Step 5: README update

Update `plugins/<plugin>/README.md` install + usage section. Per-plugin README documents:
- For LSPs: the binary install path (rustup, npm, brew, etc.)
- For MCPs: how to launch the server (npx command, env vars)
- For skills: when to invoke (frontmatter description)

#### Step 6: Validate

```bash
. .venv/bin/activate
python scripts/validate.py
python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json
pytest tests/
```

All must exit 0. If `pytest` fails, STOP and report — do NOT commit.

#### Step 7: Commit

Single atomic commit with conventional message. Examples:
- `feat(catalog): add ruff LSP to python plugin` (add-item mode)
- `feat(catalog): add c-cpp task plugin with clangd` (add-plugin mode)

### 4.3 D15 strict hooks ownership check (always)

Before any catalog mutation, verify D15 compliance:
- If `add-item` mode proposes a hook item → REFUSE unless the target plugin is `hooks`.
- If `add-plugin` mode proposes `hooks` in the new plugin's `components` list → REFUSE with a clear error pointing at D15 + the existing `tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin` invariant.

### 4.4 Testing

`.claude/skills/catalog/tests/smoke_test.sh`:
- Creates a temp dir
- Copies `catalog/catalog.yaml` into the temp dir
- Runs the catalog-update flow against the temp catalog (mock mode — no real gh calls; write a test ADR with synthetic stars/license data)
- Runs `python scripts/validate.py` against the temp catalog
- Asserts no test regressions
- Cleans up the temp dir

This test verifies the skill's pipeline works without requiring real GitHub API access. Run on skill changes; not in CI by default.

## 5. Skill 2 — `/heretek:refresh-pins`

### 5.1 Invocation

```
/heretek:refresh-pins                 # default — table of stale items
/heretek:refresh-pins --update-shas    # bump SHAs in catalog.yaml once Issue #11 lands
```

### 5.2 Implementation

Thin wrapper around `scripts/refresh_pins.py`:

```bash
. .venv/bin/activate
pip install -q -r requirements-dev.txt
TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || echo)}"
python scripts/refresh_pins.py --github-token "$TOKEN" $EXTRA_ARGS
```

Surface the output table to the user. Exit code 0 means all fresh; exit code 1 means some stale.

### 5.3 `--update-shas` mode

Issue #11 tracks the `--update-shas` wiring in `refresh_pins.py`. Once that lands:

- Default `refresh-pins` → read-only (today's behavior)
- `--update-shas` → calls `refresh_pins.py --update-shas` which queries GitHub for new HEAD SHAs, writes back to `catalog.yaml`, requires confirmation prompt before overwriting

Until #11 lands, `--update-shas` exits with a clear "not yet implemented" message pointing at Issue #11.

### 5.4 Testing

No dedicated test file — the underlying `scripts/refresh_pins.py` has tests at `tests/test_refresh_pins.py`. The skill is a 5-line wrapper; testing the wrapper tests the script's I/O, which is already covered.

## 6. Skill 3 — `/heretek:merge-and-push`

### 6.1 Invocation

```
/heretek:merge-and-push                          # interactive — asks for branch name
/heretek:merge-and-push sp4-aggregation-launch    # explicit branch
```

### 6.2 Pre-flight checks (fail fast)

Before doing anything:

1. **Confirm with the user** — print a one-line confirmation prompt listing the feature branch, base branch (default `main`), and a summary of what's about to happen.
2. **`git status --porcelain`** — refuse if the working tree is dirty (uncommitted changes).
3. **`git rev-parse --git-common-dir` vs `git rev-parse --git-dir`** — refuse if detached HEAD (can't push a detached branch without naming it).
4. **`git rev-parse --abbrev-ref HEAD`** — confirm the source branch exists.

### 6.3 Steps (only after pre-flight passes)

```bash
# Step 1: fast-forward merge
git checkout main
git pull --ff-only        # skip if upstream gone
git merge <feature-branch> --ff-only

# Step 2: run tests on merged result — refuse to push if any test fails
. .venv/bin/activate
pytest -q
python scripts/validate.py
python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json
bash tests/smoke/fast_gate_smoke.sh

# Step 3: push
git push -u origin main     # default to main; configurable via flag

# Step 4: cleanup worktree + branch (only after push succeeds)
git worktree remove <worktree-path>     # only if worktree exists
git branch -d <feature-branch>
```

Each step has a guard:
- If `git pull` fails (no upstream) → skip pull, warn user
- If merge is not fast-forwardable → refuse, suggest `git merge --no-ff` or rebase
- If any test fails → STOP, do NOT push, do NOT cleanup
- If push fails → STOP, do NOT cleanup
- If cleanup fails → warn but don't fail (branch deletion is non-critical)

### 6.4 Testing

Not testable — real git operations. The skill itself has hard guards (refuse on dirty, detached, non-fast-forward, test failure, push failure). Each guard is a single line of bash, well-tested in practice.

A unit test could mock `subprocess.run` and assert the guards fire, but that's testing bash behavior, not the skill's logic. Skip.

## 7. Cross-cutting concerns

### 7.1 D15 strict hooks ownership

All three skills must respect D15 (only the `hooks` plugin ships hooks). The catalog skill enforces this in step 4.3. The refresh-pins and merge-and-push skills don't write catalog.yaml, so D15 doesn't apply — but they should not bypass CI's `tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin` invariant.

### 7.2 Trailing newlines

Per the project's global constraint (all files end with `\n`), every file written by any skill must end with a newline. The skills' code that writes files should append a trailing `\n` if not present.

### 7.3 Conventional commits

All commits produced by any skill use conventional-commit format (`feat(scope): description`, `fix(scope): description`, `docs(scope): description`). Scope is the affected plugin name, the file category, or `catalog` for cross-cutting changes.

## 8. Acceptance criteria

For all three skills:
- [ ] `SKILL.md` exists for each skill in both `.claude/skills/` and `.agents/skills/`
- [ ] `SKILL.md` content is identical between `.claude/` and `.agents/` mirrors
- [ ] Each `SKILL.md` follows the standard Skill tool format (frontmatter with description + body with steps)
- [ ] No skill writes code that violates the project's global constraints (MIT, no version, trailing newline, D7 vetting, D11 SHA-ride, D15 strict hooks ownership)
- [ ] Skills do NOT auto-create PRs (merge-and-push stops at local push)
- [ ] Skills do NOT bypass CI invariants

For `/heretek:catalog`:
- [ ] Two modes (`add-item`, `add-plugin`) prompt user at start
- [ ] Research step uses real `gh api` (no hand-waving)
- [ ] ADR step writes per-item ADRs (not template-pointer)
- [ ] Catalog update validates against `scripts/validate.py` before commit
- [ ] D15 enforcement refines hook items to `hooks` plugin only

For `/heretek:refresh-pins`:
- [ ] Wraps `scripts/refresh_pins.py` correctly
- [ ] Surfaces output table to user
- [ ] `--update-shas` mode surfaces "not yet implemented" until Issue #11 lands

For `/heretek:merge-and-push`:
- [ ] Refuses on dirty working tree
- [ ] Refuses on detached HEAD
- [ ] Refuses if tests fail on merged result
- [ ] Refuses to push if test fails
- [ ] Skips `git pull` if no upstream

## 9. Out of scope

- Implementing `--update-shas` in `scripts/refresh_pins.py` (Issue #11)
- Real GitHub PR creation via `gh pr create` (manual step after push)
- Vendor-tied skill versions (the skills read the latest catalog schema, no need to version-pin)
- Cross-repository work (heretek has one repo)
- Skill versioning (each `SKILL.md` is regenerated per codebase state; no semantic version)

## 10. References

- `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` — parent design spec (§7 D7 vetting, §11 SP1-SP4 scope)
- `catalog/reviews/0000-template.md` — ADR template used by `/heretek:catalog`
- `tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin` — D15 enforcement
- `tests/test_catalog_vetting.py` — vetting invariant tests
- Issue #11 — `--update-shas` wiring
- `superpowers:subagent-driven-development` — the broader workflow these skills serve

---

## Appendix: SKILL.md skeleton (for reference when writing each skill)

```markdown
---
description: <one-line description of when to invoke>
---

# <skill name>

<brief intro paragraph>

## When to use

<when to invoke this skill>

## Steps

<numbered list of steps, with explicit commands>

## Acceptance criteria

- [ ] <criteria>

## Error handling

- <what to do if X fails>

## Out of scope

- <what NOT to do>
```
