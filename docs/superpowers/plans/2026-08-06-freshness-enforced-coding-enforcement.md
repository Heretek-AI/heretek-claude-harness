# Freshness-enforced Coding — Enforcement Plan (Plan C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the enforcement layer — model-card profile catalog (#44), lookup-gate hook (#45), freshness tokens system (#46). Adjusts enforcement strictness per model class, mandates doc lookup for tracked libraries, injects freshness tokens into agent prompts. Builds on Plan A's foundation and Plan B's detection layer.

**Architecture:** Per-model enforcement profiles live at `catalog/model_profiles/<model-id>.yaml` and define which patterns are warn-only vs ask-blocking, which libraries trigger mandatory lookup, and which model-card freshness tokens get injected. The lookup-gate (`scripts/lookup_gate.py`) is a D15 hook that emits a warning if an Edit touches a tracked library but no Context7/freshness-index consult happened in the prior N turns. The freshness-tokens system (`scripts/freshness_tokens.py`) builds a token cache at session start and renders `(lib, ver, ttl)` blocks injected into agent prompts via the hooks plugin install path.

**Tech Stack:** Python 3.10+, PyYAML 6.0.3, ruamel.yaml 0.18.6, pytest 9.1.1. No new runtime deps.

## Global Constraints

Same as Plans A and B. Key constraints for Plan C:

- **D5 / D7 / D11 / D15** — all still apply.
- **Edit-time blocking hook latency:** <100ms p95; lookup-gate is async-with-warning per spec §2.
- **Profile-as-code:** profiles are YAML in the repo, versioned, reviewable. Per spec §3.
- **Mandatory-lookup opt-in:** profiles declare which libraries trigger it; default off for frontier models, default on for smaller models.

## Prerequisite

Plans A and B must be complete: `catalog/freshness/*.yaml`, `scripts/stale_dep_intercept.py`, `scripts/scanners/forbidden_pattern_scanner.py`, `scripts/scanners/ast_grep_scanner.py`, `scripts/drift_detector.py` all exist and are wired in `plugins/hooks/hooks/hooks.json`.

---

## File Structure (Plan C)

**New files:**
- `catalog/model_profiles/__init__.py`
- `catalog/model_profiles/qwen3.6-27b.yaml`
- `catalog/model_profiles/deepseek-v3.yaml`
- `catalog/model_profiles/claude-opus-4.yaml`
- `catalog/model_profiles/gemini-2.5.yaml`
- `scripts/lookup_gate.py`
- `scripts/freshness_tokens.py`
- `scripts/model_profile_loader.py`
- `tests/enforcement/__init__.py`
- `tests/enforcement/conftest.py`
- `tests/enforcement/test_model_profile_loader.py`
- `tests/enforcement/test_lookup_gate.py`
- `tests/enforcement/test_freshness_tokens.py`
- `tests/enforcement/fixtures/qwen_profile.yaml`
- `tests/enforcement/fixtures/deepseek_profile.yaml`

**Modified files:**
- `plugins/hooks/hooks/hooks.json` — register lookup_gate (D15, async)
- `plugins/hooks/install.sh` — call freshness_tokens.render() at install
- `scripts/scanners/forbidden_pattern_scanner.py` — read profile to decide warn vs ask

---

### Task 1: Author initial model profiles (#44 — part 1)

**Files:**
- Create: `catalog/model_profiles/qwen3.6-27b.yaml`
- Create: `catalog/model_profiles/deepseek-v3.yaml`
- Create: `catalog/model_profiles/claude-opus-4.yaml`
- Create: `catalog/model_profiles/gemini-2.5.yaml`
- Create: `catalog/model_profiles/__init__.py`

**Interfaces:**
- Consumes: research on model classes (Qwen3.6 27B empirical studies, deepseek specs, Claude/Gemini model cards)
- Produces: 4 YAML profile files + a marker init

- [ ] **Step 1: Create the directory and marker**

Run:
```bash
mkdir -p catalog/model_profiles
touch catalog/model_profiles/__init__.py
```

- [ ] **Step 2: Write Qwen profile (smallest model — strictest profile)**

