---
name: re-yara-author
description: Author a YARA rule that matches a malware family or a custom-binary family. Use when the user has one or more sample binaries and asks for a YARA rule, OR when a rule the analyst wrote is firing too many false positives. Calls re-yara-author.extract_distinctive_features + rank_candidates + emit_rule + validate_rule + iterate_on_false_positives to produce a starter .yar text and validate it against a positive/negative sample set. The analyst reviews and tightens the rule; the tool never auto-deploys.
---

# YARA Rule Authoring

## When to use

Use this skill when the user has one or more binary
samples and wants a YARA rule that matches the
family, OR when an existing rule is firing too many
false positives and the analyst needs to tighten it.

The skill wraps `re-yara-author.*` (the rule-authoring
server) and `re-yara.scan_*` (the existing
scan-side server). The result is a starter `.yar`
text + a validation report.

## What this skill returns

1. **Feature list** — distinctive strings + import
   set + categorised keyword matches, ranked by
   specificity.
2. **Starter rule** — a `.yar` text with the
   chosen features wired into a `strings:` + `condition:`
   block.
3. **Validation report** — true-positive rate +
   false-positive rate against the analyst's
   positive + negative sample set.
4. **Refinement suggestions** — when the rule
   fires false positives, the skill proposes
   `filesize` constraints + tighter `condition:`
   blocks.

## What this skill does NOT do

- **Does not deploy the rule to production.**
  The output is a starter `.yar` text + a
  validation report. The analyst reviews and
  commits the rule.
- **Does not write rules for anti-tamper
  vendors** (banned by the `re-leak-scan`
  vendor-neutrality rule). Categories only.
- **Does not crack encrypted-VM bytecode strings.**
  The string-table pass is a *first-pass triage*
  signal; the analyst uses a dynamic trace to
  recover runtime-decrypted strings, then re-runs
  this skill against the recovered strings.

## Workflow

**Step 1 — Feature extraction (parallel-safe)**

```
re-yara-author.extract_distinctive_features(path=sample_path)
```

The walker calls `re-lief.extract_strings` +
`re-lief.categorize_strings` +
`re-lief.get_imports_exports` and returns the
unified feature set.

**Step 2 — Candidate ranking**

```
re-yara-author.rank_candidates(path=sample_path, k=20)
```

Returns the top-20 features by specificity score.

**Step 3 — Rule emission**

```
re-yara-author.emit_rule(
    name="family_xyz",
    features=top_5,
    min_strings=2,
)
```

Returns a starter `.yar` text. ``min_strings``
defaults to 2 — a rule with < 2 string conditions
is over-noisy.

**Step 4 — Validation against a positive set**

```
re-yara-author.validate_rule(
    rule_text=rule_text,
    positive_paths=[s1, s2, s3, ...],
    negative_paths=[b1, b2, b3, ...],  # optional
)
```

Returns the true-positive rate + false-positive
rate. The rule must clear a per-analyst threshold
(default: 1.0 TPR, 0.0 FPR).

**Step 5 — Refinement (if FPR > 0)**

```
re-yara-author.iterate_on_false_positives(
    rule_text=rule_text,
    fp_paths=[b1, b2, ...],
)
```

Returns a list of suggested `filesize` constraints
+ tightened `condition:` blocks. The analyst applies
the changes manually.

**Step 6 — Re-validate**

Loop steps 4-5 until the rule meets the threshold.

## Output report format

```markdown
# YARA Rule Authoring — <sample>

## Feature list (top 5)
- string: 0x... offset: "ABCDEF" (score 1.0)
- string: 0x... offset: "GHIJKL" (score 0.94)
- category: "anti_debug" (score 0.5)
- category: "hwid" (score 0.4)

## Starter rule
```yara
rule family_xyz
{
    meta:
        author = "re-yara-author"
        description = "auto-generated; refine before deploying"
    strings:
        $s0 = "ABCDEF" ascii wide
        $s1 = "GHIJKL" ascii wide
    condition:
        any of ($s*)
}
```

## Validation
- True-positive rate: 1.0 (4/4 samples)
- False-positive rate: 0.0 (0/3 negatives)

## Refinement (if FPR > 0)
- Add `filesize > 10KB` to exclude the FP path
- Tighten the `condition:` block to `2 of ($s*)`
```

## Pairing with other skills

- `re-leak-scan` — for samples that have telemetry
  pipeline leaks (the rule can be a category, not
  just a string match).
- `re-static-triage` — for the broader binary
  triage. The triage report's import list is
  the rule's `import` conditions.
- `re-anti-analysis-scan` — for samples with
  anti-debug / anti-VM primitives. The rule can
  match the primitive category, not the
  specific product.
