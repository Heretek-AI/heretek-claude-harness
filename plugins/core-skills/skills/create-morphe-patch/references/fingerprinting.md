# Fingerprinting

A `Fingerprint` is a partial description of a method — enough to uniquely identify it across app versions when names are obfuscated. The fingerprint matches if **all** declared attributes match.

## Anatomy

```kotlin
object AdLoaderFingerprint : Fingerprint(
    definingClass = "Lcom/some/app/ads/AdsLoader;",
    accessFlags = listOf(AccessFlags.PUBLIC, AccessFlags.FINAL),
    returnType = "Z",
    parameters = listOf("Ljava/lang/String;", "I", "L"),

    filters = listOf(
        fieldAccess(opcode = Opcode.IGET, definingClass = "this", type = "Ljava/util/Map;"),
        string("showBannerAds"),
        methodCall(definingClass = "Ljava/lang/String;", name = "equals"),
        opcode(Opcode.MOVE_RESULT, InstructionLocation.MatchAfterImmediately()),
        literal(1337),
        opcode(Opcode.IF_EQ),
    ),
)
```

## Field meanings

| Field | What it matches |
|---|---|
| `definingClass` | Exact class name (StringComparisonType). Use `"this"` for the enclosing class. |
| `accessFlags` | `AccessFlags.PUBLIC`, `FINAL`, `STATIC`, etc. |
| `returnType` | Return type descriptor (`Z`, `V`, `Ljava/lang/String;`). |
| `parameters` | Ordered parameter type descriptors. |

> **Obfuscated class names** change between releases. For obfuscated types, use the bare object type `L` (no name). For non-obfuscated types, use the full name.

## Filters

Filters are ordered instruction descriptors. They must appear in the same order as the target method. Zero or more unrelated instructions can exist between filters.

- **`fieldAccess(opcode, definingClass, type)`** — match a field read/write.
- **`string("literal")`** — match a `const-string` of the given value.
- **`methodCall(definingClass, name, returnType, parameters)`** — match an invoke.
- **`opcode(Opcode.X, location)`** — match an arbitrary opcode.
- **`literal(value)`** — match a constant pool literal.
- **`anyInstruction(...)`** — match one of several alternative filters.

For full smali syntax on `methodCall`/`fieldAccess`, you can paste a smali statement:

```kotlin
methodCall(smali = "Landroid/net/Uri;->parse(Ljava/lang/String;)Landroid/net/Uri;")
```

## `InstructionLocation`

Controls where the filter matches relative to the previous one:

- `MatchAfterImmediately()` — back-to-back (no instructions in between).
- `MatchAfterWithin(int)` — within N instructions of the previous.
- `MatchFirst()` — first instruction of the method.

## Strings: two ways

- **`filters = listOf(string("foo"), string("bar"))`** — ordered. `foo` must appear before `bar`.
- **`strings = listOf("foo", "bar")`** — unordered. Useful for enum-like constructors with many strings.

## Using a fingerprint

After declaration, use it inside `execute`:

```kotlin
execute {
    AdLoaderFingerprint.let { match ->
        val moveResultIndex = match.instructionMatches[3].index
        val register = match.instructionMatches[3]
            .getInstruction<OneRegisterInstruction>().registerA
        match.method.addInstructions(moveResultIndex + 1, "const/4 v$register, 0x0")
    }
}
```

Available result properties:

- `originalClassDef` / `originalMethod` — immutable.
- `classDef` / `method` — mutable (lazy copy on first access).
- `instructionMatches` — list of `InstructionMatch` results in declaration order.

> Use `*OrNull` variants (`matchOrNull`, `methodOrNull`) when a missing match is a normal case.

## Multiple modifications

If you make more than one modification to the same method, indexes shift. Work from **last to first**, or call `clearMatch()` + `match()` to refresh.

```kotlin
execute {
    AdLoaderFingerprint.let { match ->
        // Last filter first.
        match.method.removeInstruction(match.instructionMatches[5].index)
        match.method.addInstructions(
            match.instructionMatches[3].index + 1,
            "const/4 v0, 0x0",
        )
    }
}
```

A fingerprint matches **once per usage** unless `clearMatch()` is called. This makes fingerprints shareable across patches.

## Pure opcode matching

If no built-in filter works, use raw opcode patterns:

```kotlin
filters = OpcodesFilter.opcodesToFilters(Opcode.MOVE_RESULT_OBJECT, Opcode.IGET_OBJECT)
```

Opcode patterns are exact (no variable spacing) and fragile — prefer built-in filters when possible.

## Finding all matches

To transform every method that matches (e.g., rewrite a string everywhere):

```kotlin
Fingerprint(filters = listOf(string("target"))).matchAllOrNull()?.forEach { match ->
    match.method.findInstructionIndicesReversedOrThrow(string("target")).forEach { idx ->
        val register = match.method.getInstruction<OneRegisterInstruction>(idx).registerA
        match.method.replaceInstruction(idx, "const-string v$register, \"replacement\"")
    }
}
```

## Strong-fingerprint rules

- ✅ Use return type, parameter types, and instruction filters.
- ✅ Capture unique strings, method calls, or literals the method references.
- ❌ Never fingerprint on obfuscated names.
- ❌ Avoid opcode-only patterns unless nothing else disambiguates.
