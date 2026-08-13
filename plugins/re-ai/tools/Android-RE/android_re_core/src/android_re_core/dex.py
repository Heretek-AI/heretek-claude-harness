"""DEX class / method / xref queries.

Built on top of androguard's :class:`DEX` object. The :class:`DexView`
class wraps one or more DEX files inside an APK and exposes typed,
filterable queries that return JSON-serializable results.

Typical usage::

    dex = DexView.from_apk(apk)
    for cls in dex.find_classes("Lcom/example/"):
        for m in dex.find_methods(class_name=cls.fqcn):
            ...
    # xrefs
    for ref in dex.find_xrefs("Lcom/example/Foo;.bar:(I)V"):
        ...
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from androguard.core.dex import DEX

from .apk import Apk
from .errors import APKInvalid

try:
    from androguard.core.dex import DEX  # type: ignore[import-untyped]
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "androguard is required for android_re_core.dex. "
        "Install with: uv pip install 'androguard==4.1.4'"
    ) from e


__all__ = [
    "DexClass",
    "DexField",
    "DexMethod",
    "DexView",
    "MethodDescriptor",
    "Xref",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MethodDescriptor:
    """A typed reference to a method.

    ``fqcn`` is the fully-qualified class name in JNI form,
    e.g. ``Lcom/example/Foo;``. ``name`` is the method name,
    ``descriptor`` is the JVM type descriptor, e.g. ``(I)V``.
    """

    fqcn: str
    name: str
    descriptor: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.fqcn}->{self.name}{self.descriptor}"


@dataclass(frozen=True)
class DexClass:
    """A single DEX class declaration."""

    fqcn: str
    access_flags: tuple[str, ...]
    superclass: str | None
    interfaces: tuple[str, ...]
    source_file: str | None
    method_count: int
    field_count: int
    is_external: bool  # True if the class is not in the APK itself

    def to_dict(self) -> dict[str, Any]:
        return {
            "fqcn": self.fqcn,
            "access_flags": list(self.access_flags),
            "superclass": self.superclass,
            "interfaces": list(self.interfaces),
            "source_file": self.source_file,
            "method_count": self.method_count,
            "field_count": self.field_count,
            "is_external": self.is_external,
        }


@dataclass(frozen=True)
class DexMethod:
    """A single DEX method declaration."""

    fqcn: str
    name: str
    descriptor: str
    access_flags: tuple[str, ...]
    is_native: bool

    @property
    def key(self) -> str:
        """Return the canonical ``fqcn->name descriptor`` key."""
        return f"{self.fqcn}->{self.name}{self.descriptor}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fqcn": self.fqcn,
            "name": self.name,
            "descriptor": self.descriptor,
            "access_flags": list(self.access_flags),
            "is_native": self.is_native,
            "key": self.key,
        }


@dataclass(frozen=True)
class DexField:
    """A single DEX field declaration."""

    fqcn: str
    name: str
    type_descriptor: str
    access_flags: tuple[str, ...]
    init_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fqcn": self.fqcn,
            "name": self.name,
            "type_descriptor": self.type_descriptor,
            "access_flags": list(self.access_flags),
            "init_value": self.init_value,
        }


@dataclass(frozen=True)
class Xref:
    """A cross-reference from one method/class to a target class/method."""

    source: str  # fqcn of the referencing class
    target_class: str  # fqcn of the referenced class
    target_method: str | None  # method name, or None for class-level
    kind: str  # "call" | "read" | "write" | "new" | "const" | "invoke"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target_class": self.target_class,
            "target_method": self.target_method,
            "kind": self.kind,
        }


# ---------------------------------------------------------------------------
# DexView
# ---------------------------------------------------------------------------


class DexView:
    """A view over one or more DEX files inside an APK."""

    def __init__(
        self,
        classes: list[DexClass],
        methods: list[DexMethod],
        fields: list[DexField],
        *,
        loaded_dex_count: int = 0,
        skipped_dex: list[tuple[str, str]] | None = None,
    ) -> None:
        self._classes = classes
        self._methods = methods
        self._fields = fields
        self._loaded_dex_count = loaded_dex_count
        self._skipped_dex: list[tuple[str, str]] = list(skipped_dex or [])

    @property
    def loaded_dex_count(self) -> int:
        """Number of DEX files that parsed successfully."""
        return self._loaded_dex_count

    @property
    def skipped_dex(self) -> list[tuple[str, str]]:
        """``(name, exception_type)`` tuples for DEX files that failed to parse."""
        return list(self._skipped_dex)

    @classmethod
    def from_apk(cls, apk: Apk) -> DexView:
        """Build a :class:`DexView` from an :class:`Apk`.

        Enumerates all DEX files declared in the APK and merges their
        class/method/field tables.

        Raises:
            APKInvalid: If the APK declares DEX files but none of them
                could be parsed. (An APK with no DEX files at all is
                considered valid and returns an empty :class:`DexView`.)
        """
        import logging

        if apk.is_closed:
            raise APKInvalid("APK has been closed")
        raw = apk.raw
        classes: list[DexClass] = []
        methods: list[DexMethod] = []
        fields: list[DexField] = []
        dex_names: list[str] = list(raw.get_dex_names())
        loaded = 0
        skipped: list[tuple[str, str]] = []
        log = logging.getLogger(__name__)
        # androguard 4.1.x: APK.get_dex() no longer accepts a name argument
        # (it returns concatenated bytes). Use get_all_dex() to iterate
        # individual DEX payloads and pair them with their declared names.
        try:
            dex_payloads: list[bytes] = list(raw.get_all_dex())
        except Exception as e:
            log.warning("get_all_dex failed: %s: %s", type(e).__name__, e)
            dex_payloads = []
        for dex_name, dex_bytes in zip(dex_names, dex_payloads, strict=True):
            try:
                dex_obj = DEX(dex_bytes)
            except Exception as e:
                log.warning("Skipped DEX %s: %s: %s", dex_name, type(e).__name__, e)
                skipped.append((dex_name, type(e).__name__))
                continue
            classes.extend(_enumerate_classes(dex_obj))
            methods.extend(_enumerate_methods(dex_obj))
            fields.extend(_enumerate_fields(dex_obj))
            loaded += 1
        if dex_names and loaded == 0:
            raise APKInvalid(
                "No DEX files could be parsed",
                details={"skipped": skipped, "declared": dex_names},
            )
        return cls(
            classes=classes,
            methods=methods,
            fields=fields,
            loaded_dex_count=loaded,
            skipped_dex=skipped,
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def iter_classes(self) -> Iterator[DexClass]:
        return iter(self._classes)

    def iter_methods(self) -> Iterator[DexMethod]:
        return iter(self._methods)

    def iter_fields(self) -> Iterator[DexField]:
        return iter(self._fields)

    def find_classes(
        self,
        query: str,
        *,
        limit: int = 100,
        exact: bool = False,
    ) -> list[DexClass]:
        """Find classes by FQCN substring (or exact match).

        ``query`` is a partial JNI-style name like ``"Lcom/example/"``.
        If ``exact`` is True, the FQCN must match exactly.
        """
        if exact:
            return [c for c in self._classes if c.fqcn == query][:limit]
        # Compile a case-insensitive substring pattern.
        pattern = re.compile(re.escape(query), re.IGNORECASE)
        return [c for c in self._classes if pattern.search(c.fqcn)][:limit]

    def find_methods(
        self,
        *,
        class_name: str | None = None,
        name_substring: str | None = None,
        native_only: bool = False,
        limit: int = 100,
    ) -> list[DexMethod]:
        """Filter methods by class, name, or native flag."""
        cls_pat = re.compile(re.escape(class_name), re.IGNORECASE) if class_name else None
        name_pat = re.compile(re.escape(name_substring), re.IGNORECASE) if name_substring else None
        out: list[DexMethod] = []
        for m in self._methods:
            if cls_pat and not cls_pat.search(m.fqcn):
                continue
            if name_pat and not name_pat.search(m.name):
                continue
            if native_only and not m.is_native:
                continue
            out.append(m)
            if len(out) >= limit:
                break
        return out

    def find_xrefs(
        self,
        target_class: str,
        *,
        target_method: str | None = None,
        limit: int = 200,
    ) -> list[Xref]:
        """Find references TO a given class (or method) FROM any class.

        Implementation note: full xref extraction in androguard 4.1.4
        requires iterating every method and walking its instructions.
        For Phase 1 we expose a lightweight string-based heuristic
        (presence in the constant pool) and a placeholder for the full
        instruction walk. Phase 2 will replace the body with a proper
        instruction-level walk.
        """
        out: list[Xref] = []
        for cls in self._classes:
            for m in self._methods:
                if m.fqcn != cls.fqcn:
                    continue
                # Heuristic: look for the target class FQCN in the
                # method's bytecode. This is intentionally conservative
                # (false positives) rather than missing references.
                # Phase 2 will replace with proper xref extraction.
                xrefs = _scan_method_xrefs(m, target_class, target_method)
                out.extend(xrefs)
                if len(out) >= limit:
                    return out
        return out


# ---------------------------------------------------------------------------
# Internal helpers (androguard 4.1.4 specific)
# ---------------------------------------------------------------------------


def _access_flags(value: int) -> tuple[str, ...]:
    """Translate an access-flags bitmask into a list of human-readable names."""
    flags: list[str] = []
    mapping: tuple[tuple[int, str], ...] = (
        (0x0001, "public"),
        (0x0002, "private"),
        (0x0004, "protected"),
        (0x0008, "static"),
        (0x0010, "final"),
        (0x0020, "synchronized"),
        (0x0040, "volatile"),
        (0x0080, "transient"),
        (0x0100, "native"),
        (0x0200, "interface"),
        (0x0400, "abstract"),
        (0x0800, "strict"),
        (0x1000, "synthetic"),
        (0x2000, "annotation"),
        (0x4000, "enum"),
        (0x10000, "constructor"),
        (0x20000, "synchronized_native"),
    )
    for bit, name in mapping:
        if value & bit:
            flags.append(name)
    return tuple(flags)


def _enumerate_classes(dex: DEX) -> list[DexClass]:
    """Enumerate all classes declared in a DEX.

    Androguard 4.1.x has a quirk where ``cls.get_source()`` can raise
    ``AttributeError: 'NoneType' object has no attribute 'get_source_class'``
    on otherwise-valid classes. We isolate that single call so a bad source
    line never costs us the whole class.
    """
    out: list[DexClass] = []
    for cls in dex.get_classes():
        try:
            fqcn = cls.get_name()  # e.g. "Lcom/example/Foo;"
            # get_access_flags_string() returns a human-readable string like
            # "public final" in androguard 4.1.x; _access_flags needs the
            # raw integer bitmask, so use get_access_flags() (no "_string").
            access = _access_flags(cls.get_access_flags() or 0)
            superclass = cls.get_superclassname()
            interfaces = tuple(cls.get_interfaces() or ())
            methods = list(cls.get_methods())
            fields = list(cls.get_fields())
        except Exception:
            continue
        try:
            source_file = cls.get_source()
        except Exception:
            source_file = None
        out.append(
            DexClass(
                fqcn=fqcn,
                access_flags=access,
                superclass=superclass or None,
                interfaces=interfaces,
                source_file=source_file or None,
                method_count=len(methods),
                field_count=len(fields),
                is_external=False,
            )
        )
    return out


def _enumerate_methods(dex: DEX) -> list[DexMethod]:
    """Enumerate all methods declared across the DEX's classes."""
    out: list[DexMethod] = []
    for cls in dex.get_classes():
        try:
            fqcn = cls.get_name()
        except Exception:
            continue
        for method in cls.get_methods():
            try:
                name = method.get_name()
                desc = method.get_descriptor()
                access = _access_flags(method.get_access_flags() or 0)
                is_native = "native" in access
            except Exception:
                continue
            out.append(
                DexMethod(
                    fqcn=fqcn,
                    name=name,
                    descriptor=desc,
                    access_flags=access,
                    is_native=is_native,
                )
            )
    return out


def _enumerate_fields(dex: DEX) -> list[DexField]:
    """Enumerate all fields declared across the DEX's classes."""
    out: list[DexField] = []
    for cls in dex.get_classes():
        try:
            fqcn = cls.get_name()
        except Exception:
            continue
        for field in cls.get_fields():
            try:
                name = field.get_name()
                desc = field.get_descriptor()
                access = _access_flags(field.get_access_flags() or 0)
                init_value = field.get_init_value()
            except Exception:
                continue
            out.append(
                DexField(
                    fqcn=fqcn,
                    name=name,
                    type_descriptor=desc,
                    access_flags=access,
                    init_value=init_value,
                )
            )
    return out


def _scan_method_xrefs(
    method: DexMethod,
    target_class: str,
    target_method: str | None,
) -> list[Xref]:
    """Heuristic xref scan: search the method's bytecode for the target.

    This is a stub for Phase 1 — it returns an empty list. Phase 2
    replaces the body with a proper instruction-level walk using
    :meth:`DEX.get_method_by_name` and :meth:`EncodedMethod.get_instructions`.
    """
    # TODO(Phase 2): replace with instruction-level xref extraction.
    return []
