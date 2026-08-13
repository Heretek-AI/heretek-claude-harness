---
name: drizzle-migration
description: Generate + review Drizzle ORM schema migrations for the Peace-History backend
user_invocable: true
disable-model-invocation: true
---

# Drizzle Migration

Generate, inspect, and review Drizzle ORM migrations against the Peace-History backend (`backend/` workspace, Drizzle ORM + drizzle-kit, PostgreSQL).

## When to use

- Adding a new table or column
- Changing a column type, default, or nullability
- Adding/removing an index
- Reviewing a generated migration before applying

## Workflow

### 1. Generate

```bash
cd backend
npm run db:generate
```

This writes a new SQL file under `backend/drizzle/`. **Do not** edit generated SQL by hand unless you are adding a `CONCURRENTLY` index or other dialect-specific concern.

### 2. Inspect

Read the generated SQL file in full. For each statement, check:

- **Indexes** — every new foreign key column gets an index. The schema's `relations` are not auto-indexed.
- **NOT NULL** — new `NOT NULL` columns on a populated table need a default or a backfill migration first.
- **Cascade** — `onDelete: 'cascade'` only when the parent has no historical children to preserve. For event/audit tables, prefer `restrict` or `set null`.
- **Defaults** — avoid `now()` for columns that the application also writes explicitly; pick one source of truth.
- **Renames** — drizzle-kit emits `DROP` + `CREATE` for renames. If the column has data, write a manual `ALTER TABLE ... RENAME COLUMN` instead.

### 3. Antipattern cross-check

Pulled from `.claude/rules/antipatterns.md`:

- **offset pagination** — if a new query parameter accepts `?page=N&limit=M`, replace with cursor pagination (`?cursor=<id>&limit=M`) before merge.
- **n+1 query** — any new relation that loops in TypeScript and calls `.findMany()` per parent must become a single query with `with` or a join.
- **manual jwt validation** — new auth middleware must use `@fastify/jwt`, not hand-rolled token parsing.

### 4. Apply

```bash
npm run db:push    # dev only — direct schema sync
# or generate migration then apply via your migration runner
```

`db:push` is for dev. For staging/prod, generate the migration and apply it through the normal migration pipeline.

## Output

Report:

- File: `backend/drizzle/00NN_<name>.sql`
- Tables touched: [list]
- Indexes added: [list]
- Indexes needed but missing: [list with `CREATE INDEX` snippet]
- Backfill required: yes/no
- Antipattern violations: [list with file:line]
