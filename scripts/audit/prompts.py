"""Cluster lane prompt templates for the harness self-audit.

Five constants — one per cluster (A-E) per the spec's methodology table.
Each template is the prompt an Explore-agent receives; it embeds the
per-finding schema so the agent returns valid cards. Placeholders:
{repo_root}  — absolute path to the repo under audit
{commit_sha} — git HEAD commit SHA at audit time (snapshot per spec)

Use `render_prompt(letter, repo_root, commit_sha)` to get a ready-to-paste
prompt, or run the CLI:

    python scripts/audit/prompts.py <A|B|C|D|E> --repo-root PATH --commit-sha SHA
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ClusterPrompt:
    letter: str
    title: str
    principles: tuple[str, ...]
    evidence_strategy: str
    template: str


# ---------- Cluster A: Readability & quality bar ----------
_A_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster A:
**Readability & quality bar**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Small, focused functions
- Clear, consistent naming
- Comments explain WHY, not WHAT
- DRY, KISS, YAGNI
- No dead code, no copy-paste duplication

**Evidence-collection strategy**
- File size, function size, cyclomatic + cognitive complexity
- Lint output (ruff, pylint if present)
- Line counts, duplication scan
- For each candidate finding, cite a numeric metric and the tool that produced it.

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise. Prefer false positives over missed findings; synthesis will
re-verify.

**Output format** — one YAML document per finding (or one YAML list of findings).
Return ONLY findings; do not write prose.

```yaml
- finding_id: A-NNN                 # sequential, zero-padded
  cluster: "Readability & quality bar"
  principle: "<one-line principle statement>"
  severity: critical|high|medium|low|info
  adversarial_posture: violated|partial|justified
  evidence:
    code_refs: ["<path>:<start_line>-<end_line>"]
    file: "<path>"
    line_range: [<start>, <end>]
    metric: "<numeric metric + tool that produced it>"
  failure_scenario: "<concrete inputs/state -> wrong output/crash>"
  recommended_action: refactor|document|suppress|accept|escalate
  rationale: "<one sentence: the why, not the what>"
  principle_reference: "Code quality > <subsection> > <principle>"
  drift_signals: []  # any "this was already flagged in PR #N" notes
```

If a principle is fully met across the in-scope code, return an empty list. Do
NOT fabricate findings to fill quotas.
"""


# ---------- Cluster B: Design & architecture ----------
_B_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster B:
**Design & architecture**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- SOLID (especially SRP, OCP, DIP)
- Composition over inheritance
- Tell, don't ask
- Law of Demeter
- Separation of concerns; loose coupling, high cohesion

**Evidence-collection strategy**
- Import graph (look for cycles, deep inheritance)
- Class/method counts per file (god-file detection: > 500 LOC + many responsibilities)
- Base-class fanout (a base used by > 5 concrete classes may be over-reaching)
- Module boundaries (does `scripts/scanners/` import from `tests/`? vice versa?)

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card as Cluster A. Use finding_id
prefix `B-NNN`. Cluster field: `"Design & architecture"`.
"""


# ---------- Cluster C: Correctness & safety ----------
_C_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster C:
**Correctness & safety**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Explicit error handling (no silent exception swallowing)
- Input validation at boundaries
- Type hints on public functions
- Idempotent operations where possible
- Immutability over mutation when reasonable
- Defensive programming only where genuine threat exists

**Evidence-collection strategy**
- try/except scan: bare `except:` or `except Exception: pass` patterns
- Type-hint coverage scan on public functions (rough: missing `->` on > 30% of
  public callables in a module is a cluster-C finding)
- Mutability patterns: top-level mutable defaults, module-level dict/list
  mutations
- Parameter validation markers: functions that consume `Path` / `int` /
  untyped `dict` from external sources without validation

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card. Use finding_id prefix `C-NNN`.
Cluster field: `"Correctness & safety"`.
"""


# ---------- Cluster D: Testing & verification ----------
_D_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster D:
**Testing & verification**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Test pyramid (many unit, fewer integration, few E2E)
- Test isolation (no shared mutable state between tests)
- Coverage of critical paths (not 100% for its own sake)
- TDD evidence in commit history (red-green-refactor visible in `git log -- <file>`)
- No flaky-test markers (sleeps, time-dependent assertions, network mocks)
- No test smells (asserts on private attrs, oversized fixtures)

**Evidence-collection strategy**
- pytest markers: are `integration` tests actually marked? (run
  `grep -rE "@pytest.mark.integration" tests/`)
