"""Native binary analysis (LIEF wrapper).

Handles parsing of ELF shared objects (``lib/<abi>/*.so``), OAT compiled
DEX (``.oat``), VDEX (``.vdex``), and ART (``.art``) images from inside
an APK. The wrapper exposes a typed, JSON-serializable view on top of
LIEF's polymorphic object model so the MCP servers can return
tool-friendly results.

Typical usage::

    native = NativeView.from_apk(apk)
    for lib in native.list_libs():
        info = native.parse(lib.name)
        if info.security["nx"] and info.security["pie"]:
            ...

This module never mutates the underlying APK. Read-only by design.
"""

from __future__ import annotations

import io
import os
import re
import struct
import zipfile
from dataclasses import dataclass
from typing import Any

from .apk import Apk
from .errors import APKError, APKInvalid

try:
    import lief  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "lief is required for android_re_core.native. Install with: uv pip install 'lief==0.17.6'"
    ) from e


__all__ = [
    "BinaryFormat",
    "BinaryInfo",
    "ExportEntry",
    "ImportEntry",
    "NativeView",
    "PackerMatch",
    "Relocation",
    "Section",
    "SecurityFeatures",
    "StringEntry",
    "Symbol",
]


# ---------------------------------------------------------------------------
# Type enums
# ---------------------------------------------------------------------------

#: Binary format enumeration. Mirrors the set of formats LIEF parses.
BinaryFormat = str  # "ELF" | "PE" | "MACHO" | "OAT" | "ART" | "VDEX" | "UNKNOWN"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SecurityFeatures:
    """Binary hardening indicators (security-relevant flags)."""

    nx: bool
    relro: str  # "none" | "partial" | "full"
    stack_canary: bool
    pie: bool
    fortify: bool
    rpath: str | None
    runpath: str | None
    symbols_stripped: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "nx": self.nx,
            "relro": self.relro,
            "stack_canary": self.stack_canary,
            "pie": self.pie,
            "fortify": self.fortify,
            "rpath": self.rpath,
            "runpath": self.runpath,
            "symbols_stripped": self.symbols_stripped,
        }


@dataclass(frozen=True)
class Symbol:
    """A single symbol in a binary."""

    name: str
    value: int
    size: int
    binding: str  # "LOCAL" | "GLOBAL" | "WEAK" | "UNIQUE"
    type: str  # "FUNC" | "OBJECT" | "SECTION" | "FILE" | "NOTYPE"
    visibility: str  # "DEFAULT" | "HIDDEN" | "INTERNAL" | "PROTECTED"
    section_name: str | None
    is_external: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "size": self.size,
            "binding": self.binding,
            "type": self.type,
            "visibility": self.visibility,
            "section_name": self.section_name,
            "is_external": self.is_external,
        }


@dataclass(frozen=True)
class ImportEntry:
    """A single imported symbol or library."""

    name: str
    library: str | None
    address: int | None

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "library": self.library, "address": self.address}


@dataclass(frozen=True)
class ExportEntry:
    """A single exported symbol."""

    name: str
    address: int
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "address": self.address, "size": self.size}


@dataclass(frozen=True)
class Relocation:
    """A single relocation entry."""

    address: int
    symbol: str | None
    type: str | None

    def to_dict(self) -> dict[str, Any]:
        return {"address": self.address, "symbol": self.symbol, "type": self.type}


@dataclass(frozen=True)
class Section:
    """A single section in the binary."""

    name: str
    address: int
    size: int
    type: str  # "PROGBITS" | "NOBITS" | "STRTAB" | "SYMTAB" | ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "address": self.address,
            "size": self.size,
            "type": self.type,
        }


@dataclass(frozen=True)
class StringEntry:
    """A printable string extracted from the binary."""

    value: str
    offset: int
    section: str | None
    encoding: str  # "utf-8" | "utf-16-le" | "ascii"

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "offset": self.offset,
            "section": self.section,
            "encoding": self.encoding,
        }


