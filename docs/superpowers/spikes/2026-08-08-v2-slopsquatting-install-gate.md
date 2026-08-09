# v2: Slopsquatting-aware install gate

**Status:** 🔬 Spike
**Phase:** v2 (hooks + security)
**Date:** 2026-08-08

## Research question

Can we intercept `pip install` and `npm install` calls in the hooks plugin to validate package names against OSV-Scanner before allowing the install to proceed?

## Why

"Slopsquatting" — agents hallucinate package names; threat actors pre-register those names on PyPI/npm. The agent then unknowingly installs malware.

## Deliverable

- Spike: integrate OSV-Scanner into the hooks plugin's PreToolUse path for Bash commands matching install patterns.
- Decision criteria for promotion to ✅: prototype detects at least one known hallucinated package + integrates with existing fast_gate pattern.

## Evidence

- Doc 2 (Command Line Coding Agents Audit) cite #51 (DZone, Slopsquatting).
- Existing #70 (forbidden-pattern registry) covers post-install scanning; this is the pre-install gate.

## References

- Spec: `docs/superpowers/specs/2026-08-08-roadmap-restructure-design.md` §4.1
- Roadmap: `docs/superpowers/roadmap.md` §v2
