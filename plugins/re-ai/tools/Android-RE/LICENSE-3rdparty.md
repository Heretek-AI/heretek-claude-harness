# Third-Party Licenses

This project redistributes or links to several third-party components. Their
respective licenses are summarized below. Where a license is required to be
reproduced in full, it is included in the relevant subdirectory or referenced
here.

## Bundled / Vendored Binaries

| Component          | License        | Source                                          |
|--------------------|----------------|-------------------------------------------------|
| `apktool`          | Apache-2.0     | https://github.com/iBotPeaches/Apktool          |
| `jadx`             | Apache-2.0     | https://github.com/skylot/jadx                  |
| `uber-apk-signer`  | MIT            | https://github.com/patrickfav/uber-apk-signer   |
| `bundletool`       | Apache-2.0     | https://github.com/google/bundletool            |
| `frida-server`     | **wxWindows**  | https://github.com/frida/frida                  |
| `frida` (Python)   | **wxWindows**  | https://github.com/frida/frida                  |
| `frida-tools`      | **wxWindows**  | https://github.com/frida/frida                  |

### wxWindows Library Exception (Frida)

Frida is distributed under the wxWindows Library Licence, Version 3.1, with the
following exception: the binary `frida-server` is additionally licensed for
**personal, non-commercial use only** unless you have a commercial agreement
with the Frida maintainers. The Python client libraries (`frida`, `frida-tools`)
are full wxWindows and may be used in commercial products; only the on-device
`frida-server` binary carries the personal-use restriction. The full wxWindows
licence text is shipped in `vendor/frida-server/LICENSE.txt` after running
`bin/pull-tools.sh`.

For commercial deployment of `frida-server`, contact the Frida authors:
https://www.frida.re/contact/

## Python Dependencies (Linked, Not Redistributed)

| Package            | License        |
|--------------------|----------------|
| `androguard`       | Apache-2.0     |
| `lief`             | Apache-2.0     |
| `cryptography`     | Apache-2.0 OR BSD-3-Clause |
| `pyaxmlparser`     | Apache-2.0     |
| `pyelftools`       | Public Domain  |
| `capstone`         | BSD-3-Clause   |
| `mcp`              | MIT            |

## TypeScript Dependencies (Linked, Not Redistributed)

| Package                       | License  |
|-------------------------------|----------|
| `@modelcontextprotocol/sdk`   | MIT      |
| `adbkit`                      | MIT      |
| `zod`                         | MIT      |
| `typescript`                  | Apache-2.0 |
| `tsx`                         | MIT      |