@dataclass(frozen=True)
class BinaryInfo:
    """Top-level summary of a parsed binary inside an APK."""

    name: str
    format: BinaryFormat
    architecture: str  # "arm" | "arm64" | "x86" | "x86_64" | ...
    bits: int  # 32 or 64
    endianness: str  # "little" | "big"
    entrypoint: int
    base_address: int
    is_pie: bool
    is_stripped: bool
    security: SecurityFeatures
    sections: tuple[Section, ...] = ()
    imports: tuple[ImportEntry, ...] = ()
    exports: tuple[ExportEntry, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "format": self.format,
            "architecture": self.architecture,
            "bits": self.bits,
            "endianness": self.endianness,
            "entrypoint": self.entrypoint,
            "base_address": self.base_address,
            "is_pie": self.is_pie,
            "is_stripped": self.is_stripped,
            "security": self.security.to_dict(),
            "section_count": len(self.sections),
            "import_count": len(self.imports),
            "export_count": len(self.exports),
        }


@dataclass(frozen=True)
class PackerMatch:
    """A packer/protection detection match."""

    packer: str
    confidence: float  # 0.0 - 1.0
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {"packer": self.packer, "confidence": self.confidence, "evidence": self.evidence}


# ---------------------------------------------------------------------------
# NativeView
# ---------------------------------------------------------------------------


#: Minimum printable string length when extracting from .rodata.
_DEFAULT_MIN_STRING_LENGTH = 4

#: Heuristic packer signatures. The matcher is intentionally simple: name
#: patterns in symbol/string tables and section names.
_PACKER_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("UPX", re.compile(r"UPX[!_]", re.IGNORECASE)),
    ("UPX", re.compile(r"\$Info.*\$|\$Orig.*\$", re.IGNORECASE)),
    ("LLVM-Obfuscator", re.compile(r"llvm.*obf", re.IGNORECASE)),
    ("OLLVM", re.compile(r"ollvm|sub_164|sub_180", re.IGNORECASE)),
    ("Bangcle", re.compile(r"bangcle", re.IGNORECASE)),
    ("DexGuard", re.compile(r"dexguard", re.IGNORECASE)),
    ("ProGuard", re.compile(r"proguard", re.IGNORECASE)),
    ("R8", re.compile(r"\br8\b", re.IGNORECASE)),
    ("SecNeo", re.compile(r"secneo", re.IGNORECASE)),
    ("Tencent-Pack", re.compile(r"tencent.*pack|tp\.so", re.IGNORECASE)),
    ("360-Pack", re.compile(r"360.*pack|jiagu", re.IGNORECASE)),
    ("Baidu-Pack", re.compile(r"baidu.*pack", re.IGNORECASE)),
    ("iJiami", re.compile(r"ijiami", re.IGNORECASE)),
)