File: `catalog/model_profiles/qwen3.6-27b.yaml`

```yaml
# Model profile for Qwen3.6 27B (local LLM class).
# Strictest profile: most patterns ask-blocking, mandatory lookup on more libs,
# fastest freshness-token TTL (24h).
version: 1
model_id: qwen3.6-27b
model_class: local-27b
notes: >
  Smallest tested model. Empirically produces the most deprecated-API output
  (per Phase 1 #38 eval harness baseline). Strictest enforcement applied.

enforcement:
  # Patterns promoted from warn → ask based on this profile
  promote_to_block:
    - py-yaml-load-without-loader
    - py-os-popen
    - js-var-declaration
  # Patterns demoted from error → warn for this profile (none for Qwen)
  demote_to_warn: []

# Libraries that require mandatory freshness lookup before any Edit
mandatory_lookup:
  - pyyaml
  - jsonschema
  - requests
  - ruamel-yaml
  - pytest
  - ruff

# Freshness-token TTL — shorter for weaker models (data goes stale faster relative to recall)
freshness_token_ttl_hours: 24

# Drift-detector sensitivity multiplier (1.0 = baseline, higher = more sensitive)
drift_sensitivity: 1.5
```

- [ ] **Step 3: Write deepseek profile (frontier-class — moderate strictness)**

File: `catalog/model_profiles/deepseek-v3.yaml`

```yaml
# Model profile for deepseek-v3 (frontier class).
# Moderate enforcement: fewer ask-promotions, mandatory lookup only on
# rapidly-changing libraries.
version: 1
model_id: deepseek-v3
model_class: frontier
notes: >
  Frontier-class model. Empirically strong at avoiding deprecated APIs.
  Default-warn enforcement; mandatory lookup only on fast-moving libs.

enforcement:
  promote_to_block: []
  demote_to_warn:
    - js-var-declaration  # acceptable in legacy code

mandatory_lookup:
  - requests  # security-relevant
  - pytest   # fast-moving

freshness_token_ttl_hours: 168  # 1 week

drift_sensitivity: 1.0  # baseline
```

- [ ] **Step 4: Write Claude Opus profile (frontier, less strict)**

File: `catalog/model_profiles/claude-opus-4.yaml`

```yaml
# Model profile for Claude Opus 4.x.
# Lightest enforcement: trust model judgment; mandatory lookup off by default.
version: 1
model_id: claude-opus-4
model_class: frontier
notes: >
  Strongest tested model. Empirically near-zero deprecated-API output
  on the Phase 1 eval set. Trust the model; minimal enforcement.

enforcement:
  promote_to_block: []
  demote_to_warn:
    - py-yaml-load-without-loader
    - py-os-popen
    - js-var-declaration

mandatory_lookup: []  # off by default; user can opt in per-project

freshness_token_ttl_hours: 720  # 30 days

drift_sensitivity: 0.7
```

- [ ] **Step 5: Write Gemini profile (frontier, parallel to Claude)**

File: `catalog/model_profiles/gemini-2.5.yaml`

```yaml
# Model profile for Gemini 2.5.
# Similar to Claude profile; the two are interchangeable for most cases.
version: 1
model_id: gemini-2.5
model_class: frontier
notes: >
  Frontier-class model, comparable to Claude Opus on the Phase 1 eval.
  Note: Google ships Gemini API Docs MCP (see research report); profiles
  can opt into MCP-driven lookup via mandatory_lookup.

enforcement:
  promote_to_block: []
  demote_to_warn:
    - py-yaml-load-without-loader
    - py-os-popen
    - js-var-declaration

mandatory_lookup:
  - pyyaml  # Google's docs MCP covers it natively

freshness_token_ttl_htl_hours: 720

drift_sensitivity: 0.7
```

Wait — Step 5 has a typo: `freshness_token_ttl_htl_hours` is wrong. Should be `freshness_token_ttl_hours`. Fix in implementation.

- [ ] **Step 6: Fix the typo**

The Gemini profile as written in Step 5 has a typo: `freshness_token_ttl_htl_hours` → fix to `freshness_token_ttl_hours: 720`.

