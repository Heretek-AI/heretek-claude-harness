# Q4: Conductor Approval-Gate for Tier 1 Deliberation

**Status:** Approved (in-session brainstorm, 2026-06-25)
**Scope:** Add a conditional approval-gate node to the Tier 1 LangGraph graph. Fires only for high/critical-impact verdicts. Uses Catalyst's existing N-of-M ChangeRequest infrastructure as the reviewer. Peer (LLM) reviewer only — no human-in-the-loop. Honors Pillar #1 (Unbounded Autonomy).
**Sources:** Q4 drilldown at `docs/superpowers/research/2026-06-25-oss-landscape-open-questions-drilldown.md`

---

## Purpose

Wire Conductor's "pre-execution review" pattern into Tier 1 as a conditional edge, using heretek's existing Catalyst N-of-M approval infrastructure as the reviewer. Gives heretek 100% of Conductor's safety benefit (block irreversible actions until peer consensus) with 0% of Pillar #1's human-bottleneck cost.

## Non-Goals

- No human-in-the-loop. Reviewer is always an internal LLM agent.
- No rewrite of Catalyst's `_handle_approve_change` logic. Catalyst's existing N-of-M machinery is reused as-is.
- No rewrite of the Tier 1 graph. The approval-gate is an additive node, not a replacement of `_finalize`.
- No new NATS subject infrastructure. Uses existing JetStream durable subscribers.
- No new Pydantic model library. Only 2 small event models added.

---

## Architecture

### Graph topology (before)

```
START → alpha → beta → charlie → steward_tally → _should_finalize
                                                     ├─ status == completed → _finalize → END
                                                     └─ status != completed → feedback_loop → alpha (max 3 rounds)
```

### Graph topology (after)

```
START → alpha → beta → charlie → steward_tally → impact_gate
                                                     ├─ low/medium → _finalize → END
                                                     ├─ high/critical → approval_gate → _finalize → END
                                                     └─ status != completed → feedback_loop → alpha (max 3 rounds)
```

`impact_gate` is a simple conditional — routes to existing `_finalize` (skip) or to new `approval_gate` (pause + wait). Keeps approval logic isolated from verdict-reach logic.

### `approval_gate` node flow

```
approval_gate: emit change_approval_pause event on NATS JetStream
  → Catalyst receives, creates ChangeRequest
  → Catalyst routes to N-of-M reviewers (impact-tiered set)
  → Votes accumulate
  → Threshold met → Catalyst emits change_approved / change_rejected
  → approval_gate node receives event, resumes
    ├─ approved → _finalize (same path as today)
    ├─ rejected → _finalize with FinalDecision.rejected + reason
    └─ timeout → emit arbiter_escalation_request on NATS
      → Arbiter receives full verdict context + timeout=true
      → Arbiter renders binding verdict within its own window
        ├─ Arbiter approves → _finalize
        ├─ Arbiter rejects → _finalize with reason
        └─ Arbiter timeout → _finalize with no-consensus
```

---

## Components

### 1. `impact_gate` (conditional edge in Tier 1 graph)

Pure function. Checks `verdict.impact_level`. If `low`/`medium` → pass through to `_finalize` immediately. If `high`/`critical` → route to `approval_gate`.

**Implementation:** A new conditional edge from `steward_tally` output. No new LangGraph node — just a routing function.

### 2. `ApprovalGateNode` (new LangGraph node)

**File:** `backend/tier1/tier1/deliberation/nodes/gate.py`

Pure function. On receive of a high/critical verdict:
1. Emit `ChangeApprovalPause` event on `tier1.approval_gate.pause` NATS subject
2. Subscribe to `tier1.approval_gate.approved` and `tier1.approval_gate.rejected`
3. Start timeout timer (default 120s, configurable)
4. Block until: approved, rejected, or timeout
5. On timeout: emit `tier1.approval_gate.timeout` → Arbiter escalation
6. Return resume state: `approved` | `rejected` | `no-consensus`

### 3. `ChangeApprovalPause` event model

**File:** `backend/heretek_swarm/models/events.py`

```python
class ChangeApprovalPause(BaseModel):
    tier1_verdict_id: str
    impact_level: Literal["high", "critical"]
    required_approvals: int  # >= 2 for high, >= 3 for critical
    timeout_seconds: int     # from config, default 120
    requested_by: Literal["tier1_tribunal"]
    context: str             # summary of what the verdict recommends
```

### 4. `ApprovalGateResume` event model

**File:** `backend/heretek_swarm/models/events.py`

```python
class ApprovalGateResume(BaseModel):
    tier1_verdict_id: str
    decision: Literal["approved", "rejected"]
    votes: dict[str, bool]
    timeout: bool = False
```

### 5. Catalyst wiring

**File:** `backend/heretek_swarm/actors/catalyst/agent.py`

Catalyst's existing `_handle_approve_change` handler (line 317) receives the event as a new `ChangeRequest` with:
- `source = "tier1_approval_gate"`
- `required_approvals` from the event (impact-tiered: `>= 2` for high, `>= 3` for critical)
- `impact_level` mapped from the event
- Catalyst routes to the tiered reviewer set: Catalyst + triad peers for high; Catalyst + triad peers + Sentinel for critical

