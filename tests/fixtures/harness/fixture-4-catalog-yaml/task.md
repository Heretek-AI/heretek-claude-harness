# Register a new plugin in catalog/catalog.yaml

Add a new top-level plugin entry to the `plugins:` list in
`catalog/catalog.yaml` with these fields:

- `name`: `fixture-demo-plugin`
- `category`: `task`
- `tags`: `[fixture, demo]`
- `source`: `{ type: relative, path: fixture-demo-plugin }`
- `components`: `[skills]`
- `items`: a single skill item with id `fixture-skill`, upstream
  `local/fixture-skill`, sha `0123456789abcdef0123456789abcdef01234567`,
  license `MIT`, and a vetting block with `status: approved`,
  `date: 2026-08-11`, `stars: 0`, `last_commit: 2026-08-11`,
  `cve_scan: 2026-08-11`, `review: reviews/fixture-skill.md`.

The entry must be appended to the existing `plugins:` list — do not
reorder existing entries, do not touch other plugins.
