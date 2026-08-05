---
description: Research and add a vetted third-party item to the heretek marketplace (add-item mode) OR scaffold a new plugin with its first items (add-plugin mode). Uses the D7 vetting bar and writes ADRs per item.
---

# heretek:catalog

Add new vetted content to the heretek Claude Code plugin marketplace. Two modes:

- **`add-item`** — research a new third-party item (skill, MCP, LSP, agent, output-style) and add it to an existing plugin's `items[]`.
- **`add-plugin`** — scaffold a brand-new plugin (creates `plugins/<name>/.claude-plugin/plugin.json` + first content files + new catalog entry).

## When to use

Use this skill when you want to add new content to the heretek marketplace. Both modes walk the same research + ADR + catalog + content + validate + commit pipeline; the difference is whether you're extending an existing plugin or creating a new one.

## Steps

### Step 1: Determine mode

If the user didn't specify:
- They want to extend an existing plugin → `add-item` mode
- They want to create a new plugin → `add-plugin` mode
- They want to vet a candidate that exists in `ref.text` (now absorbed into `catalog/raw/ref.text`) — check the existing `catalog/rejected.md` first; if not yet evaluated, `add-item` mode

### Step 2: Research (add-item mode)

For each candidate item:

```bash
# 1. Stars / last commit / license
gh api repos/{owner}/{repo} | jq '{stargazers_count, pushed_at, license: .license.spdx_id}'

# 2. Critical CVEs (D7 says: none in 24 months)
gh api repos/{owner}/{repo}/security-advisories | jq '[.[] | select(.severity == "CRITICAL")] | length'

# 3. README (for scope confirmation)
gh api repos/{owner}/{repo}/readme | jq -r .content | base64 -d | head -100
```

Apply the D7 bar (per `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` §7):

| Criterion | Bar | Fail action |
|---|---|---|
| Stars | ≥ 500 | reject |
| Last commit | ≤ 12 months | reject |
| License | OSI-approved (MIT / Apache-2.0 / BSD / etc.) | reject |
| Source-audit pass for code-executing components | Required | reject |
| Critical CVEs (CVSS ≥ 9.0) in 24 months | 0 | reject |

If any criterion fails, append to `catalog/rejected.md` with the failing condition and stop.

### Step 3: Write the ADR

Create `catalog/reviews/<plugin>-<item>.md` using the SP1 template at `catalog/reviews/0000-template.md`. Fill in real research data — no placeholders. Include:

- `slug:` (frontmatter)
- `date:` (today)
- `status: pending` (will be flipped to `approved` or `rejected`)
- **What** — repo, what it does, latest release
- **Why** — gap filled in heretek
- **Alternatives** — what other tools cover the same need; why this one
- **Verdict** — Approved or Rejected with reason
- **Target plugin** — which plugin bundles this
- **Vetting checklist** — 5 D7 criteria with PASS/FAIL

### Step 4: Update catalog.yaml

For `add-item`: append to the existing plugin's `items[]`:

```yaml
items:
  - id: <item-slug>
    kind: skill | mcp | lsp | agent | output-style
    upstream: <owner>/<repo>
    sha: "<40-char-hex>"           # current HEAD SHA from `gh api repos/.../commits/HEAD --jq .sha`
    license: MIT | Apache-2.0 | BSD-3-Clause | ...
    vetting:
      status: approved             # or rejected
      date: 2026-08-05              # today
      stars: <int>
      last_commit: 2026-08-04
      cve_scan: 2026-08-05
      review: reviews/<item-slug>.md
```

For `add-plugin`: add a new top-level plugin entry:

```yaml
- name: <plugin-slug>
  category: task | cross
  tags: [<list>]
  source: { type: relative, path: <plugin-slug> }
  components: [skills | mcp | lsp | agents | output-styles]
  items:
    - id: <first-item-slug>
      kind: skill
      ...
```

### Step 5: Write the content file (add-item mode)

Based on `kind`:

