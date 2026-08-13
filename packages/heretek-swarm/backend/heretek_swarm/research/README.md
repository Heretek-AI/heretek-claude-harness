# Research Tier

Code in this package is **research-grade** — it computes and reports
metrics that the production runtime does not actuate on. Per the
Zero-Trust Architecture Audit (2026-06-01) and M-arch PR #8 (see
PLAN.md), the 22,979 LOC of consciousness / emergence / evolution
code is either:

- **Option A**: Research code dressed as production runtime
  (IIT phi computation is intractable in the general case; the
  1,013 LOC of `iit_phi.py` is almost certainly computing an
  approximation or returning a stub value)
- **Option B**: Aspirational telemetry (values are computed and
  reported to the dashboard but do not actuate any behavior change)

**Recommendation**: extract to `research/`, stop running in the
hot path. The Prime Directive's consciousness metrics are aspirational;
the current runtime does not validate them. Honest move: commit to
a research effort (separate workstream) or extract from production.

## Layout

This package re-exports from the legacy locations for backward
compatibility:

- `heretek_swarm.consciousness.iit_phi` → `heretek_swarm.research.IITPhi`
- `heretek_swarm.consciousness.gwt` → `heretek_swarm.research.GWT`
- `heretek_swarm.consciousness.fep` → `heretek_swarm.research.FEP`
- `heretek_swarm.consciousness.fep_active_inference` → `heretek_swarm.research.FEP_ACTIVE_INFERENCE`
- `heretek_swarm.consciousness.self_model` → `heretek_swarm.research.SELF_MODEL`
- `heretek_swarm.consciousness.introspection` → `heretek_swarm.research.INTROSPECTION`
- `heretek_swarm.consciousness.ast` → `heretek_swarm.research.AST`
- `heretek_swarm.collective.emergent_detection` → `heretek_swarm.research.EMERGENT_DETECTION`
- `heretek_swarm.collective.emergent_detection_types` → `heretek_swarm.research.EMERGENT_DETECTION_TYPES`
- `heretek_swarm.collective.evolution_engine` → `heretek_swarm.research.EVOLUTION_ENGINE`
- `heretek_swarm.collective.emergence_analyzer` → `heretek_swarm.research.EMERGENCE_ANALYZER`

New code should import from `heretek_swarm.research` directly.
Existing imports from `heretek_swarm.consciousness` and
`heretek_swarm.collective` continue to work but are deprecated.

## Migration status (as of 2026-06-01)

- ✅ `research/` namespace created
- ✅ Public API re-exported (lazy)
- ⏳ Physical file move deferred to a follow-up PR
- ⏳ Production hot-path callers audited and migrated: TODO
