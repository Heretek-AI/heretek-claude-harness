# Heretek Tracking Layer — Design Spec

**Date:** 2026-08-01
**Status:** Approved (brainstorming complete)
**Author:** Principal Systems Architect (brainstormed with Claude)
**Scope:** Umbrella bootstrapper + two child repos (`Heretek-AI/llama-builds`, `Heretek-AI/heretek-manager`)

---

## 1. Executive summary

This spec defines a single-source-of-truth tracking layer for the Heretek AI Package Ecosystem. The layer has three jobs:

1. **Capture every actionable item** from `Write out a design doc for the project.md` (3 rollout phases) and `Llama Ecosystem Repository Analysis.md` (upstream package families) as discrete, fileable work.
2. **Mirror that backlog into GitHub Issues** (one per child repo) with a 2-axis label taxonomy (`phase/*` × `component/*`) plus a `status/*` axis.
3. **Stay harness-agnostic** — any agent (Claude, Codex, Gemini, or a human) can read either the YAML seed in the umbrella or the GitHub Issues in the child and know exactly what to do, with no in-repo markdown index.

The umbrella (`monorepo-manager`) stays projectless. The two children get full Issues + GitHub Project board treatment. Backlog is bootstrapped via a checked-in YAML seed and an idempotent shell script.

## 2. Goals and non-goals

### Goals

- All ~60 initial issues derivable from a single checked-in YAML file in the umbrella.
- Re-running the bootstrap script is idempotent (zero side effects on a clean repo state).
- Each issue has a structured body (Source / Goal / Acceptance / Out of scope / Dependencies).
- Labels follow a strict 2-axis taxonomy, plus status; no custom GitHub Projects fields.
- Future agent sessions can read the seed YAML directly with no GitHub access (treats the YAML as a machine-readable backlog).
- Drift detection (already in `contract_hash.py`) covers the new seed outputs.

### Non-goals

- No in-repo markdown backlog index in either child repo. GitHub Issues + the umbrella seed are the only surfaces.
- No milestone objects, no GitHub Projects custom fields, no automation rules.
- No deletion of issues by the script. Append-only from the script's view.
- No GitHub Project board setup automation. Project board is a structural object configured once by a human.
- No PR creation, branch creation, or commits from `seed-issues.sh`. Strictly an issue tracker mirror.

## 3. Architecture

```
monorepo-manager/                          (umbrella, projectless, "throwaway")
├── seeds/
│   ├── labels.yaml                        # canonical label definitions
│   ├── llama-builds.yaml                  # initial backlog for llama-builds
│   └── heretek-manager.yaml               # initial backlog for heretek-manager
├── scripts/
│   ├── lib/
│   │   ├── seed_loader.py                 # NEW — parses seeds/*.yaml, validates against schema
│   │   ├── render_seed.py                 # NEW — sibling to render_tracking.py
│   │   └── contract_hash.py               # existing — extended to hash seed outputs
│   └── seed-issues.sh                     # NEW — one-shot, idempotent
├── schemas/
│   └── seed.schema.json                   # NEW — contract for seeds/*.yaml shape
├── tests/
│   ├── test_render_seed.py                # NEW
│   ├── test_seed_loader.py                # NEW
│   └── test_seed_issues_script.py         # NEW — sandbox test, no live GitHub
└── templates/
    └── seeds/                             # NEW Jinja sources
        ├── labels.yaml.j2
        ├── llama-builds.yaml.j2
        ├── heretek-manager.yaml.j2
        └── seed-issues.sh.j2

Heretek-AI/llama-builds/                   (child, gets Issues + Project #1)
├── .github/ISSUE_TEMPLATE/                # already rendered
├── .github/labels/labels.yaml             # NEW — copy of umbrella labels
├── AGENTS.md                              # Pointer block: +1 bullet for seed URL
├── scripts/seed-issues.sh                 # NEW — copy from umbrella
└── (no in-repo markdown index)

Heretek-AI/heretek-manager/                (child, gets Issues + Project #2)
└── (same shape as llama-builds)
```

**Single source of truth = `seeds/*.yaml`** in the umbrella. GitHub state is a projection of the seed. The seed is also a machine-readable backlog any offline agent can read directly.

**The umbrella emits, the children accept.** `scripts/init-harness.sh` calls `render_seed` alongside the existing renderers. `seed-issues.sh` (in each child) reads the seed from the umbrella at runtime — children never store a stale copy.

