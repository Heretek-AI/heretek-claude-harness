# Security Policy

## Reporting a Vulnerability

**Please do not open public issues for security vulnerabilities.**

Report security issues to `security@heretek-ai.example`. We will acknowledge
receipt within 48 hours and aim to issue a fix or mitigation within 14 days
for critical issues.

## Threat Model

This project analyzes *potentially malicious APKs*. The MCP servers that
ingest APK files are the primary attack surface. Mitigations:

- **`android_re_core.apk`** enforces a 500 MB max file size and 100:1
  decompression ratio (zip-bomb guard).
- **No `eval()` of APK content.** All decompilation is static text extraction.
- **Subprocess isolation.** Each external tool (apkleaks, androwarn, quark,
  objection) runs in its own venv to limit blast radius.
- **Destructive MCP tools require `confirm: bool`.** Skills declare their
  effect envelope (read-only / network / write-device) in their frontmatter
  so an agent can show the user what a workflow will do before invoking it.

## Frida Licensing Note

`frida-server` is licensed under the wxWindows Library Licence, **Version 3.1
with a personal-use restriction**. The on-device binary may not be
redistributed for commercial use without a commercial agreement with the
Frida maintainers. See `LICENSE-3rdparty.md` for the full terms. Users
deploying Android-RE commercially should source `frida-server` directly
from https://frida.re/.

## Data Handling

The triage orchestrator (`android-re-triage`) can persist intermediate
state to a local SQLite database under `~/.android-re/triage.db` or
`./.triage/`. No APK contents or findings are ever transmitted off-host.
