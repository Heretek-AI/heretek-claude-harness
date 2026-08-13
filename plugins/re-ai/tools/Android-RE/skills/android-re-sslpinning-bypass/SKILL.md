---
name: android-re-sslpinning-bypass
description: |
  Use when the user wants to bypass SSL/TLS certificate pinning on
  a running app to intercept HTTPS traffic (e.g. with Burp or
  mitmproxy). Triggers: "bypass SSL pinning", "unpin cert", "trust
  user CA", "MITM this app", "intercept HTTPS from <package>",
  "ssl-pinning bypass on <app>". Requires a rooted device with
  frida-server running. The app must support installing user CAs
  (or be repackaged with android-re-repackage first).
effect:
  filesystem: read
  network: forwards traffic through user's MITM proxy
  device: hooks SSL classes; does not modify app or device state otherwise
requires:
  mcp:
    - android-re-dynamic
    - android-re-repackage  # may be needed for apps that don't trust user CAs
---

# Bypass SSL/TLS pinning

Drop a universal SSL pinning bypass hook on the target app so
that the user can intercept HTTPS traffic with their MITM proxy
(Burp, mitmproxy, Charles, etc.).

## When to use

The user wants to see what HTTPS requests the app makes (or
receives). Apps that pin the certificate refuse to talk to a
proxy that uses a different CA, so a bypass is required.

Two distinct bypass techniques are in play here:

1. **Java-side pinning** — OkHttp, Retrofit, Apache HttpClient,
   Conscrypt, etc. Replaced with hooks that return `true` for
   "is this CA trusted?".
2. **Native-side pinning** — OpenSSL / BoringSSL / Conscrypt in
   native code. Requires hooking the verify function in the
   native library.

Most modern apps use **both**. The skill loads a combined script.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `serial` | yes | Frida device id |
| `package` | yes | Target package |
| `mitm_host` | yes | Host running the MITM proxy (often `10.0.2.2` for emulator) |
| `mitm_port` | no | Port (default 8080) |
| `native_only` | no | If true, only hook native-side pinning |

## Workflow

1. **Verify MITM setup.**
   - Tell the user to start their MITM proxy on `mitm_host:mitm_port`.
   - Use `mcp__android-re-dynamic__setup_mitm` to forward device
     port → host (the proxy addressable as 127.0.0.1 on the device).
   - Confirm the user's CA is installed at
     `/system/etc/security/cacerts/<hash>.0` (most AOSP userdebug
     builds allow this; on locked bootloaders, see
     `android-re-repackage`).

2. **Spawn the app.**
   `mcp__android-re-dynamic__frida_spawn` with `serial` and
   `package`. Returns `session_id`.

3. **Load the universal SSL bypass script.**
   `mcp__android-re-dynamic__frida_load_script` with
   `session_id`, `name="ssl-bypass"`, `source=<the script below>`.
   The script hooks:

   - `X509TrustManager.checkServerTrusted(...)` — return `[]` of
     certs.
   - `HostnameVerifier.verify(host, sslSession)` — return `true`.
   - `CertificatePinner.check(hostname, peerCertificates)` — empty.
   - `TrustManagerFactory.getTrustManagers()` — replace with a
     single trust-all manager.
   - `ConscryptFileDescriptorSocket.checkTrusted` — empty.
   - `OpenSSLX509CertificateFactory.verifyCertificate` — return 1
     (success).
   - Native: `ssl_verify_cert_chain` in libssl / libconscrypt.

   See [`scripts/universal-ssl-bypass.js`](scripts/universal-ssl-bypass.js)
   for the full source.

4. **Trigger network traffic.**
   Tell the user to use the app. The intercepted requests will
   appear in the proxy's UI.

5. **Diagnose failures.**
   - If the app still fails TLS, check that the user's CA is
     installed on the device.
   - If only some requests fail, the app may be using a custom
     pinning scheme (e.g. SPKI pinning). Use
     `android-re-dynamic-hook` to find the pin configuration and
     add a hook.
   - Some apps use OkHttp's certificate transparency (CT) log
     checks; these require per-app hooks.

6. **Clean up.**
   `frida_unload_script` + `close_session`.

## Output

A markdown section with:

- **Session id**: <session_id>
- **Bypassed**: list of pinning classes hooked
- **MITM endpoint**: <host>:<port>
- **Status**: TLS handshakes observed in proxy UI (user confirms)

## Examples

### Example 1: bypass OkHttp pinning on a chat app

> User: I need to intercept HTTPS from `com.example.chat`.

Steps:

1. Start mitmproxy locally.
2. `setup_mitm` with `mitm_host=10.0.2.2`, `mitm_port=8080`.
3. `frida_spawn` com.example.chat.
4. `frida_load_script` with the universal bypass.
5. Tell user to send a message in the app.
6. Inspect traffic in mitmproxy.

### Example 2: app refuses user CA (locked bootloader)

> User: This app won't trust my Burp CA. Can you bypass it?

Step 1: repackage the app first with a network_security_config
that allows user CAs (see android-re-repackage). Then proceed
with the bypass script.

## Output convention

Screenshots taken during the bypass land in:

```
Output/<apk-basename>-<short-sha>/dynamic/screenshot-<ts>.png
```

The proxy's traffic log (mitmproxy / Burp / Charles) lives on the host
proxy, NOT in `Output/`. Copy the flow files to
`Output/<apk-basename>-<short-sha>/network/` manually.

For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).

## Notes

- Universal bypass is good for 90% of apps. The remaining 10%
  use custom pinning (SPKI hash, CT log checks, custom
  OkHttp interceptors). Use `android-re-frida-script-author` to
  build a targeted bypass.
- For native-only pinning, set `native_only=true` and the script
  skips the Java hooks.
- frida-server must be running as root for `setup_mitm` to
  install the system CA.