On threshold met: Catalyst emits `ApprovalGateResume` on `tier1.approval_gate.approved` or `tier1.approval_gate.rejected`.

### 6. Arbiter escalation

On timeout, `ApprovalGateNode` emits `arbiter_escalation_request` on `tier1.approval_gate.timeout`. Arbiter (Tier 4) receives full verdict context + `timeout=true`. Arbiter renders binding verdict within its own deliberation window. On Arbiter timeout → final `no-consensus`.

### 7. Config

Thresholds live in `config/actor_defaults.yaml` under `tier1_approval_gate:`:

```yaml
tier1_approval_gate:
  enabled: true
  timeout_seconds: 120
  high_impact:
    required_approvals: 2
    reviewers: ["catalyst", "alpha", "beta", "charlie"]
  critical_impact:
    required_approvals: 3
    reviewers: ["catalyst", "alpha", "beta", "charlie", "sentinel"]
  arbiter_timeout_seconds: 60
```

---

## NATS Subject Map

| Subject | Publisher | Subscriber | Durable? |
|---|---|---|---|
| `tier1.approval_gate.pause` | ApprovalGateNode | Catalyst | Yes |
| `tier1.approval_gate.approved` | Catalyst | ApprovalGateNode | Yes |
| `tier1.approval_gate.rejected` | Catalyst | ApprovalGateNode | Yes |
| `tier1.approval_gate.timeout` | ApprovalGateNode | Arbiter | Yes |
| `tier1.approval_gate.vote` | Reviewer agents | Catalyst | Yes |

**Correlation key:** `tier1_verdict_id` is the correlation key across all 5 subjects. If missing or malformed, Catalyst rejects with `change_rejected` + `reason: "invalid_correlation_key"`. Zero-Trust pillar honored.

---

## Error Handling

**Timeout cascade:**
1. `ApprovalGateNode` timeout (default 120s) → emit `timeout` event
2. Arbiter receives, renders within `arbiter_timeout_seconds` (default 60s)
3. Arbiter timeout → `_finalize` with `no-consensus`

**Vote corruption:** If a vote arrives with mismatched `tier1_verdict_id`, Catalyst discards it with warning log. Does not count toward threshold.

**Catalyst crash:** If Catalyst dies mid-accumulation, `ApprovalGateNode` timeout fires → Arbiter escalation. No data loss (NATS durable subscriptions).

**Arbiter crash:** If Arbiter dies mid-escalation, `_finalize` gets `no-consensus` after `arbiter_timeout_seconds`. Same as existing no-consensus behavior.

**NATS broker restart:** JetStream durable subscriptions survive restarts. Votes in transit are replayed. No manual intervention needed.

---

## Backward Compatibility

- Existing Tier 1 tests that do NOT trigger high-impact verdicts pass unchanged — `impact_gate` routes them directly to `_finalize`.
- Approval-gate is additive, not a rewrite of the existing graph.
- Old `user_interjection` EventKind remains operational as advisory feedback; new `change_approval_pause` EventKind is the blocking variant.
- Existing Catalyst ChangeRequest tests pass unchanged — Catalyst's N-of-M logic is not modified, only invoked from a new source.

---

## Prime Directive Compliance

- **Pillar #1 (Unbounded Autonomy):** No human-in-the-loop. Reviewer is always an internal LLM agent. Gate is peer-in-the-loop, not human-in-the-loop.
- **Pillar #2 (Organic Evolution):** Gate uses deliberative consensus (Catalyst N-of-M) rather than hardcoded rules. Configurable thresholds in `actor_defaults.yaml`.
- **Pillar #3 (Zero-Trust):** Correlation key validation on all NATS events. Vote corruption rejected. Full audit trail via NATS durable subscriptions.
- **Pillar #5 (Persistent Operation):** JetStream durable subscriptions survive restarts. Timeout cascade ensures no infinite hangs.

---

## Acceptance Bar

| Check | Pass criterion |
|---|---|
| Graph topology | `impact_gate` routes low/medium to `_finalize`; high/critical to `approval_gate` |
| Approval-gate fires only for high/critical | Tests prove low/medium pass through without pause |
| Catalyst receives event | Catalyst creates `ChangeRequest` with `source = "tier1_approval_gate"` |
| N-of-M votes accumulate | Catalyst's existing `_handle_approve_change` handles the new source |
| Threshold met → resume | Catalyst emits `ApprovalGateResume`; Tier 1 resumes |
| Timeout → Arbiter escalation | Timeout fires; Arbiter receives `timeout=true`; Arbiter renders verdict |
| Arbiter timeout → no-consensus | Both timeouts fire; `_finalize` gets `no-consensus` |
| Correlation key validation | Mismatched `tier1_verdict_id` rejected by Catalyst |
| Config integration | Thresholds live in `actor_defaults.yaml`, not hardcoded |
| Backward compat | Existing Tier 1 tests pass unchanged |
| Prime Directive | No human-in-the-loop; peer reviewer only |

---

## Token Budget

Not applicable — this is a code spec, not a research workflow.

---

## Open Questions (None)

All decisions locked in-session.
