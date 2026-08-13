# Sovereign Services — Phase 5 of PLAN.md

Status: design document. The actual extraction into independent
processes is queued for when 24/7 autonomy pressure demands it.

## Audit reference

This document is the response to Phase 5 of the Zero-Trust
Architecture Audit (2026-06-03, §1.13). The audit's exact text:

> ### Phase 5 — Optional: graduated sovereign services (week 10+, only if needed)
>
> Goal: extract high-value services into independent processes.
> **Only pursue if 24/7 autonomy pressure demands it.**
>
> | # | Action | When to do it |
> |---|--------|---------------|
> | 5.1 | Extract consensus into a standalone service behind a gRPC interface | When consensus latency becomes the bottleneck |
> | 5.2 | Extract memory into a dedicated service (cognee + mem0 dual-backend) | When memory access becomes the dominant LLM-call cost |
> | 5.3 | Extract realtime (WebSocket) into a sidecar service | When WebSocket fan-out becomes the bottleneck |
> | 5.4 | Extract observability into a sidecar that opik connects to | When observability overhead starts showing in latency budgets |
>
> Exit criteria: each service has independent deployment,
> independent scaling, independent auth. The swarm's three-tier
> messaging fallback still works across service boundaries
> (NATS at the edge, gRPC inside the core).

## Why these are not done yet

1. The current monolith handles the load. Single-process
   deployment means one Docker container, one health check, one
   rollback. Splitting into multiple processes adds operational
   complexity (separate deployments, separate dashboards,
   inter-service auth, distributed tracing) that has real cost.
2. The 24/7 autonomy pressure hasn't materialized. The current
   cold-start verified state (PRIME_DIRECTIVE.md, 2026-06-01) is
   healthy with 6/6 services and 23 agents responding.
3. Some prerequisites are still in flight. The audit's
   exit criterion for Phase 5 is "each service has independent
   deployment, independent scaling, independent auth" — which
   is a stronger guarantee than the current process-wide
   TokenStore (Phase 2.10). Independent auth per service
   requires a JWT/PSK split that is not yet built.

## What this document ships

The 4 service designs. Each section captures the wire
protocol, the deployment surface, the auth boundary, and the
exit criterion that has to be met before the extraction
is justified.

### 5.1 — Consensus service (gRPC)

**When to do it:** when consensus round latency > 100ms at
the p99, or when cross-organization consensus requires
trust boundaries that can't be drawn inside one process.

**Wire protocol:** gRPC. The current consensus surface in
`api/consensus.py` maps almost 1-to-1 to a `.proto` file:

```protobuf
service Consensus {
  rpc CreateRound(CreateRoundRequest) returns (RoundId);
  rpc AddVote(AddVoteRequest) returns (VoteAck);
  rpc Compute(ComputeRequest) returns (ConsensusResult);
  rpc StreamRounds(StreamRequest) returns (stream Round);
}
```

**Deployment surface:** new Docker image
`heretek-swarm-consensus-svc` built from the planned
`packages/core` (Phase 4). Exposes gRPC on `:50051`. The
existing NATS event mesh continues to be the cross-service
transport.

**Auth boundary:** mTLS via the cert machinery already in
`infrastructure/nats/ca.py`. Each consensus-svc instance has
its own SPIFFE-style identity; the api process authenticates
to it the same way it authenticates to NATS today.

**Exit criterion:** a synthetic load test (locust + k6) that
demonstrates p99 consensus latency in the monolith is
unacceptable, AND the gRPC interface passes a side-by-side
parity test against the monolith for 1 week.

### 5.2 — Memory service (cognee + mem0 dual-backend)

**When to do it:** when memory access (read + write) becomes
> 30% of LLM-call latency, or when a different team needs
to share the memory surface but not the rest of the swarm.

**Wire protocol:** gRPC or HTTP (cognee already exposes
HTTP). The `MemoryStore` Protocol from Phase 1.1 is the
canonical contract.

**Deployment surface:** new Docker image
`heretek-swarm-memory-svc` that runs cognee and (optionally)
mem0 as side-cars. The dual-backend layout means writes
go to both; reads pick the faster.

