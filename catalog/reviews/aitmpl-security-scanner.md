---
slug: aitmpl-security-scanner
date: 2026-08-04
status: rejected
---

# aitmpl.com/security/security-scanner

## What

A PreToolUse-style hook (technically registered as `PostToolUse` on `Edit|Write`) that wraps external security tools (`semgrep`, `bandit`, `gitleaks`) and a regex secret-pattern check to scan modified files for vulnerabilities and hardcoded secrets. Source: JSON snippet in `davila7/claude-code-templates` at `cli-tool/components/hooks/security/security-scanner.json`.

## Why

On first reading, this looks attractive — "scan every edit for security issues" sounds like exactly what heretek's `hooks` plugin should do. But the implementation does not fit the heretek model.

## Alternatives

Heretek's existing layering already covers this need better:

- **Layer 1 (fast gates, PreToolUse, <100ms)** — blocks obvious mistakes before the edit lands. Currently `fast_gate.py` does regex secret-pattern + lint checks inline.
- **Layer 2 (slow analyzers, `/quality-gate:run`)** — on-demand full scans with `megalinter`, `tdd-guard`, `sonarqube`. The aitmpl hook would chain semgrep/bandit on every Edit, which is exactly the kind of latency-creep Layer 1 must avoid.
- **`security` plugin skills + commands** — the security plugin ships audit skills/commands, not auto-firing hooks (D15 strict).

## Verdict

- [ ] Approved
- [x] Rejected

Reason: fails D7 source-audit (non-trivial shell pass-through to semgrep + bandit + gitleaks + ad-hoc grep), and the upstream repo carries an open HIGH-severity advisory (GHSA-79wm-x847-7cvg, CVSS 8.8) for unrelated `--studio` mode — not strictly "critical" by D7 wording but a signal that the repo ships vulnerable code paths even when the hook itself is unchanged. Additionally, the hook's design (fire on every Edit|Write) collides with D15 (hooks plugin owns all hooks) and D6 (Layer 1 must stay sub-100ms).

## Target plugin

Would target `hooks` (per D15) if approved. Not approved.

## Vetting checklist (D7)

- [x] stars ≥ 500 — **PASS** upstream `davila7/claude-code-templates` has 30,106 stars (well over threshold).
- [x] last commit ≤ 12 months — **PASS** upstream last push 2026-08-04.
- [x] OSI-approved license — **PASS** MIT license confirmed.
- [ ] source-audit pass — **FAIL** the hook shells out to three external tools (`semgrep`, `bandit`, `gitleaks`) plus a naive grep for `(password|secret|key|token)[[:space:]]*=[[:space:]]*["'][^"']{8,}`. Per D7: "shelling out to a subprocess is not" trivial. The trailing `|| true` on every chain suppresses real failures, so the hook looks like it works even when tools are missing or broken. Additionally, the inline regex is a false-positive generator (any KV-pair with 8+ chars triggers it). Verdict: **fail**.
- [ ] no critical CVEs in 24 months — **PASS-with-flag** D7 specifies "critical" (CVSS ≥ 9.0). The single open advisory is HIGH (CVSS 8.8, GHSA-79wm-x847-7cvg, unauthenticated RCE in the `--studio` mode of the same repo, patched in v1.29.4). It does not affect the hook command itself but does affect the surrounding repo; recorded here as a concern against SHA-pinning this repo for any reason.
