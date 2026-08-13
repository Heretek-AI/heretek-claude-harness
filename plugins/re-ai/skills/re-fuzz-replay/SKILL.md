---
name: re-fuzz-replay
description: Fuzz-style replay of a small input corpus against a single target function. Use when the user wants to fuzz one function in a stripped binary and has a small seed input corpus. Calls re-triton symbolic_explore + emulate_function + re-gdb concrete single-step to build a coverage map and surface new basic blocks as the corpus is replayed. The analyst reviews each new edge; the tool never auto-generates inputs. Pairs with re-triton find_magic_bytes when the analyst wants a constraint-driven next input.
---

# Fuzz-Style Input Replay

## When to use

Use this skill when the user wants to fuzz a single
function inside a stripped binary and has a small
seed input corpus. The skill is *not* a full
fuzzer (no AFL / libFuzzer / WinAFL); it wraps
the existing RE-AI tools to drive a turnkey
replay loop.

The output is a per-input coverage map + the
set of new basic blocks the corpus reached. The
analyst reviews each new edge; the skill never
auto-generates inputs.

## What this skill returns

1. **Coverage map** — the basic-block set + the
   edge list reached by the first replay.
2. **Per-input replay summary** — for each
   corpus input: the edges hit, whether the
   input reached a new edge, whether the input
   crashed.
3. **Edge diff** — when re-running with a new
   corpus entry, the new edges vs the prior
   coverage.
4. **Next-input suggestions** — the analyst's
   hand-written or constraint-driven next
   input (never auto-generated).

## What this skill does NOT do

- **Does not auto-crate inputs.** The analyst
  writes the next input. The tool suggests
  strategies (extend by 1 byte, flip the high
  bit, use re-triton.find_magic_bytes) but
  never runs them.
- **Does not use AFL / libFuzzer / WinAFL.** For
  long-running fuzzing, the user runs those
  tools directly; this skill is the
  short-corpus / targeted replay use case.
- **Does not require root / a sandbox.** The
  replay runs against a copy of the function's
  bytes under re-triton, no process launch
  needed.

## Workflow

**Step 1 — Coverage map (one call)**

```
re-triton.coverage_map(code_b64=base64_of_function_bytes)
```

Returns the edge set + the signature.

**Step 2 — Seed replay (one call)**

```
re-fuzz-replay.seed_replay(
    path=binary_path,
    function=function_name_or_rva,
    corpus_dir=path_to_corpus_dir,
)
```

Returns the per-input replay summary. The
analyst reviews the new_edges counts.

**Step 3 — Edge diff (per new input)**

```
re-fuzz-replay.edge_diff(
    before=prior_coverage_map,
    after=new_coverage_map,
)
```

Returns the new_edges list.

**Step 4 — Next-input strategies (one call)**

```
re-fuzz-replay.next_inputs(
    path=binary_path,
    function=function_name_or_rva,
    k=8,
)
```

Returns the list of strategies. The analyst
applies one manually.

**Step 5 — Optional: constraint-driven input**

For a known-output target:

```
re-triton.find_magic_bytes(
    code_b64=base64_of_function_bytes,
    target_bytes_b64=base64_of_expected_output,
    length=8,
)
```

Returns a solver-driven input.

**Step 6 — Loop**

Repeat steps 2-5 until the corpus is exhausted
or the coverage plateaus.

## Output report format

```markdown
# Fuzz Replay — <function_name> in <path>

## Coverage map
- block_count: 47
- edge_count: 89
- signature: <16-char sig>

## Per-input replay
- input_0.bin: edges=89, new_edges=89 (initial)
- input_1.bin: edges=89, new_edges=0
- input_2.bin: edges=92, new_edges=3
- input_3.bin: CRASH

## Edge diff
- new edges reached by input_2: [<addr>, <addr>, <addr>]

## Next-input strategies
- extend the existing corpus by 1 byte at the end
- flip the high bit of the last byte of the last replayed input
- try the empty input (0 bytes) and a single 0x00 byte
- use re-triton.find_magic_bytes to ask the symbolic engine for the next input

## Crashes
- input_3.bin crashed at <addr>
```

## Pairing with other skills

- `re-triton.find_magic_bytes` — the
  constraint-driven input side. Pair when the
  analyst wants a Z3-derived input.
- `re-gdb` — for the concrete single-step on
  a real process. Pair when the analyst wants
  to confirm a crash on the real binary.
- `re-decompile` — for the function-level
  decompilation. Pair when the analyst wants
  to understand the new edge's code.
- `re-vm-reverse` — for the VM-pack-protected
  function case. The dispatcher body is the
  target of the fuzz replay; the new edges
  reveal the VM handler table.
