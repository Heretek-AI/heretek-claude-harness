// Minimal Android library module that compiles to a .mpe (DEX) extension for
// morphe-patches. Drop this directory into <your-bundle>/extensions/<app>/<name>/
// and add it to settings.gradle.kts as an included project.
//
// Build:
//   ./gradlew :extensions:<app>:<name>:assembleRelease
//
// The .mpe artifact will be in build/outputs/mpe/. Copy it to your patches
// directory and reference it from the patch via:
//   extendWith("<name>.mpe")

plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "<your.bundle.namespace>.extension.<name>"
    compileSdk = 34

    defaultConfig {
        minSdk = 24
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}
