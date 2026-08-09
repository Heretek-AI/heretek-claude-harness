---
slug: observability-sub-spec-1
date: 2026-08-09
status: proposed
---

# Harness Observability — Sub-spec 1 (Collector)

## What

Sub-spec 1 of the harness-observability spec ships a local-first
telemetry collector for Claude Code hook events. Components:

- `plugins/hooks/scripts/telemetry_collector.py` — collector invoked by
  PreToolUse / PostToolUse hooks; writes append-only JSONL into
  `~/.heretek/telemetry/sessions/<YYYY-MM-DD>/session-<id>.jsonl`.
- `scripts/heretek_cli.py telemetry {show,grep,schema}` — local
  read-only inspection (no network).
- `tests/fixtures/telemetry_schema.json` — JSON Schema for each
  emitted event.
- Retention sweep: 30-day cutoff into `~/.heretek/telemetry/archive/`
  via tar + zstd compression.

## Why

Issue #2 acceptance criterion 1 calls for a heretek-built monitor
plugin. Without local telemetry, the harness has no visibility into
which fast-gate rules fire, how often, and with what latencies.
Sub-specs 2 (test pipeline) and 3 (eval harness) both depend on the
collector emitting a stable JSONL schema; without sub-spec 1, neither
can be built.

Sub-spec 1 closes #2 ac-1 and unblocks the rest of the observability
roadmap.

## Alternatives

- **Vendor-only (Datadog / Honeycomb / Grafana Cloud):** rejected for
  D-D (privacy-by-default). Hook events may include user code paths,
  branch names, and tool-call arguments; shipping those to a third
  party by default violates the marketplace's privacy stance and adds
  network failure modes that would break every Edit/Write.
- **Event-shipping-only (no local store):** rejected because local
  visibility must work offline. Users on air-gapped boxes or behind
  strict egress firewalls still need to grep their own hook events to
  debug fast-gate false positives.
- **Log to stdout, parse later:** rejected because the harness cannot
  reliably multiplex hook stdout with the agent's other writes;
  append-only JSONL on disk is the simplest correct choice.

## Decision

Ship sub-spec 1 per
`docs/superpowers/specs/2026-08-08-harness-observability-collector.md`.
Collector runs as a fast-gate companion (sub-50ms p99); retention
sweep is opt-in via cron / on-demand CLI; schema is locked at
`telemetry_schema.json` so sub-specs 2 + 3 can consume the same
records.

## Consequences

**Positive:**

- Closes #2 acceptance criterion 1.
- Unblocks sub-spec 2 (test pipeline) and sub-spec 3 (eval harness).
- Privacy-by-default: events stay on disk unless user explicitly
  configures a shipper.
- Append-only JSONL is git-diffable and trivially backable up.

**Negative:**

- Collector adds <50ms p99 to every PreToolUse / PostToolUse — small
  but non-zero overhead on every Edit/Write/MultiEdit.
- Local-only visibility: no dashboards out-of-the-box. Sub-specs 2 + 3
  add dashboards, but until then the user reads JSONL directly.
- Disk usage grows linearly with hook volume; retention sweep is
  opt-in, not automatic.

## Target plugin

`hooks` — collector is a hook companion; lives alongside the existing
fast-gate scanner in `plugins/hooks/scripts/`. No new plugin needed.

## Vetting checklist (D7)

- [ ] stars ≥ 500 — N/A (first-party)
- [ ] last commit ≤ 12 months — N/A (first-party)
- [ ] OSI-approved license (MIT / Apache-2.0 / BSD / etc.) — MIT
- [ ] source-audit pass (if code-executing) — collector is code-executing; audited in PR #113
- [ ] no critical CVEs in last 24 months — N/A (first-party)

## References

- Sub-spec 1 spec: `docs/superpowers/specs/2026-08-08-harness-observability-collector.md`
- Parent spec: `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` (D1–D17)
- Sprint spec: `docs/superpowers/specs/2026-08-09-v35-collector-sprint-design.md`
- Per-issue plan: `docs/superpowers/plans/2026-08-08-harness-observability-collector.md` (Task 5)
- Issue #2: heretek-built monitor plugin (acceptance criterion 1)
- Issue #113: this ADR's tracking issue
- ADR template: `catalog/reviews/0000-template.md`

## Verdict

- [ ] Approved
- [x] Proposed

Reason: ships with sub-spec 1 close-out PR; ratification pending review.
