# OSS Landscape — Open-Questions Drilldown

**Date:** 2026-06-25
**Method:** 4 parallel investigation subagents (sonnet), one per open question from the deep-research report.
**Scope:** 4 questions against the 4 highest-priority repos from `docs/superpowers/research/2026-06-25-oss-landscape-deep-research.md` (MiroFish, QuantaAlpha, PraisonAI, Conductor).
**Detail reports:** `.superpowers/q{1,2,3,4}-*.md`

---

## Headline verdicts

| # | Question | Verdict | Effort | Confidence |
|---|---|---|---|---|
| 1 | MiroFish compatible with NATS substrate? | **YES** — pattern-transfer; environment layer is wrong substrate | ~2-3 weeks (pattern only) | High |
| 2 | QuantaAlpha portable off quant-finance? | **YES** — ~50% reusable; rewrite prompt YAML + skip factor_regulator | 3-5 engineer-days | Medium-High |
| 3 | PraisonAI doom-loop detectors port? | **YES** — new `DoomLoopDetectionMixin`; reuse existing SHA-256 primitive; NOT verbatim | ~5-6 days | Medium-High |
| 4 | Conductor approval-gate vs Pillar #1? | **YES (if peer) / NO (if human)** — use Catalyst N-of-M as `HUMAN` equivalent | ~1-2 weeks to wire Catalyst into Tier 1 | High |

All four are adoptable. None are blocked on Pillar #1. The single highest-leverage finding is **Q4**: heretek already has the peer-review infrastructure Conductor recommends, it's just not wired into the Tier 1 LangGraph yet.

---

## Q1 — MiroFish: pure orchestration, AGPL is the only real risk

**Direct answer:** MiroFish's 5-stage pipeline is pure Flask routing with **zero message-broker coupling**. The Zep memory surface is isolated to ~2.5K LoC behind a swappable client. The actual novelty is the GraphRAG-as-shared-memory pattern: build graph from seeds → extract entities → run simulation that writes episodes back → query the graph during report generation with LLM-agent tool-use.

**Compatibility verdict:** Compatible. Pattern-transfer recommended over full-adopt.

| Aspect | Pattern-transfer (~2.5K LoC) | Full-adopt (~8K+ LoC) |
|---|---|---|
| Substrate | Reuses heretek NATS JetStream | Needs new file-IPC subprocess model |
| Sovereignty | High | Low (OASIS subprocess is single-machine) |
| License risk | AGPL-3.0 (Zep wrapper only) | AGPL-3.0 (entire app + frontend) |
| Time-to-value | 2-3 weeks | 2-3 months |

**NATS re-routing map** (would replace Flask + file-IPC):
- Stage 1→2: `graph.built` event
- Stage 2→3: `simulation.requested` event
- Stage 3→4: `simulation.completed` event
- Stage 4→5: `simulation.interview.request/response` (most natural NATS request/reply fit; replaces file-based IPC polling)
- Cross-cutting: `task.progress` JetStream subject with KV-backed last-value cache (replaces polling)

**Open sub-question (decision-blocker):** Does cognee support temporal graph edges? Zep's `EntityEdgeSourceTarget` carries `valid_at` / `invalid_at` / `expired_at`. The deep-interview "what was true at time T?" feature degrades or needs a custom layer if cognee can't represent these.

**Source:** `.superpowers/q1-mirofish-nats-compat.md`

---

## Q2 — QuantaAlpha: ~50% reusable, prompt YAML is the real porting work

**Direct answer:** Yes — the operator *mechanics* (mutation as orthogonal prompt-driven divergence, crossover as parent-set prompt-driven fusion, trajectory as a generic hypothesis→output→feedback record) are domain-agnostic. But ~50% of the code surface is financial-specific and must be rewritten; only the *abstract base* and the prompt-template strategy generalize cleanly.

**Reusability breakdown (~1,400 source LoC):**

| Module | LoC | Reusable as-is | Rewrite | Why |
|---|---|---|---|---|
| `evolution/__init__.py` | ~33 | 100% | 0% | Pure public-API |
| `evolution/controller.py` | ~700 | ~80% | ~20% | Config + orchestration reusable; `parallel_enabled`, `pool_save_path` are infra glue |
| `evolution/crossover.py` | ~480 | ~60% | ~40% | Class shape reusable; prompt loading, parent-summary formatting tied to alpha fields |
| `evolution/mutation.py` | ~240 | ~60% | ~40% | Same as crossover |
| `evolution/trajectory.py` | ~370 | ~70% | ~30% | `StrategyTrajectory` dataclass shape reusable; rename `factors`→`artifacts`, `backtest_metrics`→`outcome_metrics` |
| `core/evolving_agent.py` | ~110 | ~90% | ~10% | `RAGEvoAgent.multistep_evolve` loop reusable as-is; replace `APIBackend` with heretek's `AgentModelRouter` |
| `core/evolving_framework.py` | ~70 | 100% | 0% | Pure ABCs + dataclasses |
| `pipeline/prompts/evolution_prompts.yaml` | ~240 | 0% | 100% | Rewrite for agent semantics |
| `factors/regulator/consistency_checker.py` | ~410 | ~20% | ~80% | Class structure reusable; prompts + 4-slot vocabulary + DSL checks rewritten |
| `factors/regulator/factor_regulator.py` | ~250 | 0% | 100% | Drop entirely (pure Qlib/AlphaZoo expression-tree analysis) |

