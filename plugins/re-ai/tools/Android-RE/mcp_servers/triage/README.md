# android-re-mcp-triage

MCP server for the Android-RE **triage orchestrator**. Composes the
other three servers (static, native, dynamic) into long-running,
checkpointable multi-step analyses and produces a MASVS-aligned
report.

## Tools (12)

| Tool | Purpose |
|------|---------|
| `start_triage` | Open a new triage against an APK |
| `get_plan` | Return the multi-step plan for a triage |
| `resume_triage` | Continue a paused/cancelled triage |
| `cancel_triage` | Cancel a running triage |
| `triage_status` | Snapshot of a triage's progress |
| `add_finding` | Add a finding (typed) to a triage |
| `link_finding_to_evidence` | Attach evidence to a finding |
| `correlate_findings` | Cross-source correlation (static↔dynamic, etc.) |
| `propose_dynamic_tests` | Suggest dynamic tests to run based on static findings |
| `finalize_triage` | Produce the final MASVS report |
| `get_triage_history` | List all triages in the local SQLite store |
| `resume_from_checkpoint` | Re-open a triage from a saved checkpoint file |

## Workflow model

A triage is a long-running, multi-step analysis. The orchestrator:

1. **Opens** a triage via `start_triage` (records the APK path + SHA-256
   + goals in SQLite).
2. **Plans** the steps: a fixed template based on the goals
   (``full`` / ``masvs`` / ``static_only`` / ``dynamic_only`` /
   ``native_only``).
3. **Asks the user to call the underlying tools** (static / native /
   dynamic MCP servers) and feed the results back via
   `add_finding`.
4. **Correlates** findings across sources with `correlate_findings`.
5. **Finalizes** the report via `finalize_triage`, which writes a
   markdown file under the workdir and returns its path.

All state is in SQLite at `~/.android-re/triage.db` (or
`$ANDROID_RE_DATA_DIR/triage.db`). A triage survives server
restarts and can be resumed.

## Running

```bash
uv run --package android-re-mcp-triage python -m android_re_mcp_triage
```

To register with Claude Code:

```bash
claude mcp add android-re-triage -- uv run --package android-re-mcp-triage python -m android_re_mcp_triage
```

## Composing with the other servers

The orchestrator is **not** a daemon that calls the other MCP
servers in-process. The Claude Code client holds all four server
connections and routes tool calls between them. The
`android-re-triage-orchestrator` skill is the recipe that wires
this together.

## License

Apache-2.0.
