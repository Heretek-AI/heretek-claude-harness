# Patch anatomy

A patch in Morphe Patcher is a Kotlin DSL object that describes one transformation. There are two kinds: `bytecodePatch` (modifies smali/code) and `resourcePatch` (modifies resources like XML, strings, layouts). Both share the same lifecycle.

## Basic structure

```kotlin
val myPatch = bytecodePatch(
    name = "Short verb-led name",
    description = "Third-person description ending with a period.",
    default = true,            // Default on/off in the Manager UI.
) {
    compatibleWith(COMPATIBILITY_XYZ)
    dependsOn(otherPatch)
    extendWith("optional.mpe")
    extendWithAll { dynamicList }   // Evaluated at patch time.

    execute {
        // ... fingerprint matching, smali edits, etc.
    }

    finalize {
        // ... post-processing, runs after all patches.
    }
}
```

## The two patch kinds

- **`bytecodePatch`** — operates on bytecode (smali). Use for method-level modifications, instruction inserts, class mutations.
- **`resourcePatch`** — operates on resources (XML, files). Use for manifest edits, network security config, image swaps, string lists.

## `compatibleWith`

Pin a patch to a specific `Compatibility` (package + versions + signatures). Without it, the patch runs against any package. Usually you want this — be explicit.

```kotlin
compatibleWith(COMPATIBILITY_XYZ)
```

## `dependsOn`

Run another patch first. Dependencies execute before the depending patch. If a dependency raises an exception, the dependent patch will not run.

```kotlin
dependsOn(otherPatch)
```

## `execute { }`

The transformation body. For a `bytecodePatch`, this is where you fingerprint, match, and edit. For a `resourcePatch`, this is where you read/write files with `document()`, `get()`, `delete()`.

## `extendWith` and `extendWithAll`

Inject a precompiled DEX file (`.mpe`) into the patched app **before** the patch executes. This lets you ship complex Java/Kotlin logic instead of writing smali by hand.

```kotlin
// Compile-time: a single .mpe file bundled into the patch.
extendWith("disable-ads.mpe")

// Dynamic: a list that depends on another patch's output.
extendWithAll { derivedExtensions }
```

> **`extendWith` is evaluated when the patch is built.** If your extension list depends on runtime output, use `extendWithAll` and a `Supplier<InputStream>` provider. The provider runs after the dependency's `execute {}` block has populated the list.

## `finalize { }`

Post-processing. Runs after all patches have executed, in reverse order of execution. Useful for closing files, flushing logs, or any cleanup.

```kotlin
finalize {
    println("done")
}
```

## Options

Make patches configurable with options. Useful for toggling behavior at runtime.

```kotlin
val patch = bytecodePatch(name = "Patch", default = true) {
    val value by stringOption(name = "Inbuilt option")
    val custom by option<String>(name = "Custom string")
    execute {
        println(value)
        println(custom)
    }
}
```

Options are typed (`stringOption`, `booleanOption`, `intOption`, etc.) and can be set after loading via `PatchLoader`.

## Failure mode

A patch can throw `PatchException` at any time during execution to signal failure. The exception propagates and terminates the apply.

```kotlin
execute {
    val match = myFingerprint.matchOrNull
        ?: throw PatchException("Method not found in ${PACKAGE_NAME}")
}
```

## Tips

- Patches with no `name` are skipped by `PatchLoader`. Always set one.
- If `compatibleWith` is not used, the patch is universal.
- A null `targets` (or `AppTarget(version = null)`) means "any version".
- Patches can be referenced by multiple other patches through `dependsOn`.
