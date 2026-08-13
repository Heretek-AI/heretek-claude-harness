# shadcn/ui + Radix primitives spike — Phase 2B.2

## Purpose

Validate that **shadcn/ui** (MIT, ~76k stars) — the "copy-in" component
library built on top of **Radix UI primitives** — is the integration
target for the 7+ hand-rolled UI primitive files the plan calls
out for replacement.

## shadcn/ui is unusual

shadcn/ui is **not a npm package**. It is a CLI tool that copies
component source files into your project (`components/ui/button.tsx`,
`components/ui/dialog.tsx`, etc.). You then customize them freely.
This is intentional — the project maintains a one-line dependency
on each Radix primitive but the React components themselves are
your code.

This is a **deliberate counter to vendor lock-in**: the components
in your repo are 100% your code, and the CLI can be re-run to
update them. Many projects find this a feature rather than a bug.

## Candidate files for cutover (~3,000 LOC combined)

Per the plan:

| File | LOC | Replaced by |
|------|-----|-------------|
| `components/UI/Toast.tsx` | 176 | shadcn/ui `<Toaster>` + `sonner` |
| `components/UI/DataTable.tsx` | 296 | shadcn/ui `<DataTable>` (TanStack Table wrapper) |
| `components/UI/ErrorBoundary.tsx` | 118 | `react-error-boundary` |
| `components/UI/ComponentErrorBoundary.tsx` | 253 | `react-error-boundary` |
| `components/UI/StatusBadge.tsx` | 112 | shadcn/ui `<Badge>` |
| `components/UI/EmptyState.tsx` | 118 | shadcn/ui `<EmptyState>` pattern |
| `components/UI/MetricCard.tsx` | 170 | Tremor `<Metric>` / shadcn `<Card>` |
| `components/UI/LoadingSpinner.tsx` | 106 | shadcn `<Skeleton>` / Radix |
| `Dashboard/Layout.tsx` (~150 of 194) | 150 | shadcn `<Sidebar>` v0.6 |

Plus per-page modal/drawer/tab/dropdown/select reimplementations
scattered across `Agents/`, `Settings/`, `Workflow/` folders —
another ~1,500 LOC.

## Migration pattern

The shadcn/ui CLI is configured once with `components.json`:

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.js",
    "css": "src/index.css",
    "baseColor": "gray",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

Then each component is added with `pnpm dlx shadcn@latest add <name>`,
which copies the source into `src/components/ui/`. The 7+ files
above are deleted; their callers import the new shadcn components
from the same path.

## Kill criteria

- If shadcn/ui does not cover a UI primitive we need (e.g. a
  custom gauge for Consciousness metrics), keep that primitive
  in-house.

## Result

- shadcn/ui is a well-established pattern with extensive
  community support; 76k GitHub stars.
- It is dependency-light: each Radix primitive is a small package
  with no transitive burden.
- The migration is mechanical: most files are 1-1 replacements
  with the new shadcn component.

## Migration PR plan

1. `pnpm dlx shadcn@latest init` (configure the project).
2. `pnpm dlx shadcn@latest add button card dialog drawer tabs select
   switch badge skeleton sheet dropdown-menu popover tooltip` (one
   command, ~15 components).
3. Update each of the 9 candidate files to import the new shadcn
   components.
4. Delete the 9 candidate files.
5. `pnpm dlx shadcn@latest add data-table sonner` for the
   `DataTable` and `Toaster` (specialized components).
6. Delete the 2 special files.

**Net:** ~3,000 LOC reduction + Radix accessibility primitives for
free (keyboard nav, ARIA roles, focus management) + 100% code
ownership (the shadcn components in your repo are your code, not
an opaque dependency).