**Auth boundary:** mTLS, same as 5.1. The api process holds
a memory-svc client identity; the memory-svc accepts only
authenticated callers.

**Exit criterion:** profiling the monolith shows memory
read/write is the dominant LLM-call cost, AND a side-by-side
parity test of the dual-backend shows ≥95% of the cognee
extraction quality is preserved.

### 5.3 — Realtime (WebSocket) sidecar

**When to do it:** when the WebSocket fan-out (dashboard
listeners, agent status stream, A2A message stream) becomes
the bottleneck, or when the dashboard needs to be served by
a different process from the API.

**Wire protocol:** WebSocket (unchanged). The sidecar holds
the ConnectionManager from `api/websockets.py` and subscribes
to NATS for the events it needs to fan out.

**Deployment surface:** new Docker image
`heretek-swarm-realtime-svc`. The api process publishes events
to NATS; the sidecar subscribes and forwards to its
WebSocket clients. Multiple sidecar instances share the
fan-out load via NATS queue subscriptions.

**Auth boundary:** the existing `TokenStore` (Phase 2.10)
moves to the sidecar so the WebSocket auth path is
self-contained. The api process never sees WebSocket
connections; it just publishes events.

**Exit criterion:** the dashboard's reconnect-loop latency
(F-010 from PRIME_DIRECTIVE.md) is fixed AND the sidecar
handles ≥10k concurrent WebSocket clients without
backpressure on the api process.

### 5.4 — Observability sidecar

**When to do it:** when OpenTelemetry exporter overhead
starts showing in the latency budget, or when the opik
deployment is shared with other services and the swarm's
metrics need to live alongside them.

**Wire protocol:** OTLP (the existing standard). The sidecar
runs the opik agent and the OTel collector; the api
process emits spans/metrics over the loopback (or, in
cluster mode, over gRPC).

**Deployment surface:** new Docker image
`heretek-swarm-observability-svc` running the OTel
Collector + the opik agent. The api process drops the
existing OTel exporter in favor of an OTLP forwarder to
the sidecar.

**Auth boundary:** mTLS. The api process holds an
observability-svc client identity; the sidecar accepts
only authenticated OTLP traffic.

**Exit criterion:** a load test shows the api process's
per-request latency drops by ≥10% when the OTel exporter
is moved to the sidecar.

## Cross-service design invariants

1. **Three-tier messaging fallback still works** (NATS →
   registry → queue). Inter-service traffic uses NATS where
   ordering / fan-out matter; gRPC where request/response
   matters.
2. **Each service is independently deployable.** No shared
   filesystem, no shared in-memory state.
3. **Each service has its own auth boundary.** mTLS via the
   existing `infrastructure/nats/ca.py` cert machinery.
4. **Cross-service contracts are versioned.** The
   `MemoryStore` Protocol (Phase 1.1) and the
   `ConsensusEngine` Protocol (Phase 3.1) are the wire
   formats. Additive changes only; breaking changes bump
   the major version.
5. **Distributed tracing is end-to-end.** The OTel
   TraceContext propagates across service boundaries; the
   observability sidecar joins the traces into one tree.

## What is already in place (from earlier phases)

- `MemoryStore` Protocol (Phase 1.1) — the contract a memory
  service would expose
- `ConsensusEngine` Protocol (Phase 3.1) — the contract a
  consensus service would expose
- `TokenStore` (Phase 2.10) — the auth boundary that services
  can share without re-implementing
- OTel tracing (Phase 2.9) — propagates trace context across
  process boundaries
- Three-tier NATS fallback (audit §1.1) — proven inter-service
  transport

## What is still missing

- Inter-service auth (mTLS via cert machinery exists for
  NATS; not yet for gRPC)
- Distributed-trace correlation across services
  (TraceContext propagation is in place; the join
  configuration is not)
- A service-mesh control plane (istio, linkerd, or
  homemade). Currently the swarm runs as a single Docker
  compose stack.
- Synthetic load tests for each service's exit criterion
  (5.1–5.4 above).
