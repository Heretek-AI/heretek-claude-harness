---
name: typecheck
description: Run `tsc --noEmit` on the current TypeScript project and surface type errors. Use after modifying TypeScript source.
---

Run `tsc --noEmit --pretty false` from the project root (resolves `tsconfig.json`). Surface the first 50 lines of output. If errors are present, list each with file:line:col and the diagnostic message. Do not emit JS output; that's a separate `tsc --build` workflow.

For a fast pass on changed files only, point tsc at a specific tsconfig: `tsc --noEmit --pretty false -p path/to/tsconfig.json`.
