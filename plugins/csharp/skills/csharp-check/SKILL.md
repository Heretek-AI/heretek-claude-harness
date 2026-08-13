---
name: csharp-check
description: Run dotnet format --verify-no-changes and dotnet build on C# / .NET solutions to enforce code style and compilation rules.
---

# csharp-check

Execute C# / .NET build verification and formatting quality gates.

## Step 1: Run Dotnet Formatting Check

```bash
dotnet format --verify-no-changes
```

## Step 2: Run Dotnet Build Verification

```bash
dotnet build
```

## Step 3: Interpret Diagnostics

Format compiler errors and Roslyn analyzer warnings into file:line diagnostic output.
