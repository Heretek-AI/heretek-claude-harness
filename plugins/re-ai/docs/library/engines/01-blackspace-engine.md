# BlackSpace Engine

**Engine type:** Proprietary game engine (handler-table dispatch architecture)
**Characteristics:** Handler-table dispatch architecture (Pattern A-VMT in the anti-tamper taxonomy)

## Headline

The BlackSpace Engine is a proprietary game engine. The engine's encrypted-VM protection is NOT a traditional bytecode interpreter — it uses a **handler-table-dispatch** architecture. RE-AI's `ANTI-TAMPER-TAXONOMY.md` calls this **Pattern A-VMT** (`encrypted-vm-handler-table-dispatch`).

## Architecture

The `.xcode` section has TWO sub-regimes:

1. **Dispatch table** (192KB low-entropy 3.4-3.7): 36+ 16-byte big-endian entries `[u32 handler_id][u32 reserved=0][u64 target_address]`
2. **Encrypted metadata** (3.2MB high-entropy 6.3-7.2): the encrypted dispatch metadata / key tables

Handler IDs fall in range 0x01-0x35 (with gaps for reserved/unused slots). The targets point into `.link` (zero-initialized in file = runtime-decrypted BSS). The handler bodies live in `.arch` (statically linked OpenSSL + handler library; the first 64KB contains 10+ x86_64 function prologues).

## Section map (representative analysis)

| Section | Size | Entropy | Role |
|---|---|---|---|
| `.arch` | 73MB | 6.752 | Handler library + static OpenSSL |
| `.link` | 21MB | 5.54 | Relocation + BSS |
| `.rodata` | 300MB | 6.726 | Resources |
| `.xcode` | 3.4MB | (dual) | Dispatch + encrypted metadata |
| `.xtext` | 36KB | 5.856 | Handlers (legacy) |
| `.sbss` | 2.7MB | 7.304 | BSS |

## Cross-publisher view

| Game | Status | Doc |
|---|---|---|
| Representative binary | Pattern A-VMT canonical case | See the anti-tamper taxonomy doc |
| Black Desert Online | Predecessor — likely same architecture | (deferred) |
| DokeV | Sequel — same engine | (deferred) |

## Cross-references

- RE-AI `ANTI-TAMPER-TAXONOMY.md` Pattern A-VMT (the taxonomy entry this engine motivates)
- RE-AI `servers/re-lief/src/re_lief/protection_catalog.py` `_classify_avmt_signature` (the v2.9.1+ classifier)
- See the RE-AI output directory for per-binary triage data. (the v2.9.0 source data)
- RE-UNLEASHED `protection/encrypted-vm-bytecode-interpreter/pattern-a-vmt.md`
- RE-UNLEASHED `publishers/pearl-abyss/crimson-desert/`
