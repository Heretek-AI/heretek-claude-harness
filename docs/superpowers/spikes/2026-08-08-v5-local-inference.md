# v5: Local inference (ROCm/Vulkan/KV cache reuse)

**Status:** 🔬 Spike
**Phase:** v5 (BYOK + local)
**Date:** 2026-08-08

## Research question

What is the minimum hardware spec for running the heretek harness against a local inference backend, and what backend (llama.cpp, CachyLLama, Ollama) is most compatible?

## Why

Doc 1 §Vector 3 cites lemonade-cachy-build and AMD ROCm 7 / Vulkan backends as the path for low-spec hardware acceleration.

## Deliverable

- Spike: benchmark heretek harness against 3 candidate local inference backends on a reference hardware configuration.
- Decision criteria: tokens/sec > 5 sustained + KV cache reuse demonstrably reduces latency.

## Evidence

- Doc 1 §Vector 3 (BYOK + local).
- Doc 1 cite #41 (lemonade-cachy-build issue #2471).

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.5
- Roadmap: `docs/superpowers/roadmap.md` §v5
