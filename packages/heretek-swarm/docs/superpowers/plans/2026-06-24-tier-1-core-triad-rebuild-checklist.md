# Tier 1 Core Triad Rebuild — Self-Review Checklist

Final verification across the 13 tasks. Confirms spec coverage, type
consistency, and absence of placeholders.

## Spec coverage

- §1 Context/motivation → captured in spec itself, not plan (correct).
- §2 Project structure → Task 1 (skeleton, layout) + Tasks 4 (clients) +
  5 (agents) + 6 (consensus/steward) + 7 (graph) + 8 (api) + 9 (dashboard)
  realize it.
- §3 Components (agents + types + infrastructure + dashboard) → Tasks 2,
  3, 4, 5, 6, 7, 8, 9 cover all.
- §4 Data flow (lifecycle + events + HTTP + WS + consensus) → Tasks 5,
  6, 7, 8 cover all.
- §5 Error handling (LLM, infra, consensus, transport, dashboard states)
  → Tasks 3 (LLM failover), 4 (infra clients), 5 (LLMMalformed), 8
  (interject 409), 12 (desloppify).
- §6 Testing (TDD, layers, coverage, discipline) → Tasks 1–12 each write
  tests; Task 11 is E2E; Task 12 is CI gates.
- §7 Decisions log → preserved in spec; plan respects all 12 decisions.
- §8 Open questions → deferred items reflected in plan (single-user MVP,
  etc.).
- §9 Implementation order → plan's 13 tasks map to spec §9 with same
  ordering.

## Placeholder scan

No TBD / TODO / "implement later" / "fill in details" in the plan.

## Type consistency check

- `AgentVerdict`, `FinalVerdict`, `DeliberationEvent`,
  `DeliberationState`, `AgentName`, `VerdictPosition`, `FinalDecision`,
  `EventKind`, `DeliberationStatus` defined in Task 2; used unchanged in
  Tasks 3, 5, 6, 7, 8, 9.
- `ModelGarage` defined in Task 3 with `stream_chat` + `chat`; used
  unchanged in Tasks 5, 7, 8.
- `Tribunal.run` + `Tribunal.stream` defined in Task 7; used in Task 8
  (api route) and Task 10 (smoke).
- `subject_for(deliberation_id)` defined in Task 2
  (`events/channels.py`); used in Tasks 4, 8, 11.
- `make_nats_sink_for(nats, did)` defined in Task 8; used in Task 8
  route only.

## Smoke verification

- POST `/api/deliberations` returns 201 with deliberation id.
- GET `/api/deliberations/{id}` returns persisted state with events
  (`started`, `alpha_thinking` observed).
- `/health` returns ok with all components green when infra is up.
- Failed LLM produces `status=failed` transition (graceful failure path).

No mismatches found.
