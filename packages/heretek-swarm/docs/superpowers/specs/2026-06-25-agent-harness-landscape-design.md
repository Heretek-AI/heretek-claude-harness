# Agent-Harness OSS Landscape Research

**Status:** Approved (in-session brainstorm, 2026-06-25)
**Scope:** Read-only research deliverable. No code changes in this spec.
**Targets:** `NousResearch/hermes-agent`, `openclaw/openclaw`

---

## Purpose

Produce a single decision-ready landscape document comparing two candidate agent-harness projects against our 23-agent swarm. The doc lets a future brainstorm decide whether to (a) wrap, (b) replace, or (c) ignore each repo. This spec delivers the *research*, not the decision.

## Non-Goals

- No code changes to `backend/heretek_swarm/`.
- No new dependencies added to `pyproject.toml`.
- No replacement of `AgentActor` (deferred to a follow-up spec if research recommends).
- No evaluation of repos outside the two named targets.

---

## Research Orchestration

Three-phase workflow, executed via the `Workflow` tool.

### Phase 1 — Deep Read (parallel, 2 agents)

| Agent | Input | Output |
|---|---|---|
| `reader.hermes` | `https://github.com/NousResearch/hermes-agent`, rubric axes | `findings.hermes.json` (schema-validated) |
| `reader.openclaw` | `https://github.com/openclaw/openclaw`, rubric axes | `findings.openclaw.json` (schema-validated) |

Reader contract: observe only. Does not verify own claims. Does not compare to other repo.

Reader schema:
```json
{
  "repo": "owner/name",
  "license": "string",
  "language": "string",
  "entry_points": ["path:line", ...],
  "loop_architecture": "string <=200 words",
  "tool_model": "string",
  "memory_hook": "string or null",
  "agent_lifecycle": "string",
  "patterns_observed": ["string", ...],
  "claim_evidence": [
    {"claim": "string", "evidence_path": "file:line", "confidence": "high|med|low"}
  ]
}
```

### Phase 2 — Adversarial Verify (parallel, 2 agents)

| Agent | Input | Output |
|---|---|---|
| `refuter.hermes` | `findings.hermes.json` | `verdicts.hermes.json` |
| `refuter.openclaw` | `findings.openclaw.json` | `verdicts.openclaw.json` |

Refuter contract: try to kill each `claim_evidence` row by re-fetching `evidence_path`. Pure challenge. No new findings.

Refuter schema:
```json
{
  "repo": "owner/name",
  "refutations": [
    {"target_claim": "string", "verdict": "refuted|weakened|holds|unverifiable", "evidence": "string"}
  ],
  "surviving_claims": ["string", ...]
}
```

### Phase 3 — Synthesis (1 agent)

Input: both `findings.*.json` + both `verdicts.*.json`.
Output: the committed `.md` doc + rubric scores JSON sidecar.

Synthesizer contract: pure merge. Does not re-read source. Trusts verified findings.

Synthesizer schema:
```json
{
  "doc_path": "docs/superpowers/specs/2026-06-25-agent-harness-landscape.md",
  "head_to_head": {
    "rows": [{"axis": "string", "hermes": "string", "openclaw": "string"}]
  },
  "rubric_scores": {
    "NousResearch/hermes-agent": {"prime_directive_fit": {}, "adoption": {}, "pattern_transferability": {}},
    "openclaw/openclaw": {"prime_directive_fit": {}, "adoption": {}, "pattern_transferability": {}}
  }
}
```

---

## Rubric (constant, passed to every unit)

### Prime Directive Fit (0–5 per pillar)
1. Unbounded Autonomy
2. Organic Evolution
3. Zero-Trust
4. Consciousness-by-Design
5. Persistent Operation

### Adoption (0–3 per axis)
- License compatibility (MIT, Apache-2.0, BSD-2/3-Clause, MPL-2.0, Unlicense only)
- Python 3.11+ native (no transitive Python<3.11 deps)
- Async/await throughout
- Runs without vendor cloud (sovereignty)
- No mandatory outbound telemetry

### Pattern Transferability (0–3 per pattern)
- Loop control
- Tool calling / function schema
- Memory hook interface
- Error recovery / retry policy
- Agent-to-agent message protocol

---

## Components (5 discrete units)