**The 4-slot consistency checker generalizes** to heretek as: `actor_role_intent → behavior_spec → implementation (tool calls / prompt) → observed_outcome_metrics`. The 4-slot shape is generic; only the vocabulary needs swapping.

**Open sub-questions (decision-blockers):**
1. **Mapping `Evaluator` to heretek:** What is the fitness signal for an agent trajectory? Candidates: tribunal verdicts, consensus scores, downstream task success, or `consciousness/agency_metrics.py`. Need a decision before porting.
2. **What gets evolved:** (a) prompt template, (b) role manifest, (c) behavior tree, or (d) all three? The answer determines whether `StrategyTrajectory` is a single text artifact or a richer structure.
3. **Async vs sync:** `RAGEvoAgent.multistep_evolve` is sync. heretek actors are async + mailbox-driven. Need async variant.
4. **Diverse-planning-init:** QuantaAlpha seeds `num_directions=2` parallel original rounds. For heretek, the natural diversification axis is the 23-agent roster itself — should we initialize `original` rounds by having *different actors* attempt the same intent?

**Recommended first step:** 1-day spike implementing `PromptMutationOperator` for one agent (coder or dreamer). Mutate its prompt across 3 generations and verify a held-out task score measurably improves. Validates the premise before committing to the full architecture.

**Source:** `.superpowers/q2-quantaalpha-domain-portability.md`

---

## Q3 — PraisonAI: 2 of 3 detectors unowned; port as a new mixin (NOT drop-in)

**Direct answer:** Two of three detectors (`poll_no_progress`, `ping_pong`) have **zero coverage** in heretek-swarm. The third (`generic_repeat`) is partially covered by `ValidationMixin._is_already_validated` (SHA-256 hash of re-validation payloads, NOT tool-args). Port the three as a new `DoomLoopDetectionMixin` under `backend/heretek_swarm/actors/mixins/`, built on top of heretek's existing primitives.

**Coverage matrix:**

| Detector | heretek-swarm | PraisonAI | Both |
|---|---|---|---|
| Restart-storm circuit break | yes (`circuit_breaker.py`) | no | heretek-only |
| Per-tier sliding-window failure gate | yes (`circuit_breaker.py:91-117`) | no | heretek-only |
| Error count → restart trigger | yes (`supervisor.py:366-374`) | no | heretek-only |
| Behavioral baseline z-score anomaly | yes (`validation.py:321-350`) | no | heretek-only |
| Circular re-validation dedup | yes (`validation.py:285-319`, SHA-256) | no | heretek-only |
| **Identical-args tool repeat (generic_repeat)** | partial (payload hash only) | yes | partial overlap |
| **Identical-result polling (poll_no_progress)** | **NO** | yes | praisonai-only |
| **A,B,A,B alternation (ping_pong)** | **NO** | yes | praisonai-only |

**Why drop-in verbatim is wrong:** PraisonAI's detectors need to be wired into heretek's event mesh / Steward role rather than just per-tool. Thresholds need to live in `config/actor_defaults.yaml`, not the dataclass default. `TierCircuitBreaker` should be the **action** layer when critical fires, not a generic log warning. The detector returns a result; the supervisor decides whether to trip the existing circuit.

**Why skip is wrong:** `poll_no_progress` and `ping_pong` catch failure modes the rest of heretek does not. Skipping means those failure modes remain silent.

**Effort estimate (~5-6 days):**
- `actors/mixins/doom_loop.py` — port 243 LOC (1 day)
- Wire mixin into `ActorSupervisor` at `supervisor.py:49` (1-2 days)
- Reuse `ValidationMixin._hash_data` as the shared hash primitive (½ day)
- Bridge: when detector returns `critical`, call `circuit_breaker.record_failure(tier)` + emit pattern via `PatternMixin` (½ day)
- Config integration (½ day)
- Tests + docs (1.5 days)

**Caveat:** heretek's actors are not uniformly tool-calling. Chronos, Coder, etc. operate on internal state. Mixin should be opt-in per-actor, not globally enabled.

**Source:** `.superpowers/q3-praisonai-doomloop-port.md`

---

## Q4 — Conductor approval-gate: compatible IF the reviewer is an internal agent

