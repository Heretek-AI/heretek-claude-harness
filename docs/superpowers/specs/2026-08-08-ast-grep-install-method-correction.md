---
date: 2026-08-08
topic: ast-grep install method deviation
status: amendment
amends: 2026-08-08-v1-x-test-unblockers-design.md
---

# ADR: ast-grep install method deviation from v1.x test-unblockers spec

## Context

The original v1.x test-unblockers spec (`docs/superpowers/specs/2026-08-08-v1-x-test-unblockers-design.md`) §3.1 specified installing `ast-grep` via the official installer:

```bash
curl -fsSL https://raw.githubusercontent.com/ast-grep/install-guide/v0.39.0/install.sh | bash -s -- -y --tag v0.39.0
```

PR #101 (CI run #31263498458) failed because this URL returns 404. The `ast-grep/install-guide` repo does not have a `v0.39.0` tag, and there is no `install.sh` at the path shown. The actual install method for the project is a tarball from GitHub Releases.

SonarCloud also raised two findings on the same line:
- **BLOCKER githubactions:S8482** — `curl | bash` executes a downloaded artifact without verification.
- **MAJOR githubactions:S6506** — `curl -fsSL` does not enforce HTTPS; the `-L` flag follows redirects, which could downgrade to HTTP.

## Decision

Replaced the install step with a SHA-verified GitHub Releases binary download:

```yaml
- name: Install ast-grep (required for profile_aware e2e tests)
  env:
    AST_GREP_VERSION: "0.45.1"
    AST_GREP_SHA256: "76fb6555be6734fb5057dba8d2fb756430f374bb9e1af694cf1ce00e13238d63"
  run: |
    set -euo pipefail
    curl -fsSL --proto "=https" --tlsv1.2 \
      -o /tmp/ast-grep.zip \
      "https://github.com/ast-grep/ast-grep/releases/download/${AST_GREP_VERSION}/app-x86_64-unknown-linux-gnu.zip"
    echo "${AST_GREP_SHA256}  /tmp/ast-grep.zip" | sha256sum -c -
    mkdir -p "$HOME/.cargo/bin"
    unzip -o /tmp/ast-grep.zip -d "$HOME/.cargo/bin"
    rm /tmp/ast-grep.zip
    echo "$HOME/.cargo/bin" >> "$GITHUB_PATH"
```

**Version:** `0.45.1` (latest stable as of 2026-08-08). The original spec referenced `v0.39.0`; that version was an assumption based on cut-off knowledge of the project's D20 rollout. The actual latest stable is `0.45.1`.

**Why GitHub Releases over install-guide:**
- `install-guide` doesn't ship tagged release artifacts; the curl | bash path is unmaintained.
- GitHub Releases provides deterministic binary assets (with versioned names) that can be locked to a SHA-256.

## Why this matters

- **Auditability:** SHA-256 pinning produces a verifiable download. Any modification between release and runner is caught.
- **HTTPS enforcement:** `--proto "=https" --tlsv1.2` prevents redirect-based downgrade.
- **Belt-and-suspenders:** The existing `Verify ast-grep reachable` step (`command -v ast-grep`) catches install failures loudly.

## Consequences

- The original spec text in §3.1 is now inaccurate. This amendment is the source of truth going forward.
- Future ast-grep version bumps require updating `AST_GREP_VERSION` AND re-computing `AST_GREP_SHA256` from the new release asset.
- `smoke-test.yml` no longer installs ast-grep (removed in commit `e241eac` per the final-review fix wave). Only `validate.yml` runs the install + verify.

## Reproduction

```bash
# Compute SHA for a new version
curl -fsSL --proto "=https" \
  "https://github.com/ast-grep/ast-grep/releases/download/<VERSION>/app-x86_64-unknown-linux-gnu.zip" \
  -o /tmp/ast-grep.zip
sha256sum /tmp/ast-grep.zip
unzip -l /tmp/ast-grep.zip  # should show: ast-grep, sg
/tmp/ast-grep/ast-grep --version  # should print: ast-grep <VERSION>
```

## References

- PR #101: https://github.com/Heretek-AI/heretek-claude-harness/pull/101
- Failing CI run: https://github.com/Heretek-AI/heretek-claude-harness/actions/runs/31263498458/job/93131207074
- Fix commit: `4ee43c8` on `fix/v1.x-test-unblockers`
- SonarCloud issues: `AZ_h2ORFNUsYMSHZrF7p` (BLOCKER S8482), `AZ_h2ORFNUsYMSHZrF7q` (MAJOR S6506)
- Original spec (now superseded for §3.1): `docs/superpowers/specs/2026-08-08-v1-x-test-unblockers-design.md`
