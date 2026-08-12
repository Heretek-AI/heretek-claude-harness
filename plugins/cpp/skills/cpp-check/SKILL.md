---
name: cpp-check
description: Run `clang-tidy` and `cppcheck` on C/C++ source code to catch memory leaks, undefined behavior, and style defects.
---

# cpp-check

Invoke `clang-tidy` and `cppcheck` to perform static analysis on C/C++ codebases.

## When to use

Use this skill when auditing C or C++ source files for memory safety, pointer bounds, null pointer dereferences, and formatting compliance.

## Steps

### Step 1: Run static analyzers

```bash
clang-tidy --quiet -p build/ src/*.cpp
cppcheck --enable=warning,style,performance,portability --xml --xml-version=2 src/ 2> /tmp/cppcheck.xml
```

### Step 2: Parse and format output

Parse `/tmp/cppcheck.xml` and `clang-tidy` stdout for file, line, severity, and rule warnings.

### Step 3: Group by file and report

Print findings per file. Return exit status 1 if any high-severity error or memory safety vulnerability is found.
