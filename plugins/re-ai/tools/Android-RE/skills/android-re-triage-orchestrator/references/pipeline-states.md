# Triage pipeline state machine

The orchestrator MCP server moves every triage through a
well-defined state machine. This document describes the
transitions and the gates between them.

## States

```
PENDING ──start_triage──> RUNNING ──complete all steps──> COMPLETED
                            │  │
                            │  └─ pause / cancel──> PAUSED / CANCELLED
                            │
                            └─ step fails / unhandled error──> FAILED
```

`PAUSED` and `CANCELLED` are resumable. `FAILED` and `COMPLETED`
are terminal.

## Per-step gates

Each plan step has a **gate** — a condition that must be true
before the step is allowed to run. The orchestrator enforces
these gates; the agent running the skill should check them
before invoking the corresponding MCP tool.

| Step | Gate |
|------|------|
| `static.open_project` | none — always runnable |
| `static.triage` | previous step `static.open_project` complete |
| `static.masvs` | previous step complete |
| `native.list` | `static.open_project` complete |
| `native.parse_binary` | library present in `native.list` output |
| `static.sarif` | at least one finding added |
| `static.secrets` | at least one finding added (recommendation) |
| `dynamic.attach` | device connected (auto-skipped if not) |
| `dynamic.network` | user opt-in for MITM; proxy must be running |
| `triage.correlate` | at least 2 findings from different sources |
| `triage.finalize` | all preceding steps complete |

## Cross-source correlation

The `correlate_findings` step emits **correlation cards**:

- **Same MASVS control, multiple sources** — strongest signal.
  A static finding + a matching dynamic observation =
  confirmed.
- **Static secret + dynamic log observation** — leaked secret
  in runtime logs is a high-severity correlation.
- **Static native-lib issue + dynamic crash** — confirms a
  memory-safety bug.

The agent should report each card as its own section in the
final markdown report.

## Final report shape

```markdown
# Triage Report — <package>

## Summary
- Total findings, by severity, by source
- Controls touched
- Devices used (if any)
- Time taken

## Cross-source correlations
- <correlation card> per finding pair

## Findings
- <severity>-grouped list with full evidence

## MASVS coverage
- One row per control with status (pass / fail / review)
- For dynamic-only runs, "review" is the default

## Appendix
- A: List of tools called
- B: Raw SARIF / JSON path
- C: Reproduction steps
```

## Checkpoint and resume

The orchestrator persists after every state transition. If the
server restarts mid-triage, the next `triage_status` call returns
the current snapshot. Use `resume_triage` to continue, or
`resume_from_checkpoint` to re-open a triage from a saved
JSON file.
