# Security

## Reporting a vulnerability

**Primary channel: GitHub Security Advisories** on this repository.

For reporters without a GitHub account, or when the issue is sensitive:
- Email: `security@heretek.ai` (PGP key pending — see v1.1 follow-up)

Please include:
- Item name (plugin / skill / MCP / LSP / etc.)
- Affected version (commit SHA)
- Reproduction steps or proof-of-concept
- Impact assessment

### Response SLA

| Phase | Target |
|---|---|
| Acknowledgement | 48 hours |
| Remediation timeline | 7 days |
| Critical CVE escalation | 24 hours |

The SLA is best-effort until a bug-bounty program is funded (see Known limitations).

## Supported versions

The heretek marketplace uses SHA-ride versioning (D11): every plugin entry's `sha` field pins the exact upstream commit. There is no "current version" or "LTS release" — each item is verified at the time of merge.

| Item state | Support status |
|---|---|
| sha pin matches the upstream commit verified within the last 90 days | Active |
| sha pin older than 90 days OR vetting.date older than 12 months | Stale — flagged by `scripts/refresh-pins.py`; maintainer should re-verify |
| Upstream deleted / archived / moved | Removed from catalog; recorded in `catalog/rejected.md` |

## Supply-chain risk model

heretek follows the D7 vetting bar:

- **Stars ≥ 500** — minimum social proof
- **Last commit ≤ 12 months** — active maintenance
- **OSI-approved license** — legal compatibility with our MIT-licensed marketplace
- **Source-audit pass** for code-executing components — human review recorded in the ADR
- **No critical CVEs in 24 months** (CVSS ≥ 9.0)

Vendored content retains its upstream license + a `NOTICE` file crediting the original authors.

## D15 strict hooks ownership

The `hooks` plugin is the **sole owner** of all hook components. No other plugin (including `security`) may declare hooks in its `components` list. The `test_no_plugin_ships_hooks_outside_hooks_plugin` invariant in `tests/test_plugin_components.py` enforces this at CI time.

If a user enables another Claude Code marketplace that includes hooks, ordering is resolved at the manifest level (strict mode, `plugin.json` is authority). The heretek `hooks` plugin's hooks will run; the other plugin's hooks will not.

## Quarterly refresh cadence

The `scripts/refresh-pins.py` tool re-verifies every catalog entry. Recommended run cadence:

- **Monthly** for high-traffic items (anything with ≥ 1k★ on GitHub)
- **Quarterly** for stable items
- **Immediately** when a critical CVE is published against a vetted upstream

The CI workflow includes a `smoke-test.yml` job that runs on every merge + nightly, plus the `validate.yml` job that asserts catalog → marketplace.json idempotency.

## Dependency transparency

Every catalog entry has:

- `upstream` — the source repo (e.g., `rust-lang/rust-analyzer`)
- `sha` — a 40-char hex pin
- `vetting.review` — a path to an ADR in `catalog/reviews/`

This makes the supply chain auditable: any user can verify exactly what code is being installed.

## Known limitations

- **First-party code in heretek itself** (the hooks plugin, the security plugin, agents, output styles) is reviewed by the heretek maintainers but does not have the same third-party vetting as catalog items. Trust model: heretek-AI maintainers are responsible for the first-party content; downstream users trust them by installing the marketplace.
- **Vendored content is not re-built from source.** A `sha` pin means we trust the upstream's release artifacts as-built. If you need reproducible builds, fork the vendored repo and pin to your own builds.
- **No bug-bounty program.** Vulnerability reports are triaged on a best-effort basis; SLA is best-effort, not contractually guaranteed.
