---
name: ts-check
description: Run biome check or oxlint and tsc --noEmit on TypeScript/JavaScript projects to enforce type safety and linting.
---

# ts-check

Execute TypeScript/JavaScript static analysis and type checking gates.

## Step 1: Run Linter (Biome or Oxlint)

```bash
npx biome check . || npx oxlint .
```

## Step 2: Run TypeScript Compiler Type Checker

```bash
npx tsc --noEmit
```

## Step 3: Interpret Diagnostics

Format compiler type errors and linter violations into file:line diagnostic output.
