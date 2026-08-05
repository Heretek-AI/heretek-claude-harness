---
description: Quarterly D7-bar verification — runs scripts/refresh_pins.py with GitHub credentials to flag stale catalog entries (stars, last commit, license, critical CVEs).
---

# heretek:refresh-pins

Thin wrapper around `scripts/refresh_pins.py` for the quarterly D7-bar verification workflow. Surfaces stale catalog entries so maintainers can review and (manually) update SHAs.

## When to use

- **Quarterly** for stable items (matches the recommended cadence in `SECURITY.md`)
- **Immediately** when a critical CVE is published against a vetted upstream
- After a major upstream release (e.g., 2.0 release that the catalog might want to track)

## Steps

### Step 1: Run refresh-pins

```bash
. .venv/bin/activate
pip install -q -r requirements-dev.txt

# Use GITHUB_TOKEN env var if set, else fall back to `gh auth token` (which uses the
# local `gh` CLI's stored credentials), else fail-open with all items marked "skipped".
TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || echo)}"

python scripts/refresh_pins.py --github-token "$TOKEN"
```

If neither `GITHUB_TOKEN` nor `gh auth token` is available, the script runs in offline mode — every item is marked `skipped` with reason "no GITHUB_TOKEN; offline check skipped" (only `vetting.date` staleness is checked). Surface this to the user so they know to set up a token for a real check.

### Step 2: Interpret the output

The script prints a 4-column table:

```
STATUS          PLUGIN            ITEM               DETAIL
-----------------------------------------------------------------
ok              rust              rust-analyzer
skipped         python            ruff                no GITHUB_TOKEN; offline check skipped
stale_commit    web-frontend      lighthouse          vetting.date 2026-08-04 is older than 365 days
cve_alert       mcp-pack          context7            2 critical CVE(s)
license_drift   lsp-pack          rust-analyzer       license drifted: upstream=NOASSERTION vs catalog=MIT
```

**Statuses:**
- `ok` — fresh, no action needed
- `skipped` — offline mode (no token) or vetting-date-only check; surface to user
- `stale_stars` / `stale_commit` / `stale_license` — maintainer should re-evaluate
- `cve_alert` — **urgent**: a critical CVE was published; mark the item `rejected` immediately and find a replacement
- `license_drift` — upstream changed license; may need to re-vet or replace

Exit code 0 if all items are fresh or skipped. Exit code 1 if any item is stale (maintenance signal, not merge-gate).

### Step 3: Take action

For each stale item:

1. **Re-evaluate manually.** Open the upstream's repo, check current state.
2. **If still good** → bump `sha` + `vetting.date` in `catalog/catalog.yaml` manually. Add an entry to the item's ADR documenting the re-vetting (date + reason).
3. **If upstream is dead** → mark `vetting.status: rejected` in catalog, add to `catalog/rejected.md` with a recent-eval date.
4. **If a critical CVE was found** → consider moving the item to `catalog/rejected.md` immediately (D7 says no critical CVEs in 24 months).

### Step 4: Commit

After re-evaluation commits, push and the maintainer should run the smoke-test workflow to confirm marketplace.json is still valid.

## Acceptance criteria

- [ ] `refresh_pins.py` runs without error
- [ ] Output table is readable
- [ ] Any `cve_alert` items are triaged immediately (not deferred to next quarter)
- [ ] Stale items get a follow-up commit bumping `sha` + `vetting.date` OR moved to `rejected.md`
- [ ] If `--update-shas` is wired up (Issue #11), it can be used instead of manual edits

## Error handling

- `gh` CLI not installed → fallback to `GITHUB_TOKEN` env var; if neither, fail-open with `skipped` for all items
- `gh api` rate-limited → `refresh_pins.py` catches the exception and reports empty data; the item may show `stale_stars` (conservative fallback) — note this in the report
- `refresh_pins.py` script missing → check if a recent commit deleted it; pull latest
- venv missing → run `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`

## Out of scope

- Auto-bumping SHAs in `catalog.yaml` (tracked by Issue #11; once wired, this skill will gain an `--update` mode that calls `refresh_pins.py --update-shas`)
- Auto-creating PRs (manual commit + push is the maintainer's job)
- Re-evaluating D7-bar criteria for an item (that's `/heretek:catalog` add-item mode, not this skill)
- Modifying the D7 vetting bar itself (that's a spec change, in `docs/superpowers/specs/2026-08-03-heretek-marketplace-design.md` §7)