- [ ] **Step 7: Verify all 4 profiles parse**

Run:
```bash
for f in catalog/model_profiles/*.yaml; do
  python -c "import yaml; yaml.safe_load(open('$f')); print('OK', '$f')"
done
```

Expected: 4 lines of `OK ...yaml`

- [ ] **Step 8: Commit**

```bash
git add catalog/model_profiles/
git commit -m "feat(profiles): #44 model-card profiles for 4 model classes"
```

---

### Task 2: Ship #44 — Model profile loader + scanner integration

**Files:**
- Create: `scripts/model_profile_loader.py`
- Modify: `scripts/scanners/forbidden_pattern_scanner.py` (read profile)
- Create: `tests/enforcement/test_model_profile_loader.py`

**Interfaces:**
- Consumes: `catalog/model_profiles/<model-id>.yaml` + env var `HERETEK_ACTIVE_MODEL` (set by harness)
- Produces: a Python API `load_profile(model_id) -> dict` + scanner integration that promotes/demotes severities per profile

- [ ] **Step 1: Write the failing test**

File: `tests/enforcement/test_model_profile_loader.py`

```python
"""Tests for model_profile_loader.py and scanner integration."""
import pytest
from pathlib import Path

from scripts.model_profile_loader import (
    load_profile,
    list_known_profiles,
    resolve_active_model_id,
    apply_profile_to_pattern,
)


def test_load_known_profile():
    """#44: loader reads a known profile by ID."""
    profile = load_profile("qwen3.6-27b")
    assert profile["model_id"] == "qwen3.6-27b"
    assert "py-yaml-load-without-loader" in profile["enforcement"]["promote_to_block"]


def test_load_unknown_profile_raises():
    """#44: loader raises on unknown profile ID."""
    with pytest.raises(FileNotFoundError):
        load_profile("nonexistent-model-xyz")


def test_list_known_profiles_includes_all_four():
    """#44: list_known_profiles returns the 4 initial models."""
    profiles = list_known_profiles()
    assert {"qwen3.6-27b", "deepseek-v3", "claude-opus-4", "gemini-2.5"} <= set(profiles)


def test_resolve_active_model_from_env(monkeypatch):
    """#44: env var HERETEK_ACTIVE_MODEL resolves the active profile."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "deepseek-v3")
    assert resolve_active_model_id() == "deepseek-v3"


def test_resolve_active_model_default(monkeypatch):
    """#44: missing env var returns the 'claude-opus-4' default."""
    monkeypatch.delenv("HERETEK_ACTIVE_MODEL", raising=False)
    assert resolve_active_model_id() == "claude-opus-4"


def test_apply_profile_promotes_pattern_severity():
    """#44: profile.promote_to_block upgrades pattern severity from warn → error."""
    profile = load_profile("qwen3.6-27b")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "warn"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "error"


def test_apply_profile_demotes_pattern_severity():
    """#44: profile.demote_to_warn downgrades pattern severity from error → warn."""
    profile = load_profile("claude-opus-4")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "warn"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "warn"  # no change for already-warn


    profile = load_profile("claude-opus-4")
    pattern = {"id": "py-yaml-load-without-loader", "severity": "error"}
    applied = apply_profile_to_pattern(pattern, profile)
    assert applied["severity"] == "warn"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/enforcement/test_model_profile_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts'`

- [ ] **Step 3: Implement the loader**

File: `scripts/model_profile_loader.py`

