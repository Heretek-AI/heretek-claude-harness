---
title: "Curated External Awesome-Lists for the RE Analyst"
category: "reference-awesome-lists"
platforms: ["linux", "windows", "macos", "android", "ios", "web"]
difficulty: "beginner"
tags: ["awesome-lists", "curated", "fuzzing", "yara", "llvm", "obfuscation", "anti-debug", "anti-vm", "game-reversing"]
summary: "A curated, periodically-updated index of the external awesome-lists the RE analyst should follow: fuzzing, YARA, LLVM obfuscation, Android/iOS, malware analysis, game reversing, and the canonical deep-dive awesome-lists."
updated: "2026-06-06"
related:
  - "tools/01-ghidra"
  - "anti-analysis/01-anti-debug"
  - "sandbox-emulation/01-decision-tree"
---

# Curated External Awesome-Lists for the RE Analyst

## Summary

An *awesome-list* is a community-curated GitHub
repository of links to a topic. The RE community
maintains many of them. The lists below are the
canonical "what should I follow" set for the
analyst who wants to stay current on tools,
techniques, and writeups.

Categories are observable topics, not specific
commercial products. Each list is a living
document that the maintainer updates; the
analyst's job is to skim the latest commit
every few months.

## Why this matters

The RE tooling landscape moves fast. A new
deobfuscator appears every quarter; a new
anti-debug primitive is published every month;
a new VM-pack family shows up every six
months. The awesome-lists are the *first-pass
discovery* surface — the analyst who isn't
following them misses 80% of the new work.

The cost of not following: the analyst spends
a week re-discovering a technique that was
on the front page of an awesome-list three
months ago.

## Mechanics

The list is grouped by topic. Each list has a
one-line description of *what it's good for*
(the RE use case that benefits most).

### Fuzzing

- **secfigo/Awesome-Fuzzing** — the canonical
  curated list of fuzzing tools + writeups.
  Coverage: AFL / libFuzzer / WinAFL / honggfuzz
  / structure-aware fuzzing / kernel fuzzing.
  Good for: the analyst who wants to find the
  right fuzzer for a target.
- **fuzzing-framework** (GitHub topic) — the
  topic-level index; broader than the awesome-
  list, includes every public fuzzing framework.
  Good for: quick discovery when the analyst
  doesn't know the framework's name.

### YARA

- **InQuest/awesome-yara** — the canonical
  curated list of YARA rules + rule-authoring
  tools. Coverage: rule sources, rule
  generators, rule-testing frameworks, the
  canonical rule corpus from major vendors.
  Good for: the analyst who wants to bootstrap
  a YARA rule set.
- **reversinglabs/reversinglabs-yara-rules**
  — vendor-quality rule corpus, kept current
  with the latest malware families. Good
  for: a starter rule set when the analyst
  is building an internal detection library.

### LLVM / obfuscation

- **gmh5225/awesome-llvm-security** — the
  curated list of LLVM security work
  (sanitizers, CFI, KASLR, OLLVM forks,
  d810-ng). Good for: the analyst who works
  on obfuscated binaries (the OLLVM
  deobfuscation angle is the relevant
  subset).
- **topics/obfuscation** (GitHub topic) —
  the topic-level index; broader, includes
  every public obfuscator + deobfuscator.
  Good for: quick discovery when the
  analyst doesn't know the tool's name.

### Anti-debug / anti-VM / anti-RE

- **fr0gger/unprotect** — the canonical
  curated database of anti-analysis API
  names + the structure of an anti-analysis
  primitive. The categorised API list is
  what the `re-anti-analysis` RE-AI server
  uses as its primary catalog seed.
- **CheckPointSW/Anti-Debug-DB** — the
  machine-readable Windows anti-debug DB;
  pairs with `unprotect` for the
  cross-platform coverage.
- **topics/anti-debug / anti-vm** (GitHub
  topics) — the topic-level indices for
  the broader anti-RE surface.
- **al-khaser** — the canonical anti-RE
  test binary; the source code is the
  analyst's cheat sheet for the
  anti-analysis primitive surface.
- **CheckPointSW/Evasions** — the
  cross-platform evasion test binary.
  Good for: confirming the
  anti-emulator / anti-VM coverage
  on a specific target.

