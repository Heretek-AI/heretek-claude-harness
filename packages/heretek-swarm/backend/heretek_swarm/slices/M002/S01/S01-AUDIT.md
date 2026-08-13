# M002/S01 — Validation & Pydantic Model Audit

**Purpose:** Map every validation function and Pydantic model to its canonical home, producing a refactoring guide for S02/S03.

---

## Summary of Findings

Two distinct validation layers exist in this codebase:

| Layer | File | Type | Purpose |
|---|---|---|---|
| Pydantic schemas | `actors/validation.py` | Strict input schemas | Zero-Trust message validation at the actor boundary |
| Mixin class | `actors/mixins/validation.py` | Behavioral/anomaly detection | Runtime behavioral baseline tracking per agent instance |
| Base class | `actors/base/core.py` | Integration wrapper | Wires Pydantic validation into message processing |
| ORM schemas | `schemas/external_call_log.py` | API serialization | External call log CRUD for the API layer |

---

## 1. Pydantic Models — `actors/validation.py`

**Canonical home: `actors/validation.py`** — This is the correct location. All models live here.

| Model | File | Line | What it validates | Who imports it | Recommended Home |
|---|---|---|---|---|---|
| `MessageContent` | `actors/validation.py` | ~70 | Actor message envelope (type, content, sender, correlation_id, reply_to, timestamp) | `actors/base/core.py` (_validate_message_content → validate_message) | `actors/validation.py` ✅ |
| `DeliberationRequest` | `actors/validation.py` | ~130 | Deliberation ID format (del_YYYYMMDD_HHMMSS), topic, triad members (≤10) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `MemoryStoreRequest` | `actors/validation.py` | ~160 | Memory content (non-empty), metadata (≤50 fields), ttl (1–31536000s), persistent flag, lineage | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `AnalysisRequest` | `actors/validation.py` | ~200 | Request ID (alphanumeric, ≤64), problem text (≤10000 chars) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `ValidationRequest` | `actors/validation.py` | ~220 | Generic request_id + decision + original_analysis | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `QueryRequest` | `actors/validation.py` | ~235 | Query text (≤10000), filters (≤20), limit (1–1000) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `LineageRequest` | `actors/validation.py` | ~265 | Decision ID, parent IDs (≤20) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `HealthCheckRequest` | `actors/validation.py` | ~285 | Reply-to topic (≤256) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `SuspendResumeRequest` | `actors/validation.py` | ~298 | Actor ID (≤128) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `TerminateRequest` | `actors/validation.py` | ~312 | Actor ID (≤128), optional reason (≤512) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `CollectiveTaskRequest` | `actors/validation.py` | ~325 | Task (≤10000), participant list | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `TaskRequest` | `actors/validation.py` | ~340 | Full task coordination (task_id, name, description, assigned_agents, dependencies, priority 1–10, metadata) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `DependencyRequest` | `actors/validation.py` | ~380 | Task ID list | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |
| `CoordinationRequest` | `actors/validation.py` | ~395 | Workflow/agent/task IDs, input_data (≤100 fields), protocol (≤20 fields) | MESSAGE_TYPE_VALIDATORS dispatch | `actors/validation.py` ✅ |

**Companion functions in `actors/validation.py`:**

| Function | Line | Purpose | Recommended Home |
|---|---|---|---|
| `get_immutable_rules()` | ~57 | Returns IMMUTABLE_RULES list (security patterns) | `actors/validation.py` ✅ |
| `get_baseline_config()` | ~75 | Returns BASELINE_CONFIG dict | `actors/validation.py` ✅ |
| `validate_message(message_type, content)` | ~460 | Runtime dispatcher: maps message_type → validator model | `actors/validation.py` ✅ |

**Module-level constants:**

| Name | Line | Purpose | Recommended Home |
|---|---|---|---|
| `IMMUTABLE_RULES` | ~25 | Static security rule patterns (eval, exec, __import__, subprocess, os.system, pickle, torch.load, yaml.load Loader=None) | `actors/validation.py` ✅ |
| `BASELINE_CONFIG` | ~70 | Behavioral baseline initialization config | `actors/validation.py` ✅ |
| `MESSAGE_TYPE_VALIDATORS` | ~410 | Dict mapping message_type strings → Pydantic model classes | `actors/validation.py` ✅ |
| `_TASK_DESCRIPTION` | ~17 | Shared field description constant | `actors/validation.py` ✅ |

---

## 2. Runtime Validation Mixin — `actors/mixins/validation.py`

**Canonical home: `actors/mixins/validation.py`** — Mixin class correctly placed here. Not reusable as standalone functions.

