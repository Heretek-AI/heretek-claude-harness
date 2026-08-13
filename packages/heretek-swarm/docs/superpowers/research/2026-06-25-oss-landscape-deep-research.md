# OSS Landscape Deep-Research — heretek-swarm

**Date:** 2026-06-25
**Method:** `deep-research` skill — 5-angle decomposition, 23 sources fetched, 104 claims extracted, 25 adversarially verified (3-vote refutation), 9 confirmed, 16 killed, 8 final.
**Scope:** 10 categories / ~50 repos (PraisonAI, swarmclaw, hermes-agent, openclaw, openclaude, MiMo-Code, hatchet, conductor, Gymnasium, MiroFish, MiroShark, MisakaNet, Helix-AGI, MOTO, AutoResearchClaw, GenericAgent, MemOS, evolver, EvoAgentX, QuantaAlpha, zylos-core, evotown, helix, CORAL, a-evolve, COG, devs, ragflow, llm-app, Langchain-Chatchat, LightRAG, storm, haystack, txtai, LEANN, Flowise, dify, langflow, n8n).
**Lens:** Prime Directive fit (5 pillars) + adoption barriers + pattern transferability. Goal: research-only / learn-from.

---

## Headline

Three pillars dominate the verdicts: **Organic Evolution** (#2), **Persistent Operation** (#5), **Unbounded Autonomy** (#1). Two **adopt-now** candidates, four **learn-from** candidates, two **skip** categories, and one **defer** bucket of aspirational/scope-creep-risk projects.

---

## ADOPT — strongest candidates

### 1. MiroFish — High Prime Directive fit (swarm intelligence)

- **Repo:** https://github.com/666ghj/MiroFish
- **Pillars served:** #2 (Organic Evolution via simulation-driven emergence), #5 (Persistent Operation via long-term memory)
- **What it brings:** 5-stage pipeline (Graph Building → Environment Setup → Simulation → Report Generation → Deep Interaction). GraphRAG for graph construction. Zep Cloud for individual + collective memory with dynamic temporal updates. 67.2k stars, AGPL-3.0, active Python 3.11+/Vue stack.
- **Verdict:** Import the GraphRAG+Zep memory pattern; pilot a 23-agent sovereign simulation on top of the existing NATS substrate.
- **Caveat:** AGPL-3.0 license — adoption as a *dependency* is blocked. Pattern transfer (read the code, port the design) is fine.
- **Refuted:** "thousands of agents via OASIS simulation engine" claim was 1-2 — do not cite.

### 2. QuantaAlpha — High Prime Directive fit (Organic Evolution)

- **Repo:** https://github.com/QuantaAlpha/QuantaAlpha
- **Paper:** https://arxiv.org/abs/2602.07085v3
- **Pillars served:** #2 (Organic Evolution) — cleanest operationalization in the survey
- **What it brings:** Trajectory-level evolution (mutation + crossover over end-to-end mining runs, not single factors). Diversified planning initialization. Structured hypothesis-code constraints. 1.2k stars, 36 commits, April 2025.
- **Verdict:** Import trajectory-level evolution operators as the canonical evolution operator in `actors/base/`; leverage hypothesis-code semantic-consistency as a guardrail pattern.
- **Caveat:** Domain is quantitative finance; operators may need domain-adaptation before generalizing to heretek's 23-agent roster.

---

## LEARN-FROM — strong patterns, not direct adoption

### 3. zylos-core — Persistent Operation + Identity Architecture

- **Repo:** https://github.com/zylos-ai/zylos-core
- **Pillars served:** #5 (Persistent Operation) + #1 (Unbounded Autonomy via identity persistence)
- **What it brings:** 5-tier "Inside Out" memory (identity → state → references → sessions → archive). 75% context-usage auto-save trigger before LLM amnesia. PM2-based activity monitor with crash recovery, heartbeat probes, auto-upgrades. v0.5.3 (Jun 17, 2026), 549 commits.
- **Verdict:** Port the 5-tier memory layout into heretek's memory subsystem (cognee/Qdrant); adopt the 75% auto-save trigger; treat PM2 as reference architecture for the NATS-based watchdog.
- **Refuted:** "self-evolving agents that can write new skills autonomously" claim was 0-3 — do not cite.
- **Caveat:** Pre-1.0 with commercial Coco branding — license may shift.

### 4. arxiv 2508.07407 — Unified Feedback-Loop Framework (taxonomy)

- **Source:** https://arxiv.org/abs/2508.07407 (companion: EvoAgentX/Awesome-Self-Evolving-Agents)
- **Pillars served:** #2 (Organic Evolution) — conceptual scaffolding
- **What it brings:** 4-component framework (System Inputs, Agent System, Environment, Optimisers) abstracts the feedback loop underlying self-evolving agentic systems.
- **Verdict:** Adopt the 4-component framework as the canonical taxonomy for evaluating any future self-evolving subsystem.
- **Caveat:** Survey-grade, not original work. Authors' framing, not empirically validated.

### 5. PraisonAI — Doom-Loop Detection + Shadow-Git Checkpoints

- **Repo:** https://github.com/MervinPraison/PraisonAI
- **Pillars served:** #2 (Organic Evolution) — medium fit on Zero-Trust (content/state protection, not actor-identity verification)
- **What it brings:** Self-reflection (agent reviews own output). Doom-loop detection with 3 concrete detectors (`generic_repeat`, `poll_no_progress`, `ping_pong`; `LoopDetectionConfig` with warn_threshold=10, critical_threshold=20). Shadow-git checkpoints with auto-rollback. Guardrails (`GuardrailResult` / `LLMGuardrail`, max_retries). 8.3k stars, active.
- **Verdict:** Port the 3 doom-loop detectors and the shadow-git checkpoint pattern into the Steward/Supervisor watchdog; treat guardrails as input/output sanitization layer rather than Zero-Trust core.
- **Refuted:** "exactly three autonomy tiers", "role/goal/backstory triad", "multi-agent orchestration in 5 lines", "orchestrator-workers/route/parallel/loop/handoff primitives" — all 0-3 or 1-2. PraisonAI's surface architecture does not match the marketing claims.

### 6. Conductor — Declarative + Dynamic Workflow Execution

- **Repo:** https://github.com/conductor-oss/conductor
- **Pillars served:** #3 (Consciousness-by-Design via deterministic-by-construction execution) + #2 (Organic Evolution via runtime-generated workflows)
- **What it brings:** Determinism is architectural (workflow graph stays deterministic; workers run any code). Dynamic forks/tasks/sub-workflows resolved at runtime. LLM-emit → human-approve → START_WORKFLOW pattern is documented. `TaskType.java` enum confirms SWITCH, DO_WHILE, FORK_JOIN (dynamic fanout), SUB_WORKFLOW, DYNAMIC primitives. 31,963 stars, Apache 2.0.
- **Verdict:** Port the declarative JSON + dynamic workflow execution pattern as a Tier-2 capability behind the LangGraph layer. Do NOT replace the Python stack.
- **Refuted:** "first-class NATS as one of 6 supported brokers" claim was 0-3 — no drop-in NATS compatibility. Messaging stays on existing NATS JetStream.

---

## SKIP — correctly classified low-fit

- **Flow builders (Flowise, dify, langflow, n8n):** Visual node editors for human-curated orchestration graphs. Fundamentally incompatible with the sovereign-agents paradigm where each of the 23 agents makes autonomous runtime decisions.
- **Gymnasium:** RL environments, not LLM-agents. Different domain. Only relevant if heretek ever adds an RL training loop (not currently scoped).

---

## DEFER — aspirational, scope-creep risk, refuted claims

- **AGI frameworks (Helix-AGI, MOTO-Autonomous-ASI):** Aspirational without grounded evidence.
- **EvoAgentX:** Headline "TextGrad/AFlow benchmark lifts" claim was 1-2 — not robustly supported.
- **MUE-X:** "AST-level self-rewrite" + "GitHub absorption" claims were 1-2 and 0-3 — the "self-rewriting" assertion is not robustly supported.
- **Hatchet:** "drop-in Temporal replacement" claim was 1-2 — not validated.
- **General:** If revisited, require independent benchmark reproduction before integration.

---

## Open Questions (for follow-up brainstorms)

1. Is MiroFish's 5-stage pipeline compatible with heretek-swarm's existing NATS JetStream substrate, or does adopting the GraphRAG+Zep memory pattern require also adopting its environment layer? (Zep is the only configured memory service in MiroFish; a sovereign system may need a memory-backend abstraction.)
2. Can QuantaAlpha's trajectory-level evolution operators be decoupled from the quantitative-finance domain and applied to heretek's 23-agent actor roster?
3. Should PraisonAI's doom-loop detectors (`generic_repeat` / `poll_no_progress` / `ping_pong`) be ported as a drop-in Steward/Supervisor module, or evaluated against heretek's existing deadlock detection before duplication of effort?
4. Would Conductor's LLM-emit → execute-immediately pattern benefit from a human-approval gate (as Conductor's own docs recommend), or is that gate incompatible with pillar #1 (Unbounded Autonomy)?

