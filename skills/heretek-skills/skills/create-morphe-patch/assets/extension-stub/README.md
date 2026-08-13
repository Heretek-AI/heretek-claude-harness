# Extension stub

A minimal Android library module that compiles to a `.mpe` DEX extension for use with Morphe patches.

## When to use

If your patch needs to inject compiled Java/Kotlin code (rather than raw smali instructions), build a `.mpe` extension and reference it from the patch via `extendWith("name.mpe")`.

## How to use

1. **Copy this directory** into your patches bundle under `extensions/<app>/<name>/`.
2. **Replace placeholders** in:
   - `build.gradle.kts` — `namespace` and Java/Kotlin targets.
   - `src/main/java/Stub.java` — class body and the reverse-DNS package.
   - `src/main/AndroidManifest.xml` — namespace identifier.
3. **Add the module to `settings.gradle.kts`** at the bundle root:
   ```kotlin
   include(":extensions:<app>:<name>")
   ```
4. **Build the `.mpe`**:
   ```bash
   ./gradlew :extensions:<app>:<name>:assembleRelease
   ```
   The output is in `build/outputs/mpe/`.
5. **Copy the `.mpe`** into your patches module's `resources/` directory (or wherever the Gradle plugin expects extension files).
6. **Reference from the patch**:
   ```kotlin
   val myPatch = bytecodePatch(name = "Use stub") {
       extendWith("name.mpe")
       execute {
           // ... call into the extension via smali
           match.method.addInstructions(
               0,
               "invoke-static {}, L<package>/Stub;->doSomething()V",
           )
       }
   }
   ```

## Why `.mpe` instead of raw smali?

- **Complex logic** — multiple classes, helper methods, recursion.
- **Type safety** — write in Java/Kotlin, get all the IDE/tooling support.
- **Maintainability** — easier to read than hand-written smali.

## What goes in the extension

- Public static methods are the easiest to call from smali.
- Static fields are accessible via `sget-*` instructions.
- Non-static methods require you to instantiate first; rarely worth it.

## Constraints

- The extension is merged into the patched app's classpath at apply time.
- Avoid dependencies on Android system APIs that may not exist in the target app.
- Keep the extension small — the `.mpe` adds to the patched APK size.
