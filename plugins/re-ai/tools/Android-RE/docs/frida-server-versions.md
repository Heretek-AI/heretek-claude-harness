# Frida Server Versions

`frida` (the Python client) and `frida-server` (the on-device binary)
**must be the same version** for a session to attach. A version mismatch
produces an opaque protocol error from the daemon and is the #1 source
of "Frida not working" reports.

## v0.1.0 pinning

| Component        | Version  |
|------------------|----------|
| `frida`          | 17.10.1  |
| `frida-tools`    | 13.0+ (matches 17.10.x)  |
| `frida-server`   | 17.10.1  |

`bin/pull-tools.sh` downloads `frida-server-17.10.1-<arch>.xz` for all four
architectures (arm, arm64, x86, x86_64) and unpacks them into
`vendor/frida-server/17.10.1/`.

`bin/doctor.sh` checks the version of `frida-server` running on every
connected device and warns on a mismatch with the Python client.

## Upgrading Frida

When a new Frida release comes out:

1. Update the pin in `android_re_core/pyproject.toml`:
   ```toml
   "frida==17.10.1",
   "frida-tools>=13.0",
   ```
2. Update `bin/pull-tools.sh` to fetch the new server binary.
3. Update `docs/frida-server-versions.md` (this file) with the new pin.
4. Run the device integration test matrix (Phase 3+).
5. Tag a release. Do **not** ship a release with a pinned client and an
   unpinned server.

## What if the pinned version is no longer available?

Frida publishes all releases to
https://github.com/frida/frida/releases. We pin to a specific tag and
download from the matching asset URL. If the asset has been removed
(rare; only happens for yanked security releases), the user must either:

- Stay on the previous pinned version (recommended for reproducibility).
- Or manually set `FRIDA_VERSION` in their environment to a different
  pinned version that they have vendored themselves.

We do **not** fall back to "latest" because that would break
reproducibility.

## Frida licensing note

`frida-server` is licensed under the wxWindows Library Licence, **Version
3.1 with a personal-use restriction**. The on-device binary may not be
redistributed for commercial use without a commercial agreement with the
Frida maintainers. The Python client libraries (`frida`, `frida-tools`)
are full wxWindows and may be used in commercial products. See
`LICENSE-3rdparty.md` for the full terms and contact information.
