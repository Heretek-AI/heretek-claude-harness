# Changelog

All notable changes to the `heretek` Claude Code marketplace are recorded here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## v1.0.0 (2026-08-05)

### Added

- **#14** Resolved marketplace-manifest versioning decision: SHA-ride only, no marketplace-level version (see `docs/superpowers/specs/2026-08-05-marketplace-versioning-decision.md`).
- **#9** Added `"dependencies": []` field to `web-frontend` and `lsp-pack` plugin manifests for consistency.
- **#10** Added per-item ADRs for first-party self-pin items in `catalog/reviews/`.
- **#15** Added missing `plugins/rust/skills/cargo-clippy/SKILL.md` (catalog/state drift fix).
- **#21** Reviewed 3 heretek maintenance skills (`catalog`, `refresh-pins`, `merge-and-push`); review packet at `docs/superpowers/reviews/2026-08-05-heretek-maintenance-skills-review.md`.

### Fixed

- **#11** `scripts/refresh_pins.py --update-shas` now writes new SHAs back to the catalog (round-tripped via ruamel.yaml to preserve comments).
- **#16** Bumped `jsonschema`, `PyYAML`, and `pytest` to versions resolving Dependabot moderate CVEs (`jsonschema` 4.23.0 → 4.26.0; `PyYAML` 6.0.2 → 6.0.3; `pytest` 9.0.3 → 9.1.1). `ruamel.yaml` remains at 0.18.6 — its CVE bump lives on an unmerged dependabot branch.

### Deferred to v1.0.1

- **#12** Wiring `security@heretek.ai` mailbox as primary security intake is **not** part of v1.0.0. The work was deferred per maintainer direction; `SECURITY.md` continues to use the GitHub Security Advisories reporting path for v1.0.0. Tracking remains at <https://github.com/Heretek-AI/heretek-claude-harness/issues/12>.

## Unreleased

(none — every v1.0.0 entry is closed above)

[Older versions]: see git history.
