---
title: "ELF Format"
category: "native"
platforms: ["linux", "macos", "android"]
difficulty: "intermediate"
tags: ["file-format", "static-analysis", "fundamentals"]
summary: "The Executable and Linkable Format: program headers, section headers, the dynamic loader's view, the dynamic symbol table, relocations, and the linker structures you'll be reading at the RE bench."
updated: "2026-06-04"
related: ["native/02-pe-section-layout", "native/03-macho-format", "native/06-hooking"]
---

## Summary

ELF (Executable and Linkable Format) is the binary format for Linux, *BSD, Android, Solaris, and most non-Windows desktop and embedded systems. It's also the on-disk shape of shared libraries, object files, and core dumps. The RE-relevant view is the dynamic loader's view: program headers, the dynamic section, the symbol table, and the relocation tables.

## Why this matters

If you reverse-engineer any Linux/Android/FreeBSD/embedded binary, you read ELF. If you debug crashes, you read core dumps — ELF. If you patch a binary, you edit ELF sections. If you write a custom loader, you parse ELF by hand. The format is the lingua franca of everything outside Windows.

## Mechanics

### Two views, one file

ELF has *two* parallel header tables:

- The **program header table** describes *segments* — what the loader reads. Each `PT_LOAD` entry is a chunk of the file that gets mapped into memory with specific permissions (`PF_R`, `PF_W`, `PF_X`).
- The **section header table** describes *sections* — what the linker reads. `.text`, `.data`, `.bss`, `.rodata`, `.symtab`, `.strtab`, `.dynsym`, `.dynstr`, `.rela.*`, `.init_array`, `.fini_array`, `.got`, `.plt`, etc.

The two are related but not identical. A single `PT_LOAD` segment typically covers several sections. Tools like `readelf -l` show segments, `readelf -S` shows sections, and `readelf -e` shows both. The mapping between them is one of the first things you internalise.

### The structure of an ELF file

```
+--------------------------------+
|  ELF header (Ehdr)             |  entry point, machine, header table offsets
+--------------------------------+
|  Program header table          |  (Phdr array — for the loader)
+--------------------------------+
|  .text                         |  code
|  .rodata                       |  read-only data, string literals
|  .plt / .plt.got               |  procedure linkage table (PLT)
|  .got / .got.plt               |  global offset table
|  .data                         |  initialised mutable data
|  .bss                          |  zero-initialised mutable data (no on-disk bytes)
|  .dynsym / .dynstr             |  dynamic symbol tables
|  .rela.dyn / .rela.plt         |  relocations (with addend)
|  .init_array / .fini_array     |  constructor/destructor function pointers
|  .note.* / .note.gnu.*         |  notes (build-id, ABI tags, etc.)
|  .interp                       |  dynamic linker path (for ET_DYN/ET_EXEC)
+--------------------------------+
|  Section header table          |  (Shdr array — for the linker)
+--------------------------------+
|  .shstrtab                     |  section name string table
+--------------------------------+
```

### Important fields in the ELF header

- `e_entry` — virtual address of the entry point. The loader jumps here.
- `e_phoff`, `e_phentsize`, `e_phnum` — program header table.
- `e_shoff`, `e_shentsize`, `e_shnum`, `e_shstrndx` — section header table.
- `e_type` — `ET_EXEC` (static executable), `ET_DYN` (shared object / PIE executable), `ET_REL` (relocatable object), `ET_CORE` (core dump).
- `e_machine` — `EM_X86_64`, `EM_AARCH64`, `EM_ARM`, `EM_RISCV`, `EM_386`, etc.

### Program headers (`PT_*`)

- `PT_LOAD` — a chunk of the file to be mapped. The permissions are encoded in `p_flags` (`PF_R`, `PF_W`, `PF_X`).
- `PT_INTERP` — the dynamic linker to invoke (`/lib64/ld-linux-x86-64.so.2` on glibc).
- `PT_DYNAMIC` — points to the `.dynamic` section.
- `PT_GNU_STACK` — `PF_X` flag indicates the stack should be executable. If present and **without** `PF_X`, the kernel will refuse to make the stack executable (NX).
- `PT_GNU_RELRO` — read-only relocations; tells the loader which parts to make read-only *after* applying relocations. Critical for RELRO security.
- `PT_GNU_PROPERTY` — notes for the loader (e.g. CET, IBT flags).
- `PT_TLS` — thread-local storage template.

### The dynamic section

The `.dynamic` section is an array of `{d_tag, d_val}` entries. The loader walks it to set up the process:

- `DT_NEEDED` — required shared libraries (e.g. `libc.so.6`).
- `DT_SONAME` — the shared object's name.
- `DT_SYMTAB` / `DT_STRTAB` — dynamic symbol table and string table addresses.
- `DT_PLTGOT` — address of the GOT (used for PLT resolution).
- `DT_JMPREL` / `DT_PLTREL` / `DT_PLTRELSZ` — PLT relocations.
- `DT_RELA` / `DT_RELASZ` / `DT_RELAENT` — `.rela.dyn` relocations.
- `DT_FLAGS` / `DT_FLAGS_1` — `BIND_NOW`, `NOW`, `PIE`, etc.
- `DT_INIT` / `DT_FINI` / `DT_INIT_ARRAY` / `DT_FINI_ARRAY` — constructors and destructors.

