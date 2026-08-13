# re-binary-diff

MCP server for **read-only** binary comparison: a unified diff
between two files, and a per-section fingerprint of one file.
**Dry-run only** — the server never writes a byte to disk.

## Why

The 2026-06-05 stress test surfaced a need to compare an
original binary against a patched copy (the `Output/.../patches/`
workflow) without re-introducing the on-disk patch primitive.
`re-binary-diff` is the read-only cousin: it reports the diff,
it never applies it.

## Tools

| Tool | What it does |
|---|---|
| `check_binary_diff` | Health check — `re-binary-diff` has no system deps; always `status: OK` |
| `unified_diff` | Run `difflib.unified_diff` over the byte streams of two files (or, if too large, hash their chunks) and return a structured diff |
| `fingerprint_sections` | Return per-chunk SHA-256 + offset + size for a single file (a structural fingerprint, like `re-lief.normalize_for_diff` but at chunk granularity) |

## Install

Part of the RE-AI plugin; `./install.sh` installs the package. To
install standalone:

```bash
pip install -e ./servers/re-binary-diff
```

## Run

```bash
re-binary-diff                              # stdio transport (default for MCP)
python -m re_binary_diff                    # equivalent
```
