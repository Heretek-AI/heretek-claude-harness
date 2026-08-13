---
name: android-re-network-intercept
description: |
  Use when the user wants to capture and inspect an app's network
  traffic end-to-end. Sets up an MITM proxy (Burp, mitmproxy,
  Charles) on the host, routes device traffic through it, and uses
  a Frida SSL-pinning bypass to defeat certificate pinning.
  Triggers: "intercept the traffic from <app>", "set up MITM",
  "capture HTTPS from <package>", "Burp this app", "see what
  <app> sends over the network". Requires a rooted device with
  frida-server, plus a running proxy on the host.
effect:
  filesystem:
    - read APK (for the SSL bypass scripts)
    - write a tiny patched APK (only if the user opts in to the
      repackage step)
  network:
    - opens a TCP reverse forward (device → host)
    - routes all app traffic through the proxy
    - reads decrypted HTTPS via the proxy UI
  device:
    - installs the proxy CA (root required)
    - loads a universal SSL-bypass Frida script
requires:
  mcp:
    - android-re-dynamic
    - android-re-triage
  proxy: burp / mitmproxy / charles running on the host
---

# Network traffic interception

Capture an app's HTTPS traffic via a host MITM proxy. Combines
adb reverse-forwarding, system CA installation, and a universal
Frida SSL-pinning bypass.

## When to use

The user wants to see the actual HTTPS requests an app makes —
URIs, headers, bodies. Without a bypass, certificate-pinned apps
refuse to talk to the proxy. This skill chains the moving parts
together.

If the user just wants to see *which* hosts the app talks to
(DNS-level) or to look at the app's source for URLs, route to
`android-re-secrets-scan` instead.

## Inputs

| Field | Required | Description |
|-------|----------|-------------|
| `package` | yes | Target package |
| `proxy_host` | yes | Host running the proxy (often `10.0.2.2` for the emulator) |
| `proxy_port` | no | Port (default 8080) |
| `mitm` | no | Install the system CA on the device (default true) |
| `record_duration_s` | no | Length of the capture window (default 60) |

## Workflow

1. **Verify the proxy is up.**
   Tell the user to start Burp / mitmproxy / Charles on the
   host:port. Don't proceed until they confirm. If the user is
   using mitmproxy, they need to run it in transparent mode.

2. **Forward device port → host.**
   `mcp__android-re-dynamic__tcp_forward` (or
   `setup_mitm` which wraps this) with `device_port=proxy_port`
   and `host_port=proxy_port`. The app can now reach
   `127.0.0.1:proxy_port` on the device and hit the host proxy.

3. **Install the proxy CA.**
   `mcp__android-re-dynamic__setup_mitm` with
   `install_cert=true, confirm=true`. This pushes the proxy's
   root CA into `/system/etc/security/cacerts/` so the
   platform's trust store includes it.

4. **Bypass SSL pinning.**
   `mcp__android-re-dynamic__frida_spawn` (or
   `frida_attach`) for the package, then
   `frida_load_script` with the
   `android-re-sslpinning-bypass` skill's
   `scripts/universal-ssl-bypass.js`. The script hooks
   `X509TrustManager`, `HostnameVerifier`, OkHttp's
   `CertificatePinner`, Conscrypt, and native
   `ssl_verify_cert_chain`.

5. **Trigger traffic.**
   Tell the user to use the app. The proxy's UI will start
   filling up with the decrypted requests.

6. **Persist the capture.**
   `mcp__android-re-dynamic__take_screenshot` periodically
   for visual context. Save the proxy's HAR / PCAP / log
   under `./.triage/network-<id>/`.

7. **Stop.**
   `mcp__android-re-dynamic__frida_unload_script` +
   `close_session`. Optionally remove the system CA:
   `adb shell rm /system/etc/security/cacerts/<hash>.0`.

8. **Add findings to a triage (optional).**
   `mcp__android-re-triage__add_finding` for every endpoint
   the user cares about. Use
   `mcp__android-re-triage__link_finding_to_evidence` to
   attach the request / response bodies.

## Output

- A `network-<id>/` directory under `./.triage/` with:
  - `screenshot-*.png` (visual context at intervals)
  - `proxy-log.txt` (if the user provided one)
  - `findings.json` (the entries added to the triage)
- A markdown report section listing the captured endpoints
  and any findings.

## Examples

### Example 1: capture an emulator app via mitmproxy

> User: Set up mitmproxy at `10.0.2.2:8080` and capture traffic
> from `com.example.app` for 60 seconds.

Steps: 1-7 above with `mitmproxy_host=10.0.2.2`,
`proxy_port=8080`, `mitm=true`, `record_duration_s=60`.

### Example 2: app uses SSL pinning we can't bypass

> User: This app uses SPKI hash pinning. The universal bypass
> doesn't work.

Step 1: hook the OkHttp `CertificatePinner` directly to log
the SPKI hashes the app expects. Step 2: add the proxy's SPKI
to the pin list. Step 3: use `frida_attach` to override the
pin check at runtime.

## Output convention

Screenshots taken during the MITM session land in:

```
Output/<apk-basename>-<short-sha>/network/screenshot-<ts>.png
```

`setup_mitm` accepts an `output_dir` parameter (defaulting to
`$ANDROID_RE_OUTPUT_DIR/network/`) to make this convention explicit.
The actual HTTPS flow capture lives on the host proxy (mitmproxy /
Burp / Charles); copy the flow files to
`Output/<apk-basename>-<short-sha>/network/` manually.

For the convention itself, see [`docs/output-convention.md`](../../docs/output-convention.md).

## Notes

- `setup_mitm` requires frida-server running as root (for
  `/system/etc/security/cacerts/` writes).
- For apps that detect proxying (e.g. OkHttp's
  `ConnectionSpec` excluding user CAs), see the
  `android-re-repackage` skill to add a `network_security_config.xml`.
- The universal bypass script is in
  `android-re-sslpinning-bypass/scripts/universal-ssl-bypass.js`.
- For non-HTTP traffic (gRPC, WebSocket, mDNS), the proxy
  configuration differs; mitmproxy in transparent mode is the
  simplest path.
