# MITM certificate installation on Android

A reference for installing a proxy CA into the Android system
trust store via the `setup_mitm` tool. The user must be on a
rooted device (frida-server running as root) for the install to
work; on locked bootloaders, see the alternative approaches at
the bottom.

## Standard path (rooted device)

```bash
# 1. On the host, start your proxy. mitmproxy:
mitmproxy --listen-port 8080
# Burp: launch and bind 8080

# 2. Once mitmproxy has handled a single HTTPS request from
# any browser, the CA is at:
#    ~/.mitmproxy/mitmproxy-ca-cert.cer
# Or for Burp, export the cert from Proxy → Options → Import
# / Export CA certificate → Export in DER format.

# 3. Compute the OpenSSL hash that Android uses as the filename:
hash=$(openssl x509 -inform PEM -subject_hash_old -in mitmproxy-ca-cert.cer -noout 2>/dev/null \
       || openssl x509 -inform PEM -subject_hash -in mitmproxy-ca-cert.cer -noout)
# Older Android (< 7) uses subject_hash_old; newer uses subject_hash.

# 4. Push to the device:
adb push mitmproxy-ca-cert.cer /system/etc/security/cacerts/${hash}.0

# 5. Fix perms:
adb shell chmod 644 /system/etc/security/cacerts/${hash}.0

# 6. Reboot (Android 7+ requires a reboot for the system
# store to pick up the new cert).
adb reboot
```

## Alternative 1: app-level trust (no root)

Modern Android (API 24+) lets you install user CAs, but apps
that opt in to `networkSecurityConfig` (or target API 28+)
*ignore* them by default. To make an app trust user CAs, add a
`network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <base-config cleartextTrafficPermitted="false">
    <trust-anchors>
      <certificates src="system" />
      <certificates src="user" />
    </trust-anchors>
  </base-config>
</network-security-config>
```

Reference it from the manifest:

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ...>
```

Then repackage and re-sign. This is exactly what the
`android-re-repackage` skill automates.

## Alternative 2: Magisk + MagiskTrustUserCerts

If the device has Magisk, the
[MagiskTrustUserCerts](https://github.com/VV1N/MagiskTrustUserCerts)
module forces all apps to honor user-installed CAs. No repackage
required.

## Alternative 3: Frida-only (no cert install)

If you can't touch the system store, the universal
SSL-pinning bypass script (`universal-ssl-bypass.js`) hooks
the Java and native verification paths so a user CA is
accepted at the app layer. This is what the
`android-re-sslpinning-bypass` skill uses.

## Diagnosing failed captures

- **No traffic in the proxy UI** — the app's traffic is
  pinned to a specific IP that bypasses the proxy. Use
  `tcpdump -i any` on the host to confirm.
- **TLS handshake failures** — the app uses a custom TrustManager
  that's not in the universal bypass's hook list. Hook it
  explicitly via `frida_load_script`.
- **App crashes on launch** — the app has an emulator /
  root / debugger check that fires. See
  `android-re-sslpinning-bypass` "Diagnose failures" for the
  checklist.
- **Captures only initial traffic** — the app opens
  short-lived connections that close before the proxy logs
  them. Increase the proxy's log retention, or run
  `mitmproxy --set stream_large_bodies=10m`.