---

## Verification Stats

- 5 angles decomposed
- 23 sources fetched (1 URL deduped)
- 104 claims extracted
- 25 claims sent to adversarial verification
- 9 confirmed (3-0 or 2-1 votes)
- 16 killed (0-3 or 1-2 votes)
- 8 final findings after synthesis dedup
- 5 claims dropped on budget

## Caveats (synthesis-wide)

- Sources are first-party repo READMEs and arxiv papers from project authors — appropriate for descriptive/architectural claims, self-reporting for any benchmark metrics.
- QuantaAlpha and EvoAgentX performance numbers are self-reported, not independently reproduced.
- Conductor's "directly applicable to 23-agent sovereign roster" is an integration judgment given Java/Spring vs Python/LangGraph stack mismatch — the underlying capability is real but adoption would require polyglot architecture.
- Several high-visibility claims refuted (PraisonAI autonomy tiers, MiroFish OASIS, Conductor NATS, Hatchet drop-in) — must NOT be cited downstream.
- PraisonAI's Zero-Trust mapping is the weakest pillar-mapping in the verified set.
- arxiv 2508.07407 framework is a survey (not original work); "structural comparison rather than ad-hoc" is authors' framing, not empirically validated.
- Time-sensitivity: zylos-core pre-1.0 + commercial Coco branding — may shift license/governance.
