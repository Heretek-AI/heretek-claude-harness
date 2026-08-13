---
name: grilling
description: Sharpen technical plans and architectural designs through a structured interview framework before code generation.
---

# grilling

Frontier interview skill inspired by Matt Pocock's grilling workflow to stress-test technical decisions and write ADRs.

## Interview Protocol

When invoked:

1. **Map Problem Space**: Construct a decision tree of unsettled architectural questions and trade-offs.
2. **Frontier Batching**: Present questions in small, numbered batches on the "frontier" (decisions whose prerequisites are settled).
3. **Format**:
   ```markdown
   ❓ **Q1 - <Title>**: <Context & Options>
   ➡️ **Agent Recommendation**: <Option A because ...>
   ```
4. **Separate Facts from Decisions**:
   - For **Facts** (code paths, API signatures), look them up using file/grep tools.
   - For **Decisions** (architectural choices, trade-offs), wait for user confirmation.
5. **Document ADRs**: Summarize confirmed choices into an Architectural Decision Record (ADR) file.
