---
title: "Freshness-enforced coding — research report"
date: 2026-08-06
sources_verified: 2026-08-06
status: complete
---

# Freshness-enforced coding — research report

> Synthesizes brainstorming session research conducted 2026-08-06 for the
> spec `2026-08-06-freshness-enforced-coding-roadmap-design.md`.

## Sources (verified 2026-08-06)

| Source | URL | Used by issues |
|---|---|---|
| bswen: Context7 MCP prevents hallucinated deprecated methods | https://docs.bswen.com/blog/2026-03-17-prevent-ai-hallucinations-outdated-docs/ | #36, #45, #50 |
| techbuzz: Google fixes AI coding agents' outdated code problem | https://techbuzz.ai/articles/google-fixes-ai-coding-agents-outdated-code-problem | #36, #46, #50 |
| lunidev: AI training data currency developer guide 2026 | https://lunidev.com/dev/blog/ai-training-data-currency-developer-guide-2026 | #39, #52 |
| Hakim Ziad: 5-line directive cut deprecated output 100→0% | https://medium.com/@hakim.ziad/how-to-stop-coding-agents-from-using-stale-versions-473dcea7359d | #39, #52 |
| propelcode: Emergent code review patterns | https://www.propelcode.ai/blog/emergent-code-review-patterns-ai-generated-code | #40, #43 |
| tianpan: Deprecated API trap | https://tianpan.co/blog/2026-04-17-deprecated-api-trap-ai-coding-agents | #40, #44, #53 |
| dev.to/ayame0328: AI-generated code is a minefield (AST mining) | https://dev.to/ayame0328/why-ai-generated-code-is-a-minefield-is-trending-and-what-2-months-of-building-a-static-scanner-4fg4 | #40, #43 |
| Mala.dev: context agent drift detection | https://www.mala.dev/blog/context-engineering-agent-drift-detection-monitoring/ | #41, #52, #53 |
| AttractorFlow: agent trajectory monitoring | https://mcpmarket.com/tools/skills/attractorflow-agent-monitoring | #41, #53 |
| arXiv 2512.24601: Recursive Language Models (Zhang, Kraska, Khattab) | https://arxiv.org/pdf/2512.24601 | #42, #53 |
| primeintellect.ai/blog/prime-agent | https://www.primeintellect.ai/blog/prime-agent | #42, #53 |
| primeintellect.ai/blog/rlm | https://www.primeintellect.ai/blog/rlm | #42, #53 |
| InfoQ: Refreshing stale code intelligence (QCon London 2026) | https://www.infoq.com/news/2026/03/stale-code-intelligence/ | #46, #50, #52 |
| arxiv 2406.09834: LLMs Use Deprecated APIs (empirical study) | https://arxiv.org/html/2406.09834v1 | #40, #44, #50 |

## Cross-cutting observations

1. **Stale training data is the dominant failure mode** across all sources. Both bswen/Context7 and techbuzz/Gemini Docs MCP frame the same problem from different angles: models emit code reflecting their training cutoff.
2. **External-data triangulation works**: every documented successful mitigation involves fetching external state at edit time or before commit, not relying on model knowledge.
3. **Forcing directive language helps**: Hakim Ziad's "do not rely on training-data knowledge" directive cut deprecated output 100→0%. Compatible with the spec's #39 spike.
4. **RLM scaffold offers a generalizable primitive** for handling large context without stuffing it into the prompt. Directly relevant to #42 spike.

## Open research questions

- Empirically, does the 5-line directive generalize to heretek's specific hooks context? (#39)
- Does RLM actually reduce stale-output rate when running on Qwen3.6 27B-class models? (#42)
- Is forbidden-pattern AST mining sufficient, or do we need LLM-driven pattern detection? (#40, #43)

## Phase 4 results (added 2026-08-06)

The three Phase 4 spikes (#47, #48, #49) ran as Plan D tasks. Full results:
see `docs/superpowers/research/2026-08-06-freshness-enforced-coding-vision-report.md`.
