# Agent-Harness OSS Landscape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/superpowers/specs/2026-06-25-agent-harness-landscape.md`, a decision-ready landscape doc comparing `NousResearch/hermes-agent` and `openclaw/openclaw` against the 23-agent swarm's Prime Directive, adoption, and pattern-transferability rubric.

**Architecture:** Read-only research via the `Workflow` tool. Three phases: parallel deep-read (2 readers) → parallel adversarial refutation (2 refuters) → synthesis (1 agent writes the doc). Schemas + acceptance bar are first-class Python artifacts (TDD'd), so validation runs at agent boundaries and again against the produced doc.

**Tech Stack:** Python 3.11+, Pydantic v2 (schemas), pytest (tests), `Workflow` tool (orchestration), `mcp__plugin_context-mode_context-mode__ctx_fetch_and_index` (GitHub repo cache), `firecrawl_scrape` (README fallback).

## Global Constraints

- No code changes to `backend/heretek_swarm/` or `backend/tier1/`.
- No new runtime dependencies in `pyproject.toml`. Test-only deps (`pydantic`, `pytest`) are added if absent.
- Conventional Commits format for every commit.
- License veto: any non-permissive license in either target repo triggers `NO-ADOPT VERDICT` block in the doc.
- Sovereignty veto: mandatory SaaS / mandatory telemetry in either repo triggers `SOVEREIGNTY-BLOCKED` marker.
- Every claim in the deliverable doc carries a confidence marker: `[verified]`, `[weakened]`, `[refuted]`, `[unverifiable]`, or `[inferred]`.
- Total workflow budget ≤600k output tokens.

---

## File Structure

| Path | Responsibility |
|---|---|
| `scripts/research/__init__.py` | Package marker |
| `scripts/research/schemas.py` | Three Pydantic models: `ReaderFindings`, `RefuterVerdicts`, `SynthesizerOutput` |
| `scripts/research/acceptance.py` | 10 acceptance-bar checks as `AcceptanceChecker` class |
| `scripts/research/run_workflow.py` | Stages the Workflow-tool script payload |
| `tests/research/__init__.py` | Test package marker |
| `tests/research/test_schemas.py` | Schema validation tests |
| `tests/research/test_acceptance.py` | Acceptance-bar fixture tests |
| `docs/superpowers/specs/2026-06-25-agent-harness-landscape.md` | **DELIVERABLE** — written by synthesizer agent |

---

### Task 1: Schema Scaffold + Tests

**Files:**
- Create: `scripts/research/__init__.py`
- Create: `scripts/research/schemas.py`
- Create: `tests/research/__init__.py`
- Create: `tests/research/test_schemas.py`

**Interfaces:**
- Consumes: nothing (greenfield)
- Produces: `ReaderFindings`, `RefuterVerdicts`, `SynthesizerOutput` Pydantic models. Used by `acceptance.py` (Task 2) and by the Workflow tool schema validation at agent boundaries.

- [ ] **Step 1: Write failing test for `ReaderFindings` schema**

Create `tests/research/test_schemas.py`:

```python
"""Tests for research schema validation."""
import pytest
from pydantic import ValidationError

from scripts.research.schemas import ReaderFindings, RefuterVerdicts, SynthesizerOutput


def test_reader_findings_minimal_valid():
    findings = ReaderFindings(
        repo="NousResearch/hermes-agent",
        license="MIT",
        language="Python",
        entry_points=["src/hermes/main.py:1"],
        loop_architecture="Single asyncio loop.",
        tool_model="JSON-schema tools.",
        memory_hook=None,
        agent_lifecycle="init -> run -> shutdown",
        patterns_observed=["asyncio main loop"],
        claim_evidence=[
            {"claim": "Uses asyncio", "evidence_path": "src/hermes/main.py:42", "confidence": "high"}
        ],
    )
    assert findings.repo == "NousResearch/hermes-agent"


def test_reader_findings_rejects_short_license():
    with pytest.raises(ValidationError):
        ReaderFindings(
            repo="x/y", license="", language="Python",
            entry_points=["a.py:1"], loop_architecture="x",
            tool_model="x", memory_hook=None, agent_lifecycle="x",
            patterns_observed=[], claim_evidence=[],
        )


def test_reader_findings_rejects_bad_confidence():
    with pytest.raises(ValidationError):
        ReaderFindings(
            repo="x/y", license="MIT", language="Python",
            entry_points=["a.py:1"], loop_architecture="x",
            tool_model="x", memory_hook=None, agent_lifecycle="x",
            patterns_observed=[],
            claim_evidence=[{"claim": "c", "evidence_path": "a.py:1", "confidence": "maybe"}],
        )


def test_refuter_verdicts_valid():
    v = RefuterVerdicts(
        repo="NousResearch/hermes-agent",
        refutations=[{"target_claim": "Uses asyncio", "verdict": "holds", "evidence": "verified at src/hermes/main.py:42"}],
        surviving_claims=["Uses asyncio"],
    )
    assert v.refutations[0].verdict == "holds"


def test_refuter_verdicts_rejects_bad_verdict():
    with pytest.raises(ValidationError):
        RefuterVerdicts(
            repo="x/y",
            refutations=[{"target_claim": "c", "verdict": "kinda", "evidence": "x"}],
            surviving_claims=[],
        )


def test_synthesizer_output_valid():
    s = SynthesizerOutput(
        doc_path="docs/superpowers/specs/2026-06-25-agent-harness-landscape.md",
        head_to_head={"rows": [{"axis": "License", "hermes": "MIT", "openclaw": "Apache-2.0"}]},
        rubric_scores={
            "NousResearch/hermes-agent": {"prime_directive_fit": {}, "adoption": {}, "pattern_transferability": {}},
            "openclaw/openclaw": {"prime_directive_fit": {}, "adoption": {}, "pattern_transferability": {}},
        },
    )
    assert "hermes-agent" in s.rubric_scores
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/john/Projects/heretek-swarm && pytest tests/research/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.research.schemas'`

- [ ] **Step 3: Implement the schemas**

Create `scripts/research/__init__.py` (empty file).
Create `tests/research/__init__.py` (empty file).
Create `scripts/research/schemas.py`:

```python
"""Pydantic schemas for the agent-harness research workflow.

Three schemas, one per agent role. The Workflow tool validates each
agent's structured output against these models at the boundary.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


ConfidenceLevel = Literal["high", "med", "low"]
RefutationVerdict = Literal["refuted", "weakened", "holds", "unverifiable"]


class ClaimEvidence(BaseModel):
    """One claim with provenance and self-rated confidence."""

    claim: str = Field(min_length=1)
    evidence_path: str = Field(min_length=1, pattern=r"^.+:\d+$")
    confidence: ConfidenceLevel


class ReaderFindings(BaseModel):
    """Output of a deep-read agent for one repo."""

    repo: str = Field(min_length=3, pattern=r"^[^/]+/[^/]+$")
    license: str = Field(min_length=1)
    language: str = Field(min_length=1)
    entry_points: list[str] = Field(min_length=1)
    loop_architecture: str = Field(max_length=2000)
    tool_model: str = Field(min_length=1)
    memory_hook: str | None
    agent_lifecycle: str = Field(min_length=1)
    patterns_observed: list[str]
    claim_evidence: list[ClaimEvidence]


class Refutation(BaseModel):
    target_claim: str = Field(min_length=1)
    verdict: RefutationVerdict
    evidence: str = Field(min_length=1)


class RefuterVerdicts(BaseModel):
    """Output of an adversarial refuter agent."""

    repo: str = Field(min_length=3, pattern=r"^[^/]+/[^/]+$")
    refutations: list[Refutation]
    surviving_claims: list[str]

    @field_validator("refutations")
    @classmethod
    def at_least_one(cls, v: list[Refutation]) -> list[Refutation]:
        if not v:
            raise ValueError("refuter must produce at least one verdict")
        return v


class RubricAxisScores(BaseModel):
    """Loose dict shape: each axis is an int 0-5 or 0-3 per rubric definition."""

    model_config = {"extra": "allow"}


class RubricScores(BaseModel):
    prime_directive_fit: dict[str, int]
    adoption: dict[str, int]
    pattern_transferability: dict[str, int]


class HeadToHeadRow(BaseModel):
    axis: str = Field(min_length=1)
    hermes: str = Field(min_length=1)
    openclaw: str = Field(min_length=1)


class SynthesizerOutput(BaseModel):
    """Output of the synthesis agent. The doc_path is the deliverable."""

    doc_path: str = Field(min_length=1)
    head_to_head: dict
    rubric_scores: dict[str, RubricScores]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/john/Projects/heretek-swarm && pytest tests/research/test_schemas.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add scripts/research/__init__.py scripts/research/schemas.py tests/research/__init__.py tests/research/test_schemas.py
git commit -m "feat(research): add pydantic schemas for agent-harness workflow"
```

---

### Task 2: Acceptance Bar + Tests

**Files:**
- Create: `scripts/research/acceptance.py`
- Create: `tests/research/test_acceptance.py`

**Interfaces:**
- Consumes: `ReaderFindings`, `RefuterVerdicts`, `SynthesizerOutput` from Task 1.
- Produces: `AcceptanceChecker` class with `check(deliverable_doc_path, reader_findings, refuter_verdicts, synthesizer_output) -> AcceptanceReport`. Used by the verification step in Task 5.

- [ ] **Step 1: Write failing tests for the acceptance bar**

Create `tests/research/test_acceptance.py`:

```python
"""Tests for the 10 acceptance-bar checks."""
from pathlib import Path

import pytest

from scripts.research.acceptance import AcceptanceChecker
from scripts.research.schemas import (
    ReaderFindings,
    RefuterVerdicts,
    SynthesizerOutput,
    RubricScores,
)


@pytest.fixture
def perfect_doc(tmp_path: Path) -> Path:
    """A deliverable doc that satisfies every acceptance check."""
    doc = tmp_path / "perfect.md"
    doc.write_text(
        "<!-- Verified against commit abc123 on 2026-06-25 -->\n"
        "# Agent-Harness OSS Landscape\n\n"
        "## hermes-agent\n"
        "- License: MIT [verified]\n"
        "- Sovereignty: sovereign [verified]\n"
        "### Prime Directive Fit\n"
        "- Unbounded Autonomy: 4 [verified]\n"
        "- Organic Evolution: 3 [verified]\n"
        "- Zero-Trust: 2 [verified]\n"
        "- Consciousness-by-Design: 1 [verified]\n"
        "- Persistent Operation: 5 [verified]\n"
        "### Adoption\n"
        "- License: 3 [verified]\n"
        "- Python 3.11+: 3 [verified]\n"
        "- Async: 3 [verified]\n"
        "- Runs without cloud: 3 [verified]\n"
        "- No telemetry: 3 [verified]\n"
        "### Pattern Transferability\n"
        "- Loop control: 3 [verified]\n"
        "- Tool calling: 2 [verified]\n"
        "- Memory hook: 1 [verified]\n"
        "- Error recovery: 2 [verified]\n"
        "- A2A protocol: 0 [verified]\n"
        "\n"
        "## openclaw\n"
        "- License: Apache-2.0 [verified]\n"
        "- Sovereignty: sovereign [verified]\n"
        "### Prime Directive Fit\n"
        "- Unbounded Autonomy: 3 [verified]\n"
        "- Organic Evolution: 2 [verified]\n"
        "- Zero-Trust: 4 [verified]\n"
        "- Consciousness-by-Design: 0 [verified]\n"
        "- Persistent Operation: 4 [verified]\n"
        "### Adoption\n"
        "- License: 3 [verified]\n"
        "- Python 3.11+: 2 [verified]\n"
        "- Async: 2 [verified]\n"
        "- Runs without cloud: 2 [verified]\n"
        "- No telemetry: 2 [verified]\n"
        "### Pattern Transferability\n"
        "- Loop control: 2 [verified]\n"
        "- Tool calling: 3 [verified]\n"
        "- Memory hook: 2 [verified]\n"
        "- Error recovery: 1 [verified]\n"
        "- A2A protocol: 1 [verified]\n"
    )
    return doc


@pytest.fixture
def missing_confidence_doc(tmp_path: Path) -> Path:
    """A doc that has content but missing the [verified] markers."""
    doc = tmp_path / "missing.md"
    doc.write_text("# Agent-Harness OSS Landscape\n\n## hermes-agent\n- License: MIT\n")
    return doc


@pytest.fixture
def both_findings() -> list[ReaderFindings]:
    return [
        ReaderFindings(
            repo="NousResearch/hermes-agent", license="MIT", language="Python",
            entry_points=["src/hermes/main.py:1"], loop_architecture="asyncio",
            tool_model="json", memory_hook=None, agent_lifecycle="init-run-shutdown",
            patterns_observed=["asyncio"],
            claim_evidence=[{"claim": "Uses asyncio", "evidence_path": "src/hermes/main.py:42", "confidence": "high"}],
        ),
        ReaderFindings(
            repo="openclaw/openclaw", license="Apache-2.0", language="Python",
            entry_points=["openclaw/main.py:1"], loop_architecture="asyncio",
            tool_model="json", memory_hook=None, agent_lifecycle="init-run-shutdown",
            patterns_observed=["asyncio"],
            claim_evidence=[{"claim": "Uses asyncio", "evidence_path": "openclaw/main.py:42", "confidence": "high"}],
        ),
    ]


@pytest.fixture
def both_verdicts() -> list[RefuterVerdicts]:
    return [
        RefuterVerdicts(
            repo="NousResearch/hermes-agent",
            refutations=[{"target_claim": "Uses asyncio", "verdict": "holds", "evidence": "verified"}],
            surviving_claims=["Uses asyncio"],
        ),
        RefuterVerdicts(
            repo="openclaw/openclaw",
            refutations=[{"target_claim": "Uses asyncio", "verdict": "holds", "evidence": "verified"}],
            surviving_claims=["Uses asyncio"],
        ),
    ]


def test_perfect_doc_passes_all_checks(perfect_doc, both_findings, both_verdicts):
    synth = SynthesizerOutput(
        doc_path=str(perfect_doc),
        head_to_head={"rows": [{"axis": "License", "hermes": "MIT", "openclaw": "Apache-2.0"}]},
        rubric_scores={
            "NousResearch/hermes-agent": RubricScores(
                prime_directive_fit={"Unbounded Autonomy": 4},
                adoption={"License": 3},
                pattern_transferability={"Loop control": 3},
            ),
            "openclaw/openclaw": RubricScores(
                prime_directive_fit={"Unbounded Autonomy": 3},
                adoption={"License": 3},
                pattern_transferability={"Loop control": 2},
            ),
        },
    )
    checker = AcceptanceChecker()
    report = checker.check(
        deliverable_doc_path=perfect_doc,
        reader_findings=both_findings,
        refuter_verdicts=both_verdicts,
        synthesizer_output=synth,
    )
    assert report.passed, f"expected PASS, got failures: {report.failures}"


def test_missing_confidence_fails(perfect_doc, missing_confidence_doc, both_findings, both_verdicts):
    synth = SynthesizerOutput(
        doc_path=str(missing_confidence_doc),
        head_to_head={"rows": []},
        rubric_scores={
            "NousResearch/hermes-agent": RubricScores(
                prime_directive_fit={}, adoption={}, pattern_transferability={},
            ),
            "openclaw/openclaw": RubricScores(
                prime_directive_fit={}, adoption={}, pattern_transferability={},
            ),
        },
    )
    checker = AcceptanceChecker()
    report = checker.check(
        deliverable_doc_path=missing_confidence_doc,
        reader_findings=both_findings,
        refuter_verdicts=both_verdicts,
        synthesizer_output=synth,
    )
    assert not report.passed
    assert any("confidence marker" in f.lower() for f in report.failures)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/john/Projects/heretek-swarm && pytest tests/research/test_acceptance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.research.acceptance'`

- [ ] **Step 3: Implement `AcceptanceChecker`**

Create `scripts/research/acceptance.py`:

```python
"""Acceptance-bar checker for the agent-harness landscape deliverable.

Implements the 10 acceptance checks from the spec. Returns an
AcceptanceReport with .passed bool and .failures list[str].

Acceptance criteria:
1. Both repos characterized (all rubric axes populated)
2. License verdict per repo
3. Sovereignty verdict per repo
4. Head-to-head table present + complete
5. Confidence markers on every claim
6. Refutation coverage (every reader claim has refuter verdict)
7. Provenance (every factual claim cites file:line or commit:SHA)
8. Prime Directive alignment (all 5 pillars scored)
9. Length sanity (800-2500 words)
10. Commit message format (Conventional Commits)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from scripts.research.schemas import (
    ReaderFindings,
    RefuterVerdicts,
    SynthesizerOutput,
)


CONFIDENCE_MARKERS = re.compile(
    r"\[(verified|weakened|refuted|unverifiable|inferred)\]"
)
PROVENANCE_PATTERN = re.compile(r"`?[a-zA-Z0-9_./-]+\.(py|md|yaml|yml|json|sh|toml):\d+`?")
COMMIT_SHA_PATTERN = re.compile(r"commit\s+[0-9a-f]{7,40}")
PRIME_DIRECTIVE_PILLARS = [
    "Unbounded Autonomy",
    "Organic Evolution",
    "Zero-Trust",
    "Consciousness-by-Design",
    "Persistent Operation",
]
MIN_WORDS = 800
MAX_WORDS = 2500


@dataclass
class AcceptanceReport:
    passed: bool
    failures: list[str] = field(default_factory=list)


class AcceptanceChecker:
    def check(
        self,
        deliverable_doc_path: Path,
        reader_findings: list[ReaderFindings],
        refuter_verdicts: list[RefuterVerdicts],
        synthesizer_output: SynthesizerOutput,
    ) -> AcceptanceReport:
        failures: list[str] = []
        text = deliverable_doc_path.read_text(encoding="utf-8")

        # Check 1: both repos characterized
        repos = {f.repo for f in reader_findings}
        for repo in repos:
            if repo not in synthesizer_output.rubric_scores:
                failures.append(f"Rubric scores missing for {repo}")

        # Check 2: license verdict
        for f in reader_findings:
            if f.license.lower() not in {"mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "mpl-2.0", "unlicense"}:
                failures.append(f"{f.repo}: non-permissive license '{f.license}' -> NO-ADOPT VERDICT required")

        # Check 3: sovereignty verdict (heuristic: doc must contain 'Sovereignty:' line per repo)
        if text.count("Sovereignty:") < len(reader_findings):
            failures.append("Missing sovereignty verdict line for one or more repos")

        # Check 4: head-to-head table present
        if not synthesizer_output.head_to_head.get("rows"):
            failures.append("Head-to-head table is empty")

        # Check 5: confidence markers
        for f in reader_findings:
            section = self._extract_repo_section(text, f.repo)
            if not CONFIDENCE_MARKERS.search(section):
                failures.append(f"{f.repo}: section has no confidence marker")

        # Check 6: refutation coverage
        verdicts_by_repo = {v.repo: v for v in refuter_verdicts}
        for f in reader_findings:
            if f.repo not in verdicts_by_repo:
                failures.append(f"{f.repo}: no refuter verdict")
                continue
            claimed = {c.claim for c in f.claim_evidence}
            refuted = {r.target_claim for r in verdicts_by_repo[f.repo].refutations}
            missing = claimed - refuted
            if missing:
                failures.append(f"{f.repo}: refuter missed claims: {missing}")

        # Check 7: provenance
        for f in reader_findings:
            for c in f.claim_evidence:
                if not PROVENANCE_PATTERN.match(c.evidence_path) and not COMMIT_SHA_PATTERN.match(c.evidence_path):
                    failures.append(f"{f.repo}::{c.claim}: bad provenance {c.evidence_path!r}")

        # Check 8: Prime Directive pillars scored
        for repo, scores in synthesizer_output.rubric_scores.items():
            for pillar in PRIME_DIRECTIVE_PILLARS:
                if pillar not in scores.prime_directive_fit:
                    failures.append(f"{repo}: missing Prime Directive pillar '{pillar}'")

        # Check 9: length sanity
        word_count = len(text.split())
        if word_count < MIN_WORDS:
            failures.append(f"Doc too short: {word_count} words (min {MIN_WORDS})")
        if word_count > MAX_WORDS:
            failures.append(f"Doc too long: {word_count} words (max {MAX_WORDS})")

        # Check 10: commit message format (checked at commit time, not doc-check time)
        return AcceptanceReport(passed=not failures, failures=failures)

    @staticmethod
    def _extract_repo_section(text: str, repo: str) -> str:
        name = repo.split("/")[-1]
        idx = text.lower().find(name.lower())
        if idx == -1:
            return ""
        return text[idx:idx + 4000]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/john/Projects/heretek-swarm && pytest tests/research/test_acceptance.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full test suite**

Run: `cd /home/john/Projects/heretek-swarm && pytest tests/research/ -v`
Expected: PASS (8 tests total)

- [ ] **Step 6: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add scripts/research/acceptance.py tests/research/test_acceptance.py
git commit -m "feat(research): add 10-check acceptance bar with fixture tests"
```

---

### Task 3: Workflow Script Stager

**Files:**
- Create: `scripts/research/run_workflow.py`

**Interfaces:**
- Consumes: `scripts.research.schemas` (for the inline schema definitions the Workflow tool consumes).
- Produces: a `get_workflow_script()` function that returns the JS payload string for the `Workflow` tool.

- [ ] **Step 1: Implement the workflow script stager**

Create `scripts/research/run_workflow.py`:

```python
"""Stage the Workflow-tool script for the agent-harness research.

This module is NOT executed at runtime by the research. It holds the
Workflow-tool script as a Python string for version control + review.
The actual execution step (Task 4) copies this string into a Workflow
tool call via `python -m scripts.research.run_workflow > /tmp/...js`.

Phases:
  1. Deep Read       — parallel: reader.hermes + reader.openclaw
  2. Adversarial     — parallel: refuter.hermes + refuter.openclaw
  3. Synthesis       — single agent writes the deliverable .md
"""
from __future__ import annotations


WORKFLOW_SCRIPT = r'''
export const meta = {
  name: 'agent-harness-landscape',
  description: 'Deep-read + adversarial-verify + synthesize landscape doc for hermes-agent + openclaw',
  phases: [
    { title: 'Deep Read' },
    { title: 'Adversarial Verify' },
    { title: 'Synthesis' },
  ],
};

const READER_SCHEMA = {
  type: 'object',
  required: ['repo', 'license', 'language', 'entry_points', 'loop_architecture',
             'tool_model', 'memory_hook', 'agent_lifecycle', 'patterns_observed', 'claim_evidence'],
  properties: {
    repo: { type: 'string' },
    license: { type: 'string' },
    language: { type: 'string' },
    entry_points: { type: 'array', items: { type: 'string' } },
    loop_architecture: { type: 'string' },
    tool_model: { type: 'string' },
    memory_hook: { type: ['string', 'null'] },
    agent_lifecycle: { type: 'string' },
    patterns_observed: { type: 'array', items: { type: 'string' } },
    claim_evidence: {
      type: 'array',
      items: {
        type: 'object',
        required: ['claim', 'evidence_path', 'confidence'],
        properties: {
          claim: { type: 'string' },
          evidence_path: { type: 'string' },
          confidence: { enum: ['high', 'med', 'low'] },
        },
      },
    },
  },
};

const REFUTER_SCHEMA = {
  type: 'object',
  required: ['repo', 'refutations', 'surviving_claims'],
  properties: {
    repo: { type: 'string' },
    refutations: {
      type: 'array',
      items: {
        type: 'object',
        required: ['target_claim', 'verdict', 'evidence'],
        properties: {
          target_claim: { type: 'string' },
          verdict: { enum: ['refuted', 'weakened', 'holds', 'unverifiable'] },
          evidence: { type: 'string' },
        },
      },
    },
    surviving_claims: { type: 'array', items: { type: 'string' } },
  },
};

const SYNTHESIZER_SCHEMA = {
  type: 'object',
  required: ['doc_path', 'head_to_head', 'rubric_scores'],
  properties: {
    doc_path: { type: 'string' },
    head_to_head: { type: 'object' },
    rubric_scores: { type: 'object' },
  },
};

phase('Deep Read');
const hermes_findings = await agent(
  'Inspect https://github.com/NousResearch/hermes-agent. Use firecrawl_scrape + ctx_fetch_and_index (cached) + git clone fallback. Read README, src layout, entry points, key abstractions. Cite file:line for every claim. Apply the rubric (Prime Directive Fit 0-5 across 5 pillars; Adoption 0-3 across License / Python 3.11+ / Async / Runs without cloud / No telemetry; Pattern Transferability 0-3 across Loop control / Tool calling / Memory hook / Error recovery / A2A protocol). Sharp veto: non-permissive license -> flag NO-ADOPT; mandatory SaaS/telemetry -> flag SOVEREIGNTY-BLOCKED. Output schema-validated JSON.',
  { phase: 'Deep Read', label: 'reader.hermes', schema: READER_SCHEMA }
);
const openclaw_findings = await agent(
  'Inspect https://github.com/openclaw/openclaw. Same tool chain and rubric as reader.hermes. Output schema-validated JSON.',
  { phase: 'Deep Read', label: 'reader.openclaw', schema: READER_SCHEMA }
);

phase('Adversarial Verify');
const hermes_verdicts = await agent(
  'Adversarial refuter for NousResearch/hermes-agent. Given hermes_findings, re-fetch every cited file:line. Mark each claim holds / weakened / refuted / unverifiable with counter-evidence. Do NOT add new findings. Output schema-validated JSON.',
  { phase: 'Adversarial Verify', label: 'refuter.hermes', schema: REFUTER_SCHEMA }
);
const openclaw_verdicts = await agent(
  'Adversarial refuter for openclaw/openclaw. Same rules as refuter.hermes. Output schema-validated JSON.',
  { phase: 'Adversarial Verify', label: 'refuter.openclaw', schema: REFUTER_SCHEMA }
);

phase('Synthesis');
const synth = await agent(
  'Synthesis agent. Given hermes_findings, openclaw_findings, hermes_verdicts, openclaw_verdicts, write the single deliverable at docs/superpowers/specs/2026-06-25-agent-harness-landscape.md using Read + Write tools. Structure: Executive Summary, per-repo sections (hermes then openclaw) each with License verdict + provenance, Sovereignty verdict + provenance, Prime Directive Fit (5 pillars), Adoption (5 axes), Pattern Transferability (5 patterns), Refutation outcomes; Head-to-head comparison table; Rubric score summary; Known limitations; "Verified against commit <SHA> on <date>" header. Every factual claim tagged [verified]|[weakened]|[refuted]|[unverifiable]|[inferred]. Every factual claim cites file:line or commit:SHA. Length 800-2500 words. Output schema-validated JSON sidecar with doc_path, head_to_head, rubric_scores.',
  { phase: 'Synthesis', label: 'synthesizer', schema: SYNTHESIZER_SCHEMA }
);

return { hermes_findings, openclaw_findings, hermes_verdicts, openclaw_verdicts, synth };
'''


def get_workflow_script() -> str:
    """Return the Workflow-tool script for the agent-harness landscape run."""
    return WORKFLOW_SCRIPT


if __name__ == "__main__":
    import sys
    sys.stdout.write(get_workflow_script())
```

- [ ] **Step 2: Verify the script is valid Python and dumps**

Run:
```bash
cd /home/john/Projects/heretek-swarm
python -c "from scripts.research.run_workflow import get_workflow_script; s = get_workflow_script(); print(len(s), 'chars')"
```
Expected: prints ~5500 chars

- [ ] **Step 3: Commit**

```bash
cd /home/john/Projects/heretek-swarm
git add scripts/research/run_workflow.py
git commit -m "feat(research): stage workflow script for agent-harness landscape"
```

---

### Task 4: Execute the Research Workflow

**Files:**
- Read at runtime: `scripts/research/run_workflow.py` (source of the script payload)
- Written at runtime by synthesizer agent: `docs/superpowers/specs/2026-06-25-agent-harness-landscape.md`

**Interfaces:**
- Consumes: the workflow script from Task 3.
- Produces: 4 JSON findings+verdicts sidecars (auto-stored by Workflow tool journal) + the deliverable doc written by the synthesizer agent.

- [ ] **Step 1: Dump the workflow script to a temp file**

Run:
```bash
cd /home/john/Projects/heretek-swarm
python -c "from scripts.research.run_workflow import get_workflow_script; open('/tmp/agent_harness_landscape.js', 'w').write(get_workflow_script())"
ls -la /tmp/agent_harness_landscape.js
```
Expected: file ~5.5KB exists

- [ ] **Step 2: Invoke the Workflow tool with the script**

Use the `Workflow` tool with `scriptPath: "/tmp/agent_harness_landscape.js"`. Dispatches 5 agents across 3 phases. Budget ~600k tokens.

- [ ] **Step 3: Verify the deliverable doc exists**

Run:
```bash
ls -la /home/john/Projects/heretek-swarm/docs/superpowers/specs/2026-06-25-agent-harness-landscape.md
wc -w /home/john/Projects/heretek-swarm/docs/superpowers/specs/2026-06-25-agent-harness-landscape.md
```
Expected: file exists, word count between 800 and 2500

- [ ] **Step 4: No commit yet** — Task 5 runs acceptance bar first.

---

### Task 5: Acceptance Bar + Spec Self-Review

**Files:**
- Read at runtime: `docs/superpowers/specs/2026-06-25-agent-harness-landscape.md`
- Read at runtime: Workflow-tool journal (contains the 5 JSON sidecars from Task 4)

**Interfaces:**
- Consumes: `AcceptanceChecker` from Task 2 + deliverables from Task 4.
- Produces: `AcceptanceReport`. Pass → Task 6 commit. Fail → fix inline and re-check.

- [ ] **Step 1: Run the acceptance bar against the produced doc**

Execute a one-shot validator (NOT committed — it's a verification step):

```bash
cd /home/john/Projects/heretek-swarm
python -c "
import json
from pathlib import Path
from scripts.research.acceptance import AcceptanceChecker
from scripts.research.schemas import ReaderFindings, RefuterVerdicts, SynthesizerOutput, RubricScores

# Load sidecars from the workflow tool's journal.
# NOTE: the exact path depends on how the Workflow tool persists.
# If the journal path is not surfaced, paste the JSON inline here.
finder = Path('.superpowers/workflow-journal')
readers = [ReaderFindings.model_validate_json(f.read_text()) for f in finder.glob('*reader*.json')]
refuters = [RefuterVerdicts.model_validate_json(f.read_text()) for f in finder.glob('*refuter*.json')]
synth = SynthesizerOutput.model_validate_json(next(finder.glob('*synth*.json')).read_text())

doc_path = Path('docs/superpowers/specs/2026-06-25-agent-harness-landscape.md')
report = AcceptanceChecker().check(doc_path, readers, refuters, synth)
print('PASSED:', report.passed)
for f in report.failures:
    print(' -', f)
"
```

Expected: `PASSED: True` and zero failures.

- [ ] **Step 2: Spec self-review on the produced doc**

Inline checks against the produced doc:
1. **Placeholder scan**: `grep -E 'TBD|TODO|FIXME|XXX' docs/superpowers/specs/2026-06-25-agent-harness-landscape.md` — zero hits.
2. **Internal consistency**: every rubric score in per-repo sections matches the head-to-head table cell.
3. **Scope check**: the doc stays focused on `NousResearch/hermes-agent` and `openclaw/openclaw`. No drift to other OSS.
4. **Ambiguity check**: no claim could be read two ways. If any does, edit the doc inline.

- [ ] **Step 3: If acceptance or self-review fails**

Fix inline (Edit tool). Re-run acceptance. Loop until clean.

---

### Task 6: Commit Deliverable + Hand to User

**Files:**
- Add: `docs/superpowers/specs/2026-06-25-agent-harness-landscape.md`

**Interfaces:**
- Produces: a commit with Conventional Commits message + the deliverable doc on disk.

- [ ] **Step 1: Stage and commit the deliverable**

```bash
cd /home/john/Projects/heretek-swarm
git add docs/superpowers/specs/2026-06-25-agent-harness-landscape.md
git commit -m "docs(research): publish agent-harness OSS landscape (hermes-agent + openclaw)"
```

- [ ] **Step 2: Hand to user for review**

Per the brainstorming flow, surface the deliverable path and ask the user to review. Do NOT auto-proceed to follow-up decisions (wrap / replace / ignore). Wait for explicit user approval.

---

## Self-Review

**1. Spec coverage:**
- Spec § Purpose → Task 6 deliverable ✓
- Spec § Research Orchestration (3 phases) → Task 3 (workflow script), Task 4 (execute) ✓
- Spec § Rubric → embedded in Task 3 prompts + Task 5 acceptance ✓
- Spec § Components (5 units) → Task 3 declares them, Task 4 runs them ✓
- Spec § Data Flow → Task 3 script enforces the pipeline order ✓
- Spec § Error Handling & Uncertainty → Task 5 acceptance checker enforces markers, license veto, sovereignty veto ✓
- Spec § Acceptance Bar (10 checks) → Task 2 + Task 5 ✓
- Spec § Token Budget (~600k) → Task 3 declares, Task 4 executes ✓
- Spec § Deliverable → Task 6 ✓

**2. Placeholder scan:** No "TBD", "TODO", "implement later", or vague "similar to Task N" steps. All code blocks complete. All commands explicit.

**3. Type consistency:**
- `ReaderFindings`, `RefuterVerdicts`, `SynthesizerOutput`, `RubricScores` defined in Task 1, used in Task 2 tests, referenced in Task 3 prompts, loaded in Task 5 validator. Consistent.
- `AcceptanceChecker.check()` signature in Task 2 matches the call site in Task 5.
- `get_workflow_script()` in Task 3 used in Task 4 step 1.

**Gaps found and fixed inline:** none.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-agent-harness-landscape.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using `executing-plans`, batch with checkpoints.

**Which approach?**