### Reverse engineering (general)

- **mytechnotalent/Reverse-Engineering**
  — the canonical "intro to RE" GitBook,
  the first read for an analyst new to
  the field.
- **topics/reverse-engineering** (GitHub
  topic) — the topic-level index; every
  public RE tool eventually shows up
  here.
- **OWASP/mastg** — the OWASP Mobile
  Application Security Testing Guide;
  the canonical mobile-side RE +
  pentesting reference. Good for: the
  Android / iOS RE workflow.
- **dsasmblr/game-hacking** — the
  canonical game-hacking reference. The
  read-side is general RE; the write-side
  is the game-RE / anti-cheat-analysis
  angle.
- **kovidomi/game-reversing** — a curated
  list of game-RE tools + writeups.
- **pwndbg/pwndbg** — the canonical GDB
  front-end (better than GEF for the
  exploit-development side; GEF is
  already loaded in `re-gdb` for the
  RE side).

### Android / iOS

- **Android-RE** — a curated list of
  Android RE resources (the repo is
  itself an awesome-list; appears as a
  sibling directory in `RE-AI/Input/`
  neighbourhood).
- **hack-different/apple-knowledge** —
  the canonical iOS RE reference.
- **majd/ipatool** — the canonical
  IPA downloader (used to get the
  pre-release app from the App Store
  for analysis).

### Decompilers + tool primers

- **mrexodia/ida-pro-mcp** — the canonical
  IDA Pro MCP bridge. The pattern
  (LLM-driven decompilation via the MCP
  transport) is what `re-llm-decompile`
  in RE-AI follows.
- **bethington/ghidra-mcp** — the Ghidra
  MCP bridge; same pattern.
- **zinja-coder/jadx-ai-mcp** — the
  JADX (Android decompiler) MCP bridge.
  Good for: a reference implementation
  for any future Android-side RE-AI
  tool.

### AI / LLM-for-RE

- **JusticeRage/Gepetto** — the canonical
  "send a function to an LLM" reference.
  The closest analog to RE-AI's
  `re-llm-decompile` skill.
- **0x251/Prometheus-DeobfuscatorV2** —
  the LLM-assisted .NET deobfuscator. The
  closest analog to RE-AI's
  `re-dotnet-analysis` skill + the new
  `re-dotnet.classify_dotnet_protection`.

### Frida / dynamic instrumentation

- **iddoeldor/frida-snippets** — a
  curated collection of small Frida
  scripts. Smaller and cleaner than
  the alternatives; good as a reference
  for any new `re-frida` tool.
- **0xdea/frida-scripts** — the
  most-comprehensive public Frida
  script collection.

## Approach

The analyst's discovery loop:

1. **Subscribe to the relevant awesome-list's
   RSS feed.** Most awesome-lists have a
   "commits" RSS that fires on every change.
2. **Skim new entries every week.** A new
   tool that's relevant to your analysis
   area is worth a 30-min read.
3. **Cross-reference with `potential.txt` +
   the RE-AI gap analysis.** When a new
   tool is on-trend, the RE-AI plugin
   should add a wrapper server or a
   skill for it.

The list is also a useful *first-pass
discoverability* surface — when the
analyst hears a tool name in a writeup
or a tweet, the awesome-list is the
quickest way to find the canonical
README.

## Common pitfalls

- **Don't subscribe to every list.** Pick
  the 2-3 most relevant to your work;
  the rest is noise.
- **Don't treat the list as a recommendation
  list.** An entry on an awesome-list is
  *not* an endorsement — the maintainer
  lists the tool, the analyst's job is
  to evaluate it.
- **Don't follow the GitHub topic pages
  as a discovery surface alone.** The
  awesome-lists are curated; the topic
  pages are auto-generated and noisy.

## Tooling pointers

- `tools/01-ghidra` — the Ghidra primer;
  pairs with the awesome-lists for the
  tool-ecosystem view.
- `anti-analysis/01-anti-debug` — the
  anti-RE primer; pairs with the
  anti-debug / anti-VM lists.
- `sandbox-emulation/01-decision-tree` —
  the sandbox / emulator primer; pairs
  with the fuzzing + sandbox lists.
