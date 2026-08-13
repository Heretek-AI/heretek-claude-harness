# Code Extraction Pattern for Oversized Actor Files

This document describes the extraction pattern established during the sentinel.py refactoring (M006-S03), providing a replicable process for reducing file sizes below 500 lines.

## Pattern Overview

The extraction pattern transforms monolithic actor files into modular packages by:
1. **Extracting type definitions** to `types.py`
2. **Extracting pure helper functions** to `helpers.py`
3. **Refactoring the main class** to inherit behavior from a `HelpersMixin`
4. **Maintaining backwards compatibility** via `__init__.py` re-exports

## Step-by-Step Process

### Step 1: Audit Structure

Before extracting anything, audit the source file to identify:

- **Top-level classes**: Main class and any mixins
- **Method counts**: Group methods by category (validation, reporting, utilities)
- **Imports**: Identify external dependencies and cross-module imports
- **Dependencies**: What other actors/modules does this file import from

**Audit checklist:**
```python
# Count lines of each section
- Class definitions
- Method definitions
- Import statements
- Docstrings
- Constants/Configuration
```

### Step 2: Identify Extraction Candidates

#### Types → `types.py`

Extract standalone types that don't depend on instance state:

- [x] **Enums** (StrEnum classes)
- [x] **Dataclasses** (immutable data containers)
- [x] **Type aliases** (complex type definitions)
- [ ] Nested classes that don't reference outer class state

**Example from sentinel.py:**
```python
# types.py
class SafetyLevel(StrEnum):
    SAFE = "safe"
    LOW_RISK = "low_risk"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    CRITICAL = "critical"

@dataclass
class SafetyViolation:
    violation_id: str
    violation_type: ViolationType
    severity: SafetyLevel
    content_hash: str
    description: str
    timestamp: datetime
```

#### Pure Helpers → `helpers.py`

Extract methods that:
- [x] Don't require `self` state (or can work with passed parameters)
- [x] Are stateless or can operate on passed data
- [x] Are used by the main class but could be reused elsewhere
- [x] Have clear input/output contracts

**Pattern for helpers:**
```python
class SentinelHelpers:
    """Helper methods for Sentinel operations."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize and forward MRO chain (cooperative inheritance)."""
        super().__init__(*args, **kwargs)

    def _helper_method(self, content: str) -> list[dict]:
        """Document the method purpose."""
        # Implementation
        pass

# Also provide standalone functions for independent use
def check_patterns(content: str, patterns: list[str] | None = None) -> list[dict]:
    """Standalone version for use without a class instance."""
    patterns = patterns or SentinelHelpers.DEFAULT_PATTERNS
    # Implementation
    pass
```

**Key pattern insight:** Use `super().__init__(*args, **kwargs)` for cooperative multiple inheritance.

### Step 3: Create Submodule Files

Create the following structure:

```
actor_name/
├── __init__.py       # Main exports with backwards compat
├── types.py          # Enums and dataclasses
├── helpers.py        # Helper methods and mixin
└── agent.py          # Main class (renamed from original)
```

**File creation order:**
1. `types.py` first (no dependencies on other modules)
2. `helpers.py` (depends on types.py)
3. `agent.py` (depends on types.py and helpers.py)
4. `__init__.py` (re-exports from all)

### Step 4: Update Imports in Main File

**Before (original sentinel.py):**
```python
from heretek_swarm.actors.sentinel import SentinelAgent, SafetyLevel
```

**After (sentinel/agent.py):**
```python
from heretek_swarm.actors.sentinel.helpers import SentinelHelpers
from heretek_swarm.actors.sentinel.types import (
    SafetyLevel,
    SafetyViolation,
    ViolationType,
)
```

**Main class inheritance:**
```python
class SentinelAgent(
    HealthReportingMixin,
    ValidationMixin,
    SentinelHelpers,  # Extracted mixin
    AgentActor,
):
    pass
```

### Step 5: Update `__init__.py` Re-exports