- conftest.py review: shared fixtures, autouse patterns, module-level state
- Test counts per source module (rough: < 1 test per 50 LOC of source = smell)
- Fixture audit: oversized fixtures used by > 20 tests = god-fixture
- Commit history: spot-check 3 source files for TDD-shaped commit pairs

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card. Use finding_id prefix `D-NNN`.
Cluster field: `"Testing & verification"`.
"""


# ---------- Cluster E: Operations & docs ----------
_E_TEMPLATE = """\
You are auditing the heretek-claude-harness repository for Cluster E:
**Operations & docs**.

Repo: {repo_root}
Snapshot commit: {commit_sha}

**Principles in scope**
- Observability: structured logs, no bare `print()` in library code
- CI/CD maturity: workflows run on every PR, fail loud
- Feature flags / rollback: changes have a way back
- Security hygiene: pinned deps, no shell-injection sinks, secret-handling
- Doc freshness: README matches reality, ADRs for non-trivial decisions
- Onboarding: a new contributor can be productive in < 1 day

**Evidence-collection strategy**
- log/print scan: `grep -rnE "^\\s*print\\(" scripts/` (library code should
  use the `logging` module)
- Requirements freshness: `requirements.txt` pins, `requirements.lock.txt`
  presence, last-updated date
- GH workflow audit (READABILITY only — does the YAML parse? does each step
  have a name? timeout set? — NOT enforcement behavior, that's Spec 3)
- Docstring coverage on public functions
- README freshness (does install command work? do plugin counts match?)
- Look for missing ADRs on non-trivial decisions

**Posture: ADVERSARIAL.** Assume each principle is being violated until evidence
proves otherwise.

**Output format** — same per-finding YAML card. Use finding_id prefix `E-NNN`.
Cluster field: `"Operations & docs"`.
"""


CLUSTERS: dict[str, ClusterPrompt] = {
    "A": ClusterPrompt(
        letter="A",
        title="Readability & quality bar",
        principles=(
            "Small, focused functions",
            "Clear, consistent naming",
            "Comments explain WHY, not WHAT",
            "DRY, KISS, YAGNI",
            "No dead code, no copy-paste duplication",
        ),
        evidence_strategy="file/function size, complexity metrics, lint, duplication scan",
        template=_A_TEMPLATE,
    ),
    "B": ClusterPrompt(
        letter="B",
        title="Design & architecture",
        principles=(
            "SOLID (SRP, OCP, DIP)",
            "Composition over inheritance",
            "Tell, don't ask",
            "Law of Demeter",
            "Separation of concerns; loose coupling, high cohesion",
        ),
        evidence_strategy="import graph, god-file detection, base-class fanout, module boundaries",
        template=_B_TEMPLATE,
    ),
    "C": ClusterPrompt(
        letter="C",
        title="Correctness & safety",
        principles=(
            "Explicit error handling",
            "Input validation at boundaries",
            "Type hints on public functions",
            "Idempotent operations",
            "Immutability over mutation",
            "Defensive programming where threat exists",
        ),
        evidence_strategy="try/except scan, type-hint coverage, mutability patterns, validation markers",
        template=_C_TEMPLATE,
    ),
    "D": ClusterPrompt(
        letter="D",
        title="Testing & verification",
        principles=(
            "Test pyramid",
            "Test isolation",
            "Coverage of critical paths",
            "TDD evidence in commit history",
            "No flaky-test markers",
            "No test smells",
        ),
        evidence_strategy="pytest markers, conftest review, test counts per module, fixture audit, commit history",
        template=_D_TEMPLATE,
    ),
    "E": ClusterPrompt(
        letter="E",
        title="Operations & docs",
        principles=(
            "Observability",
            "CI/CD maturity",
            "Feature flags / rollback",
            "Security hygiene",
            "Doc freshness",
            "Onboarding",
        ),
        evidence_strategy="log/print scan, requirements freshness, GH workflow audit, docstring coverage, README freshness, ADR presence",
        template=_E_TEMPLATE,
    ),
}


def render_prompt(letter: str, repo_root: Path, commit_sha: str) -> str:
    """Substitute placeholders and return the ready-to-paste prompt."""
    cp = CLUSTERS[letter]  # raises KeyError for unknown letters
    return cp.template.replace("{repo_root}", str(repo_root)).replace("{commit_sha}", commit_sha)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "cluster",
        choices=sorted(CLUSTERS.keys()),
        help="Cluster letter (A, B, C, D, or E).",
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--commit-sha", required=True, help="Audit snapshot commit SHA.")
    args = parser.parse_args(argv)
    print(render_prompt(args.cluster, args.repo_root, args.commit_sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