| Component | Line | What it does | Recommended Home |
|---|---|---|---|
| `ValidationMixin` class | ~35 | ZERO-02 Zero-Trust mixin; wraps any agent with behavioral validation | `actors/mixins/validation.py` ✅ |
| `validate_input()` | ~65 | Public async entry: circular-check → timeout → behavioral baseline → anomaly detection | `actors/mixins/validation.py` ✅ |
| `validate_output()` | ~280 | Pre-send output validation against behavioral baseline | `actors/mixins/validation.py` ✅ |
| `_perform_validation()` | ~130 | Override hook for custom logic; default checks not-None + baseline + anomaly | `actors/mixins/validation.py` ✅ |
| `_run_with_timeout()` | ~175 | asyncio.wait_for wrapper (10ms default) | `actors/mixins/validation.py` ✅ |
| `_is_already_validated()` | ~185 | SHA256 hash check in `_validated_outputs` set | `actors/mixins/validation.py` ✅ |
| `_mark_as_validated()` | ~200 | Adds SHA256 hash to circular-prevention set, prunes oldest 10% at 10k entries | `actors/mixins/validation.py` ✅ |
| `_hash_data()` | ~220 | JSON-sort + sha256 for dict/list, fallback to str hash | `actors/mixins/validation.py` ✅ |
| `_check_behavioral_baseline()` | ~235 | z-score anomaly detection against per-operation mean/std_dev | `actors/mixins/validation.py` ✅ |
| `_extract_metrics()` | ~270 | Extracts numeric metrics from dict/list/scalar for baseline comparison | `actors/mixins/validation.py` ✅ |
| `_update_behavioral_history()` | ~300 | Appends to `_behavioral_history`, recalculates baseline every 100 points | `actors/mixins/validation.py` ✅ |
| `_recalculate_baseline()` | ~320 | Rebuilds baseline mean/std_dev from history per operation | `actors/mixins/validation.py` ✅ |
| `get_validation_stats()` | ~355 | Returns validation stats dict | `actors/mixins/validation.py` ✅ |
| `reset_validation_stats()` | ~370 | Zeros all counters | `actors/mixins/validation.py` ✅ |
| `clear_validated_outputs()` | ~378 | Clears circular-prevention set | `actors/mixins/validation.py` ✅ |

---

## 3. Base Class Integration — `actors/base/core.py`

**Canonical home: `actors/base/core.py`** — Entry point that wires validation into message processing.

| Component | Line | What it does | Recommended Home |
|---|---|---|---|
| `_validate_message_content()` | ~155 | Calls `validate_message()` from `actors/validation.py`, wraps ValidationError → ValueError | `actors/base/core.py` ✅ |
| `validate_message` import | ~25 | Imported from `actors.validation` | `actors/base/core.py` ✅ |
| `AgentActor` class | ~100 | Base actor class; uses `_validate_message_content()` in message pipeline | `actors/base/core.py` ✅ |
| `ActorState`, `ActorMessage`, `ActorStatus` | ~45–100 | Core dataclasses/enums (no validation) | `actors/base/core.py` ✅ |

---

## 4. ORM/API Schemas — `schemas/external_call_log.py`

**Canonical home: `schemas/external_call_log.py`** — Separate from actor validation layer.

| Model | Line | What it validates | Recommended Home |
|---|---|---|---|
| `ExternalCallLogBase` | ~30 | Agent ID, type, call type, URL, method, status, duration, tool name, error message | `schemas/external_call_log.py` ✅ |
| `ExternalCallLogCreate` | ~50 | Create: + encrypted request/response headers+bodies (≤10KB each) | `schemas/external_call_log.py` ✅ |
| `ExternalCallLogResponse` | ~75 | Response: + UUID, domain extraction, decrypted bodies, created_at | `schemas/external_call_log.py` ✅ |
| `ExternalCallLogListItem` | ~130 | List item: excludes bodies for performance | `schemas/external_call_log.py` ✅ |
| `ExternalCallLogListResponse` | ~150 | Paginated list: items, total, offset, limit, has_more | `schemas/external_call_log.py` ✅ |
| `extract_domain()` | ~18 | URL → domain helper | `schemas/external_call_log.py` ✅ |

---

## 5. No Overlap / No Conflicts Found

- `actors/validation.py` — Pydantic v2 models for **message schemas** (Zero-Trust at actor boundary)
- `actors/mixins/validation.py` — Class mixin for **behavioral/anomaly detection** (runtime per-agent)
- `actors/base/core.py` — Uses `actors/validation.py`; does NOT duplicate models
- `schemas/external_call_log.py` — **Separate domain** (API persistence); no imports from actors layer

---

## 6. Recommended Canonical Homes (No Changes Needed)

| Item | Current Home | Recommended Home | Change? |
|---|---|---|---|
| All Pydantic models | `actors/validation.py` | `actors/validation.py` | **No** |
| `IMMUTABLE_RULES`, `BASELINE_CONFIG` | `actors/validation.py` | `actors/validation.py` | **No** |
| `MESSAGE_TYPE_VALIDATORS` dict | `actors/validation.py` | `actors/validation.py` | **No** |
| `ValidationMixin` | `actors/mixins/validation.py` | `actors/mixins/validation.py` | **No** |
| `validate_message()` function | `actors/validation.py` | `actors/validation.py` | **No** |
| `AgentActor._validate_message_content()` | `actors/base/core.py` | `actors/base/core.py` | **No** |
| All ExternalCallLog schemas | `schemas/external_call_log.py` | `schemas/external_call_log.py` | **No** |

**Conclusion:** The validation and model locations are already canonical. No refactoring of file locations is needed. The primary opportunity for S02/S03 is deduplication: several message-type models in `actors/validation.py` share identical field validators (e.g., `validate_filters`, `validate_metadata`, `validate_input_data` all check `len(v) > N`). These could be extracted to shared helper validators or a base class, but the file layout itself is correct.

---

## 7. Dependencies / Consumers Map

```
actors/validation.py
  └─ exports: validate_message, MESSAGE_TYPE_VALIDATORS, IMMUTABLE_RULES, BASELINE_CONFIG, all Pydantic models
       ├─ actors/base/core.py      ← imports validate_message
       │   └─ AgentActor._validate_message_content()
       └─ (self-contained; no external imports)

actors/mixins/validation.py
  └─ ValidationMixin class (mixin pattern)
       └─ Use via multiple inheritance: class MyAgent(ValidationMixin, AgentActor): ...

schemas/external_call_log.py
  └─ ExternalCallLog schemas (API layer)
       └─ Consumed by API routes/controllers (out of scope for this audit)
```

---

*Audit produced by M002/S01/T01 — 2025-05-07*
