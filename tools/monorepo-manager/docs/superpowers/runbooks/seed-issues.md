# seed-issues.sh — first-run and reseed runbook

This runbook is the human-side companion to `scripts/seed-issues.sh`. It walks a human with `gh` auth through the one-time setup and the daily/weekly reseed cadence.

## Prerequisites

- `gh` CLI ≥ 2.40 on your `$PATH`.
- `gh auth login` completed for the `Heretek-AI` org.
- `yq` and `jq` installed.
- Read access to the relevant seed file in `https://github.com/Heretek-AI/monorepo-manager`.

## First-time setup (one human, ~10 minutes per repo)

1. Create one GitHub Project per child repo (manual UI step, Projects #1 and #2).
2. Note the project node ID: open the project → ⋯ menu → Settings → copy the ID (format `PVT_xxxxx`).
3. In the umbrella repo, edit `seeds/llama-builds.yaml` and `seeds/heretek-manager.yaml`, replacing the `project_id: ""` field with the new ID. Commit and push.
4. From inside the child repo, run `scripts/seed-issues.sh --only-labels` to create the 21 labels (5 phase + 11 component + 5 status).
5. Run `scripts/seed-issues.sh` to file the issues. Expect `created=36 updated=0 skipped=0 failed=0` for `llama-builds`, or `created=25 updated=0 skipped=0 failed=0` for `heretek-manager` (61 total across both repos).
6. Configure the two project-board views (By Phase, By Component) per spec §7.
7. Verify by opening one issue in each repo and confirming the body has all five sections and the `seed-id` HTML comment.

## Reseed (when the seed file changes)

After a PR merges that edits `seeds/<repo>.yaml`:

1. Pull the latest umbrella commit in your local clone.
2. From inside the child repo, run `scripts/seed-issues.sh`.
3. Expect `created=0 updated=N skipped=M failed=0` where updated is the number of changed bodies.

## Offline reseed

If the umbrella is unreachable from the runner (e.g. air-gapped CI):

```bash
scripts/seed-issues.sh --seed-file /path/to/local/seeds/llama-builds.yaml
```

The seed file is the same canonical data; the script accepts any local path.

## Rollback

`seed-issues.sh` never deletes or closes issues. To roll back a bad seed run, manually close the affected issues with `gh issue close <number>` and re-run with the previous seed (or edit the seed by hand and re-run).

## Common failure modes

| symptom | cause | fix |
|---|---|---|
| `gh is not authenticated` | `gh auth login` not completed | Run `gh auth login` and retry |
| `failed to fetch seed from <url>` | Network or rate limit | Use `--seed-file /path/to/local.yaml` |
| `seed validation failed` | Seed has a structural error | Run `python -m scripts.lib.seed_loader validate <path>` to see specific failure |
| `create failed for <id>` | Repo permissions | Verify `gh auth status` shows write access to the target repo |
