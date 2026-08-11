---
description: Quarterly D7-bar verification — runs scripts/refresh_pins.py with GitHub credentials to flag stale catalog entries (stars, last commit, license, critical CVEs).
---

# heretek:refresh-pins

Thin wrapper around `scripts/refresh_pins.py`. The Python script handles all
the logic (checks stars, license, last commit, CVEs) and exits non-zero on
staleness. This skill is just a one-line invocation.

## Run

```bash
scripts/refresh_pins.sh                     # scripts/refresh_pins.py --github-token ${GH_TOKEN:-$(gh auth token)}
```

## Interpret status

The script prints a 4-column table: `STATUS | PLUGIN | ITEM | DETAIL`.

- `ok` — fresh, no action
- `stale_stars` / `stale_commit` / `stale_license` — re-evaluate
- `cve_alert` — **urgent**: critical CVE published; mark `rejected` immediately
- `license_drift` — upstream changed license; re-vet or replace

Exit 0 = clean. Exit 1 = some items stale (maintenance signal, not merge gate).

## Triage stale items

For each row:

1. Open the upstream repo, check current state.
2. If still good → bump `sha` + `vetting.date` in `catalog/catalog.yaml` + add an ADR line.
3. If dead → `vetting.status: rejected` + add to `catalog/rejected.md`.
4. CVE → move to `rejected.md` (D7 says no critical CVEs in 24 months).

## Don't

- Auto-create PRs (manual commit + push).
- Re-evaluate D7 criteria (that's `/heretek:catalog`).
- Modify the D7 bar itself (spec change).