```python
"""Model profile loader (#44).

Loads per-model enforcement profiles from `catalog/model_profiles/<model-id>.yaml`
and applies them to pattern definitions (promote/demote severities).

Active model is resolved from env var HERETEK_ACTIVE_MODEL, defaulting to
'claude-opus-4' (the lightest enforcement profile).
"""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROFILES_DIR = Path(__file__).resolve().parent.parent / "catalog" / "model_profiles"
DEFAULT_MODEL_ID = "claude-opus-4"


def list_known_profiles() -> list[str]:
    """Return IDs of all known model profiles."""
    return sorted(p.stem for p in PROFILES_DIR.glob("*.yaml"))


def resolve_active_model_id() -> str:
    """Resolve the active model ID from env var HERETEK_ACTIVE_MODEL."""
    return os.environ.get("HERETEK_ACTIVE_MODEL", DEFAULT_MODEL_ID)


def load_profile(model_id: str) -> dict:
    """Load a profile by ID. Raises FileNotFoundError if unknown."""
    path = PROFILES_DIR / f"{model_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No profile for model {model_id!r}")
    return yaml.safe_load(path.read_text())


def apply_profile_to_pattern(pattern: dict, profile: dict) -> dict:
    """Apply a profile's enforcement rules to a single pattern definition.

    Promotes warn → error for IDs in profile.enforcement.promote_to_block.
    Demotes error → warn for IDs in profile.enforcement.demote_to_warn.
    Other severities are unchanged.
    """
    pid = pattern["id"]
    severity = pattern["severity"]
    enforcement = profile.get("enforcement", {})

    if pid in enforcement.get("promote_to_block", []) and severity == "warn":
        severity = "error"
    if pid in enforcement.get("demote_to_warn", []) and severity == "error":
        severity = "warn"

    return {**pattern, "severity": severity}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `pytest tests/enforcement/test_model_profile_loader.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Modify `scripts/scanners/forbidden_pattern_scanner.py` to read profile**

Add at top of the file (after existing imports):

```python
import os
from scripts.model_profile_loader import load_profile, resolve_active_model_id, apply_profile_to_pattern
```

Modify the `_load_catalog` function (or the loop in `_scan`) to apply the active profile:

```python
def _scan(file_path: str, content: str) -> list[str]:
    ext = Path(file_path).suffix
    lang = EXT_TO_LANG.get(ext)
    if not lang:
        return []

    ast_grep = shutil.which("ast-grep")
    if not ast_grep:
        return []

    try:
        profile = load_profile(resolve_active_model_id())
    except FileNotFoundError:
        profile = None

    patterns = [p for p in _load_catalog() if p["language"] == lang]
    if profile is not None:
        patterns = [apply_profile_to_pattern(p, profile) for p in patterns]

    warnings = []
    for pattern_def in patterns:
        result = subprocess.run(
            [ast_grep, "scan", "--pattern", pattern_def["pattern"], "--lang", lang, "-"],
            input=content, capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            severity_marker = "🚫" if pattern_def["severity"] == "error" else "⚠️"
            warnings.append(
                f"{severity_marker} [{pattern_def['id']}] {pattern_def['reason']} "
                f"Replacement: {pattern_def['replacement']}"
            )

    return warnings
```

- [ ] **Step 6: Verify the scanner still passes its existing tests**

