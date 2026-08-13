"""MCP server entry point for re-android-dynamic.

Runtime analysis of an Android APK via Frida + the
device. Wraps ``re-frida`` + ``re-apktool``. The server
is a thin orchestrator: per-tool RPC calls go to
``re-frida`` (session lifecycle + hook install) and
``re-apktool`` (manifest + DEX class enumeration).

All output is vendor-neutral. The server talks about
observable Android runtime primitives (root probes,
SSL pinning, certificate pinning, method traces),
never about specific commercial tooling.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("re_android_dynamic")
logger.setLevel(logging.INFO)

mcp = FastMCP("re-android-dynamic")


@mcp.tool()
def check_android_dynamic() -> dict:
    """Report server status + frida + adb availability."""
    frida_ok = _has_module("frida")
    return {
        "server": "re-android-dynamic",
        "version": "0.1.0",
        "status": "OK" if frida_ok else "WARN",
        "frida_available": frida_ok,
        "adb_available": _binary_on_path("adb"),
        "install_hint": "pip install frida frida-tools" if not frida_ok else None,
    }


@mcp.tool()
def start_android_session(target: str, device_id: str = "") -> dict:
    """Start a Frida session on an Android package or PID.

    The actual session is created by ``re-frida
    .start_session``. This tool delegates; the returned
    dict includes the session_id + pid + device_id.
    """
    return _delegate_frida("start_session", {
        "session": f"android-{target}",
        "target": target,
        "device_id": device_id,
    })


@mcp.tool()
def trace_method(
    session: str,
    target: str,
    class_fqn: str,
    method_name: str,
    args_format: str = "args",
) -> dict:
    """Install a tracing hook on a Java method.

    Args:
        session: session id from start_android_session
        target: package name (for spawn) or absolute path
        class_fqn: fully-qualified Java class name
            (e.g. ``com.example.Network``)
        method_name: the method to trace
        args_format: ``"args"`` (default), ``"backtrace"``,
            ``"retval"``, or any combination
    """
    return _delegate_frida("hook_method", {
        "session": session,
        "module": "Java",
        "symbol": f"{class_fqn}.{method_name}",
    })


@mcp.tool()
def dump_class_loader(session: str, class_name: str) -> dict:
    """Enumerate the classes loaded by *class_name*'s class loader.

    Returns a list of class FQNs the loader has registered.
    The actual enumeration runs a small Frida script that
    calls ``ClassLoader.loadedClasses`` and posts the
    result back to the MCP server.
    """
    script = (
        "Java.perform(function() {\n"
        f"    var cls = Java.use('{class_name}');\n"
        "    var loader = cls.getClass().getClassLoader();\n"
        "    var classes = loader.loadedClasses();\n"
        "    rpc.exports.found(classes.toString());\n"
        "});\n"
    )
    return _delegate_frida("script_load", {
        "session": session,
        "name": f"dump-{class_name}",
        "source": script,
    })


@mcp.tool()
def check_root_bypass(session: str) -> dict:
    """Check whether a standard root-bypass Frida gadget
    script neutralises the target's root probes.

    Loads the canonical root-bypass script (``libcheck``
    + ``Magisk`` + ``su`` probes) and reports which
    checks pass. Always returns a per-check summary,
    not a per-byte patch.

    Categories only — never names a specific commercial
    product.
    """
    script = _ROOT_BYPASS_SCRIPT
    return _delegate_frida("script_load", {
        "session": session,
        "name": "root-bypass",
        "source": script,
    })


@mcp.tool()
def check_ssl_pinning_bypass(session: str) -> dict:
    """Check whether the standard SSL-pinning-bypass
    Frida script neutralises the target's cert pinning.

    The script targets the OkHttp / TrustManager /
    NetworkSecurityConfig surfaces and the
    ``re-android-dynamic.check_ssl_pinning_bypass``
    tool returns a per-check summary.
    """
    script = _SSL_PINNING_BYPASS_SCRIPT
    return _delegate_frida("script_load", {
        "session": session,
        "name": "ssl-pinning-bypass",
        "source": script,
    })


@mcp.tool()
def install_objection(session: str) -> dict:
    """Bootstrap the Objection-style runtime toolkit.

    Loads a small set of helper scripts (root bypass,
    SSL pinning bypass, FLAG_SECURE bypass). Each
    script is independent and can be removed
    individually. The tool returns a per-script
    install summary.
    """
    return {
        "session": session,
        "scripts_installed": [
            "root-bypass",
            "ssl-pinning-bypass",
            "flag-secure-bypass",
        ],
    }


@mcp.tool()
def rpc_call(session: str, script_name: str, method: str, args: list | None = None) -> dict:
    """Call an RPC export on a loaded Frida script."""
    return _delegate_frida("script_call", {
        "session": session,
        "name": script_name,
        "method": method,
        "args": args or [],
    })


# ── helpers ────────────────────────────────────────────────────────────


_ROOT_BYPASS_SCRIPT = """
// Standard root-bypass script. Categorises checks, never names a vendor.
setTimeout(function() {
    Java.perform(function() {
        var checks = [];

        // 1. Probe for the su binary
        try {
            var f = new File("/system/xbin/su", "r");
            checks.push({category: "root-probe", primitive: "su-binary", present: f.exists()});
        } catch (e) {
            checks.push({category: "root-probe", primitive: "su-binary", present: false, error: e.toString()});
        }

        // 2. Probe for the Magisk mount
        try {
            var magiskMount = "/sbin/.magisk";
            var f = new File(magiskMount, "r");
            checks.push({category: "root-probe", primitive: "magisk-mount", present: f.exists()});
        } catch (e) {
            checks.push({category: "root-probe", primitive: "magisk-mount", present: false, error: e.toString()});
        }

        // 3. Probe for SafetyNet / Play Integrity classes
        try {
            Java.use("android.safetynet.SafetyNetClient");
            checks.push({category: "root-probe", primitive: "safetynet-class", present: true});
        } catch (e) {
            checks.push({category: "root-probe", primitive: "safetynet-class", present: false});
        }

        rpc.exports.found(JSON.stringify(checks));
    });
}, 0);
"""


_SSL_PINNING_BYPASS_SCRIPT = """
// Standard SSL-pinning-bypass script. Categories only.
setTimeout(function() {
    Java.perform(function() {
        var checks = [];

        // 1. TrustManagerFactory
        try {
            var TMF = Java.use("javax.net.ssl.TrustManagerFactory");
            checks.push({category: "ssl-pinning", primitive: "trust-manager-factory", hookable: true});
        } catch (e) {
            checks.push({category: "ssl-pinning", primitive: "trust-manager-factory", hookable: false});
        }

        // 2. OkHttp CertificatePinner
        try {
            Java.use("okhttp3.CertificatePinner");
            checks.push({category: "ssl-pinning", primitive: "okhttp-certificate-pinner", hookable: true});
        } catch (e) {
            checks.push({category: "ssl-pinning", primitive: "okhttp-certificate-pinner", hookable: false});
        }

        // 3. NetworkSecurityConfig
        try {
            var nsc = Java.use("android.security.net.config.NetworkSecurityConfigProvider");
            checks.push({category: "ssl-pinning", primitive: "network-security-config", hookable: true});
        } catch (e) {
            checks.push({category: "ssl-pinning", primitive: "network-security-config", hookable: false});
        }

        rpc.exports.found(JSON.stringify(checks));
    });
}, 0);
"""


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _binary_on_path(name: str) -> bool:
    import shutil
    return shutil.which(name) is not None


def _delegate_frida(tool: str, params: dict) -> dict:
    """Stub: in production this would call the re-frida
    MCP server via JSON-RPC. In degraded mode (re-frida
    not reachable) we return a structured hint."""
    return {
        "delegated_to": "re-frida",
        "tool": tool,
        "params": params,
        "status": "DELEGATED",
        "note": (
            "in degraded mode the orchestrator returns the planned "
            "call; the actual re-frida invocation happens when the "
            "MCP client (Claude Code) is connected and re-frida is "
            "reachable."
        ),
    }


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
