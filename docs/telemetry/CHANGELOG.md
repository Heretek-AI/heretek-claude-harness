# Telemetry Schema Changelog

All notable changes to `tests/fixtures/telemetry_schema.json` are recorded here.

## [1] — 2026-08-08

Initial schema. Covers fields from `docs/superpowers/specs/2026-08-08-harness-observability-collector.md` §2.1:

- `ts`, `session_id`, `event_type`, `tool_name`, `tool_input_path`
- `hook_decision`, `hook_latency_ms`, `hook_exit_code`, `hook_stderr_summary`
- `matcher_matched`, `plugin_root`, `schema_version`

Future schema changes bump `schema_version` in `telemetry_schema.json` and add an entry here with a migration note.
