---
name: go-check
description: Run `go vet` and `golangci-lint` on a Go project and report structured findings.
---

# go-check

Invoke Go's official linter and static analyzer (`go vet` and `golangci-lint`) to inspect Go source code for correctness, performance, and style issues.

## When to use

Use this skill when auditing, reviewing, or validating a Go repository before merging or committing changes.

## Steps

### Step 1: Run Go vet & lint

```bash
go vet ./...
golangci-lint run --out-format json > /tmp/golangci-lint.json
```

If `golangci-lint` is not present, fall back to `go vet ./...`.

### Step 2: Parse findings

Read `/tmp/golangci-lint.json`. Parse issues array and group findings by file, line, and rule ID.

### Step 3: Report findings

Print a structured summary of:
- Path, line, column
- Linter rule ID (e.g. `errcheck`, `staticcheck`, `gosec`)
- Severity and remediation advice

If any error-severity issue is found, exit with status 1.