**AGENTS.md schema unchanged.** The Pointer block slot already exists; we add one bullet for the seed URL.

## 4. Seed YAML schema

### `seeds/llama-builds.yaml` (and `seeds/heretek-manager.yaml`)

```yaml
schema_version: 1
repo: Heretek-AI/llama-builds
project_id: PVT_xxxxxxxxxxxx          # GitHub Project node ID; filled at first sync

issues:
  - id: lb-0001                        # stable, monotonic; idempotency key
    title: "Set up GitHub Actions matrix workflow skeleton"
    phase: phase/1-ci-setup            # one phase/* label
    component: component/ci            # one component/* label
    status: status/backlog             # one status/* label, default backlog
    source:
      doc: "Write out a design doc for the project.md"
      section: "2.1 Repository Directory Structure"
    goal: |
      Create .github/workflows/build-matrix.yml with an empty matrix
      block and a no-op job that runs on every PR.
    acceptance:
      - Workflow file committed at .github/workflows/build-matrix.yml
      - Workflow runs on pull_request and is green on a trivial push
      - No secrets referenced; uses GITHUB_TOKEN only
    out_of_scope:
      - Actual matrix entries (see lb-0002)
      - ROCm runner setup (see lb-0007)
    depends_on: []
```

### `seeds/labels.yaml` (one file shared by both repos)

```yaml
schema_version: 1
labels:
  - name: phase/1-ci-setup
    color: "0E8A16"
    description: "Phase 1 — llama-builds CI/CD foundation"
  - name: phase/2-cli-runtime
    color: "1D76DB"
    description: "Phase 2 — heretek-manager CLI + hardware auditor"
  - name: phase/3-webui
    color: "5319E7"
    description: "Phase 3 — WebUI dashboard"
  - name: phase/4-matrix-pkg
    color: "BFD4F2"
    description: "Phase 4 — upstream package families (ecosystem matrix)"
  - name: phase/meta
    color: "C5DEF5"
    description: "Cross-cutting items"
  - name: component/ci
    color: "D4C5F9"
    description: "GitHub Actions workflows"
  - name: component/manifest
    color: "C2E0C6"
    description: "manifest.json schema, generator, fetcher"
  - name: component/auditor
    color: "FBCA04"
    description: "Hardware detection (nvidia-smi / rocminfo / vulkaninfo)"
  - name: component/symlink
    color: "F9D0C4"
    description: "Atomic symlink swap in ~/.heretek/bin/"
  - name: component/upstream-sync
    color: "B084CC"
    description: "Tracking upstream llama.cpp forks"
  - name: component/webui
    color: "0052CC"
    description: "WebUI dashboard (Express server on :9048)"
  - name: component/api
    color: "006B75"
    description: "REST API endpoints"
  - name: component/store
    color: "BFD4F2"
    description: "Version store layout under ~/.heretek/store/"
  - name: component/infra
    color: "D93F0B"
    description: "Infrastructure-as-code (runners, secrets, caches)"
  - name: component/docs
    color: "0E8A16"
    description: "Documentation, README, examples"
  - name: component/manager
    color: "E99695"
    description: "CLI/runtime manager internals (downloads, flags, logging)"
  - name: status/backlog
    color: "BFBFBF"
    description: "Not started"
  - name: status/in-progress
    color: "FBCA04"
    description: "Actively being worked"
  - name: status/blocked
    color: "D93F0B"
    description: "Cannot progress; needs human intervention"
  - name: status/review
    color: "0E8A16"
    description: "PR open, awaiting review"
  - name: status/done
    color: "828282"
    description: "Merged and verified"
```

### Schema contract

`schemas/seed.schema.json` enforces:

- `schema_version: 1` (literal int).
- Required top-level keys: `schema_version`, `repo`, `project_id`, `issues`. `project_id` may be the empty string `""` until the GitHub Project is created during first-run (runbook §13); the seed loader accepts empty but warns on validation.
- Per-issue required keys: `id`, `title`, `phase`, `component`, `status`, `source.doc`, `goal`, `acceptance` (≥1 item), `out_of_scope`, `depends_on`.
- `id` matches `^[a-z]{2}-[0-9]{4}$`. Convention: 2-letter repo prefix (`lb-` for llama-builds, `hm-` for heretek-manager) followed by a monotonic 4-digit zero-padded counter. The regex is the contract; the convention is enforced by reviewer discipline, not the schema.
- `phase`, `component`, `status` values match a label name defined in `seeds/labels.yaml`.
- `depends_on` references only ids that exist in the same seed (no forward references to missing ids).

