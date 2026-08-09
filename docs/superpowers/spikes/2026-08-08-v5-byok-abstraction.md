# v5: BYOK endpoint abstraction layer

**Status:** 🔬 Spike
**Phase:** v5 (BYOK + local)
**Date:** 2026-08-08

## Research question

Can we add a Bring-Your-Own-Key (BYOK) abstraction to the heretek marketplace that allows routing inference to OpenAI-compatible endpoints, local Ollama, or specialized coding models?

## Why

Doc 1 §Vector 3 + Doc 2 cite #39 (GDevelop-BYOK issue #7932) describe demand for endpoint-agnostic harnesses.

## Deliverable

- Spike: identify the Claude Code API surface that would need abstraction.
- Decision criteria: prototype routes a non-Anthropic model through the marketplace hooks without breakage.

## Evidence

- Doc 1 §Vector 3 (BYOK paradigm).
- Doc 2 cite #39 (GDevelop-BYOK feature request).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.5
- Roadmap: `docs/superpowers/roadmap.md` §v5