```python
# __init__.py
from heretek_swarm.actors.sentinel.agent import SentinelAgent
from heretek_swarm.actors.sentinel.types import (
    SafetyLevel,
    SafetyViolation,
    ViolationType,
)
from heretek_swarm.actors.sentinel.helpers import (
    SentinelHelpers,
    check_patterns,
)

__all__ = [
    "SentinelAgent",
    "SafetyLevel",
    "SafetyViolation",
    "ViolationType",
    "SentinelHelpers",
    "check_patterns",
]
```

### Step 6: Verify Backwards Compatibility

**Old import paths must continue to work:**
```python
# These must all still work:
from heretek_swarm.actors.sentinel import SentinelAgent
from heretek_swarm.actors.sentinel import SafetyLevel, ViolationType
from heretek_swarm.actors.sentinel import SentinelHelpers
```

**Run regression tests:**
```bash
pytest tests/ -k sentinel
```

## Extraction Complexity Guide

| Complexity | Characteristics | Action |
|------------|-----------------|--------|
| **Low** | - Pure utility functions<br>- No state dependencies<br>- Standalone types | Direct extraction to `helpers.py` and `types.py` |
| **Medium** | - Some state dependencies<br>- Complex initialization<br>- Multiple method categories | Use mixin pattern, extract cleanly |
| **High** | - Heavy state coupling<br>- Complex inheritance<br>- Cross-cutting concerns | Consider partial extraction, incremental refactor |

## Remaining 11 Oversized Files

### Priority Order for Extraction

| # | File | Lines | Recommended Extraction | Complexity |
|---|------|-------|----------------------|------------|
| 1 | sentinel_prime.py | 1733 | `types.py` (enums for anomaly types, response statuses) + `handlers.py` (request handlers) | **High** |
| 2 | chronos.py | 1625 | `types.py` (temporal types, cycle definitions) + `scheduler.py` (scheduling logic) | **High** |
| 3 | nexus.py | 1546 | `types.py` (connection states, message types) + `routing.py` (routing helpers) | **Medium** |
| 4 | perceiver_plus.py | 1516 | `types.py` (perception types) + `filters.py` (filtering helpers) | **Medium** |
| 5 | examiner.py | 1348 | `types.py` (examiner enums) + `analysis.py` (analysis helpers) | **Medium** |
| 6 | habit_forge.py | 1317 | `types.py` (habit/streak types) + `tracking.py` (tracking helpers) | **Low** |
| 7 | explorer.py | 1317 | `types.py` (exploration types) + `pathfinding.py` (navigation helpers) | **Low** |
| 8 | coordinator.py | 1273 | `types.py` (coordination enums) + `strategies.py` (coordination strategies) | **Medium** |
| 9 | prism.py | 1268 | `types.py` (transformation types) + `transforms.py` (transformation functions) | **Low** |
| 10 | dreamer.py | 1187 | `types.py` (dream/state types) + `generators.py` (generation helpers) | **Low** |
| 11 | triad.py | 1161 | `types.py` (triad component types) + `balancing.py` (balancing algorithms) | **Low** |

### Per-File Recommendations

#### 1. sentinel_prime.py (1733 lines) - HIGH COMPLEXITY
**Why:** Sentinel-Prime has complex SAFE-01 integration, immune response building, and anomaly handling.

**Recommended extraction strategy:**
1. Extract all anomaly-related enums to `sentinel_prime/types.py`
2. Extract immune response building logic to `sentinel_prime/immune.py`
3. Extract response handlers to `sentinel_prime/handlers.py`
4. Extract baseline management to `sentinel_prime/baseline.py`

#### 2. chronos.py (1625 lines) - HIGH COMPLEXITY
**Why:** Time-based scheduling with complex cycle management and event handling.

**Recommended extraction strategy:**
1. Extract temporal types to `chronos/types.py`
2. Extract cycle management to `chronos/cycles.py`
3. Extract event scheduling to `chronos/scheduler.py`
4. Extract time utilities to `chronos/utils.py`