## 5. Issue body contract

Every GitHub Issue filed by `seed-issues.sh` has this exact structure:

```markdown
<!-- seed-id: lb-0001 -->
## Source
- Doc: `Write out a design doc for the project.md`
- Section: §2.1 Repository Directory Structure
- Repo: Heretek-AI/llama-builds

## Goal
Create `.github/workflows/build-matrix.yml` with an empty matrix
block and a no-op job that runs on every PR.

## Acceptance criteria
- [ ] Workflow file committed at `.github/workflows/build-matrix.yml`
- [ ] Workflow runs on `pull_request` and is green on a trivial push
- [ ] No secrets referenced; uses `GITHUB_TOKEN` only

## Out of scope
- Actual matrix entries (see lb-0002)
- ROCm runner setup (see lb-0007)

## Dependencies
_None._

---
_Filed by `scripts/seed-issues.sh` from `seeds/llama-builds.yaml`.
Re-running the script with the same seed is idempotent (issues are
matched by `seed-id: <id>` HTML comment at the top)._
```

**Five required sections, in this order:** Source, Goal, Acceptance criteria, Out of scope, Dependencies. The footer line telling readers the issue is machine-generated and re-derivable is mandatory.

**Idempotency key:** the HTML comment `<!-- seed-id: <id> -->` at the top. `seed-issues.sh` searches existing issues for this comment; if found, the script skips (or updates only when the body hash differs).

**Body contract is enforced** by `scripts/lib/seed_loader.py`, which validates every issue against the required-sections regex before any `gh issue create` call. Validation failure exits non-zero with the failing issue id and the missing section name.

## 6. Label taxonomy

Labels are the entire schema for state. No milestone objects, no custom project fields, no automation rules.

### Phase axis (5 labels)

| label | meaning | typical lifespan |
|---|---|---|
| `phase/1-ci-setup` | llama-builds CI/CD foundation | weeks 1–3 |
| `phase/2-cli-runtime` | heretek-manager CLI + hardware auditor | weeks 3–6 |
| `phase/3-webui` | heretek-manager WebUI dashboard | weeks 6–9 |
| `phase/4-matrix-pkg` | upstream package families (ecosystem matrix) | weeks 1–∞, ongoing |
| `phase/meta` | cross-cutting items | as needed |

Every issue has exactly **one** `phase/*` label. Phase is the "what" dimension.

### Component axis (11 labels)

`component/ci`, `component/manifest`, `component/auditor`, `component/symlink`, `component/upstream-sync`, `component/webui`, `component/api`, `component/store`, `component/infra`, `component/manager`, `component/docs`.

Every issue has exactly **one** `component/*` label. Component is the "where" dimension.

### Status axis (5 labels)

| label | meaning | who sets it |
|---|---|---|
| `status/backlog` | Not started | seed-issues.sh at filing time |
| `status/in-progress` | Actively being worked | the implementer (agent or human) |
| `status/blocked` | Cannot progress; needs human intervention | the implementer |
| `status/review` | PR open, awaiting review | the implementer when they open the PR |
| `status/done` | Merged and verified | the implementer after merge |

Status is the only label that **changes** during the issue's life. `seed-issues.sh` never sets anything above `status/backlog` — promotion is a human/agent action.

### Naming rules

1. Labels are forward-slash-namespaced: `phase/`, `component/`, `status/` prefixes.
2. Lowercase kebab after the slash: `phase/1-ci-setup` not `phase/1-CI-Setup`.
3. Color is informational. Phase labels get a 5-color ramp; component labels share a soft hue family; status labels mirror the GitHub-native palette (grey / yellow / red / green / dark-grey).

## 7. GitHub Project board

Two views per child repo, configured once by a human after the first seed run:

- **By Phase**: rows = `phase/1-ci-setup`, `phase/2-cli-runtime`, `phase/3-webui`, `phase/4-matrix-pkg`, `phase/meta`. Columns = `status/backlog` | `status/in-progress` | `status/review` | `status/done`. Blocked items stay in their current column; `status/blocked` label is the visual signal.
- **By Component**: rows = the 11 `component/*` labels. Same columns.