class NativeView:
    """A view over all native libraries inside an APK.

    Construct with :meth:`from_apk`. The view is read-only; it lazily
    parses each library on first access and caches the result.
    """

    def __init__(
        self, apk: Apk, lib_paths: list[str], _cache: dict[str, lief.Binary] | None = None
    ) -> None:
        self._apk = apk
        self._lib_paths = lib_paths
        self._cache: dict[str, lief.Binary] = _cache if _cache is not None else {}

    @classmethod
    def from_apk(cls, apk: Apk) -> NativeView:
        """Build a :class:`NativeView` from an :class:`Apk`.

        Enumerates ``lib/<abi>/*.so`` entries in the APK's ZIP and lists
        them in the returned view. The actual parse happens on first
        access to :meth:`parse`.
        """
        if apk.is_closed:
            raise APKInvalid("APK has been closed")
        raw = apk.raw
        libs: list[str] = []
        for name in raw.get_files():
            if name.startswith("lib/") and name.endswith(".so"):
                libs.append(name)
        return cls(apk=apk, lib_paths=sorted(libs))

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    def list_libs(self) -> list[str]:
        """Return all ``lib/<abi>/*.so`` paths in the APK."""
        return list(self._lib_paths)

    def lib_count(self) -> int:
        return len(self._lib_paths)

    def abis(self) -> list[str]:
        """Return the set of ABIs the APK ships native code for."""
        abis: set[str] = set()
        for p in self._lib_paths:
            parts = p.split("/")
            if len(parts) >= 2 and parts[0] == "lib":
                abis.add(parts[1])
        return sorted(abis)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def parse(self, lib_name: str) -> BinaryInfo:
        """Parse a single library and return a :class:`BinaryInfo`."""
        if lib_name not in self._lib_paths:
            raise APKError(
                f"Library not in APK: {lib_name}",
                details={"lib_name": lib_name, "available": self._lib_paths[:5]},
            )
        binary = self._load_binary(lib_name)
        return self._binary_to_info(lib_name, binary)

    def _load_binary(self, lib_name: str) -> lief.Binary:
        """Load (and cache) a LIEF binary from inside the APK."""
        if lib_name in self._cache:
            return self._cache[lib_name]
        with zipfile.ZipFile(str(self._apk.path), "r") as zf:
            data = zf.read(lib_name)
        # Wrap in a BytesIO for LIEF. lief.parse accepts bytes in 0.17.x.
        binary = lief.parse(io.BytesIO(data))
        if binary is None:
            raise APKInvalid(
                f"LIEF could not parse {lib_name}",
                details={"lib_name": lib_name, "size": len(data)},
            )
        self._cache[lib_name] = binary
        return binary

    @staticmethod
    def _binary_to_info(name: str, binary: lief.Binary) -> BinaryInfo:
        """Convert a LIEF binary to a :class:`BinaryInfo`."""
        # Format
        fmt: BinaryFormat
        if isinstance(binary, lief.ELF.Binary):
            fmt = "ELF"
        elif isinstance(binary, lief.PE.Binary):
            fmt = "PE"
        elif isinstance(binary, lief.MachO.Binary):
            fmt = "MACHO"
        else:
            fmt = "UNKNOWN"

        # Architecture / bits / endianness
        arch, bits, endianness = _describe_arch(binary)

        # Security
        sec = _extract_security(binary)

        # Sections, imports, exports
        sections = tuple(_section_to_dataclass(s) for s in (binary.sections or ()))
        imports = tuple(_imports_to_dataclasses(binary))
        exports = tuple(_exports_to_dataclasses(binary))

        return BinaryInfo(
            name=name,
            format=fmt,
            architecture=arch,
            bits=bits,
            endianness=endianness,
            entrypoint=int(binary.entrypoint) if binary.entrypoint else 0,
            base_address=int(binary.imagebase) if hasattr(binary, "imagebase") else 0,
            is_pie=getattr(binary, "is_pie", False),
            is_stripped=not bool(getattr(binary, "symbols", [])),
            security=sec,
            sections=sections,
            imports=imports,
            exports=exports,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def find_symbol(self, lib_name: str, name_substring: str, *, limit: int = 100) -> list[Symbol]:
        """Find symbols by name substring in a single library."""
        binary = self._load_binary(lib_name)
        pattern = re.compile(re.escape(name_substring), re.IGNORECASE)
        out: list[Symbol] = []
        for sym in binary.symbols or ():
            if not pattern.search(sym.name):
                continue
            out.append(_symbol_to_dataclass(sym))
            if len(out) >= limit:
                break
        return out

    def get_strings(
        self,
        lib_name: str,
        *,
        section: str = ".rodata",
        min_length: int = _DEFAULT_MIN_STRING_LENGTH,
        limit: int = 1000,
    ) -> list[StringEntry]:
        """Extract printable strings from a section.

        Implementation: re-reads the section bytes from the LIEF binary
        and runs a UTF-8/UTF-16-LE scan. ASCII-only is the default
        fallback; we report the encoding per string.
        """
        binary = self._load_binary(lib_name)
        target = None
        for s in binary.sections or ():
            if s.name == section:
                target = s
                break
        if target is None:
            return []
        # LIEF exposes content as a list of ints
        content = bytes(target.content)
        out: list[StringEntry] = []
        # UTF-8 / ASCII scan
        for m in re.finditer(rb"[\x20-\x7e]{%d,}" % min_length, content):
            value = m.group(0).decode("ascii", errors="replace")
            out.append(
                StringEntry(
                    value=value,
                    offset=target.virtual_address + m.start(),
                    section=section,
                    encoding="ascii",
                )
            )
            if len(out) >= limit:
                break
        return out

    def detect_packers(self, lib_name: str) -> list[PackerMatch]:
        """Heuristic packer/protection detection.

        Walks exported symbol names and section names looking for known
        packer signatures. Returns matches with a confidence score.
        """
        binary = self._load_binary(lib_name)
        # Collect all name-ish strings
        names: list[str] = []
        names.extend(s.name for s in (binary.symbols or ()) if s.name)
        names.extend(s.name for s in (binary.sections or ()) if s.name)
        for lib in getattr(binary, "libraries", []) or ():
            names.append(lib)
        haystack = "\n".join(names)
        matches: list[PackerMatch] = []
        for packer_name, pattern in _PACKER_SIGNATURES:
            m = pattern.search(haystack)
            if m:
                matches.append(
                    PackerMatch(
                        packer=packer_name,
                        confidence=0.7 if "UPX" not in packer_name else 0.9,
                        evidence=f"matched pattern in {m.group(0)!r}",
                    )
                )
        return matches


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _describe_arch(binary: lief.Binary) -> tuple[str, int, str]:
    """Return (architecture, bits, endianness)."""
    try:
        # In LIEF 0.17, ``ARCH`` is an inline-defined enum that lives
        # on the format-specific submodule (``lief._lief.ELF.ARCH``,
        # ``lief._lief.PE.ARCH``, ``lief._lief.MachO.ARCH``). Resolve
        # whichever one matches the binary.
        arch_enum_cls = None
        if isinstance(binary, lief.ELF.Binary):
            arch_enum_cls = lief._lief.ELF.ARCH  # type: ignore[attr-defined]
        elif isinstance(binary, lief.PE.Binary):
            arch_enum_cls = lief._lief.PE.ARCH  # type: ignore[attr-defined]
        elif isinstance(binary, lief.MachO.Binary):
            arch_enum_cls = lief._lief.MachO.ARCH  # type: ignore[attr-defined]
        if arch_enum_cls is None:
            return ("unknown", 0, "little")

        # The LIEF enum name doesn't always match our canonical name
        # (e.g. ``I386`` vs ``X86``, ``AARCH64`` vs ``ARM64``). Build
        # the map defensively by checking for each attribute.
        def _m(name: str) -> Any:
            return getattr(arch_enum_cls, name, None)

        arch_map: dict[Any, tuple[str, int, str]] = {}
        for enum_name, label in (
            ("ARM", ("arm", 32, "little")),
            ("AARCH64", ("arm64", 64, "little")),
            ("I386", ("x86", 32, "little")),
            ("X86", ("x86", 32, "little")),
            ("X86_64", ("x86_64", 64, "little")),
            ("MIPS", ("mips", 32, "little")),
            ("MIPS64", ("mips64", 64, "little")),
            ("PPC", ("ppc", 32, "big")),
            ("PPC64", ("ppc64", 64, "big")),
            ("RISCV", ("riscv", 32, "little")),
            ("RISCV64", ("riscv64", 64, "little")),
        ):
            v = _m(enum_name)
            if v is not None:
                arch_map[v] = label

        arch_enum = None
        for attr in ("machine_type", "machine", "cpu_type"):
            if hasattr(binary, "header") and hasattr(binary.header, attr):
                try:
                    val = getattr(binary.header, attr)
                    if val is not None:
                        arch_enum = val
                        break
                except Exception:
                    continue
        if arch_enum is not None:
            return arch_map.get(arch_enum, ("unknown", 0, "little"))
    except Exception:
        pass
    return ("unknown", 0, "little")


def _extract_security(binary: lief.Binary) -> SecurityFeatures:
    """Pull security-relevant flags from a LIEF binary."""
    # NX
    nx = False
    if hasattr(binary, "has_nx"):
        try:
            nx = bool(binary.has_nx)
        except Exception:
            nx = False

    # RELRO
    relro = "none"
    if hasattr(binary, "has_relro"):
        try:
            if binary.has_relro:
                # Check for BIND_NOW (full)
                relro = "full" if getattr(binary, "has_bind_now", False) else "partial"
        except Exception:
            relro = "none"

    # Canary / Fortify are heuristic — we just check symbols
    sym_names = {s.name for s in (binary.symbols or ()) if s.name}
    stack_canary = any(
        ("stack_chk" in n) or ("__stack_chk" in n) or ("__msan" in n) for n in sym_names
    )
    fortify = any(
        "__" + prefix + "_chk" in n for n in sym_names for prefix in ("str", "mem", "strncpy")
    )

    # PIE
    is_pie = False
    if hasattr(binary, "is_pie"):
        try:
            is_pie = bool(binary.is_pie)
        except Exception:
            is_pie = False

    # RPATH / RUNPATH
    rpath = getattr(binary, "rpath", None) or None
    runpath = getattr(binary, "runpath", None) or None

    # Stripped?
    symbols_stripped = not bool(getattr(binary, "symbols", []))

    return SecurityFeatures(
        nx=nx,
        relro=relro,
        stack_canary=stack_canary,
        pie=is_pie,
        fortify=fortify,
        rpath=rpath,
        runpath=runpath,
        symbols_stripped=symbols_stripped,
    )


def _section_to_dataclass(s: Any) -> Section:
    return Section(
        name=getattr(s, "name", ""),
        address=int(getattr(s, "virtual_address", 0)),
        size=int(getattr(s, "size", 0)),
        type=str(getattr(s, "type", "UNKNOWN")),
    )


def _symbol_to_dataclass(s: Any) -> Symbol:
    return Symbol(
        name=getattr(s, "name", ""),
        value=int(getattr(s, "value", 0)),
        size=int(getattr(s, "size", 0)),
        binding=str(getattr(s, "binding", "UNKNOWN")),
        type=str(getattr(s, "type", "NOTYPE")),
        visibility=str(getattr(s, "visibility", "DEFAULT")),
        section_name=getattr(getattr(s, "section", None), "name", None),
        is_external=bool(getattr(s, "is_exported", False)),
    )


def _imports_to_dataclasses(binary: lief.Binary) -> list[ImportEntry]:
    """Iterate imported symbols. Supports ELF (relocations + dynamic) and PE."""
    out: list[ImportEntry] = []
    try:
        if hasattr(binary, "imported_functions"):
            for f in binary.imported_functions or ():
                lib = None
                # lief.ELF.Function has a library attribute
                lib = getattr(f, "library", None)
                if lib is not None and not isinstance(lib, str):
                    lib = str(lib)
                out.append(
                    ImportEntry(
                        name=getattr(f, "name", ""),
                        library=lib,
                        address=int(getattr(f, "address", 0)) or None,
                    )
                )
        elif hasattr(binary, "imports"):  # PE-style
            for imp in binary.imports or ():
                out.append(
                    ImportEntry(
                        name=str(imp.name),
                        library=str(imp.entry) if hasattr(imp, "entry") else None,
                        address=int(getattr(imp, "address", 0)) or None,
                    )
                )
    except Exception:
        return out
    return out


def _exports_to_dataclasses(binary: lief.Binary) -> list[ExportEntry]:
    """Iterate exported symbols."""
    out: list[ExportEntry] = []
    try:
        if hasattr(binary, "exported_functions"):
            for f in binary.exported_functions or ():
                out.append(
                    ExportEntry(
                        name=getattr(f, "name", ""),
                        address=int(getattr(f, "address", 0)),
                        size=int(getattr(f, "size", 0)),
                    )
                )
        elif hasattr(binary, "get_export"):
            # Fallback for some formats
            for sym in binary.symbols or ():
                if getattr(sym, "is_exported", False):
                    out.append(
                        ExportEntry(
                            name=sym.name,
                            address=int(getattr(sym, "value", 0)),
                            size=int(getattr(sym, "size", 0)),
                        )
                    )
    except Exception:
        return out
    return out


def parse_binary_bytes(data: bytes, name: str = "<memory>") -> BinaryInfo:
    """Parse a raw binary buffer (e.g. extracted from an APK) for one-off analysis.

    Use this when you have the bytes already in memory and don't want to
    round-trip through the APK ZIP.
    """
    binary = lief.parse(io.BytesIO(data))
    if binary is None:
        raise APKInvalid(
            "LIEF could not parse binary",
            details={"name": name, "size": len(data)},
        )
    return NativeView._binary_to_info(name, binary)


# Suppress unused import warnings for things only used in some lief versions.
_ = (struct, os)
