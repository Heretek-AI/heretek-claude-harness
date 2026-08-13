"""Smoke tests for :mod:`android_re_core.gradle` (Gradle project scaffolder).

The tests do NOT run ``./gradlew :app:assembleDebug`` (that requires
an Android SDK on the test host and is slow). They assert the
file inventory and manifest cleanup that the builder writes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Import the gradle module directly to avoid the androguard-dependent
# `android_re_core/__init__.py` chain.
from android_re_core.gradle import (
    APP_BUILD_GRADLE_KTS_TEMPLATE,
    DEFAULT_BUILDCONFIG_FIELDS,
    LIBS_VERSIONS_TOML,
    PROGUARD_RULES_PRO,
    SETTINGS_GRADLE_KTS,
    GradleProjectBuilder,
    GradleProjectReport,
    create_gradle_project,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ANDROID_NS = "http://schemas.android.com/apk/res/android"


@pytest.fixture
def apk_path(tmp_path: Path) -> Path:
    """A minimal stand-in APK path. The builder reads manifest
    metadata from the apktool directory, not the APK, so a placeholder
    is sufficient.
    """
    p = tmp_path / "app.apk"
    p.touch()
    return p


@pytest.fixture
def cleaned_sources(tmp_path: Path) -> Path:
    """A minimal cleaned-sources directory with one Kotlin class."""
    src = tmp_path / "sources" / "app" / "myapp"
    src.mkdir(parents=True, exist_ok=True)
    (src / "BuildConfig.java").write_text(
        "package app.myapp;\n"
        "public final class BuildConfig {\n"
        '  public static final String FLAVOR = "prod";\n'
        '  public static final String OAUTH_APP_RETURN_URI = "myapp://auth/callback";\n'
        '  public static final String OAUTH_CALLBACK_SCHEME = "myapp";\n'
        '  public static final String OPENROUTER_CALLBACK_URL = "https://example.com/cb";\n'
        '  public static final String PREMIUM_SUBS_PRODUCT_ID = "myapp_premium_monthly";\n'
        "}\n"
    )
    return tmp_path / "sources"


@pytest.fixture
def apktool_workdir(tmp_path: Path) -> Path:
    """A minimal apktool-decoded directory with a real manifest."""
    workdir = tmp_path / "apktool"
    (workdir / "res").mkdir(parents=True, exist_ok=True)
    (workdir / "assets").mkdir(parents=True, exist_ok=True)
    (workdir / "lib" / "arm64-v8a").mkdir(parents=True, exist_ok=True)
    (workdir / "lib" / "arm64-v8a" / "libfoo.so").write_bytes(b"fake")
    # A realistic manifest
    (workdir / "AndroidManifest.xml").write_text(
        f'<?xml version="1.0" encoding="utf-8"?>\n'
        f'<manifest xmlns:android="{ANDROID_NS}" '
        f'package="com.example.myapp" '
        f'compileSdkVersion="35" '
        f'platformBuildVersionCode="35">\n'
        f'  <uses-permission android:name="android.permission.INTERNET"/>\n'
        f'  <application android:name="com.example.myapp.App" '
        f'android:label="@string/app_name" '
        f'android:extractNativeLibs="true">\n'
        f'    <activity android:name="com.example.myapp.MainActivity"/>\n'
        f'    <service android:name="androidx.work.impl.foreground.SystemForegroundService"/>\n'
        f'    <receiver android:name="com.example.myapp.MessagingReceiver"/>\n'
        f"  </application>\n"
        f"</manifest>\n"
    )
    return workdir


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    return tmp_path / "rebuild"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGradleProjectBuilder:
    def test_writes_top_level_files(self, apk_path, cleaned_sources, apktool_workdir, output_dir):
        GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        for relpath in [
            "settings.gradle.kts",
            "build.gradle.kts",
            "gradle.properties",
            "local.properties",
            ".gitignore",
            "gradle/libs.versions.toml",
            "gradle/wrapper/gradle-wrapper.properties",
        ]:
            assert (output_dir / relpath).exists(), f"missing {relpath}"

    def test_writes_app_build_files(self, apk_path, cleaned_sources, apktool_workdir, output_dir):
        GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        assert (output_dir / "app/build.gradle.kts").exists()
        assert (output_dir / "app/proguard-rules.pro").exists()

    def test_strips_agp_attrs_from_manifest(
        self, apk_path, cleaned_sources, apktool_workdir, output_dir
    ):
        GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        manifest_path = output_dir / "app/src/main/AndroidManifest.xml"
        assert manifest_path.exists()
        text = manifest_path.read_text()
        # AGP-injected attrs are stripped
        assert "package=" not in text.split(">", 1)[0]  # no package= on <manifest>
        assert "compileSdkVersion" not in text
        # Library-injected components are stripped
        assert "androidx.work" not in text
        assert "com.google.firebase" not in text
        # App's own components and permissions are preserved
        assert "com.example.myapp.MainActivity" in text
        assert "android.permission.INTERNET" in text
        assert 'android:name="com.example.myapp.App"' in text

    def test_injects_buildconfig_fields(
        self, apk_path, cleaned_sources, apktool_workdir, output_dir
    ):
        GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        build_script = (output_dir / "app/build.gradle.kts").read_text()
        for field_name in DEFAULT_BUILDCONFIG_FIELDS:
            assert "buildConfigField(" in build_script
            assert f'"{field_name}"' in build_script

    def test_copies_res_assets_jnilibs(
        self, apk_path, cleaned_sources, apktool_workdir, output_dir
    ):
        GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        assert (output_dir / "app/src/main/res").exists()
        assert (output_dir / "app/src/main/assets").exists()
        assert (output_dir / "app/src/main/jniLibs/arm64-v8a/libfoo.so").exists()

    def test_copies_cleaned_sources(self, apk_path, cleaned_sources, apktool_workdir, output_dir):
        GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        assert (output_dir / "app/src/main/java/app/myapp/BuildConfig.java").exists()

    def test_report_has_application_id(
        self, apk_path, cleaned_sources, apktool_workdir, output_dir
    ):
        report = GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        assert report.application_id == "com.example.myapp"

    def test_project_name_uses_last_segment_of_package(
        self, apk_path, cleaned_sources, apktool_workdir, output_dir
    ):
        report = GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        assert report.project_name == "myapp"
        # settings.gradle.kts uses the project name
        settings = (output_dir / "settings.gradle.kts").read_text()
        assert 'rootProject.name = "myapp"' in settings

    def test_default_buildconfig_when_source_missing(
        self, apk_path, tmp_path, apktool_workdir, output_dir
    ):
        # No BuildConfig.java in cleaned_sources → use defaults
        empty_sources = tmp_path / "empty"
        empty_sources.mkdir()
        report = GradleProjectBuilder(
            apk_path=apk_path,
            cleaned_sources=empty_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        ).build()
        assert report.build_config_fields_injected == len(DEFAULT_BUILDCONFIG_FIELDS)


class TestCreateGradleProjectHelper:
    def test_returns_gradle_project_report(
        self, apk_path, cleaned_sources, apktool_workdir, output_dir
    ):
        report = create_gradle_project(
            apk_path=apk_path,
            cleaned_sources=cleaned_sources,
            apktool_workdir=apktool_workdir,
            output_dir=output_dir,
        )
        assert isinstance(report, GradleProjectReport)
        assert report.output_dir == output_dir


class TestTemplateStrings:
    """Sanity-check the embedded template strings don't drift."""

    def test_settings_template_has_required_keys(self):
        for key in ["pluginManagement", "dependencyResolutionManagement", "rootProject.name"]:
            assert key in SETTINGS_GRADLE_KTS

    def test_libs_versions_toml_has_agp_and_kotlin(self):
        assert "agp" in LIBS_VERSIONS_TOML
        assert "kotlin" in LIBS_VERSIONS_TOML
        assert "compose" in LIBS_VERSIONS_TOML

    def test_app_build_gradle_has_required_blocks(self):
        for key in [
            "namespace",
            "compileSdk",
            "applicationId",
            "minSdk",
            "targetSdk",
            "versionCode",
            "versionName",
            "multiDexEnabled",
            "abiFilters",
            "compose = true",
            "buildConfig = true",
            "implementation(libs.kotlin.stdlib)",
        ]:
            assert key in APP_BUILD_GRADLE_KTS_TEMPLATE, f"missing {key}"

    def test_proguard_rules_donotobfuscate(self):
        assert "-dontobfuscate" in PROGUARD_RULES_PRO
        assert "app.myapp" in PROGUARD_RULES_PRO