No automation rules — humans/agents move cards by changing `status/*` labels. This keeps the project board derivable from labels and avoids GitHub Projects API drift.

## 8. AGENTS.md Pointer block update

Each child's `AGENTS.md` Pointer block gains one bullet (per repo):

```markdown
- GitHub Project: https://github.com/orgs/Heretek-AI/projects/1
- Backlog seed: https://github.com/Heretek-AI/monorepo-manager/blob/main/seeds/llama-builds.yaml
```

The umbrella's `AGENTS.md` Pointer block stays unchanged (umbrella is projectless).

The AGENTS.md schema (`schemas/agents-md.schema.json`) does not need to change — it constrains section names, not bullet count within the Pointer block.

## 9. `seed-issues.sh` lifecycle

### Command surface

```bash
scripts/seed-issues.sh --repo Heretek-AI/llama-builds              # default mode
scripts/seed-issues.sh --repo Heretek-AI/llama-builds --dry-run
scripts/seed-issues.sh --repo Heretek-AI/llama-builds --id lb-0001  # one issue
scripts/seed-issues.sh --repo Heretek-AI/llama-builds --only-labels # sync labels only
scripts/seed-issues.sh --repo Heretek-AI/llama-builds --prune-closed # also update closed issues
```

### Six-step flow per run

1. **Pre-flight.** Check `gh auth status`; if not authenticated, exit non-zero. Detect missing repo (404) and exit.
2. **Label sync.** `gh label create <name> --color <c> --description <d> --force` for each label in `seeds/labels.yaml`. `--force` overwrites color/description; never deletes. Then `gh label delete` for any label *in the repo* with a `phase/`, `component/`, or `status/` prefix that is **not** in the seed, **refusing to delete** if any open issue uses the label.
3. **Issue discovery.** For each seed `id`, call `gh issue list --label <phase-label> --label <component-label> --state all --json body,number,state` and grep each body for `<!-- seed-id: <id> -->`. Cache the mapping in `~/.cache/heretek-seed/<repo>.json`.
4. **Diff per seed entry.** Three branches:
   - **No matching issue** → `gh issue create --title --body-file --label <phase,component,status/backlog>`.
   - **Matching issue, body hash unchanged** → skip.
   - **Matching issue, body hash changed** → `gh issue edit --body-file` and reconcile label drift (`--add-label` / `--remove-label`). Refuse to edit title if the issue is closed; emit a warning.
5. **Post-create label reconciliation.** Ensure exactly one `phase/*`, one `component/*`, one `status/*` per issue. Remove stray duplicates; warn on removals.
6. **Summary.** Print created / updated / skipped / failed counts and the cache file path. Exit non-zero only on failures in step 4.

### Guarantees

- **Idempotency:** running twice with no seed changes creates 0 issues the second time.
- **No destructive overwrite:** human-edited issue bodies stick until the seed catches up.
- **Refuses to act on closed issues without `--prune-closed`:** closed issues may be won't-fix or duplicate. Default behavior leaves them alone and warns. With `--prune-closed`, the script will update body and labels but will not reopen or re-title the issue.

### Error handling

- Network failure on a `gh` call → retry once after 5 s, then exit non-zero with the failing issue id. The cache file records success so a re-run picks up where it left off.
- Seed validation failure (missing body section) → exit before any `gh` call.
- Label deletion refusal (open issue uses label) → log, skip, continue. Never aborts the whole run.

### Dependencies

- `gh` CLI ≥ 2.40.
- `yq` ≥ 4.30.
- `jq`.
- `python3` (calls `seed_loader.py` as a subprocess).

## 10. Umbrella integration

### New artefacts

