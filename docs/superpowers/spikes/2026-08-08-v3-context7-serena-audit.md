# v3: Context7/Serena ADR re-evaluation

**Status:** 🔬 Spike
**Phase:** v3 (MCP/ACI expansion)
**Date:** 2026-08-08

## Research question

Do the Context7 and Serena MCP server ADRs in `catalog/reviews/` (filed 2026-08-04) still represent best practice given Qwen Code's Architect/Editor pattern (2026)?

## Why

Doc 2 (CLI Coding Agents Audit) cite #24 highlights the Architect/Editor pattern as solving hallucination-execution loops. Our existing Serena ADR may predate this insight.

## Deliverable

- Audit report comparing Context7 + Serena interfaces to the Qwen Code pattern.
- Decision criteria for promotion: re-validate interface contracts OR file spec change requests.

## Evidence

- Doc 2 cite #24 (QwenLM/qwen-code discussion #8340).
- Existing ADRs: `catalog/reviews/mcp-pack-context7.md`, `catalog/reviews/mcp-pack-serena.md`.

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.2
- Roadmap: `docs/superpowers/roadmap.md` §v3