### Relocations

A relocation is a *patch instruction* the loader applies to the binary. For `ET_REL` (object files), relocations are how the linker resolves symbol references; for `ET_EXEC`/`ET_DYN` (executables and shared libraries), they're the *remaining* patches that couldn't be done at link time (because the actual load address isn't known until run time).

The important relocation types you'll see:

- `R_X86_64_GOTPCREL` — patch a 32-bit PC-relative offset to a GOT entry.
- `R_X86_64_PLT32` — a call to a function in another shared object, resolved via the PLT.
- `R_X86_64_RELATIVE` — `*reloc_addr = base_addr + addend`. Used heavily in PIE binaries to fix up absolute addresses.
- `R_AARCH64_*` — the equivalent AArch64 relocations.
- `R_386_JMP_SLOT` / `R_X86_64_JUMP_SLOT` — entries in `.got.plt`, one per imported function. Hooking an imported function is just *changing the value in the GOT slot* to point at your wrapper.

### Symbol tables

`.symtab` (and `.strtab` for the names) is the *full* symbol table — every function, every global, every static — used by the linker and by debuggers. `.dynsym` (and `.dynstr`) is the *dynamic* subset: only the symbols that need to be visible to other shared objects. Stripping a binary with `strip` removes `.symtab` but typically leaves `.dynsym` intact (you still need to find `main`).

Symbol types: `STT_FUNC`, `STT_OBJECT`, `STT_SECTION`, `STT_FILE`, `STT_NOTYPE`. Bindings: `STB_LOCAL` (file-local), `STB_GLOBAL` (exported), `STB_WEAK` (overridable).

## Approach

For a first pass on an unknown ELF:

1. `file target` — sanity check (machine, class, type).
2. `readelf -h target` — ELF header, entry point, machine.
3. `readelf -l target` — program headers. Note `PT_INTERP`, the `PT_LOAD` map, `PT_GNU_STACK` (NX?), `PT_GNU_RELRO`.
4. `readelf -d target` — dynamic section. Note `DT_NEEDED` (linked libraries), `DT_FLAGS_1` (PIE/NOW).
5. `readelf -s target` — symbol table. If `.symtab` is present, locate the entry point symbol. If only `.dynsym`, find exported functions.
6. `readelf -r target` — relocations. The presence of `R_*_JUMP_SLOT` entries means the binary has a working PLT/GOT.
7. `objdump -d target` — disassembly. Or open in your disassembler of choice.
8. For PIE: `readelf -d target | grep FLAGS_1.*PIE` to confirm, and remember that `e_entry` is a *relative* address (added to the runtime base).

## Common pitfalls

- **Confusing file offsets and virtual addresses.** `objdump` and `gdb` use VAs; `hexdump` and `xxd` use file offsets. For a `PT_LOAD` mapping that starts at file offset 0 and VA 0x400000, the two are equal — but for most shared libraries, they're not.
- **Stripped symbols.** Many release binaries have `.symtab` removed. You can still recover symbols via `__ksymtab_*` (kernel modules), `.dynsym`, or by walking the `.symtab` in a matching debug-info package. `addr2line` and `eu-addr2line` use the debug-info package.
- **PIE binaries with absolute `0` addresses in static views.** `readelf -h` will show a tiny `e_entry`; the real address is base + entry. The loader picks the base; tools like `gdb` and `objdump` display the loaded address when you attach.
- **Forgetting that relocations happen at load time.** When you dump a running process, the relocations have been applied — the file offsets and the in-memory layout are *not* identical. To convert, you need the loader's base address and the `PT_LOAD` mapping.
- **Treating `.plt` as static code.** The PLT is dynamically rewired (lazy binding) the first time a function is called. After the first call, the `jmp *GOT[n]` slot points at the resolved function; before, it points back at the PLT's resolver stub.

## Tooling pointers

- `readelf` — comprehensive ELF inspector (in `binutils`).
- `objdump` — disassembler and section dumper.
- `nm` — symbol table lister.
- `ldd` — show `DT_NEEDED` resolution at runtime.
- `eu-readelf` / `eu-objdump` (elfutils) — faster, DWARF-aware variants.
- [`ghidra`](../tools/01-ghidra.md) / [`binary-ninja`](../tools/03-binary-ninja.md) / IDA — full decompilation.

## References

- [System V ABI — ELF Specification](https://refspecs.linuxfoundation.org/elf/gabi4+/contents.html) — the canonical reference.
- [ELF man page (`man 5 elf`)](https://man7.org/linux/man-pages/man5/elf.5.html)
- [Linux Foundation: ELF Handling for Thread-Local Storage](https://www.akkadia.org/drepper/tls.pdf) — Ulrich Drepper's TLS note, which is the de-facto reference for `PT_TLS`.