| artefact | role |
|---|---|
| `schemas/seed.schema.json` | JSON-Schema contract for `seeds/*.yaml` |
| `scripts/lib/seed_loader.py` | validate + emit body markdown for one issue |
| `scripts/lib/render_seed.py` | render labels + per-repo seeds from Jinja templates |
| `templates/seeds/labels.yaml.j2` | Jinja source for label definitions |
| `templates/seeds/llama-builds.yaml.j2` | Jinja source for the llama-builds seed (≈30 issues) |
| `templates/seeds/heretek-manager.yaml.j2` | Jinja source for the heretek-manager seed (≈30 issues) |
| `templates/seeds/seed-issues.sh.j2` | Jinja source for the shell script |
| `seeds/` (umbrella root, **checked in**) | generated by `render_seed` from `templates/seeds/*.yaml.j2`, also committed to git as the canonical backlog data that `seed-issues.sh` reads |
| `tests/test_render_seed.py` | smoke tests for `render_seed` |
| `tests/test_seed_loader.py` | validation tests for `seed_loader` |
| `tests/test_seed_issues_script.py` | sandbox test that runs `seed-issues.sh --dry-run` |

### Render pipeline change

`render_seed.py` is structurally a sibling of `render_tracking.py` — same Jinja loader, same output-as-dict API, same test shape. New contributors see one familiar pattern.

### `init-harness.sh` change (one line)

```bash
scripts/lib/render_seed.py --org Heretek-AI --repo ...
```

Both invocations already happen inside `init-harness.sh --generate`. No new CLI flags.

### Contract hash

`scripts/lib/contract_hash.py` is extended to hash the seed outputs (`seeds/llama-builds.yaml`, `seeds/heretek-manager.yaml`, `scripts/seed-issues.sh`). Editing a seed and not regenerating → `init-harness.sh --verify` flags drift.

### Child repo receiving line

Each child repo gets, in addition to today's rendered files:

- `.github/labels/labels.yaml` — copy of `seeds/labels.yaml` for `--only-labels` and `--dry-run` support (no network needed).
- `scripts/seed-issues.sh` — copy from `templates/seeds/seed-issues.sh.j2`, with `--repo Heretek-AI/<repo>` baked in as the default.

**Children do NOT receive a copy of `seeds/<repo>.yaml`.** The script reads the seed from the umbrella at runtime (default: `https://raw.githubusercontent.com/Heretek-AI/monorepo-manager/main/seeds/<repo>.yaml`), with an optional `--seed-file <path>` override for offline or air-gapped runs. This avoids the child ever storing a stale copy of the canonical backlog.

## 11. Testing strategy

Five test layers, each catching a different class of bug.

### Layer 1 — Seed schema validation (`tests/test_seed_loader.py`)

- Valid seed → all issues parse, `validate_issue()` returns True for each.
- Missing required YAML field (`source.doc`, `goal`, etc.) → validator returns False with the failing id and field name.
- `phase/*` label not in `seeds/labels.yaml` → validator returns False with both seed id and unknown label.
- `depends_on` references an id not in the seed → validator returns False (forward references forbidden).
- `id` not matching `^[a-z]{2,4}-[0-9]{4}$` → validator returns False.
- Acceptance criteria empty list → validator returns False (≥1 required).

### Layer 2 — Renderer tests (`tests/test_render_seed.py`)

- `render_labels()` produces all 21 expected labels (5 phase + 11 component + 5 status,
  including `component/manager` added in a follow-up revision for heretek-manager
  CLI/runtime items).
- `render_repo_seed("llama-builds")` produces a YAML with `schema_version: 1`, correct `repo`, ≥1 issue.
- `render_seed_issues_script()` produces a shell script with shebang, `set -euo pipefail`, templated `--repo` default.
- Idempotency: calling `render_seed` twice with the same input produces byte-identical output.

### Layer 3 — Script sandbox test (`tests/test_seed_issues_script.py`)

Uses a tiny local fake GitHub API to verify `seed-issues.sh` without live GitHub auth in CI.

- `--dry-run` makes zero `gh` calls that mutate state.
- Idempotency: second run logs 0 created, 0 updated, N skipped.
- Body hash drift: change one character in one issue body → 1 updated, N-1 skipped.
- Label deletion refusal: pre-create open issue with `phase/old-name`, run script → label NOT deleted, warning logged.
- Missing required body section → script exits non-zero before any `gh` call.
- Network failure on one `gh` call → script retries once, then exits non-zero with failing issue id.

### Layer 4 — Schema lint

`render_seed.py` output round-trips through `jsonschema.validate(...)` against `schemas/seed.schema.json`.

### Layer 5 — Contract hash drift

Extend existing contract-hash tests so seed outputs are in the hashed set.

- Run `init-harness.sh --verify` after a seed edit → drift detected.
- Run `init-harness.sh --generate` → hash regenerates, drift clears.

