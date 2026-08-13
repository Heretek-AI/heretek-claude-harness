# ADB Setup

## Install Android Platform Tools

### Linux (Debian/Ubuntu/Fedora)

```bash
# Ubuntu/Debian
sudo apt install -y adb

# Fedora
sudo dnf install -y android-tools
```

### macOS

```bash
brew install --cask android-platform-tools
```

### Windows

Download the SDK Platform Tools ZIP from
https://developer.android.com/studio/releases/platform-tools and extract
to a directory on your PATH.

## Verify

```bash
adb version
# Android Debug Bridge version 1.0.41
# Version 37.0.0-...
```

## Connect a device

### Physical device (USB)

1. On the device, enable **Developer options** (tap **Build number** 7
   times in **Settings → About phone**).
2. Enable **USB debugging** in **Developer options**.
3. Plug in the device. The first time, accept the host fingerprint on
   the device.
4. Verify with `adb devices`. You should see your device listed as
   `device` (not `unauthorized`).

### Physical device (wireless, Android 11+)

```bash
adb pair <ip>:<port>     # one-time pairing
adb connect <ip>:<port>  # persistent connection
```

### Emulator

```bash
# List available AVDs
emulator -list-avds

# Start one
emulator -avd Pixel_API_33 -no-snapshot-load &

# Verify
adb devices
```

## Rooted device

Dynamic analysis (Phase 3+) requires root. To root:

- **Emulator** — Use a Google APIs or `aosp_atd` system image, which is
  pre-rooted. Run `adb root` then `adb unroot` to toggle.
- **Physical device** — Magisk is the standard rooting tool. See
  https://topjohnwu.github.io/Magisk/.

## Install frida-server

Once rooted, push the matching `frida-server` binary to the device:

```bash
# Vendored by bin/pull-tools.sh
adb push vendor/frida-server/17.10.1/frida-server-<arch> /data/local/tmp/frida-server
adb shell chmod 755 /data/local/tmp/frida-server
adb shell /data/local/tmp/frida-server &  # or run via `su` for proper root
```

The architecture must match the device (`arm`, `arm64`, `x86`, `x86_64`).
`bin/doctor.sh` detects this and warns on a mismatch.

## Disable SELinux (optional, for Frida)

On some devices, Frida's ptrace-based attach requires permissive SELinux:

```bash
adb shell su -c setenforce 0
```

This is a per-session setting; SELinux is restored on reboot.

## Troubleshooting

| Symptom                              | Cause                        | Fix                                              |
|--------------------------------------|------------------------------|--------------------------------------------------|
| `adb devices` shows `unauthorized`   | RSA fingerprint not accepted  | Accept the prompt on the device                  |
| `frida-server` exits immediately     | Architecture mismatch        | Push the correct `frida-server-<arch>` binary    |
| `error: inaccessible or not found`   | SELinux blocking ptrace      | `setenforce 0` (or use Magisk's `magiskpolicy`)  |
| `error: closed` on attach            | frida-server not running     | Re-run `adb shell /data/local/tmp/frida-server &` |
| Slow `adb push` over USB 2.0         | USB hub or cable issue       | Use a back-panel USB port; avoid hubs            |