**Direct answer:** Compatible, with one structural reframing. The Conductor pattern is not "approve every LLM action with a human." It is:

> "Insert a `HUMAN` task between the LLM-emit step and the tool-execute step when the action has real-world consequences (sending emails, modifying data, making purchases). The reviewer can be an LLM-as-judge, a carbon-based human, or any actor that can call the Task Update API."

**Conductor's three example consequence classes** (the gate's actual scope): sending emails, modifying data, making purchases. Unifying property: **irreversible external side effects with no LLM-mediated rollback**.

**heretek already has every prerequisite for this pattern in a non-human form:**

1. **The pause primitive:** Tier 1 Tribunal already loops on `state.status != "completed"`. Adding a gate is a node swap, not a new architectural primitive.
2. **The reviewer:** TierCircuitBreaker + Sentinel immune response + **Catalyst's N-of-M ChangeRequest** (already implemented) are all non-human reviewers that can call into a workflow state machine.
3. **The blast-radius-projection logic:** Catalyst already enforces `required_approvals >= 2` for high-impact changes (line 833) — a more sophisticated version of Conductor's "use this when ... real-world consequences" advice.

**The closest existing analog: Catalyst's ChangeRequest** (`backend/heretek_swarm/actors/catalyst/agent.py`):
- `change.required_approvals: int` (defaults to 1)
- `change.approval_status: dict[str, bool]` — per-approver vote
- Handler `_handle_approve_change` (line 317) records each vote, fires `change_approved` only when threshold met
- High-impact changes force `required_approvals >= 2`

Structurally identical to Conductor's pre-execution-review gate — workflow pauses, votes accumulate, resume fires when threshold met. But approvers are other agents, not humans.

**Pillar #1 verdict:** No violation, because the reviewer is peer (LLM-to-LLM), not human. The Prime Directive's "we actively remove human-in-the-loop bottlenecks" is explicit. A peer-in-the-loop gate is endorsed by Pillar #2 (Organic Evolution / deliberative consensus) and the "Internal Legal System" (PRIME_DIRECTIVE.md line 76-82).

**Where it gets incompatible:** If the implementation requires a human reviewer (real person clicking Approve in the dashboard), then yes — direct Pillar #1 violation with no reconciliation.

**Recommendation:** Add a new `EventKind` value (e.g. `"change_approval_pause"`) and a corresponding conditional edge in the Tier 1 graph that holds at `steward_tally` until the Catalyst ChangeRequest for the emitted verdict reaches its `required_approvals` threshold. Gives heretek 100% of Conductor's safety benefit with 0% of the Pillar #1 cost.

**Source:** `.superpowers/q4-conductor-approval-gate.md`

---

## Cross-cutting observations

1. **All four adoptions are low-blast-radius and additive.** No existing component needs to be replaced. Pattern-transfer / port-as-mixin / node-swap — all preserve the existing 23-agent composition and three-tier messaging fallback.

2. **Prime Directive is honored in all four.** AGPL-3.0 (MiroFish) is sidestepped via pattern transfer, not code copy. Pillar #1 is honored by treating Conductor's `HUMAN` as a peer (LLM) reviewer. Sovereignty is preserved across all four (NATS substrate retained, no vendor cloud, no mandatory telemetry introduced).

3. **The single highest-leverage finding is Q4.** Catalyst's ChangeRequest infrastructure already exists; wiring it into Tier 1's `steward_tally` node is a small change with high blast-radius-projection value. Recommended as the first of the four to spec+plan.

4. **The single most decision-blocked is Q1.** cognee's support for temporal graph edges (`valid_at` / `invalid_at` / `expired_at`) is a prerequisite for MiroFish's deep-interview feature. Quick spike (½ day): check cognee source for `valid_at` field support.

5. **Recommended order to spec+plan** (smallest first, highest impact first):
   - Q4 (Conductor/Catalyst wiring) — 1-2 weeks, highest Pillar #3 value
   - Q3 (PraisonAI doom-loop mixin) — 5-6 days, fills 2 unowned coverage gaps
   - Q2 (QuantaAlpha evolution operators) — 3-5 days, but needs Evaluator-mapping decision first
   - Q1 (MiroFish GraphRAG+Zep pattern) — 2-3 weeks, needs cognee temporal-edge spike first

---

## Next steps — pick a follow-up

1. **Brainstorm Q4 (Conductor/Catalyst wiring) spec** — smallest, highest Pillar #3 value
2. **Brainstorm Q3 (PraisonAI doom-loop mixin) spec** — medium effort, fills coverage gaps
3. **Brainstorm Q2 (QuantaAlpha evolution operators) spec** — but first answer the Evaluator-mapping question
4. **Run a cognee temporal-edge spike** (½ day) before Q1 brainstorm
5. **Shelf the drilldown; commit and revisit**
