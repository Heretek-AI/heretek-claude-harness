# re-report-write

MCP server for **writing analyst reports** to a file. Provides:

- Free-text Markdown write to a path
- Structured Markdown table write to a path (headers + rows)

The server is pure-Python (no system deps) and is the
foundational primitive the `re-report` skill uses to commit
report fragments to `Output/<run-id>/<file>.md`.

## Why

The 2026-06-05 stress test surfaced a need for a single,
auditable write-primitive that:

- Refuses to write outside the run's working dir (the
  gitignored `Output/<run-id>/`)
- Returns a SHA-256 of the written content (so the run
  manifest can verify the report is intact)
- Renders Markdown tables in the GitHub-Flavored style
  the rest of RE-AI uses (per `CLAUDE.md` §"Output report
  structure")

## Tools

| Tool | What it does |
|---|---|
| `check_report_write` | Health check — `re-report-write` has no system deps; always `status: OK` |
| `write_report` | Write free-text content to a path; return the SHA-256 of the written content |
| `write_table` | Render a Markdown table from `headers` + `rows` and write it to a path; return the SHA-256 |

## Install

Part of the RE-AI plugin; `./install.sh` installs the package. To
install standalone:

```bash
pip install -e ./servers/re-report-write
```

## Run

```bash
re-report-write                            # stdio transport (default for MCP)
python -m re_report_write                  # equivalent
```
