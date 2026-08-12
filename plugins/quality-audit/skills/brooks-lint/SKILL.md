---
name: brooks-lint
description: Evaluate codebases for code and test decay risks using the Brooks-Lint taxonomy.
---

# brooks-lint

Code quality and architectural decay auditor based on hyhmrright/brooks-lint.

## Code Decay Risks (R1 - R6)

- **R1: Cognitive Overload**: Deep nesting (>4 levels), giant functions (>100 LOC), excessive branch complexity.
- **R2: Change Propagation**: Shotgun surgery — modifying one feature requires edits across 10+ disjointed files.
- **R3: Feature Envy**: A function accesses fields of another class more than its own.
- **R4: Accidental Complexity**: Over-engineered abstractions, premature patterns, unnecessary generic wrappers.
- **R5: Hidden Coupling**: Silent temporal coupling (Function A MUST be called before Function B without type enforcement).
- **R6: Dead Code**: Unused parameters, orphan modules, unreferenced exports.

## Test Decay Risks (T1 - T6)

- **T1: Brittle Assertions**: Tests asserting exact string outputs instead of semantic state.
- **T2: Slow Test Suite**: Blocking network/DB calls in unit tests without mocks.
- **T3: Flaky Tests**: Tests relying on non-deterministic timing, random seeds, or global mutable state.
- **T4: Test Duplication**: Copy-pasted test setup blocks.
- **T5: Coverage Illusion**: High coverage numbers on empty assertion tests (`assert True`).
- **T6: Mystery Guest**: Tests dependent on external files/environment variables not defined in test fixture.

## Mandatory Reporting Format

For every finding, format output strictly as:

```markdown
### [Risk Code] Title (File:Line)
- **Symptom**: Concrete code snippet showing the defect.
- **Source**: Why the architecture allowed this defect to occur.
- **Consequence**: Operational or maintenance risk if uncorrected.
- **Remedy**: Exact diff or refactoring steps to fix it.
```
