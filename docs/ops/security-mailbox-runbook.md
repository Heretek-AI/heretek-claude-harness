# security@heretek.ai Mailbox Wiring — Runbook

> Date: 2026-08-05. Resolves #12.

## Goal

Make `security@heretek.ai` a live, monitored mailbox so SECURITY.md can
point to it as the primary intake. Replaces the GitHub Advisories-only
fallback.

## Steps

### 1. DNS records (operator: domain owner)

Add to the heretek.ai DNS zone:

```
@ TXT "v=spf1 include:_spf.google.com ~all"   ; SPF for Google Workspace
@ MX 1 aspmx.l.google.com                     ; primary
@ MX 5 alt1.aspmx.l.google.com
@ MX 5 alt2.aspmx.l.google.com
@ MX 10 alt3.aspmx.l.google.com
@ MX 10 alt4.aspmx.l.google.com
```

Verify with `dig TXT heretek.ai +short` and `dig MX heretek.ai +short`.

### 2. Google Workspace alias (operator: workspace admin)

In the Google Admin console for `heretek.ai`:

- Users → find or create `team@heretek.ai`
- Add alias `security@heretek.ai` → routes to `team@heretek.ai`
- Enable catch-all forwarding to `security@` if needed

Verify by sending a test email from a personal account; check the inbox.

### 3. GitHub repo settings (operator: repo admin)

In `Heretek-AI/heretek-claude-harness → Settings → Code security & analysis`:

- Private vulnerability reporting: ENABLED (already done per SECURITY.md)
- Under "Configure email notifications" → set "Send security alert emails to" to
  `security@heretek.ai`

### 4. Update SECURITY.md

After Steps1–3 succeed, edit `docs/SECURITY.md`:

```diff
-Please report security issues to **security@heretek.ai** (or via GitHub
-private vulnerability reporting).
+Please report security issues to **security@heretek.ai** (primary) or via
+GitHub private vulnerability reporting (secondary). The mailbox is
+monitored; we aim to acknowledge within 2 business days.
```

Remove the "(currently SECURITY.md uses GitHub Advisories)" framing from the issue body — the mailbox is now wired.

### 5. Verification

Send a test email to `security@heretek.ai`; confirm receipt within 1 hour.

## Rollback

If the alias is misconfigured, remove the `security@` alias from the
Google Admin and revert the SECURITY.md change. No destructive actions
are taken by this runbook.

## Confirmation

Once Steps1–4 succeed, comment "mailbox live" on the PR for #12.