| Unit | Purpose | Boundary |
|---|---|---|
| `reader.hermes` | Deep code-read of hermes-agent | No verification. No comparison. |
| `reader.openclaw` | Deep code-read of openclaw | Symmetric isolation. |
| `refuter.hermes` | Kill reader.hermes claims | No new findings. Pure challenge. |
| `refuter.openclaw` | Kill reader.openclaw claims | Symmetric isolation. |
| `synthesizer` | Merge + write doc | No re-read of source. |

Each unit reads its own context, writes small JSON, hands off. Unit dies alone → re-runnable individually via workflow resume.

---

## Data Flow

```
reader.hermes ──→ findings.hermes.json ──→ refuter.hermes ──→ verdicts.hermes.json ──┐
                                                                                    │
reader.openclaw ──→ findings.openclaw.json ──→ refuter.openclaw ──→ verdicts.openclaw.json ──┐
                                                                                            ▼
                                                                       synthesizer ──→ committed .md
```

Persistent state: workflow journal handles intermediate JSON. Final committed artifact = the markdown doc. Intermediate JSONs are research scratch, NOT committed.

---

## Error Handling & Uncertainty

**Schema validation** at every agent boundary. Mismatch → retry with schema reminder (max 2 retries).

**Conflicting findings**:
- Reader says X, refuter kills X → doc says "claim X proposed, refuted because Y."
- Reader says X, refuter weakens X → doc says "claim X held with caveat: Y."
- Reader silent on Z → doc says "topic Z not characterized."

**Unverifiable claims** (file moved, line drift, force-push): refuter returns `unverifiable`. Doc tags with yellow-flag caveat, not refuted, not held.

**Token cap exhaustion**: each agent output budget enforced. JSON closes with `"truncated": true`. Doc marks section "partial — re-run with higher cap."

**License veto** (sharp): non-permissive license → `NO-ADOPT VERDICT` block at top of repo section. Adoption recommendation binary-blocked regardless of other scores. Honors Zero-Trust pillar.

**Sovereignty veto** (sharp): mandatory SaaS endpoint, mandatory account, or mandatory un-disable-able telemetry → `SOVEREIGNTY-BLOCKED` marker. Honors Persistent Operation pillar.

**Confidence markers** (every claim tagged in final doc):
- `[verified]` — refuter held
- `[weakened]` — refuter partially challenged
- `[refuted]` — refuter killed
- `[unverifiable]` — couldn't check
- `[inferred]` — drawn from indirect evidence

**No silent drops**: empty rubric cell → `not characterized`, not blank.

---

## Acceptance Bar

| Check | Pass criterion |
|---|---|
| Both repos characterized | All rubric axes populated per repo (no "not characterized" cells) |
| License verdict | Explicit license line + adopt/no-adopt per repo |
| Sovereignty verdict | Sovereign / sovereignty-blocked per repo with reason |
| Head-to-head table | Present, complete, scores match per-repo sections |
| Confidence markers | Every claim carries one of 5 markers |
| Refutation coverage | Every reader claim accounted for in refuter output |
| Provenance | Every factual claim cites `file:line` or `commit:SHA` |
| Prime Directive alignment | All 5 pillars scored per repo; 0-scores explained |
| Length sanity | 800–2500 words |
| Commit | Conventional Commits format |

Failure to clear any check → doc NOT shipped. Unfixable conflicts surfaced in "Known limitations" section.

---

## Token Budget

- Readers: ≤80k output tokens each
- Refuters: ≤30k output tokens each
- Synthesizer: ≤50k output tokens (real markdown + JSON sidecar)
- Total workflow budget: ~600k tokens. Well under reasonable ceiling. Honors "burn tokens like there is no tomorrow" without bankrupting the session.

---

## Workflow Tool Strategy

Use the `Workflow` tool with `pipeline()` for phase chains and `parallel()` within phases. Sub-agents dispatched via `agent()` with `schema:` option for structured output validation. Script-level `meta` declares phase titles. Budget guards via `budget.remaining()` to prevent runaway loops.

---

## Deliverable

One file: `docs/superpowers/specs/2026-06-25-agent-harness-landscape.md`

Committed to git. Triggers user review per brainstorming flow. After approval, the next brainstorm/spec decides whether to wrap, replace, or ignore based on this landscape.

---

## Open Questions (None)

All scope, depth, format, lens, and orchestration decisions locked in-session.
