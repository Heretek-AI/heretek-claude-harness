---
name: java-check
description: Run Checkstyle and SpotBugs static analysis on Java code.
---

# java-check

Invoke Checkstyle and SpotBugs to inspect Java code for formatting, bug patterns, and vulnerability risks.

## When to use

Use this skill when auditing Java repositories for code quality and bug patterns.

## Steps

### Step 1: Run Maven/Gradle verification

```bash
mvn checkstyle:check spotbugs:check
```

Or for Gradle:
```bash
./gradlew checkstyleMain spotbugsMain
```

### Step 2: Parse findings

Parse XML/HTML reports generated under `target/` or `build/reports/`.

### Step 3: Summarize and exit

Group errors by file and rule. Return non-zero status if violations exist.
