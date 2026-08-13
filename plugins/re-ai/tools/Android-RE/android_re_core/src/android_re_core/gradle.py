"""Generate a buildable Gradle project from a decompiled + cleaned APK.

This module is the heart of the :class:`android_re_core.gradle.GradleProjectBuilder`
that powers the MCP ``create_gradle_project`` tool. It takes a jadx
output directory (already cleaned by :class:`android_re_core.cleanup.JadxCleanup`),
an apktool-decoded directory, and the original APK, and writes a
buildable Gradle project.

The generated project mirrors the structure of a typical large
Kotlin/Compose APK rebuild (Kotlin 2.0.21 bytecode, AGP 8.7, modern
Compose, R8-deobfuscated). The static parts (settings.gradle.kts,
build.gradle.kts, the version catalog, the proguard rules, the
wrapper) are templated; the dynamic parts (manifest cleanup,
buildConfigField injection, file inventory) are computed from the
inputs.
"""

from __future__ import annotations

import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

__all__ = [
    "GradleProjectBuilder",
    "GradleProjectReport",
    "create_gradle_project",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Default Gradle version (matches the version already extracted on
#: the build host at ``~/.gradle/wrapper/dists/gradle-8.11.1-bin/``).
DEFAULT_GRADLE_VERSION: str = "8.11.1"

#: Default Android Gradle Plugin version.
DEFAULT_AGP_VERSION: str = "8.7.3"

#: Default Kotlin version. Matches ``mv = {2, 0, 0}`` in the decompiled
#: ``@kotlin.Metadata`` annotations.
DEFAULT_KOTLIN_VERSION: str = "2.0.21"

#: AGP attributes that must be stripped from ``<manifest>`` and
#: ``<application>`` (AGP injects these from build.gradle.kts).
_MANIFEST_ATTRS_TO_STRIP = {
    "package",
    "compileSdkVersion",
    "compileSdkVersionCodename",
    "platformBuildVersionCode",
    "platformBuildVersionName",
}

#: Manifest components that come from libraries — these will be
#: injected by the manifest merger from each AAR's manifest, so
#: we strip them from the source manifest to avoid duplicates.
#: The list is generous because duplicate-component errors are
#: easier to fix by adding back than by re-discovering missing
#: classes in the dex.
_LIBRARY_COMPONENT_PACKAGE_PREFIXES = (
    "androidx.work.",
    "androidx.startup.",
    "androidx.profileinstaller.",
    "androidx.emoji2.",
    "com.google.firebase.",
    "com.google.android.gms.",
    "com.google.android.datatransport.",
    "com.android.billingclient.api.ProxyBilling",
    "androidx.room.MultiInstanceInvalidationService",
)


# ---------------------------------------------------------------------------
# Version catalog
# ---------------------------------------------------------------------------

LIBS_VERSIONS_TOML = """\
[versions]
agp = "{agp_version}"
kotlin = "{kotlin_version}"
compose-bom = "2024.10.01"
lifecycle = "2.8.7"
room = "2.6.1"
navigation-compose = "2.8.4"
datastore = "1.1.1"
work = "2.9.1"
coroutines = "1.8.1"
firebase-bom = "33.5.1"
play-services-ads = "23.5.0"
play-review = "2.0.2"
billing = "7.1.1"
material = "1.12.0"
browser = "1.8.0"
graphics-path = "1.0.1"
commons-lang3 = "3.14.0"
commons-compress = "1.27.1"
zstd-jni = "1.5.7-7"
okhttp = "4.12.0"
multidex = "2.0.1"
appcompat = "1.7.0"
core-ktx = "1.13.1"
activity-compose = "1.9.3"
profileinstaller = "1.4.1"

[plugins]
android-application = {{ id = "com.android.application", version.ref = "agp" }}
kotlin-android = {{ id = "org.jetbrains.kotlin.android", version.ref = "kotlin" }}
kotlin-compose = {{ id = "org.jetbrains.kotlin.plugin.compose", version.ref = "kotlin" }}

[libraries]
kotlin-stdlib = {{ module = "org.jetbrains.kotlin:kotlin-stdlib", version.ref = "kotlin" }}
kotlinx-coroutines-android = {{ module = "org.jetbrains.kotlinx:kotlinx-coroutines-android", version.ref = "coroutines" }}
kotlinx-coroutines-play-services = {{ module = "org.jetbrains.kotlinx:kotlinx-coroutines-play-services", version.ref = "coroutines" }}
androidx-multidex = {{ module = "androidx.multidex:multidex", version.ref = "multidex" }}
androidx-core-ktx = {{ module = "androidx.core:core-ktx", version.ref = "core-ktx" }}
androidx-appcompat = {{ module = "androidx.appcompat:appcompat", version.ref = "appcompat" }}
androidx-activity-compose = {{ module = "androidx.activity:activity-compose", version.ref = "activity-compose" }}
androidx-lifecycle-runtime-ktx = {{ module = "androidx.lifecycle:lifecycle-runtime-ktx", version.ref = "lifecycle" }}
androidx-lifecycle-runtime-compose = {{ module = "androidx.lifecycle:lifecycle-runtime-compose", version.ref = "lifecycle" }}
androidx-lifecycle-viewmodel-compose = {{ module = "androidx.lifecycle:lifecycle-viewmodel-compose", version.ref = "lifecycle" }}
androidx-lifecycle-service = {{ module = "androidx.lifecycle:lifecycle-service", version.ref = "lifecycle" }}
androidx-lifecycle-process = {{ module = "androidx.lifecycle:lifecycle-process", version.ref = "lifecycle" }}
androidx-compose-bom = {{ module = "androidx.compose:compose-bom", version.ref = "compose-bom" }}
androidx-compose-ui = {{ module = "androidx.compose.ui:ui" }}
androidx-compose-ui-graphics = {{ module = "androidx.compose.ui:ui-graphics" }}
androidx-compose-foundation = {{ module = "androidx.compose.foundation:foundation" }}
androidx-compose-material3 = {{ module = "androidx.compose.material3:material3" }}
androidx-compose-material-icons-extended = {{ module = "androidx.compose.material:material-icons-extended" }}
androidx-compose-ui-tooling-preview = {{ module = "androidx.compose.ui:ui-tooling-preview" }}
androidx-compose-ui-tooling = {{ module = "androidx.compose.ui:ui-tooling" }}
androidx-navigation-compose = {{ module = "androidx.navigation:navigation-compose", version.ref = "navigation-compose" }}
androidx-datastore-preferences = {{ module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }}
androidx-room-runtime = {{ module = "androidx.room:room-runtime", version.ref = "room" }}
androidx-room-ktx = {{ module = "androidx.room:room-ktx", version.ref = "room" }}
androidx-work-runtime-ktx = {{ module = "androidx.work:work-runtime-ktx", version.ref = "work" }}
androidx-profileinstaller = {{ module = "androidx.profileinstaller:profileinstaller", version.ref = "profileinstaller" }}
material = {{ module = "com.google.android.material:material", version.ref = "material" }}
androidx-browser = {{ module = "androidx.browser:browser", version.ref = "browser" }}
androidx-graphics-path = {{ module = "androidx.graphics:graphics-path", version.ref = "graphics-path" }}
firebase-bom = {{ module = "com.google.firebase:firebase-bom", version.ref = "firebase-bom" }}
firebase-analytics = {{ module = "com.google.firebase:firebase-analytics" }}
firebase-crashlytics = {{ module = "com.google.firebase:firebase-crashlytics" }}
firebase-config-ktx = {{ module = "com.google.firebase:firebase-config-ktx" }}
firebase-sessions = {{ module = "com.google.firebase:firebase-sessions" }}
firebase-installations = {{ module = "com.google.firebase:firebase-installations" }}
play-services-ads = {{ module = "com.google.android.gms:play-services-ads", version.ref = "play-services-ads" }}
play-review-ktx = {{ module = "com.google.android.play:review-ktx", version.ref = "play-review" }}
billing-ktx = {{ module = "com.android.billingclient:billing-ktx", version.ref = "billing" }}
commons-lang3 = {{ module = "org.apache.commons:commons-lang3", version.ref = "commons-lang3" }}
commons-compress = {{ module = "org.apache.commons:commons-compress", version.ref = "commons-compress" }}
zstd-jni = {{ module = "com.github.luben:zstd-jni", version.ref = "zstd-jni" }}
okhttp = {{ module = "com.squareup.okhttp3:okhttp", version.ref = "okhttp" }}
"""


# ---------------------------------------------------------------------------
# Top-level build files
# ---------------------------------------------------------------------------

SETTINGS_GRADLE_KTS = """\
pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}

dependencyResolutionManagement {{
    repositoriesMode.set(RepositoriesMode.PREFER_PROJECT)
    repositories {{
        google()
        mavenCentral()
        maven {{ url = uri("https://jitpack.io") }}
    }}
}}

rootProject.name = "{project_name}"
include(":app")
"""

ROOT_BUILD_GRADLE_KTS = """\
// Top-level build file. AGP and Kotlin plugins are declared in the version
// catalog and applied in :app.
plugins {{
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
}}
"""

GRADLE_PROPERTIES = """\
org.gradle.jvmargs=-Xmx6g -XX:MaxMetaspaceSize=1g -XX:+UseG1GC -Dfile.encoding=UTF-8
org.gradle.parallel=true
org.gradle.caching=true
org.gradle.configuration-cache=false

android.useAndroidX=true
android.nonTransitiveRClass=false
android.defaults.buildfeatures.buildconfig=true

kotlin.code.style=official
kotlin.jvm.target.validation.mode=warning
"""

LOCAL_PROPERTIES = """\
sdk.dir={sdk_dir}
"""

GITIGNORE = """\
build/
.gradle/
local.properties
*.keystore
.idea/
*.iml
captures/
.externalNativeBuild/
.cxx/
"""

GRADLE_WRAPPER_PROPERTIES = """\
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\\://services.gradle.org/distributions/gradle-{gradle_version}-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
"""


# ---------------------------------------------------------------------------
# app/ build files
# ---------------------------------------------------------------------------

APP_BUILD_GRADLE_KTS_TEMPLATE = """\
plugins {{
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}}

android {{
    namespace = "{namespace}"
    compileSdk = 35

    defaultConfig {{
        applicationId = "{application_id}"
        minSdk = 26
        targetSdk = 35
        versionCode = {version_code}
        versionName = "{version_name}"
        multiDexEnabled = true
        ndk {{ abiFilters += "arm64-v8a" }}

        // Mirror original BuildConfig constants so source compiles unchanged.
{build_config_fields}
    }}

    buildTypes {{
        debug {{
            isMinifyEnabled = false
            isDebuggable = true
        }}
        release {{
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }}
    }}

    buildFeatures {{
        compose = true
        buildConfig = true
    }}

    compileOptions {{
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }}

    kotlin {{
        jvmToolchain(17)
    }}

    sourceSets {{
        getByName("main") {{
            java.srcDirs("src/main/java")
            res.srcDirs("src/main/res")
            assets.srcDirs("src/main/assets")
            jniLibs.srcDirs("src/main/jniLibs")
        }}
    }}

    packaging {{
        jniLibs {{
            useLegacyPackaging = true
            pickFirsts += listOf(
                "lib/arm64-v8a/libandroidx.graphics.path.so",
                "lib/arm64-v8a/libdatastore_shared_counter.so",
                "lib/arm64-v8a/libzstd-jni-1.5.7-7.so"
            )
        }}
        resources {{
            excludes += listOf(
                "META-INF/AL2.0",
                "META-INF/LGPL2.1",
                "META-INF/DEPENDENCIES",
                "META-INF/LICENSE*",
                "META-INF/NOTICE*",
                "META-INF/*.kotlin_module",
                "META-INF/versions/9/*"
            )
        }}
    }}
}}

dependencies {{
    // Kotlin & coroutines
    implementation(libs.kotlin.stdlib)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.coroutines.play.services)

    // Multidex
    implementation(libs.androidx.multidex)

    // AndroidX core
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.service)
    implementation(libs.androidx.lifecycle.process)
    implementation(libs.androidx.profileinstaller)

    // Compose BOM
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.foundation)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons.extended)
    implementation(libs.androidx.compose.ui.tooling.preview)
    debugImplementation(libs.androidx.compose.ui.tooling)

    // Navigation
    implementation(libs.androidx.navigation.compose)

    // DataStore (preferences)
    implementation(libs.androidx.datastore.preferences)

    // Room
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)

    // Work
    implementation(libs.androidx.work.runtime.ktx)

    // Material Components
    implementation(libs.material)

    // Browser custom tabs
    implementation(libs.androidx.browser)

    // androidx.graphics-path
    implementation(libs.androidx.graphics.path)

    // Firebase (using BOM, no google-services plugin required)
    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.analytics)
    implementation(libs.firebase.crashlytics)
    implementation(libs.firebase.config.ktx)
    implementation(libs.firebase.sessions)
    implementation(libs.firebase.installations)

    // Play Services
    implementation(libs.play.services.ads)
    implementation(libs.play.review.ktx)

    // Play Billing
    implementation(libs.billing.ktx)

    // Apache Commons
    implementation(libs.commons.lang3)
    implementation(libs.commons.compress)

    // zstd-jni for rootfs.tar.zst.bin decompression
    implementation(libs.zstd.jni)

    // OkHttp
    implementation(libs.okhttp)
}}
"""

PROGUARD_RULES_PRO = """\
# Decompile-and-rebuild project: do not re-obfuscate, do not strip.
# Preserve everything jadx recovered so the rebuild matches the original layout.
-dontobfuscate
-keepattributes *Annotation*,InnerClasses,Signature,Exceptions,SourceFile,LineNumberTable

# Keep everything in the app's own package and its lambdas.
-keep class app.myapp.** { *; }

# Multidex: keep classes accessed reflectively from the lower-dex buckets.
-keepclassmembers class **$$inlined$* { *; }

# Compose runtime metadata
-keep class androidx.compose.runtime.** { *; }
"""


# ---------------------------------------------------------------------------
# BuildConfig field injection
# ---------------------------------------------------------------------------

#: The 5 non-default BuildConfig fields observed in a typical
#: Kotlin/Compose app rebuild. When the decompile's BuildConfig.java
#: is present, its values are read; otherwise the defaults below are
#: used.
DEFAULT_BUILDCONFIG_FIELDS: dict[str, tuple[str, str]] = {
    "FLAVOR": ("String", '"prod"'),
    "OAUTH_APP_RETURN_URI": ("String", '"myapp://auth/callback"'),
    "OAUTH_CALLBACK_SCHEME": ("String", '"myapp"'),
    "OPENROUTER_CALLBACK_URL": (
        "String",
        '"https://example.com/callback?scheme=myapp&package=com.example.myapp"',
    ),
    "PREMIUM_SUBS_PRODUCT_ID": ("String", '"myapp_premium_monthly"'),
}


def _render_buildconfig_fields(fields: dict[str, tuple[str, str]]) -> str:
    """Format the ``buildConfigField`` block for the app build script."""
    lines = []
    for name, (type_, value) in fields.items():
        lines.append(f'        buildConfigField("{type_}", "{name}", {value})')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Manifest cleanup
# ---------------------------------------------------------------------------

_ANDROID_NS = "http://schemas.android.com/apk/res/android"
_TOOLS_NS = "http://schemas.android.com/tools"


def _clean_manifest(apktool_manifest: Path) -> tuple[Path, dict[str, str]]:
    """Strip AGP-injected attrs + library components from the apktool manifest.

    Args:
        apktool_manifest: Path to ``AndroidManifest.xml`` decoded by apktool.

    Returns:
        (cleaned_manifest_path, extracted_metadata) where
        ``extracted_metadata`` is a dict with keys ``package``,
        ``version_code``, ``version_name``, ``application_class``,
        ``has_ads``.
    """
    tree = ET.parse(apktool_manifest)
    root = tree.getroot()
    # ET registers namespaces as ``ns0``, ``ns1``... — re-register for
    # cleaner XPath below.
    ET.register_namespace("android", _ANDROID_NS)
    ET.register_namespace("tools", _TOOLS_NS)

    # Extract metadata
    metadata: dict[str, str] = {
        "package": root.attrib.get("package", ""),
        "version_code": root.attrib.get(f"{{{_ANDROID_NS}}}versionCode", "0"),
        "version_name": root.attrib.get(f"{{{_ANDROID_NS}}}versionName", "0.0.0"),
    }
    # Manifest-level attrs to strip
    for attr in list(root.attrib):
        local = attr.split("}")[-1] if "}" in attr else attr
        if local in _MANIFEST_ATTRS_TO_STRIP:
            del root.attrib[attr]

    # Application-level attrs to strip
    application = root.find(f"{{{_ANDROID_NS}}}application")
    if application is not None:
        for attr in list(application.attrib):
            local = attr.split("}")[-1] if "}" in attr else attr
            if local in _MANIFEST_ATTRS_TO_STRIP:
                del application.attrib[attr]
        # Save the application class name
        metadata["application_class"] = application.attrib.get(f"{{{_ANDROID_NS}}}name", "")
        # Detect ad-services conflict
        has_ads = False
        for prop in application.findall(f"{{{_ANDROID_NS}}}property"):
            if (
                prop.attrib.get(f"{{{_ANDROID_NS}}}name", "")
                == "android.adservices.AD_SERVICES_CONFIG"
            ):
                has_ads = True
                break
        metadata["has_ads"] = "true" if has_ads else "false"
        # Strip library-injected components
        for child_tag in ("activity", "service", "receiver", "provider", "meta-data"):
            for child in list(application.findall(f"{{{_ANDROID_NS}}}{child_tag}")):
                name_attr = child.attrib.get(f"{{{_ANDROID_NS}}}name", "")
                if any(
                    name_attr.startswith(prefix) for prefix in _LIBRARY_COMPONENT_PACKAGE_PREFIXES
                ):
                    application.remove(child)

    return apktool_manifest, metadata


def _render_cleaned_manifest(
    original_manifest: Path, metadata: dict[str, str], output: Path
) -> None:
    """Write the AGP-compatible manifest to ``output``.

    Re-parses the cleaned apktool manifest (which now has library
    components stripped) and adds the ``AD_SERVICES_CONFIG`` override
    if ads are present.
    """
    ET.register_namespace("android", _ANDROID_NS)
    tree = ET.parse(original_manifest)
    root = tree.getroot()

    # Re-add the xmlns:tools namespace if not present (needed for
    # tools:replace on the AD_SERVICES_CONFIG override).
    if f"{{{_TOOLS_NS}}}" not in root.attrib:
        root.set(f"{{{_TOOLS_NS}}}replace", "android:fullBackupContent")

    # Add the AD_SERVICES_CONFIG override if ads are present.
    if metadata.get("has_ads") == "true":
        application = root.find(f"{{{_ANDROID_NS}}}application")
        if application is not None:
            ET.SubElement(
                application,
                f"{{{_ANDROID_NS}}}property",
                attrib={
                    f"{{{_ANDROID_NS}}}name": "android.adservices.AD_SERVICES_CONFIG",
                    f"{{{_ANDROID_NS}}}resource": "@xml/gma_ad_services_config",
                },
            )
            # Add the tools:replace attribute. ET can't easily mix
            # attribute namespaces in attrib dicts; use a workaround.
            prop = application.findall(f"{{{_ANDROID_NS}}}property")[-1]
            prop.set(f"{{{_TOOLS_NS}}}replace", "android:resource")

    output.parent.mkdir(parents=True, exist_ok=True)
    # ET's default write produces ugly ns0/ns1 prefixes; the
    # ``register_namespace`` calls above fix that.
    tree.write(output, encoding="utf-8", xml_declaration=True)


# ---------------------------------------------------------------------------
# BuildConfig reader (best-effort)
# ---------------------------------------------------------------------------

_BUILDCONFIG_RE = re.compile(
    r'public\s+static\s+final\s+[\w.]+\s+(\w+)\s*=\s*("[^"]*"|null|true|false|\d+);'
)


def _read_buildconfig_fields(decompiled_java_dir: Path) -> dict[str, tuple[str, str]]:
    """Read non-default BuildConfig fields from the decompiled BuildConfig.java.

    Returns a dict ``{name: (type, value)}`` ready for the
    ``buildConfigField`` Gradle syntax. Falls back to
    :data:`DEFAULT_BUILDCONFIG_FIELDS` if the BuildConfig is missing
    or empty.
    """
    bc = decompiled_java_dir / "app" / "myapp" / "BuildConfig.java"
    if not bc.exists():
        return dict(DEFAULT_BUILDCONFIG_FIELDS)
    text = bc.read_text()
    found: dict[str, tuple[str, str]] = {}
    for m in _BUILDCONFIG_RE.finditer(text):
        name, value = m.group(1), m.group(2)
        if name in DEFAULT_BUILDCONFIG_FIELDS:
            # Detect the type by quoting
            type_ = "String" if value.startswith('"') else "int"
            if value == "true" or value == "false":
                type_ = "boolean"
            found[name] = (type_, value)
    return found if found else dict(DEFAULT_BUILDCONFIG_FIELDS)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


@dataclass
class GradleProjectReport:
    """Summary of a :meth:`GradleProjectBuilder.build` invocation.

    Attributes:
        output_dir: Absolute path of the generated project.
        project_name: ``rootProject.name`` value (from package).
        application_id: ``applicationId`` value (from manifest package).
        manifest_stripped: Number of attributes stripped from the
            original manifest.
        build_config_fields_injected: Number of ``buildConfigField``
            entries written to ``app/build.gradle.kts``.
        files_written: Number of files the builder wrote (excluding
            copied/symlinked source).
        files_copied: Number of files copied from apktool into the
            project (res, assets, jniLibs).
        warnings: Human-readable warnings (e.g. "BeanShell AWT classes
            not copied, will not compile").
    """

    output_dir: Path
    project_name: str
    application_id: str
    manifest_stripped: int = 0
    build_config_fields_injected: int = 0
    files_written: int = 0
    files_copied: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "output_dir": str(self.output_dir),
            "project_name": self.project_name,
            "application_id": self.application_id,
            "manifest_stripped": self.manifest_stripped,
            "build_config_fields_injected": self.build_config_fields_injected,
            "files_written": self.files_written,
            "files_copied": self.files_copied,
            "warnings": self.warnings,
        }


class GradleProjectBuilder:
    """Generate a buildable Gradle project from decompile outputs.

    Typical usage::

        builder = GradleProjectBuilder(
            apk_path=Path("app.apk"),
            cleaned_sources=Path("jadx-deobf/sources"),
            apktool_workdir=Path("apktool"),
            output_dir=Path("rebuild"),
        )
        report = builder.build()
        # ... then on the build host:
        #   cd rebuild && ./gradlew :app:assembleDebug
    """

    def __init__(
        self,
        *,
        apk_path: str | Path,
        cleaned_sources: str | Path,
        apktool_workdir: str | Path,
        output_dir: str | Path,
        gradle_version: str = DEFAULT_GRADLE_VERSION,
        agp_version: str = DEFAULT_AGP_VERSION,
        kotlin_version: str = DEFAULT_KOTLIN_VERSION,
        sdk_dir: str | Path | None = None,
        copy_mode: Literal["copy", "symlink"] = "copy",
    ) -> None:
        self.apk_path = Path(apk_path).expanduser().resolve()
        self.cleaned_sources = Path(cleaned_sources).expanduser().resolve()
        self.apktool_workdir = Path(apktool_workdir).expanduser().resolve()
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.gradle_version = gradle_version
        self.agp_version = agp_version
        self.kotlin_version = kotlin_version
        self.sdk_dir = (
            Path(sdk_dir).expanduser().resolve()
            if sdk_dir
            else Path(os.environ.get("ANDROID_HOME", "/opt/android-sdk"))
        )
        self.copy_mode = copy_mode

    def build(self) -> GradleProjectReport:
        """Write the project to ``self.output_dir`` and return a summary.

        Steps:
          1. Read the apktool manifest, extract metadata, strip
             AGP-injected attrs + library components.
          2. Write the cleaned manifest.
          3. Read BuildConfig fields from the decompiled source.
          4. Write the top-level Gradle files.
          5. Write the app/build.gradle.kts with BuildConfig fields
             and the namespace.
          6. Copy or symlink cleaned sources, res, assets, jniLibs.
          7. Copy the Gradle wrapper from
             ``~/.gradle/wrapper/dists/gradle-<v>-bin/.../gradle-<v>/``.
          8. Copy the native-triage report (if present) into
             ``reports/native-triage.md``.
        """
        report = GradleProjectReport(
            output_dir=self.output_dir,
            project_name="rebuild",
            application_id="",
        )
        # 1. Read & clean manifest. ``_clean_manifest`` does both:
        # extracts metadata first (BEFORE stripping package=), then
        # writes the cleaned file. Returns ``(stripped_count, metadata)``.
        apktool_manifest = self.apktool_workdir / "AndroidManifest.xml"
        if not apktool_manifest.exists():
            raise FileNotFoundError(f"apktool manifest not found: {apktool_manifest}")
        cleaned_manifest_path = self.output_dir / "app/src/main/AndroidManifest.xml"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        manifest_stripped_count, metadata = self._clean_manifest(
            apktool_manifest, cleaned_manifest_path
        )
        # 2. Apply the AD_SERVICES_CONFIG override if applicable.
        # This re-renders the cleaned manifest in place (overwrites
        # the file we just wrote with the augmented version).
        _render_cleaned_manifest(cleaned_manifest_path, metadata, cleaned_manifest_path)
        report.manifest_stripped = manifest_stripped_count
        report.project_name = metadata.get("package", "rebuild").split(".")[-1]
        report.application_id = metadata.get("package", "")

        # 3. BuildConfig fields
        bc_fields = _read_buildconfig_fields(self.cleaned_sources)
        report.build_config_fields_injected = len(bc_fields)

        # 4. Top-level Gradle files
        for relpath, content in self._render_top_level(metadata):
            self._write(relpath, content)
            report.files_written += 1

        # 5. app/ build files
        for relpath, content in self._render_app_level(metadata, bc_fields):
            self._write(relpath, content)
            report.files_written += 1

        # 6. Copy or symlink source tree, res, assets, jniLibs
        report.files_copied += self._copy_sources()
        report.files_copied += self._copy_apktool_tree(report.warnings)

        # 7. Gradle wrapper
        report.files_written += self._install_wrapper()

        # 8. Native triage report (if any)
        self._install_native_triage_report()

        return report

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _clean_manifest(self, src: Path, dst: Path) -> tuple[int, dict[str, str]]:
        """Strip attrs and library components; return (count, metadata).

        Metadata (``package``, ``versionCode``, ``versionName``,
        ``application_class``, ``has_ads``) is extracted BEFORE the
        ``package=`` attribute is stripped (we still need it for
        ``applicationId``).
        """
        # ElementTree's ``fromstring`` does NOT honour ``xmlns:android``
        # declarations: parsed element tags have NO namespace prefix
        # even when the source declares one. We work around this by
        # doing all the namespace handling via ``_local_name`` (strip
        # ``{uri}`` prefix from attribute names) and direct attribute
        # access. The downstream serialisation does use the
        # registered namespace (via ``register_namespace``), so the
        # output manifest is properly prefixed.
        ET.register_namespace("android", _ANDROID_NS)
        ET.register_namespace("tools", _TOOLS_NS)
        tree = ET.parse(src)
        root = tree.getroot()

        # Extract metadata BEFORE stripping. ET keeps attribute names
        # verbatim from the source, so ``xmlns:android:foo`` becomes
        # ``{http://schemas.android.com/apk/res/android}foo`` in
        # ``element.attrib``. We need the ``{...}foo`` form.
        def _a(name: str) -> str:
            """Look up an attribute, supporting both the
            ``{ns}name`` and the bare ``name`` forms.
            """
            return root.attrib.get(f"{{{_ANDROID_NS}}}{name}", "") or root.attrib.get(name, "")

        metadata: dict[str, str] = {
            "package": root.attrib.get("package", ""),
            "version_code": _a("versionCode") or "0",
            "version_name": _a("versionName") or "0.0.0",
        }
        # Find the <application> element (no namespace prefix
        # because ET stripped it on parse).
        application = None
        for child in root:
            if _local_name(child.tag) == "application":
                application = child
                break
        if application is not None:
            metadata["application_class"] = application.attrib.get(
                f"{{{_ANDROID_NS}}}name", ""
            ) or application.attrib.get("name", "")
            # Detect ad-services conflict
            has_ads = False
            for prop in application:
                if _local_name(prop.tag) != "property":
                    continue
                pname = prop.attrib.get(f"{{{_ANDROID_NS}}}name", "") or prop.attrib.get("name", "")
                if pname == "android.adservices.AD_SERVICES_CONFIG":
                    has_ads = True
                    break
            metadata["has_ads"] = "true" if has_ads else "false"
        else:
            metadata["has_ads"] = "false"

        removed = 0
        for attr in list(root.attrib):
            local = _local_name(attr)
            if local in _MANIFEST_ATTRS_TO_STRIP:
                del root.attrib[attr]
                removed += 1
        if application is not None:
            for attr in list(application.attrib):
                local = _local_name(attr)
                if local in _MANIFEST_ATTRS_TO_STRIP:
                    del application.attrib[attr]
                    removed += 1
            for child in list(application):
                local_tag = _local_name(child.tag)
                if local_tag not in ("activity", "service", "receiver", "provider"):
                    continue
                name_attr = child.attrib.get(f"{{{_ANDROID_NS}}}name", "") or child.attrib.get(
                    "name", ""
                )
                if any(
                    name_attr.startswith(prefix) for prefix in _LIBRARY_COMPONENT_PACKAGE_PREFIXES
                ):
                    application.remove(child)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tree.write(dst, encoding="utf-8", xml_declaration=True)
        return removed, metadata

    def _render_top_level(self, metadata: dict[str, str]) -> list[tuple[str, str]]:
        """Generate ``(relative_path, content)`` for top-level files."""
        return [
            (
                "settings.gradle.kts",
                SETTINGS_GRADLE_KTS.format(
                    project_name=metadata.get("package", "rebuild").split(".")[-1]
                ),
            ),
            ("build.gradle.kts", ROOT_BUILD_GRADLE_KTS),
            ("gradle.properties", GRADLE_PROPERTIES),
            ("local.properties", LOCAL_PROPERTIES.format(sdk_dir=self.sdk_dir)),
            (".gitignore", GITIGNORE),
            (
                "gradle/libs.versions.toml",
                LIBS_VERSIONS_TOML.format(
                    agp_version=self.agp_version,
                    kotlin_version=self.kotlin_version,
                ),
            ),
            (
                "gradle/wrapper/gradle-wrapper.properties",
                GRADLE_WRAPPER_PROPERTIES.format(gradle_version=self.gradle_version),
            ),
        ]

    def _render_app_level(
        self, metadata: dict[str, str], bc_fields: dict[str, tuple[str, str]]
    ) -> list[tuple[str, str]]:
        """Generate ``(relative_path, content)`` for ``app/`` files."""
        application_id = metadata.get("package", "")
        namespace = "app.myapp"  # The decompiled app package
        return [
            (
                "app/build.gradle.kts",
                APP_BUILD_GRADLE_KTS_TEMPLATE.format(
                    namespace=namespace,
                    application_id=application_id,
                    version_code=metadata.get("version_code", "0"),
                    version_name=metadata.get("version_name", "0.0.0"),
                    build_config_fields=_render_buildconfig_fields(bc_fields),
                ),
            ),
            ("app/proguard-rules.pro", PROGUARD_RULES_PRO),
        ]

    def _write(self, relpath: str, content: str) -> None:
        """Write ``content`` to ``self.output_dir / relpath``."""
        path = self.output_dir / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def _copy_sources(self) -> int:
        """Copy the cleaned jadx source tree into the project."""
        dst = self.output_dir / "app/src/main/java"
        if not self.cleaned_sources.exists():
            return 0
        return _copy_or_link_tree(self.cleaned_sources, dst, self.copy_mode)

    def _copy_apktool_tree(self, warnings: list[str]) -> int:
        """Copy ``res/``, ``assets/``, and ``lib/<abi>/`` from apktool."""
        total = 0
        for src_name, dst_rel in [
            ("res", "app/src/main/res"),
            ("assets", "app/src/main/assets"),
            ("lib", "app/src/main/jniLibs"),
        ]:
            src = self.apktool_workdir / src_name
            if not src.exists():
                continue
            dst = self.output_dir / dst_rel
            total += _copy_or_link_tree(src, dst, self.copy_mode)
        return total

    def _install_wrapper(self) -> int:
        """Copy gradlew, gradlew.bat, and gradle-wrapper.jar from the
        gradle distribution already on disk.
        """
        dist_root = Path.home() / ".gradle/wrapper/dists" / f"gradle-{self.gradle_version}-bin"
        if not dist_root.exists():
            return 0
        # Find the extracted distribution (hash subdir)
        candidates = list(dist_root.glob("*/gradle-*/bin/gradle"))
        if not candidates:
            return 0
        gradle_bin = candidates[0]
        # gradle_bin is `<extracted>/bin/gradle`; the wrapper bits live
        # under `<extracted>/lib/...` and the gradle distribution
        # doesn't actually ship gradlew. We have to find them from
        # another source. Simplest fallback: bootstrap by running
        # ``gradle wrapper`` from a temporary settings.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "settings.gradle.kts").write_text('rootProject.name = "wrapper-bootstrap"')
            try:
                import subprocess

                subprocess.run(  # noqa: S603 — gradle binary, not user input
                    [
                        str(gradle_bin),
                        "wrapper",
                        f"--gradle-version={self.gradle_version}",
                        "--distribution-type=bin",
                        "--no-daemon",
                    ],
                    cwd=str(tmp_path),
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
            except Exception:
                return 0
            # Copy the wrapper files into our project
            files_written = 0
            for name in ("gradlew", "gradlew.bat"):
                src = tmp_path / name
                if src.exists():
                    dst = self.output_dir / name
                    shutil.copy2(src, dst)
                    os.chmod(dst, 0o755)  # noqa: S103 — gradle wrapper needs to be executable
                    files_written += 1
            for name in ("gradle-wrapper.jar", "gradle-wrapper.properties"):
                src = tmp_path / "gradle/wrapper" / name
                if src.exists():
                    dst = self.output_dir / "gradle/wrapper" / name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    files_written += 1
            return files_written

    def _install_native_triage_report(self) -> None:
        """Copy the native-triage report (if present) to ``reports/``."""
        # The report is emitted by android-re-native-triage at
        # ``reports/native-triage.md`` next to the project. We don't
        # have a stable path to it; the caller can copy it manually.
        # We do create the ``reports/`` directory so the user's
        # ``build-log.md`` has a home.
        (self.output_dir / "reports").mkdir(parents=True, exist_ok=True)
        # Create an empty build-log.md so the project documents the
        # convention.
        (self.output_dir / "reports" / "build-log.md").touch()


def _local_name(attr: str) -> str:
    """Return the local name of an ElementTree attribute (strip namespace)."""
    return attr.split("}")[-1] if "}" in attr else attr


def _copy_or_link_tree(src: Path, dst: Path, mode: Literal["copy", "symlink"]) -> int:
    """Copy or symlink a directory tree. Returns the file count.

    ``mode="copy"`` is the default (works everywhere, including
    Windows). ``mode="symlink"`` is faster and saves 789 MB of
    duplicated disk for the AnyClaw rootfs, but only works on
    filesystems that support symlinks.
    """
    if not src.exists():
        return 0
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    if mode == "symlink":
        try:
            dst.symlink_to(src, target_is_directory=True)
        except OSError:
            # Fall back to copy if symlinks are unsupported
            shutil.copytree(src, dst, symlinks=True)
    else:
        shutil.copytree(src, dst, symlinks=True)
    return sum(1 for _ in dst.rglob("*") if _.is_file())


#: Module-level convenience wrapper.
def create_gradle_project(
    *,
    apk_path: str | Path,
    cleaned_sources: str | Path,
    apktool_workdir: str | Path,
    output_dir: str | Path,
    gradle_version: str = DEFAULT_GRADLE_VERSION,
    agp_version: str = DEFAULT_AGP_VERSION,
    kotlin_version: str = DEFAULT_KOTLIN_VERSION,
    sdk_dir: str | Path | None = None,
    copy_mode: Literal["copy", "symlink"] = "copy",
) -> GradleProjectReport:
    """Build a Gradle project; see :class:`GradleProjectBuilder`."""
    return GradleProjectBuilder(
        apk_path=apk_path,
        cleaned_sources=cleaned_sources,
        apktool_workdir=apktool_workdir,
        output_dir=output_dir,
        gradle_version=gradle_version,
        agp_version=agp_version,
        kotlin_version=kotlin_version,
        sdk_dir=sdk_dir,
        copy_mode=copy_mode,
    ).build()