Run: `pytest tests/detection/test_forbidden_pattern_scanner.py -v`
Expected: 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/model_profile_loader.py tests/enforcement/test_model_profile_loader.py
git add scripts/scanners/forbidden_pattern_scanner.py
git commit -m "feat(profiles): #44 model profile loader + scanner integration"
```

---

### Task 3: Ship #45 — Lookup-gate hook

**Files:**
- Create: `scripts/lookup_gate.py`
- Modify: `plugins/hooks/hooks/hooks.json` (register lookup_gate)
- Create: `tests/enforcement/test_lookup_gate.py`

**Interfaces:**
- Consumes: `catalog/model_profiles/<active-model>.yaml` (mandatory_lookup list) + `catalog/freshness/*.yaml` (freshness age) + Edit event payload
- Produces: a D15 async PostToolUse hook that, when an Edit touches a tracked library, checks if the freshness-index cache was refreshed in the prior N agent turns; emits warning if stale or never consulted

- [ ] **Step 1: Write the failing test**

File: `tests/enforcement/test_lookup_gate.py`

```python
"""Tests for lookup_gate.py (#45)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

LOOKUP_GATE = Path("scripts/lookup_gate.py")
CACHE_DIR = Path("catalog/freshness")
SENTINEL_FILE = Path(".heretek/last_lookup.json")


def _run_gate(file_path: str, content: str, set sentinel_age_hours: float = 0) -> dict:
    """Invoke the gate; optionally pre-age the sentinel file."""
    if SENTINEL_FILE.exists():
        SENTINEL_FILE.unlink()

    if set sentinel_age_hours > 0:
        SENTINEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        import json as _json
        SENTINEL_FILE.write_text(_json.dumps({
            "last_lookup_at": time.time() - (set sentinel_age_hours * 3600),
        }))

    payload = json.dumps({
        "session_id": "test-lookup",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": file_path, "new_string": content},
    })
    result = subprocess.run(
        [sys.executable, str(LOOKUP_GATE)],
        input=payload, capture_output=True, text=True, timeout=5,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_lookup_gate_warns_on_tracked_lib_without_recent_lookup(tmp_path, monkeypatch):
    """#45: editing a tracked lib without recent lookup → warning."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "qwen3.6-27b")
    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.34.0\n")

    # Pre-condition: freshness cache exists for 'requests'
    if not (CACHE_DIR / "requests.yaml").exists():
        pytest.skip("populate catalog/freshness/requests.yaml first")

    output = _run_gate(str(fake_req), fake_req.read_text(), sentinel_age_hours=999)
    assert "lookup" in json.dumps(output).lower() or "freshness" in json.dumps(output).lower(), \
        f"expected lookup warning, got: {output}"


def test_lookup_gate_silent_after_recent_lookup(tmp_path, monkeypatch):
    """#45: editing a tracked lib with recent lookup → silent."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "qwen3.6-27b")
    fake_req = tmp_path / "requirements.txt"
    fake_req.write_text("requests==2.34.0\n")

    if not (CACHE_DIR / "requests.yaml").exists():
        pytest.skip("populate catalog/freshness/requests.yaml first")

    output = _run_gate(str(fake_req), fake_req.read_text(), sentinel_age_hours=0)
    assert output == {}, f"unexpected warning after recent lookup: {output}"


def test_lookup_gate_ignores_untracked_libs(tmp_path, monkeypatch):
    """#45: editing a non-tracked library → silent."""
    monkeypatch.setenv("HERETEK_ACTIVE_MODEL", "deepseek-v3")  # minimal lookup list
    fake = tmp_path / "main.py"
    fake.write_text("import json\n")

    output = _run_gate(str(fake), fake.read_text())
    assert output == {}, f"unexpected warning on untracked lib: {output}"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/enforcement/test_lookup_gate.py -v`
Expected: FAIL with `FileNotFoundError`

- [ ] **Step 3: Implement the lookup gate**

File: `scripts/lookup_gate.py`

```python
"""Lookup-gate hook (#45) — D15 async PostToolUse.

When an Edit touches a library in the active model's `mandatory_lookup`
list, checks if a freshness-index consult happened recently. If not,
emits a warning via additionalContext. Per spec §2: async-with-warning
(non-blocking; the agent receives context for the next turn).

D15 compliance: this lives in the hooks plugin only.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

from scripts.model_profile_loader import load_profile, resolve_active_model_id

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
SENTINEL_FILE = Path.cwd() / ".heretek" / "last_lookup.json"
# Default freshness TTL if not in profile
DEFAULT_TTL_HOURS = 24
# Pattern for `name==X.Y.Z` or similar pins
PIN_RE = re.compile(r"^\s*([a-zA-Z0-9_.+-]+)\s*([=<>~!]=)\s*([0-9][^,;\s]*)", re.MULTILINE)


def _tracked_libs_for_active_model() -> set[str]:
    try:
        profile = load_profile(resolve_active_model_id())
    except FileNotFoundError:
        return set()
    return set(profile.get("mandatory_lookup", []))


def _libs_in_content(content: str) -> set[str]:
    libs = set()
    for match in PIN_RE.finditer(content):
        libs.add(match.group(1).lower().replace(".", "-"))
    return libs


def _last_lookup_age_hours() -> float:
    if not SENTINEL_FILE.exists():
        return float("inf")  # never consulted
    try:
        data = json.loads(SENTINEL_FILE.read_text())
    except json.JSONDecodeError:
        return float("inf")
    last = data.get("last_lookup_at", 0)
    return (time.time() - last) / 3600.0


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return 0

    tool_input = payload.get("tool_input", {})
    new_content = tool_input.get("new_string", "")
    if not new_content:
        return 0

    tracked = _tracked_libs_for_active_model()
    edited_libs = _libs_in_content(new_content)
    relevant = tracked & edited_libs

    if not relevant:
        return 0

    try:
        profile = load_profile(resolve_active_model_id())
        ttl = profile.get("freshness_token_ttl_hours", DEFAULT_TTL_HOURS)
    except FileNotFoundError:
        ttl = DEFAULT_TTL_HOURS

    age_hours = _last_lookup_age_hours()
    if age_hours <= ttl:
        return 0  # recent enough

    libs_str = ", ".join(sorted(relevant))
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                f"⚠️  lookup-gate: edit touches tracked lib(s) {libs_str}, but the "
                f"freshness index was last consulted {age_hours:.0f}h ago (TTL: {ttl}h). "
                f"Run `python -m scripts.freshness_index --lib <name>` before continuing."
            ),
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Register the hook**

Add to `plugins/hooks/hooks/hooks.json` (append to existing PostToolUse hooks):

```json
{
  "type": "command",
  "command": "python ${CLAUDE_PROJECT_DIR}/scripts/lookup_gate.py",
  "async": true,
  "timeout": 500
}
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `pytest tests/enforcement/test_lookup_gate.py -v`
Expected: 3 tests PASS

- [ ] **Step 6: Verify D15 enforcement test still passes**

Run: `pytest tests/test_plugin_components.py::test_no_plugin_ships_hooks_outside_hooks_plugin -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/lookup_gate.py tests/enforcement/test_lookup_gate.py
git add plugins/hooks/hooks/hooks.json
git commit -m "feat(lookup-gate): #45 lookup-gate D15 hook"
```

---

### Task 4: Ship #46 — Freshness tokens system

**Files:**
- Create: `scripts/freshness_tokens.py`
- Create: `tests/enforcement/test_freshness_tokens.py`

**Interfaces:**
- Consumes: `catalog/freshness/*.yaml` + active model profile (TTL config)
- Produces: a `render(model_id) -> str` function that emits a token block like:

```
# Freshness tokens (auto-injected by heretek hooks)
# Model: qwen3.6-27b · TTL: 24h · Refreshed: 2026-08-06T...
- requests==2.34.0 (fetched 2026-08-06; consult Context7 if older)
- pyyaml==6.0.3 (fetched 2026-08-06; consult Context7 if older)
...
```

- [ ] **Step 1: Write the failing test**

File: `tests/enforcement/test_freshness_tokens.py`

```python
"""Tests for freshness_tokens.py (#46)."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.freshness_tokens import render, _format_token_line


def test_render_includes_tracked_libs():
    """#46: render() emits one line per tracked lib."""
    if not list(Path("catalog/freshness").glob("*.yaml")):
        pytest.skip("populate catalog/freshness/ first")

    output = render("claude-opus-4")
    # At minimum, requests and pyyaml should be tracked
    assert "requests" in output or "pyyaml" in output
    assert "TTL" in output
    assert "Refreshed" in output


def test_render_handles_missing_profile_gracefully():
    """#46: render() with unknown profile uses defaults."""
    output = render("nonexistent-model-xyz")
    assert "TTL" in output
    assert "default" in output.lower() or "24h" in output


def test_format_token_line_includes_metadata():
    """#46: token line has lib, version, fetched date, refresh hint."""
    fetched_at = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    line = _format_token_line("requests", "2.34.0", fetched_at, ttl_hours=24)
    assert "requests" in line
    assert "2.34.0" in line
    assert "2026-08-06" in line
    assert "24" in line
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/enforcement/test_freshness_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the freshness tokens system**

File: `scripts/freshness_tokens.py`

```python
"""Freshness tokens system (#46).

Renders a token block summarizing the freshness state of all tracked
libraries. The block is injected into agent prompts at session start
(via the hooks plugin install path), giving the agent a snapshot of
"what's current" so it doesn't fall back on training-time memory.

Token format:
    # Freshness tokens (auto-injected by heretek hooks)
    # Model: <model_id> · TTL: <hours>h · Refreshed: <iso8601>
    - <lib>==<version> (fetched <iso8601>; refresh if ><ttl>h old)

The TTL is read from the active model's profile; default 24h.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from scripts.model_profile_loader import (
    load_profile,
    resolve_active_model_id,
)

CACHE_DIR = Path(__file__).resolve().parent.parent / "catalog" / "freshness"
DEFAULT_TTL_HOURS = 24


def _format_token_line(lib: str, version: str, fetched_at: datetime, ttl_hours: int) -> str:
    return (
        f"- {lib}=={version} "
        f"(fetched {fetched_at.date().isoformat()}; "
        f"refresh if >{ttl_hours}h old)"
    )


def _tracked_libs_for(model_id: str) -> list[str]:
    try:
        profile = load_profile(model_id)
        return profile.get("mandatory_lookup", [])
    except FileNotFoundError:
        return []


def render(model_id: str | None = None) -> str:
    """Render the freshness-token block for the given (or active) model."""
    model_id = model_id or resolve_active_model_id()

    try:
        profile = load_profile(model_id)
        ttl = profile.get("freshness_token_ttl_hours", DEFAULT_TTL_HOURS)
    except FileNotFoundError:
        profile = None
        ttl = DEFAULT_TTL_HOURS

    now = datetime.now(timezone.utc)
    tracked = _tracked_libs_for(model_id)

    lines = [
        "# Freshness tokens (auto-injected by heretek hooks)",
        f"# Model: {model_id} · TTL: {ttl}h · Refreshed: {now.isoformat()}",
    ]

    for lib in tracked:
        cache_file = CACHE_DIR / f"{lib.replace('.', '-')}.yaml"
        if not cache_file.exists():
            continue
        try:
            data = yaml.safe_load(cache_file.read_text())
        except yaml.YAMLError:
            continue
        version = data.get("latest_version")
        if not version:
            continue
        # Use the file's mtime as fetched_at (best available signal)
        fetched_at = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
        lines.append(_format_token_line(lib, version, fetched_at, ttl))

    if not lines[2:]:
        lines.append(f"# (no tracked libs found for {model_id}; default TTL: {ttl}h)")

    return "\n".join(lines)


if __name__ == "__main__":
    print(render())
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `pytest tests/enforcement/test_freshness_tokens.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Wire `render()` into the hooks plugin install path**

Modify `plugins/hooks/install.sh` to call `render()` after installation and append the output to the harness's startup prompt config (or print for the installer to pipe):

```bash
# After existing install steps:
echo ""
echo "## Freshness tokens (auto-injected at session start):"
python -m scripts.freshness_tokens || echo "(failed to render tokens — run manually: python -m scripts.freshness_tokens)"
```

Verify: `bash plugins/hooks/install.sh | grep "Freshness tokens"`
Expected: shows the tokens block.

- [ ] **Step 6: Commit**

```bash
git add scripts/freshness_tokens.py tests/enforcement/test_freshness_tokens.py
git add plugins/hooks/install.sh
git commit -m "feat(tokens): #46 freshness tokens system + install wiring"
```

---

### Task 5: Profile-aware enforcement integration test

**Files:**
- Create: `tests/enforcement/test_profile_aware_enforcement.py`

**Interfaces:**
- Consumes: `scripts/scanners/forbidden_pattern_scanner.py` (Plan B) + `scripts/model_profile_loader.py` (Task 2)
- Produces: a single end-to-end test verifying that the same Edit produces different scanner output for different model profiles

- [ ] **Step 1: Write the integration test**

File: `tests/enforcement/test_profile_aware_enforcement.py`

```python
"""End-to-end test: same Edit, different profiles, different outcomes."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

FIXTURES = Path("tests/detection/fixtures")
SCANNER = Path("scripts/scanners/forbidden_pattern_scanner.py")


def _scan_as(model_id: str, content: str) -> dict:
    payload = json.dumps({
        "session_id": "test-e2e",
        "hook_event_name": "PostToolUse",
        "tool_name": "Edit",
        "tool_input": {"file_path": str(FIXTURES / "bad_yaml_load.py"), "new_string": content},
    })
    env = {"HERETEK_ACTIVE_MODEL": model_id, "PATH": __import__("os").environ["PATH"]}
    result = subprocess.run(
        [sys.executable, str(SCANNER)],
        input=payload, capture_output=True, text=True, timeout=5, env=env,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def test_qwen_strict_profile_flags_yaml_load_as_block():
    """Qwen profile promotes py-yaml-load-without-loader to error."""
    bad = (FIXTURES / "bad_yaml_load.py").read_text()
    output = _scan_as("qwen3.6-27b", bad)
    output_str = json.dumps(output)
    assert "🚫" in output_str or "block" in output_str.lower(), \
        f"Qwen strict profile should flag as block, got: {output}"


def test_claude_lax_profile_silences_yaml_load():
    """Claude profile demotes py-yaml-load-without-loader — no warning at all."""
    bad = (FIXTURES / "bad_yaml_load.py").read_text()
    output = _scan_as("claude-opus-4", bad)
    assert output == {}, f"Claude profile should silence, got: {output}"


def test_deepseek_moderate_profile_warns_only():
    """deepseek profile keeps default warn severity."""
    bad = (FIXTURES / "bad_yaml_load.py").read_text()
    output = _scan_as("deepseek-v3", bad)
    output_str = json.dumps(output)
    # Should warn (default severity), not block
    assert "⚠️" in output_str or "warn" in output_str.lower(), \
        f"deepseek should warn only, got: {output}"
    assert "🚫" not in output_str, "deepseek should not block at default severity"
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/enforcement/test_profile_aware_enforcement.py -v`
Expected: 3 tests PASS

If `test_claude_lax_profile_silences_yaml_load` fails because the Claude profile only has the ID in `demote_to_warn` (which only demotes from error→warn, not from warn→silent), see implementation note in profile loader — the demote rule is correct (already-warn stays warn). The test asserts no output at all, which means the pattern needs to be filtered, not just demoted.

Update the test if needed to match the actual behavior: Claude profile demotes the pattern to warn; the scanner still emits a warning, just not a block. Adjust the assertion to check for "warn" only, no "block" marker.

- [ ] **Step 3: Commit**

```bash
git add tests/enforcement/test_profile_aware_enforcement.py
git commit -m "test(enforcement): profile-aware scanner integration"
```

---

### Task 6: Update smoke-test workflow to exercise enforcement

**Files:**
- Modify: `.github/workflows/smoke-test.yml`

**Interfaces:**
- Consumes: full enforcement stack (Plan A + B + C)
- Produces: a smoke test that installs heretek, exercises each new hook, and asserts the expected output

- [ ] **Step 1: Read the current smoke-test.yml**

Run: `cat .github/workflows/smoke-test.yml`

- [ ] **Step 2: Add a `freshness-enforced-coding-smoke` job**

Append to `.github/workflows/smoke-test.yml`:

```yaml
  freshness-enforced-coding-smoke:
    name: Freshness-enforced coding smoke (Plans A+B+C)
    runs-on: ubuntu-latest
    if: github.event_name == 'workflow_dispatch' || github.event_name == 'schedule'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - name: Install runtime + dev deps
        run: pip install -r requirements-dev.txt ast-grep-cli
      - name: Populate freshness cache
        run: python -m scripts.freshness_index --all
      - name: Run all enforcement tests
        run: pytest tests/freshness_eval/ tests/detection/ tests/enforcement/ -v
      - name: Render freshness tokens (model = qwen3.6-27b)
        run: HERETEK_ACTIVE_MODEL=qwen3.6-27b python -m scripts.freshness_tokens
      - name: Render freshness tokens (model = claude-opus-4)
        run: HERETEK_ACTIVE_MODEL=claude-opus-4 python -m scripts.freshness_tokens
```

- [ ] **Step 3: Verify YAML parses**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/smoke-test.yml'))"`
Expected: no error

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/smoke-test.yml
git commit -m "ci(smoke): Plan A+B+C enforcement stack smoke test"
```

---

**Plan C ends here. Plan D (Vision — #47–49) is the 24-month horizon research bets.**