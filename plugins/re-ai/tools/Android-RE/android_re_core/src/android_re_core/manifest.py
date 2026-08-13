"""Manifest views: components, intent filters, permissions, exported APIs.

Built on top of :mod:`androguard.core.axml`. The :class:`ManifestView`
class wraps a parsed manifest and exposes typed, JSON-serializable views
that MCP tools can return directly.

This module is intentionally read-only. Mutating the manifest happens
in :mod:`android_re_core.smali` (Phase 2) via apktool's decode/build
pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .apk import Apk
from .errors import APKInvalid

__all__ = [
    "Component",
    "ComponentType",
    "ManifestView",
    "Permission",
]


# ---------------------------------------------------------------------------
# Type enums
# ---------------------------------------------------------------------------


#: Valid component types in an AndroidManifest.xml.
ComponentType = str  # "activity" | "service" | "receiver" | "provider" | "application"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Component:
    """A single component declaration in the manifest."""

    type: ComponentType
    name: str
    exported: bool | None = None
    permission: str | None = None
    intent_filters: tuple[dict[str, Any], ...] = ()
    meta_data: dict[str, str] = field(default_factory=dict)
    authorities: str | None = None  # content providers only
    grant_uri_permissions: bool | None = None  # content providers only

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "exported": self.exported,
            "permission": self.permission,
            "intent_filters": list(self.intent_filters),
            "meta_data": dict(self.meta_data),
            "authorities": self.authorities,
            "grant_uri_permissions": self.grant_uri_permissions,
        }


@dataclass(frozen=True)
class Permission:
    """A single ``<uses-permission>`` entry, classified by protection level."""

    name: str
    protection_level: str = "unknown"  # "normal" | "dangerous" | "signature" | "unknown"
    is_dangerous: bool = False
    is_custom: bool = False  # not in Android's known permission list

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "protection_level": self.protection_level,
            "is_dangerous": self.is_dangerous,
            "is_custom": self.is_custom,
        }


# ---------------------------------------------------------------------------
# Known dangerous permissions (Android 14 / API 34 list).
# Sourced from https://developer.android.com/reference/android/Manifest.permission
# ---------------------------------------------------------------------------

_DANGEROUS_PERMISSIONS: frozenset[str] = frozenset(
    {
        # Calendar
        "android.permission.READ_CALENDAR",
        "android.permission.WRITE_CALENDAR",
        # Call log
        "android.permission.READ_CALL_LOG",
        "android.permission.WRITE_CALL_LOG",
        "android.permission.PROCESS_OUTGOING_CALLS",
        # Camera
        "android.permission.CAMERA",
        # Contacts
        "android.permission.READ_CONTACTS",
        "android.permission.WRITE_CONTACTS",
        "android.permission.GET_ACCOUNTS",
        # Location
        "android.permission.ACCESS_FINE_LOCATION",
        "android.permission.ACCESS_COARSE_LOCATION",
        "android.permission.ACCESS_BACKGROUND_LOCATION",
        # Microphone
        "android.permission.RECORD_AUDIO",
        # Phone
        "android.permission.READ_PHONE_STATE",
        "android.permission.READ_PHONE_NUMBERS",
        "android.permission.CALL_PHONE",
        "android.permission.ANSWER_PHONE_CALLS",
        "android.permission.ADD_VOICEMAIL",
        "android.permission.USE_SIP",
        "android.permission.ACCEPT_HANDOVER",
        # Sensors
        "android.permission.BODY_SENSORS",
        "android.permission.ACTIVITY_RECOGNITION",
        # SMS
        "android.permission.SEND_SMS",
        "android.permission.RECEIVE_SMS",
        "android.permission.READ_SMS",
        "android.permission.RECEIVE_WAP_PUSH",
        "android.permission.RECEIVE_MMS",
        "android.permission.READ_CELL_BROADCASTS",
        # Storage
        "android.permission.READ_EXTERNAL_STORAGE",
        "android.permission.WRITE_EXTERNAL_STORAGE",
        "android.permission.MANAGE_EXTERNAL_STORAGE",
        "android.permission.READ_MEDIA_IMAGES",
        "android.permission.READ_MEDIA_VIDEO",
        "android.permission.READ_MEDIA_AUDIO",
        # Nearby devices
        "android.permission.BLUETOOTH_CONNECT",
        "android.permission.BLUETOOTH_SCAN",
        "android.permission.BLUETOOTH_ADVERTISE",
        "android.permission.NEARBY_WIFI_DEVICES",
        # Notifications
        "android.permission.POST_NOTIFICATIONS",
    }
)

#: Custom (non-Android) permissions start with the app's own package name.
#: We mark them as :attr:`Permission.is_custom`.


# ---------------------------------------------------------------------------
# ManifestView
# ---------------------------------------------------------------------------


class ManifestView:
    """Typed view over a parsed AndroidManifest.xml.

    Construct with :meth:`from_apk` or :meth:`from_xml`.
    """

    def __init__(
        self,
        *,
        package: str | None,
        components: list[Component],
        permissions: list[Permission],
        uses_sdk: dict[str, int | None],
        uses_features: list[str],
        application: dict[str, Any],
        xml: str,
    ) -> None:
        self.package = package
        self.components = components
        self.permissions = permissions
        self.uses_sdk = uses_sdk
        self.uses_features = uses_features
        self.application = application
        self.xml = xml

    @classmethod
    def from_apk(cls, apk: Apk) -> ManifestView:
        """Build a :class:`ManifestView` from an :class:`Apk`."""
        if apk.is_closed:
            raise APKInvalid("APK has been closed")
        raw = apk.raw
        package = raw.get_package()
        xml = apk.read_manifest_xml()
        return cls._from_xml_android(xml, package, raw)

    @classmethod
    def from_xml(cls, xml: str) -> ManifestView:
        """Build a :class:`ManifestView` from a raw manifest XML string."""
        return cls._from_xml_android(xml, package=None, raw=None)

    # ------------------------------------------------------------------
    # Internal: androguard-backed parsing
    # ------------------------------------------------------------------

    @classmethod
    def _from_xml_android(
        cls,
        xml: str,
        package: str | None,
        raw: Any,
    ) -> ManifestView:
        """Parse the manifest XML and assemble typed views.

        We use the standard library's :mod:`xml.etree.ElementTree` rather
        than androguard's higher-level API, because the ElementTree view
        is portable, well-documented, and free of androguard's version
        churn.
        """
        from xml.etree import ElementTree as ET

        ns = "{http://schemas.android.com/apk/res/android}"
        try:
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            raise APKInvalid(
                "Invalid AndroidManifest.xml",
                details={"error": str(e)},
            ) from e

        if root.tag != "manifest":
            raise APKInvalid(
                f"Root element is not <manifest>: <{root.tag}>",
            )

        manifest_package = root.get("package") or package

        # --- uses-sdk ---
        uses_sdk: dict[str, int | None] = {"min": None, "target": None, "max": None}
        sdk_node = root.find("uses-sdk")
        if sdk_node is not None:
            for key in ("minSdkVersion", "targetSdkVersion", "maxSdkVersion"):
                v = sdk_node.get(f"{ns}{key}")
                if v is not None:
                    try:
                        uses_sdk[key.replace("SdkVersion", "")] = int(v)
                    except ValueError:
                        # Some manifests use "Lollipop" or similar; ignore.
                        pass

        # --- uses-feature ---
        uses_features: list[str] = []
        for feat in root.findall("uses-feature"):
            name = feat.get(f"{ns}name")
            if name:
                uses_features.append(name)

        # --- uses-permission ---
        permissions: list[Permission] = []
        for perm in root.findall("uses-permission"):
            name = perm.get(f"{ns}name")
            if not name:
                continue
            is_dangerous = name in _DANGEROUS_PERMISSIONS
            is_custom = bool(manifest_package) and name.startswith(f"{manifest_package}.")
            permissions.append(
                Permission(
                    name=name,
                    protection_level="dangerous" if is_dangerous else "normal",
                    is_dangerous=is_dangerous,
                    is_custom=is_custom,
                )
            )

        # --- components ---
        components: list[Component] = []
        app = root.find("application")
        if app is not None:
            for comp_type in ("activity", "service", "receiver", "provider"):
                for node in app.findall(comp_type):
                    components.append(_parse_component(node, comp_type, ns))

            # --- application-level attributes ---
            application: dict[str, Any] = {
                "label": app.get(f"{ns}label"),
                "icon": app.get(f"{ns}icon"),
                "debuggable": _to_bool(app.get(f"{ns}debuggable")),
                "allow_backup": _to_bool(app.get(f"{ns}allowBackup")),
                "uses_cleartext_traffic": _to_bool(app.get(f"{ns}usesCleartextTraffic")),
                "network_security_config": app.get(f"{ns}networkSecurityConfig"),
                "extract_native_libs": _to_bool(app.get(f"{ns}extractNativeLibs")),
            }
        else:
            application = {}

        return cls(
            package=manifest_package,
            components=components,
            permissions=permissions,
            uses_sdk=uses_sdk,
            uses_features=uses_features,
            application=application,
            xml=xml,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def components_of_type(self, type_: ComponentType) -> list[Component]:
        """Return all components of a given type."""
        return [c for c in self.components if c.type == type_]

    def dangerous_permissions(self) -> list[Permission]:
        """Return only the dangerous-level permissions."""
        return [p for p in self.permissions if p.is_dangerous]

    def exported_components(self) -> list[Component]:
        """Return all components that are explicitly ``exported=true``."""
        return [c for c in self.components if c.exported is True]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict for tool responses."""
        return {
            "package": self.package,
            "uses_sdk": self.uses_sdk,
            "uses_features": self.uses_features,
            "permissions": [p.to_dict() for p in self.permissions],
            "components": [c.to_dict() for c in self.components],
            "application": self.application,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value.lower() == "true"


def _parse_component(node: Any, comp_type: ComponentType, ns: str) -> Component:
    """Parse a single ``<activity>``/``<service>``/etc. element."""
    name = node.get(f"{ns}name") or ""
    exported = _to_bool(node.get(f"{ns}exported"))
    permission = node.get(f"{ns}permission")

    intent_filters: list[dict[str, Any]] = []
    for filt in node.findall("intent-filter"):
        actions = [a.get(f"{ns}name") for a in filt.findall("action") if a.get(f"{ns}name")]
        categories = [c.get(f"{ns}name") for c in filt.findall("category") if c.get(f"{ns}name")]
        data = []
        for d in filt.findall("data"):
            data.append(
                {
                    "scheme": d.get(f"{ns}scheme"),
                    "host": d.get(f"{ns}host"),
                    "port": d.get(f"{ns}port"),
                    "path": d.get(f"{ns}path"),
                    "pathPrefix": d.get(f"{ns}pathPrefix"),
                    "pathPattern": d.get(f"{ns}pathPattern"),
                    "mimeType": d.get(f"{ns}mimeType"),
                }
            )
        intent_filters.append(
            {
                "actions": actions,
                "categories": categories,
                "data": data,
            }
        )

    meta_data: dict[str, str] = {}
    for m in node.findall("meta-data"):
        key = m.get(f"{ns}name")
        value = m.get(f"{ns}value")
        if key and value:
            meta_data[key] = value

    authorities = node.get(f"{ns}authorities") if comp_type == "provider" else None
    grant = _to_bool(node.get(f"{ns}grantUriPermissions")) if comp_type == "provider" else None

    return Component(
        type=comp_type,
        name=name,
        exported=exported,
        permission=permission,
        intent_filters=tuple(intent_filters),
        meta_data=meta_data,
        authorities=authorities,
        grant_uri_permissions=grant,
    )


def find_components(
    components: Iterable[Component],
    *,
    type_: ComponentType | None = None,
    name_contains: str | None = None,
    exported: bool | None = None,
) -> list[Component]:
    """Filter a list of components by simple criteria."""
    out: list[Component] = []
    for c in components:
        if type_ is not None and c.type != type_:
            continue
        if name_contains is not None and name_contains not in c.name:
            continue
        if exported is not None and c.exported != exported:
            continue
        out.append(c)
    return out
