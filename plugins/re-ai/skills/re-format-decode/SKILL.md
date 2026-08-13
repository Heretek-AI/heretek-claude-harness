---
name: re-format-decode
description: Reverse engineer a custom or proprietary binary format. Use when the user says "decode this blob", "what's in this file", "I have a .DAT/.BIN/.DAT from device X", "this is a firmware image", "what's in this .utoc / .ucas", "decode this IoStore", "decode this .paz / .pamt / .papgt / .pathc / .paver". Compiles a Kaitai .ksy spec on the fly, parses the file, visualizes the structure, supports structural diff between two files.
---

# Custom Format Reverse Engineering

## When to use

Use this skill when you have a binary file whose format is unknown or proprietary — a firmware image, a save file from a game, a `.DAT` from a device, a packet capture from a closed protocol. The goal is to write a [Kaitai Struct](https://kaitai.io/) `.ksy` spec that fully describes the file.

Common prompts:

- "Decode this firmware blob"
- "I have a save file from device X, what are the fields?"
- "Document this proprietary format"
- "Compare two versions of this file"

## Workflow (iterative .ksy authoring)

The Kaitai workflow is **iterative**: you write a partial `.ksy`, compile it, parse the file, look at what worked and what didn't, fix the spec, repeat. Expect 3-10 iterations.

**Iteration 0 — Identify the file**

1. `re-lief.parse_binary(path)` — get the magic bytes, file size, hashes.
2. `re-lief.categorize_strings(path, min_length=5, max_per_category=50, include_misc=true)` — the `misc` bucket's `uncategorized_sample[]` is what you grep for printable strings (the format name, version tag, or magic-byte trailer is usually there).  The categorized buckets are noise here; the categorized vocabularies are tuned for binary-protection indicators, not for format identification.
3. If the file has a known file-extension → magic-byte lookup table, try `re-kaitai.list_known_formats()` and parse with a known format to seed the work.

**Iteration 1 — First .ksy**

1. Write a stub .ksy with the magic bytes and an end-of-file terminator.
2. `re-kaitai.compile_format(ksy_path)` to compile it.
3. `re-kaitai.parse_with_format(path, ksy_path=...)` to parse.
4. Look at the parse tree, identify the next unknown field.

**Iteration 2..N — Refine**

1. Add a new field to the .ksy (length-prefixed, fixed-size, type indicator, etc.).
2. Recompile + reparse. Inspect.
3. If the parse succeeds, move to the next unknown offset. If it fails, fix the schema.

**Final — Compare**

When the spec is stable, run `re-kaitai.diff_parses(path_a=..., path_b=...)` on two files of the same format to confirm the spec handles variants.

## When to give up

- After 10 iterations, if the parse tree is still mostly wrong, the file may be:
  - **Encrypted**: tell the user. Stop and suggest `re-rizin` to find the decryption routine.
  - **Compressed**: same — `re-rizin` for the inflate/deflate call.
  - **Obfuscated/anti-RE**: escalate to `re-malware-triage`.
- If the file is <1KB, it may not be worth a full .ksy — a 30-line Python parser might be faster.

## Hex-edit-driven validation

For ambiguous fields, do this:

1. Pick a 4-byte value in the file at offset X (find it with `re-lief.extract_strings`).
2. Change it in a copy of the file (e.g. with a hex editor or `printf` in bash).
3. Re-parse. If the parsed field X changes, your .ksy is correct.
4. Repeat.

This is the **only** way to validate variable-length fields. Reading disassembly of the producer is also valid but slower.

## Kaitai schema tips

- Use `size: eos` for the last field if the format is "header + variable-length payload".
- Use `if X.has_field_y` for conditional fields — Kaitai's `if` works at the spec level.
- Use `enum` for known tag values (file-type tags, version tags).
- Use `repeat: eos` for trailing arrays, `repeat: until` for counted arrays, `repeat: expr` for explicit counts.
- Prefer `size:` over fixed sizes when the format is little-endian with explicit length prefixes.

## Output

Produce:

1. The .ksy file (committed to a formats/ directory)
2. A Python parser generated from the .ksy (so the user can `import formats_X`)
3. A Markdown report describing the file structure
4. For pair-of-files work: the structural diff

## Common file types

| Magic bytes | Likely format | Suggested .ksy source |
|---|---|---|
| `1F 8B` | gzip | `kaitaistruct` (no built-in; write a 5-line .ksy) |
| `50 4B 03 04` | ZIP | `kaitaistruct.zip` (if available) or write your own |
| `7F 45 4C 46` | ELF | `kaitaistruct.elf` |
| `4D 5A` | PE | `kaitaistruct.pe_mz` |
| `FF D8 FF` | JPEG | `kaitaistruct.jpg` |
| `89 50 4E 47` | PNG | `kaitaistruct.png` |
| `42 4D` | BMP | `kaitaistruct.bmp` |
| `GIF87a` / `GIF89a` | GIF | `kaitaistruct.gif` |
| `RIFF` | WAV/AVI/WebP | `kaitaistruct.wav` |
| `AF 1B B1 FA` | IL2CPP global-metadata.dat (Unity) | use `re-il2cpp-decompile`; do NOT hand-author a .ksy |
| `55 6E 69 74 79 46 53 00` (`UnityFS\x00`) | Unity asset bundle (modern) | `data/ksy/unityfs.ksy` (shipped starter) |
| `55 6E 69 74 79 57 65 62` (`UnityWeb`) | Unity Web Player asset bundle (legacy) | author a .ksy from scratch |
| `55 6E 69 74 79 52 61 77` (`UnityRaw`) | Unity raw asset bundle (legacy) | author a .ksy from scratch |

For proprietary formats, start with a 10-line .ksy and iterate.