### Out of scope for tests

- Real GitHub API behavior (we trust `gh`).
- WebUI / project board visual output (children have their own UI tests).
- Individual seed entry text quality (human review concern; schema catches malformed entries).

### Test pyramid (rough counts)

- Layer 1: ~6 tests
- Layer 2: ~4 tests
- Layer 3: ~6 tests (highest value; catches real bugs)
- Layer 4: ~2 tests
- Layer 5: ~2 tests

≈ 20 new tests, all unit/sandbox, no live GitHub dependency.

## 12. Initial backlog enumeration (preview)

The seed templates contain the canonical enumeration. Preview by phase:

| phase | approx count | source |
|---|---|---|
| `phase/1-ci-setup` | ~6 | Design §2.1, §2.2 (GitHub Actions matrix, manifest generator) |
| `phase/2-cli-runtime` | ~10 | Design §3.1, §3.2 (heretek-manager skeleton, hardware auditor) |
| `phase/3-webui` | ~8 | Design §4 (REST API endpoints, WebUI dashboard) |
| `phase/4-matrix-pkg` | ~30 | Ecosystem §Core + §Hardware + §Quantization (ik_llama.cpp, sglang, CachyLLama, KVarN, TurboQuant, etc.) |
| `phase/meta` | ~6 | cross-cutting (label sync, drift detection, AGENTS.md updates) |

Total ≈ 60 issues across both repos (llama-builds carries phases 1, 4, and the matrix-pkg slice; heretek-manager carries phases 2, 3, and the CLI/WebUI slice; some `phase/meta` items live in both).

The exact enumeration is committed in `templates/seeds/llama-builds.yaml.j2` and `templates/seeds/heretek-manager.yaml.j2` at implementation time.

## 13. Migration / first-run runbook

After implementation lands in the umbrella:

1. **Run `init-harness.sh --generate`** against both reference installs to regenerate AGENTS.md, .github/, scripts/, .github/labels/, and scripts/seed-issues.sh in each child. The umbrella seeds/ files are also regenerated from the templates.
2. **Run `pytest tests/`** — all 20 new tests pass; existing tests still green.
3. **Hand to a human with `gh` auth** to:
   a. Create one GitHub Project per child repo (manual UI step, Projects #1 and #2). Note the project node ID for each (Settings → Developers → GraphQL).
   b. Update `seeds/llama-builds.yaml` and `seeds/heretek-manager.yaml` `project_id` fields with the new IDs, commit, push.
   c. Run `scripts/seed-issues.sh --repo Heretek-AI/llama-builds --only-labels` → creates the labels.
   d. Run `scripts/seed-issues.sh --repo Heretek-AI/llama-builds` → files the 30 issues.
   e. Repeat for `Heretek-AI/heretek-manager`.
   f. Configure the two views (By Phase, By Component) on each Project board per §7.
4. **Verify** by opening one issue in each repo and confirming the body has all five sections and the `seed-id` HTML comment.

## 14. Risks and mitigations

| risk | mitigation |
|---|---|
| Seed grows stale as scope evolves | `scripts/lib/contract_hash.py` flags drift when the seed is edited but children aren't regenerated |
| Human-edited issue bodies get clobbered on re-run | Body-hash diff; only update when seed body diverges from issue body |
| Closed issues accumulate, never pruned | `--prune-closed` opt-in; default leaves closed issues untouched |
| `gh` API rate limits on large seeds | Single repo first-run is <100 issues; well within limits. Re-runs are cache-only after first sync. |
| Phase label color clashes with existing org labels | `--force` overwrites color/description but never deletes. Document in runbook. |
| Future agent can't read seed without GitHub access | Seed lives in the umbrella, which is a git repo. Any agent with read access to the umbrella gets the canonical backlog. |

## 15. Open questions deferred to writing-plans

None for the original 20-label taxonomy. A follow-up revision added
`component/manager` (CLI/runtime manager internals — downloads, flags,
logging) to support heretek-manager-specific items, bringing the
component axis to 11 labels and the total taxonomy to 21 labels
(5 phase + 11 component + 5 status). The §6 component list, §7
project-board row count, and §11 Layer-2 expected-label count were
updated to match the rendered labels.

---

**Next step:** Run `superpowers:writing-plans` against this spec to produce an implementation plan with bite-sized tasks.
