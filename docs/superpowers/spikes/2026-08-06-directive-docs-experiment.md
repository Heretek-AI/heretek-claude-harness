# #39 — Directive-docs system-prompt augmentation experiment

> Date: 2026-08-06. Status: spike protocol. Type: spike. Approach: failure-mode.

## Hypothesis

Adding a one-line directive to heretek-installed agents' system prompts —

> "Do not rely on training-data knowledge for any library, API, or version.
> Verify against Context7 MCP or the freshness index in `catalog/freshness/`
> before generating code."

— reduces the rate of deprecated-API output by ≥50% (vs. baseline) when
measured on a controlled 30-task eval set across model classes (Qwen3.6 27B,
deepseek-class).

## Background

Hakim Ziad's pilot showed a "5-line directive" approach dropping deprecated
API output from 100% to 0% in an unrelated harness
([source](https://medium.com/@hakim.ziad/how-to-stop-coding-agents-from-using-stale-versions-473dcea7359d),
verified 2026-08-06). This spike tests whether the technique generalizes
to heretek's specific hooks context.

## Method

1. **Baseline measurement (without directive):** Run a 30-task eval set
   (10 Python, 10 JS/TS, 10 Rust). Each task asks the agent to produce
   code that touches a known-deprecated API. Count deprecated-API output
   rate per model class.
2. **Treatment measurement (with directive):** Same 30 tasks, with the
   directive injected into the agent's system prompt at session start.
   Count deprecated-API output rate per model class.
3. **Comparison:** Per-model-class reduction in deprecated output rate.

## Eval set

The 30 tasks live at `tests/freshness_eval/tasks/` (authored as part of
this spike's M1–M3 work — see Timeline below). Each task has:
- A short natural-language prompt (e.g., "parse YAML config and warn on
  deprecated keys")
- A deprecated-API surface (e.g., `yaml.load()` without `Loader=`)
- A reference to the modern equivalent

Tasks should be drawn from real deprecations in heretek's own runtime
deps (pyyaml, requests, etc.).

## Decision criteria

- **Adopt directive** if reduction ≥50% across all tested model classes.
- **Adopt with caveats** if reduction ≥50% for ≥50% of model classes.
- **Reject** if reduction <50% across all tested model classes.

## Deliverables

- [ ] 30-task eval set authored
- [ ] Baseline + treatment measurements run on ≥2 model classes
- [ ] Decision documented in this file's "Result" section
- [ ] If adopted: ADR at `docs/superpowers/specs/YYYY-MM-DD-directive-docs-decision.md`
- [ ] If adopted: directive added to heretek's plugin install hook template

## Timeline

- Eval set authoring: 2 weeks (relies on existing deprecation knowledge)
- Baseline + treatment: 1 week (model runs)
- Decision + ADR: 1 week

## Cross-references

- Issue #39
- Spec §3
- Research report (`docs/superpowers/research/2026-08-06-freshness-enforced-coding-research.md`)
- Hakim Ziad source