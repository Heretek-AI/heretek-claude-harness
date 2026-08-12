---
name: humanizer
description: Enforce natural, professional, anti-AI-slop writing style free of buzzwords and robotic corporate fluff.
---

# humanizer

Eliminate robotic AI writing tropes, marketing buzzwords, and redundant explanations. Based on Wikipedia's WikiProject AI Cleanup guide and human writing standards.

## Forbidden AI Cliché Vocabulary

Strictly ban the following words and phrases in generated text, commits, pull requests, and documentation:

- `delve into`, `tapestry of`, `testament to`, `beacon of`, `foster`, `spearhead`, `intertwined`, `culmination`, `underscores`, `nestled`, `pivotal`, `synergy`, `leverage`.

## Structural Rules

1. **No Superficial Participle Clauses**: Avoid ending sentences with comma-joined `-ing` phrases (e.g. "..., highlighting the importance of clean code", "..., ensuring smooth operations").
2. **No Em-Dash Overuse**: Limit em-dashes (`—`) to at most one per document.
3. **No Rule-of-Three Stuffing**: Do not artificially pad bullet points or adjective lists into triplets.
4. **No Conversational Preamble**: Never say "Sure, I can help with that!", "Here is the updated code:", or "I hope this helps!".

## Voice Calibration

- State what was changed, why it was changed, and how it was verified.
- Write in clean, active, direct human voice.
