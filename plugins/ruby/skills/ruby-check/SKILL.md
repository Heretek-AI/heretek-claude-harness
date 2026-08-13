---
name: ruby-check
description: Run rubocop and solargraph verification on Ruby codebases to enforce code style and type safety.
---

# ruby-check

Execute Ruby static analysis and linter quality gates.

## Step 1: Run RuboCop Linter

```bash
bundle exec rubocop || rubocop
```

## Step 2: Interpret Diagnostics

Format RuboCop cop offenses and syntax errors into file:line diagnostic output.
