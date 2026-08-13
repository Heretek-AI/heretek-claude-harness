---
name: re-archive-author
description: Guided Kaitai authoring for proprietary archive formats (3-5 iterations with auto-suggestions). Use when the user says "author a KSY for this archive", "what format is this binary", "I have a custom .paz / .pak / .dat file — reverse the format", or hands you a binary whose first 16-64 bytes don't match any known format. Pairs with re-kaitai.compile_format + re-kaitai.parse_with_format. Iteratively produces a working .ksy in data/ksy/.
---

# Proprietary Archive Format Authoring

## When to use

Use this skill when the analyst encounters a binary whose first
16-64 bytes don't match any known format (PE, ELF, MachO, ZIP,
PNG, UnityFS, etc.) and the user wants to reverse the format.
The output is a working `.ksy` file in `data/ksy/` that
`re-kaitai.compile_format` + `re-kaitai.parse_with_format` can
parse end-to-end.

**What this skill returns**:

1. **Magic-byte analysis** — comparison of the first 16-64 bytes
   against the known-magic catalog
2. **Hex walk** — entropy map, length-field candidates, record
   boundaries
3. **Draft `.ksy`** — version 0.1, with placeholder field names
4. **Parse iteration** — compile + parse + diff
5. **Final `.ksy`** — the committed format spec, with
   `vendor-neutral: true` metadata

## What this skill does NOT do

- **Does not produce a runtime trace.** Archive format
  reverse-engineering is a static problem; you only need
  to read the bytes.
- **Does not produce a loader.** The KSY is a *spec*, not a
  loader. To read a sample file with a working loader, use
  `re-kaitai.parse_with_format` after the KSY is committed.
- **Does not produce a writer.** KSY is a read-side spec; the
  write-side is a separate concern.

## Workflow

The workflow is 3-5 iterations. Each iteration ends with a
compiled + parsed .ksy; the analyst adjusts the spec based on
what the parser found (and what it didn't).

**Iteration 1 — Magic-byte analysis**

```
xxd <file> | head -8
```

Compare the first 16 bytes against the known-magic catalog:
PE (`MZ`), ELF (`\x7fELF`), MachO (`\xcf\xfa\xed\xfe` or
`\xfe\xed\xfa\xce`), ZIP (`PK\x03\x04`), PNG
(`\x89PNG\r\n\x1a\n`), UnityFS (`UnityFS\x00`),
Unity-raw (`UnityRaw\x00`), 7z, RAR, etc.

If the magic matches a known format, escalate to that
format's skill. If not, this skill's territory.

**Iteration 2 — Hex walk**

```
re-kaitai.walk_header(path, length=256)
```

(or use `xxd` / `hexdump` directly)

Identify:
- **Magic** (4-16 bytes at offset 0)
- **Version field** (4 bytes at offset N) — usually a uint32 LE
- **Length field** (4-8 bytes at offset M) — usually a uint32 LE
- **Count field** (4 bytes at offset K) — usually a uint32 LE
- **First record** (starts after the header)

The header is usually 16-64 bytes. The first record's start
gives you a candidate "header size" constant.

**Iteration 3 — Draft the .ksy**

Create `data/ksy/<format>.ksy` with:

```yaml
meta:
  id: my-format
  title: My Format
  license: MIT
  vendor-neutral: true
seq:
  - id: magic
    contents: [4 bytes]  # placeholder
  - id: version
    type: u4le
  - id: header_size
    type: u4le
  - id: record_count
    type: u4le
  - id: records
    type: record(_index, _)
    repeat: expr
    repeat-expr: record_count
types:
  record:
    seq:
      - id: index
        type: u4le
      - id: data
        size: ???  # placeholder — refine in iteration 4
```

**Iteration 4 — Compile + parse + diff**

```bash
kaitai-struct-compiler --target python --outdir data/ksy/_compiled data/ksy/<format>.ksy
```

Then:

```python
from kaitaistruct import my_format
with open(path, "rb") as f:
    parsed = my_format.MyFormat.from_bytes(f.read())
print(parsed)
```

Look at what the parser found and what it didn't. Refine
the placeholder fields (e.g. `size: ???` becomes
`size-eos: true` if the record is variable-length, or
`size: 64` if every record is a fixed 64 bytes).

**Iteration 5 — Finalize + commit**

Once the parser handles every record, add a docstring
with the field meanings, run the leakage test, and commit:

```yaml
meta:
  id: my-format
  title: My Format
  license: MIT
  vendor-neutral: true
  endian: le
doc: |
  Format reverse-engineered from <source>. Field meanings:
  - magic: 4-byte ASCII tag
  - version: file format version (currently 1)
  - header_size: total header size in bytes (currently 32)
  - record_count: number of records that follow
  - records: array of <record_count> record entries
```

Run `./verify.sh` to confirm the leakage test passes (the KSY
must not name any specific commercial product).

## Output report format

```markdown
# Archive Format Reverse — <format>

## Magic analysis
- First 16 bytes: ...
- Closest known format: ...
- No known match — proprietary format.

## Hex walk
- Offset 0x00: magic (4 bytes, ASCII "....")
- Offset 0x04: version (u4le, observed: 1)
- Offset 0x08: header_size (u4le, observed: 32)
- Offset 0x0C: record_count (u4le, observed: 42)
- Offset 0x10..0x20: reserved
- Offset 0x20: first record (record[0])

## Draft KSY
- Path: data/ksy/my_format.ksy
- Status: parses 42/42 records cleanly

## Open questions
- record[0].data ends with what looks like a length prefix —
  variable-length record, or fixed-length with a different
  size?
- The last record's data extends to EOF — is record[41] a
  terminator?

## Limitations
- The KSY is read-only. A write-side spec is a separate
  concern.
- Strings inside records are not auto-decoded; the analyst
  may need to add `type: str` or `type: strz` after a
  parse-and-look pass.
```

## Pairing with other skills

- `re-static-triage` — for the first-pass "what format is this"
  call. If `re-lief.parse_binary` returns a known format, this
  skill's territory is over before it starts.
- `re-format-decode` — for the read-side runtime after the KSY
  is committed. `re-kaitai.parse_with_format` calls the compiled
  KSY and returns the parsed tree.
- `re-leak-scan` — for the string-side analysis of the
  archive's content (after the KSY lets you extract the
  per-record data).
- `re-decompile` — for the binary-side analysis of the
  loader that *reads* this format. The KSY is the read-side;
  the loader is the consumer.
