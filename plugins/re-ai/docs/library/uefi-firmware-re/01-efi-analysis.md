---
title: "UEFI / EFI Firmware Reverse Engineering Workflow"
category: "uefi-firmware-re"
platforms: ["linux", "windows"]
difficulty: "advanced"
tags: ["uefi", "efi", "firmware", "spi-flash", "smm", "pei", "dxe", "secure-boot", "chain-of-trust"]
summary: "UEFI/EFI firmware RE workflow: SPI flash layout, SEC/PEI/DXE phases, Boot Services vs Runtime Services, the canonical Ghidra plugin for EFI binaries, and the chain-of-trust primitives (SMM, secure boot, measured boot)."
updated: "2026-06-06"
related:
  - "native/01-elf-format"
  - "native/02-pe-section-layout"
  - "tools/01-ghidra"
  - "anti-analysis/01-anti-debug"
---

# UEFI / EFI Firmware Reverse Engineering Workflow

## Summary

UEFI (Unified Extensible Firmware Interface) is
the modern replacement for the legacy BIOS. The
firmware binary lives in a SPI flash chip on the
motherboard; it's loaded by the platform's
reset vector, runs through a multi-phase boot
chain, and hands control to the OS bootloader.
The reverse-engineering workflow treats the
firmware as a structured file format with
a defined boot chain.

The canonical entry-point tool is a Ghidra
plugin that auto-detects the EFI binary format
and applies the canonical PE/TE/COFF loaders.

## Why this matters

UEFI firmware is the **root of trust** for the
platform. A vulnerability in the firmware (a
SMM handler bug, a DXE driver overflow, a
secure-boot bypass) compromises the entire OS
that runs on top. The RE workflow is the
analyst's first view of the platform's security
posture.

The cost of not knowing: the analyst assumes
the platform is secure because the OS is
patched; the firmware-level compromise makes
the OS-level patch moot.

## Mechanics

### SPI flash layout

The firmware binary lives in a 16-32 MB SPI
flash chip on the motherboard. The chip is
divided into **regions**:

- **FD** (Flash Descriptor) — the platform
  vendor's region. Defines the chip's
  partition table + the read / write
  protections.
- **ME** (Management Engine) — the Intel
  Management Engine region. The ME is a
  separate ARC / x86 processor on the chipset
  that runs its own firmware. Often
  cryptographically opaque.
- **BIOS** — the main firmware region. The
  UEFI payload lives here.
- **GbE** (Gigabit Ethernet) — the network
  card's option ROM.
- **PDR** (Platform Data Region) — the
  vendor's serial-number + MAC + licence
  storage.

The UEFI payload is in the **BIOS** region.
A 16 MB flash chip is the common case; the
UEFI payload itself is 4-8 MB.

### SEC / PEI / DXE / BDS / TSL / RT phases

The UEFI boot chain is a sequence of phases.
Each phase is a separately compiled EFI binary
that hands off to the next:

1. **SEC** (Security) — the reset vector.
   Sets up the temporary RAM (CAR — Cache As
   RAM). The SEC core lives in the platform
   vendor's boot ROM (often a small SPI
   sub-region).
2. **PEI** (Pre-EFI Initialization) —
   initialises the DRAM. The PEI core is a
   separate EFI binary; PEIMs (PEI Modules)
   are the drivers.
3. **DXE** (Driver Execution Environment) —
   the main driver phase. The DXE core is a
   separate EFI binary; DXE drivers are
   individual EFI binaries that each handle
   one protocol (Console, Network, BlockIo,
   etc.).
4. **BDS** (Boot Device Selection) — selects
   the boot device (UEFI Shell, GRUB, Windows
   Boot Manager, etc.).
5. **TSL** (Transient System Load) — runs
   the OS bootloader.
6. **RT** (Runtime) — the OS is running; the
   runtime services (GetTime, GetVariable,
   SetVariable, etc.) are still available.

The SEC + PEI + DXE phases are the RE
analyst's primary surface. The DXE drivers
are the most common analysis target — they
implement the platform's protocol stack.

### Boot Services vs Runtime Services

UEFI exports two sets of services:

- **Boot Services** — available from SEC through
  TSL. Includes the protocol stack (LocateProtocol,
  OpenProtocol, HandleProtocol), the memory
  services (AllocatePages, FreePages), and the
  event / timer services.
