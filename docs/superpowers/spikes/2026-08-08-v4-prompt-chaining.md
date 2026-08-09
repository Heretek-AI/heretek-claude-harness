# v4: Prompt chaining decomposition utilities

**Status:** 🔬 Spike
**Phase:** v4 (workflow + eval)
**Date:** 2026-08-08

## Research question

Should prompt chaining (Doc 1 §Vector 4) be a first-class utility in the heretek harness, or is it subsumed by subagent delegation?

## Why

Prompt chaining decomposes a task into sequential LLM calls. Subagent delegation does the same thing with isolation. Trade-off: chaining shares context (efficient); subagents get fresh context (clean).

## Deliverable

- Decision document comparing chaining vs subagents in the heretek context.
- Decision criteria for promotion: clear use case where chaining beats subagents, OR explicit defer with rationale.

## Evidence

- Doc 1 cite #18 (Anthropic "Building Effective Agents" 5 patterns).
- Doc 2 cite #24 (Qwen Code Architect/Editor uses chaining in the Planner→Coder path).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.4
- Roadmap: `docs/superpowers/roadmap.md` §v4
