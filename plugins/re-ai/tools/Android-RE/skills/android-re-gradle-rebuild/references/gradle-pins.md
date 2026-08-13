# Gradle version pins and Maven coordinate notes

Pinned versions known to work with large modern Kotlin/Compose APKs
(Kotlin 2.0.21 bytecode, AGP 8.7, modern Compose, R8-deobfuscated).
Update with care — these are the versions that produce a working
APK without manual intervention.

## Tool versions

| Tool | Version | Notes |
|---|---|---|
| Gradle | **8.11.1** | Already extracted at `~/.gradle/wrapper/dists/gradle-8.11.1-bin/` on the build host. |
| Android Gradle Plugin | **8.7.3** | Last 8.7.x patch; requires Gradle ≥ 8.9. Pairs cleanly with `compileSdk = 35`. |
| Kotlin | **2.0.21** | Matches `mv = {2, 0, 0}` in the decompiled `@kotlin.Metadata`. The Compose Compiler plugin (`org.jetbrains.kotlin.plugin.compose`) is bundled with the Kotlin plugin; it must match exactly. |
| Java toolchain | **21** (host) → **17** (target) | Android Studio's bundled JBR is Java 21. `jvmToolchain(17)` targets the bytecode level. |
| jadx | 1.5.0 | Vendored at `vendor/jadx/0.1.0/lib/jadx-1.5.0-all.jar`. **Does NOT support `--use-kotlin-source`.** |
| apktool | 2.10.0 | Vendored. |
| AGP-injected NDK | None | The APK ships `arm64-v8a` only; no NDK toolchain needed for the rebuild. |

## Maven coordinates

Most third-party deps resolve cleanly from `google()` and
`mavenCentral()`. The exceptions:

| Coordinate | Notes |
|---|---|
| `com.github.luben:zstd-jni:1.5.7-7` | zstd-jni for `assets/rootfs.tar.zst.bin` decompression. Maven Central. |
| `org.apache.commons:commons-lang3:3.14.0` | Use `--rename_apache_commons_static_fields` to strip jadx's `f<digits>` prefixes. |
| `org.beanshell:bsh:2.0b6` | **Not on Maven Central.** Vendored from the jadx decompile. AWT/Swing-dependent `bsh.util.*` are excluded (`java.awt` not on Android); JSR-223 wrappers excluded (`javax.script` not on Android). |
| `com.termux.terminal:terminal-view:0.118.1` (jcenter / jitpack) | **Not on Maven Central.** Vendored from the original plain (non-deobf) jadx output. |
| `com.android.vending.BILLING` permission | Comes from `com.android.billingclient:billing-ktx:7.1.1` (a mobile-payment library). |

## JITPACK for Termux

Some projects need jitpack; add to `settings.gradle.kts`:

```kotlin
dependencyResolutionManagement {
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://jitpack.io") }
    }
}
```

The original rebuild this skill was derived from didn't need jitpack
(Termux is vendored, not Maven), but it's useful for projects that
pull Termux from `com.github.termux:termux-app:vX.Y.Z`.

## `bintray()` / `jcenter()` — REMOVED

JCenter has been sunset. Any project that still references it will
fail to resolve. If the decompiled code has a `jcenter()` line, replace
with `mavenCentral()`.

## multidex

Always set `multiDexEnabled = true`. Modern Android (minSdk 26)
handles multidex natively, so the `androidx.multidex` dependency is
included for the `MultiDex.install(context)` call on older devices
but isn't strictly required at minSdk 26+. Set it anyway — costs
nothing and lets the same APK run on Android 5/6.

## Compose Compiler

The Compose Compiler is now a Kotlin plugin (since Kotlin 2.0.0).
Apply with:

```kotlin
plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}
```

The plugin version is locked to the Kotlin version (no separate
`composeOptions.kotlinCompilerExtensionVersion` setting needed).

## ABI filters

The reference APK ships `arm64-v8a` only. To match:

```kotlin
defaultConfig {
    ndk { abiFilters += "arm64-v8a" }
}
```

If the source APK ships multiple ABIs (`armeabi-v7a`, `arm64-v8a`,
`x86`, `x86_64`), enumerate them. The original jadx cache splits
`lib/<abi>/*.so` into per-ABI subdirs; `create_gradle_project`
copies them all into `app/src/main/jniLibs/<abi>/`.

## NDK toolchain

The reference APK does not need to compile any C/C++. The `lib/`
subdirs are pre-built and copied verbatim. If a target project
needs an NDK, set `ndkVersion` in `defaultConfig` and add a
`buildFeatures { nativeBuild = true }` block; the rest is the
default AGP NDK pipeline.

## `packagingOptions`

Always set:

```kotlin
packaging {
    jniLibs {
        useLegacyPackaging = true
        pickFirsts += listOf(
            "lib/arm64-v8a/libandroidx.graphics.path.so",
            "lib/arm64-v8a/libdatastore_shared_counter.so",
            "lib/arm64-v8a/libzstd-jni-1.5.7-7.so"
        )
    }
    resources {
        excludes += listOf(
            "META-INF/AL2.0",
            "META-INF/LGPL2.1",
            "META-INF/DEPENDENCIES",
            "META-INF/LICENSE*",
            "META-INF/NOTICE*",
            "META-INF/*.kotlin_module",
            "META-INF/versions/9/*"
        )
    }
}
```

- `useLegacyPackaging = true` matches the original `extractNativeLibs="true"` and avoids the AGP 8.x default of unpacking `.so` files into the APK (which is a Play Store warning).
- `pickFirsts` resolves conflicts when an AAR ships the same `.so` as the project (e.g. `androidx.graphics:graphics-path` ships `libandroidx.graphics.path.so`).
- The `META-INF/AL2.0` / `LGPL2.1` excludes prevent the standard "duplicate LICENSE" build error when multiple deps ship the same Apache-2 / LGPL-2 metadata.