- **Runtime Services** — available from RT onwards
  (after the OS has taken over). Includes the
  variable services (GetVariable, SetVariable,
  GetNextVariableName), the time services, and
  the reset services.

The Runtime Services are the **secure-boot
primitives** — `SetVariable` is what the OS uses
to write to the UEFI variables, and the
authentication chain (PK / KEK / DB / DBX) is
enforced by the firmware's `SetVariable`
implementation.

### Chain-of-trust primitives

The UEFI chain of trust has three layers:

- **Secure Boot** — the platform's
  authentication chain. The firmware refuses
  to load a DXE driver / bootloader that
  doesn't have a valid signature in the DB
  (allowed signatures) or that matches an
  entry in the DBX (revoked signatures). The
  PK / KEK / DB / DBX are themselves stored
  in the firmware's authenticated variables.
- **Measured Boot** (TPM-based) — the
  firmware measures (hashes) each phase
  before loading it and stores the hash in
  the TPM's PCRs. The OS can later attest
  to the TPM that the boot chain was
  un-tampered.
- **SMM** (System Management Mode) — the
  firmware's most privileged mode. SMM
  handlers run below the OS; a vulnerability
  in an SMM handler is the most severe
  class of firmware vulnerability (the
  handler can read / write any memory).

## Approach

The typical UEFI RE workflow:

1. **Dump the SPI flash.** The `flashrom`
   tool reads the SPI chip via a hardware
   programmer (SOIC clip + CH341A, or
   vendor-specific tool for Intel
   platforms). The dump is a 16-32 MB
   binary.
2. **Extract the UEFI region.** Use a
   firmware-parsing tool (UEFITool,
   IFRExtractor) to split the dump into
   the FD / ME / BIOS / GbE / PDR regions.
3. **Identify the EFI binaries.** The
   UEFI firmware is a collection of
   separately-compiled EFI binaries
   (PE32+ format with a different
   subsystem field). The `efiXplorer`
   Ghidra plugin auto-detects the EFI
   format and applies the canonical
   PE32+ loader.
4. **Load the SEC / PEI / DXE cores in
   Ghidra.** The cores are the first
   targets — they implement the platform's
   protocol stack.
5. **Walk the DXE drivers.** Each DXE
   driver is a separate EFI binary; the
   Ghidra `efiXplorer` plugin provides
   a tree view of the drivers + their
   protocols.
6. **Audit the secure-boot variables.**
   The PK / KEK / DB / DBX are stored in
   the firmware's authenticated variables.
   The `UEFIReplace` tool reads the variables
   and dumps them.
7. **Audit the SMM handlers.** The SMM
   handler code lives in the SMM core +
   the SMM drivers. The audit is a
   pattern-by-pattern check: any handler
   that reads / writes arbitrary memory
   without an authorisation check is a
   candidate for a CVE.

## Common pitfalls

- **Don't disassemble the ME region.** The
  Intel Management Engine runs its own
  ARC / x86 firmware that is often
  cryptographically signed and opaque.
  Trying to RE the ME is a separate
  project, often blocked by the
  cryptography.
- **Don't confuse UEFI with BIOS.** Legacy
  BIOS is a 16-bit real-mode binary; UEFI
  is a 32/64-bit protected-mode EFI binary.
  The RE workflow is completely different.
- **Don't trust the secure-boot variables
  at face value.** The DB / DBX are
  themselves authenticated; a tampered
  DB is a sign of a compromised firmware.
- **Don't assume the SPI flash is read-only.**
  The platform's firmware-update path
  writes to the SPI flash; an attacker
  with code execution in the firmware can
  rewrite the entire flash.

## Tooling pointers

- `flashrom` — the SPI flash reader.
- `UEFITool` / `IFRExtractor` — the
  firmware-region parser.
- `efiXplorer` — the Ghidra plugin for
  EFI binary auto-detection.
- `UEFIReplace` — the secure-boot
  variable audit tool.
- `chipsec` — the platform-security
  audit framework (SMM handler audit,
  SPI flash write-protect audit, etc.).
- `tools/01-ghidra` — the Ghidra
  workflow; pairs with the efiXplorer
  plugin.
- `anti-analysis/01-anti-debug` — for the
  secure-boot-bypass angle (the bypass
  is often a chain-of-trust primitive,
  not a single-CPU anti-debug check).
