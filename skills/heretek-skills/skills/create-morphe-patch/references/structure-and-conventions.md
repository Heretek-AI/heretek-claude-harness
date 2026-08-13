# Structure and conventions

Patches are organized under `patches/src/main/kotlin/<bundle.namespace>/patches/<category>/` (or in a fork's namespace). Each category groups related patches for one feature area.

## Folder layout

```
📦your.patches.app.category
 ├ 🔍Fingerprints.kt
 └ 🧩SomePatch.kt
```

- `Fingerprints.kt` — declares `object` fingerprints shared by the patches in this folder.
- `SomePatch.kt` — declares one patch (and its private fingerprints if needed).

A separate `Fingerprints.kt` file is not strictly required, but it helps when a patch uses multiple fingerprints.

## Real-world example

From `morphe-patches` (upstream):

```
patches/src/main/kotlin/app/morphe/patches/music/ad/
 ├ Fingerprints.kt
 └ HideAdsPatch.kt
```

Nested grouping by app + feature keeps the patch list browsable.

## Naming rules

### Patch name

- **Verb-led, short, descriptive.** "Disable ads", "Change button color", "Override certificate pinning".
- **Capitalized** like a title. No periods.
- **Stable across versions** — don't put the version number in the name.

### Patch description

- **Third-person, present tense.** "Disables ads in the app."
- **End with a period.**
- Can be omitted only if the name is already self-explanatory.

### Fingerprint name

- **Best guess at what the target method does.** `AdLoaderFingerprint`, `ShowAdsFingerprint`, `OnCreateFingerprint`.
- Object-style: `object MyFingerprint : Fingerprint(...)`.

### File name

- **Matches the patch name** with `Patch` suffix: `HideAdsPatch.kt`.
- **Fingerprints file**: `Fingerprints.kt` (plural).

## Modularity

- **Patches can depend on other patches.** Use `dependsOn(...)` to chain them.
- **Write patches for reuse.** A patch that "removes ads" should not assume a specific app — let `compatibleWith` constrain it.
- **Keep patches minimal.** Tiny patches are robust across updates. If a patch grows large, split it or move logic into a `.mpe` extension.

## Documentation

Patches are abstract. Non-obvious code should be commented:

- Why a specific method is being patched.
- What the new instruction sequence does.
- Why a particular instruction index was chosen.
- Why an extension is required.

```kotlin
// PairIP bypass: replace verification result with success.
// The original method calls into native libpairipcore.so.
// Here we short-circuit the flow so the runtime check passes.
match.method.addInstructions(
    0,
    """
        const/4 v0, 0x1
        return v0
    """,
)
```

## Naming across the bundle

- **Bundle namespace** (e.g., `app.morphe.patches.youtube.ad`) matches the bundle's `groupId` in `settings.gradle.kts` and the `Patches` package in `morphe-patches-gradle-plugin`.
- **Forks** should use a different namespace (e.g., `grindrmorphe.morphe.patches.…`) to avoid collisions on the generated `.mpp` and to make the derivative clear.

## Linting

Most Morphe bundles ship an `.editorconfig` and a Kotlin lint config. Match the format of existing patches in your bundle. Use 4-space indentation, no wildcard imports, trailing commas where Kotlin allows.
