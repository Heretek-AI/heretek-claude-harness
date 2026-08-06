# Security Policy

## Reporting a vulnerability

Please report security issues to **security@heretek.ai** (primary) or via
GitHub private vulnerability reporting (secondary). The mailbox is
monitored; we aim to acknowledge within 2 business days.

Do not file a public issue.

## Supply-chain reporting

For issues with a third-party item bundled into a heretek plugin (e.g., a
maintainer account takeover, malicious commit, or license drift on an
already-pinned SHA):

1. File an issue at <https://github.com/Heretek-AI/heretek-claude-harness/issues/new>
   with the `security-scan` label.
2. The daily `security-scan.yml` cron will detect the next upstream
   release and open a draft PR to bump the SHA — but for an active
   compromise, you can manually invoke the scan via
   `Actions → security-scan (daily) → Run workflow`.

## Hardening guarantees

- **D11 SHA-ride**: every third-party item is pinned to a 40-char commit
  SHA. Drift between vetting cycles is impossible without a maintainer
  action.
- **D20 Action-pinning**: every GitHub Action used in our workflows is
  pinned to a commit SHA, not a tag. Defends against TeamPCP-style
  Action compromises (Trivy, May 2026).
- **D22 ≥2 scanner vendors** per kind (where third-party scanners
  meaningfully apply). Scanners are imperfect; their output is a merge
  blocker, not a ground truth — a maintainer with context can override
  via PR comment + second reviewer (CODEOWNERS).