#### 3. nexus.py (1546 lines) - MEDIUM COMPLEXITY
**Why:** Connection management and message routing, moderately complex state.

**Recommended extraction strategy:**
1. Extract connection state types to `nexus/types.py`
2. Extract routing logic to `nexus/routing.py`
3. Extract connection pool management to `nexus/pool.py`

#### 4. perceiver_plus.py (1516 lines) - MEDIUM COMPLEXITY
**Why:** Extended perception with multiple input channels, moderate complexity.

**Recommended extraction strategy:**
1. Extract perception types to `perceiver_plus/types.py`
2. Extract filtering logic to `perceiver_plus/filters.py`
3. Extract channel management to `perceiver_plus/channels.py`

#### 5. examiner.py (1348 lines) - MEDIUM COMPLEXITY
**Why:** Analysis and examination logic, moderately complex.

**Recommended extraction strategy:**
1. Extract examination types to `examiner/types.py`
2. Extract analysis helpers to `examiner/analysis.py`
3. Extract evaluation logic to `examiner/evaluation.py`

#### 6. habit_forge.py (1317 lines) - LOW COMPLEXITY
**Why:** Habit tracking with clear, separable concerns.

**Recommended extraction strategy:**
1. Extract habit/streak types to `habit_forge/types.py`
2. Extract tracking helpers to `habit_forge/tracking.py`
3. Extract streak calculations to `habit_forge/streaks.py`

#### 7. explorer.py (1317 lines) - LOW COMPLEXITY
**Why:** Exploration with clear pathfinding algorithms.

**Recommended extraction strategy:**
1. Extract exploration types to `explorer/types.py`
2. Extract pathfinding to `explorer/pathfinding.py`
3. Extract navigation to `explorer/navigation.py`

#### 8. coordinator.py (1273 lines) - MEDIUM COMPLEXITY
**Why:** Multi-agent coordination with complex strategies.

**Recommended extraction strategy:**
1. Extract coordination types to `coordinator/types.py`
2. Extract strategies to `coordinator/strategies.py`
3. Extract synchronization logic to `coordinator/sync.py`

#### 9. prism.py (1268 lines) - LOW COMPLEXITY
**Why:** Transformation logic with clear, separable functions.

**Recommended extraction strategy:**
1. Extract transformation types to `prism/types.py`
2. Extract transform functions to `prism/transforms.py`
3. Extract pipeline helpers to `prism/pipeline.py`

#### 10. dreamer.py (1187 lines) - LOW COMPLEXITY
**Why:** Dream/state generation, clear algorithmic separation.

**Recommended extraction strategy:**
1. Extract dream state types to `dreamer/types.py`
2. Extract generators to `dreamer/generators.py`
3. Extract state management to `dreamer/states.py`

#### 11. triad.py (1161 lines) - LOW COMPLEXITY
**Why:** Three-component balancing, straightforward extraction.

**Recommended extraction strategy:**
1. Extract component types to `triad/types.py`
2. Extract balancing algorithms to `triad/balancing.py`
3. Extract component management to `triad/components.py`

## Success Criteria

After extraction, each module should:
- [ ] Have each submodule under 500 lines
- [ ] Maintain all original functionality
- [ ] Pass all existing tests
- [ ] Provide backwards-compatible imports
- [ ] Have clear docstrings for each module
- [ ] Export types and helpers from `__init__.py`

## Key Decisions from sentinel.py Extraction

1. **Cooperative Inheritance**: The mixin's `__init__` must call `super().__init__(*args, **kwargs)` to work correctly in Python's MRO.

2. **Dual Interface**: Provide both a mixin class (for class integration) AND standalone functions (for independent use).

3. **Backwards Compatibility**: Always update `__init__.py` to re-export from the new locations, preserving old import paths.

4. **Type-First Extraction**: Extract types before helpers since helpers often depend on types.

5. **Instance State Access**: Helper methods that need instance state should reference `self._state` attributes, matching the pattern used in the original class.

---

*Pattern established during M006-S03 sentinel.py refactoring. Document version 1.0.*