- **`kind: skill`** → `plugins/<plugin>/skills/<name>/SKILL.md` with frontmatter `name: <slug>` and `description: <when to invoke>`, plus a system-prompt body
- **`kind: mcp`** → `plugins/<plugin>/.mcp.json` (single file with multiple servers) or per-server in `mcp/<name>/.mcp.json`
- **`kind: lsp`** → `plugins/<plugin>/.lsp.json` (single file with multiple language servers)
- **`kind: agent`** → `plugins/<plugin>/agents/<name>.md`
- **`kind: output-style`** → `plugins/<plugin>/output-styles/<name>.md`

For `add-plugin` mode, also create the directory tree:

```bash
mkdir -p plugins/<name>/.claude-plugin
# Create plugins/<name>/.claude-plugin/plugin.json
# Create first content files in plugins/<name>/{skills,mcp,lsp,agents,output-styles}/
```

### Step 6: Update plugin.json (both modes)

For `add-item` mode, update `plugins/<plugin>/.claude-plugin/plugin.json` to declare the new component path (e.g., `"skills": "./skills/"`).

For `add-plugin` mode, create `plugins/<plugin>/.claude-plugin/plugin.json`:

```json
{
  "name": "<plugin-slug>",
  "displayName": "<Display Name>",
  "description": "...",
  "author": { "name": "Heretek-AI", "url": "https://github.com/Heretek-AI" },
  "license": "MIT",
  "<component>": "<path>"
}
```

Do NOT add a `version` field (D11 SHA-ride).

### Step 7: D15 strict hooks ownership check (ALWAYS)

Before committing, verify D15:

- If `add-item` mode proposes a hook item → REFUSE unless the target plugin is `hooks`.
- If `add-plugin` mode declares `hooks` in `components` → REFUSE.

The invariant is enforced at CI by `tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin`. A new plugin entry violating D15 will fail tests.

### Step 8: Update README

Update `plugins/<plugin>/README.md` install + usage section. Per-plugin README documents:
- For LSPs: the binary install path (rustup, npm, brew)
- For MCPs: how to launch the server (npx command, env vars)
- For skills: when to invoke (frontmatter description)

### Step 9: Validate

```bash
. .venv/bin/activate
python scripts/validate.py
python scripts/generate_marketplace.py && git diff --exit-code .claude-plugin/marketplace.json
pytest tests/
```

All must exit 0. If `pytest` fails, STOP and report — do NOT commit.

### Step 10: Commit

Single atomic commit with conventional message:

- `add-item` mode: `feat(catalog): add <item-slug> to <plugin> plugin`
- `add-plugin` mode: `feat(catalog): scaffold <plugin-slug> plugin with <first-item-slug>`

Body: list the items, their vetted status, and the ADR path.

## Acceptance criteria

- [ ] Item passes all 5 D7 criteria (or was rejected with documented reason in `catalog/rejected.md`)
- [ ] ADR written at `catalog/reviews/<plugin>-<item>.md` using the SP1 template
- [ ] `catalog/catalog.yaml` updated with full vetting block (status, date, stars, last_commit, cve_scan, review path)
- [ ] Content file written based on `kind`
- [ ] `plugin.json` updated to declare new component path (no `version` field — D11 SHA-ride)
- [ ] D15 enforced: no new plugin declares hooks; no `add-item` adds hook to non-hooks plugin
- [ ] `scripts/validate.py` exits 0
- [ ] `tests/` all pass
- [ ] Single atomic commit

## Error handling

- If `gh api` returns 404 or rate-limit → check token, retry with exponential backoff
- If D7 fails → append to `catalog/rejected.md`, do not commit
- If `pytest` fails → STOP, report which test failed and why, do not commit
- If `git diff --exit-code` fails → check `git status`, restore any untracked `marketplace.json` to original (it should be regenerated identically)

## Out of scope

- Auto-creating PRs (manual step after push)
- Implementing `--update-shas` for refresh-pins (covered by `/heretek:refresh-pins` once Issue #11 lands)
- Modifying the D7 vetting bar itself (that's a spec change, not a catalog task)
- Removing existing items (use a separate `archive` mode if needed)
