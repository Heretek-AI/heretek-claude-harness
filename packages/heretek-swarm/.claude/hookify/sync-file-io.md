# Hookify rule: antipattern:sync file I/O → async

- **Audit row:** 37
- **Spec:** `docs/superpowers/specs/2026-06-22-hooks-audit.md` (row 37)
- **Antipattern source:** `.claude/rules/antipatterns.md:11`
- **Hook event:** `PreToolUse` (matcher `Edit|Write|MultiEdit`)
- **Enforcement:** `.claude/hooks/pre-sync-file-io.sh` (referenced from `.claude/settings.json`)

## Rule

Synchronous Node `fs` APIs (`fs.readFileSync`, `fs.writeFileSync`, `fs.appendFileSync`,
`fs.existsSync`, `fs.statSync`, `fs.mkdirSync`, `fs.rmSync`, `fs.readdirSync`) must not
appear in app code. They block the event loop and break Fastify 5's async request model.

## Scope

Only files matching one of:

- `apps/web/src/**`
- `apps/backend/src/**`
- `web/src/**`
- `backend/src/**`

Excluded: scripts (`scripts/**`, `tools/**`), `.claude/**`, test files (`*.test.*`, `*.spec.*`),
shell scripts (`*.sh`).

## Behavior

- **Match found** → exit 2, stderr lists each hit + its async alternative, tool call blocked.
- **No match / out of scope** → exit 0, allow.

For `Write`, the file does not yet exist, so the scanner exits 0 (best-effort). The
next `Edit` re-scans the persisted content and blocks on next match. This avoids
re-parsing the entire proposed write payload and keeps the hook fast.

## Async alternatives

| Sync | Async |
|---|---|
| `fs.readFileSync(path)` | `await fs.promises.readFile(path, "utf8")` |
| `fs.writeFileSync(path, data)` | `await fs.promises.writeFile(path, data)` |
| `fs.appendFileSync(path, data)` | `await fs.promises.appendFile(path, data)` |
| `fs.existsSync(path)` | `await fs.promises.access(path)` (catch ENOENT) |
| `fs.statSync(path)` | `await fs.promises.stat(path)` |
| `fs.mkdirSync(path)` | `await fs.promises.mkdir(path, { recursive: true })` |
| `fs.rmSync(path)` | `await fs.promises.rm(path, { recursive: true, force: true })` |
| `fs.readdirSync(path)` | `await fs.promises.readdir(path)` |

## Verification

- **Blocked case:** `apps/web/src/server/foo.ts` containing `fs.readFileSync` → exit 2, block reason printed.
- **Allowed case:** `apps/web/src/server/bar.ts` with only async `fs.promises.*` → exit 0.
- **Out of scope:** `tools/rip.ts` with `fs.readFileSync` → exit 0 (tools are excluded).

## Caveats

- `Write` matches pass through (file not yet on disk) — Edit guard is the strict gate.
- False-positive risk: low. Test files and shell scripts are excluded; the regex anchors on
  `\bfs\.<name>\b` to avoid matches against `myfs.readFileSync`-style false names.
- Performance: a `cat` on Edit is cheap for source files; the rule is grep-only, no Node spawn.
