# Rejected items

Items that did not pass the D7 vetting bar, with the reason for rejection. Each entry is preserved here so the decision is auditable; remove only when the item is reconsidered.

<!-- Newest entries at the top. -->

- `microsoft/pyright` — D5/D15 scope rejection (NOT a D7 quality fail): the `python` plugin ships `ruff` as both LSP and skill per the plan's "pragmatic" note; adding pyright on top would mean two tools, two install steps, two config files, and overlapping diagnostics. D7 vetting passed (15,562★, MIT, pushed 2026-08-04, zero advisories) — see ADR `catalog/reviews/python-pyright.md`. Revisit if the plugin later needs strict PEP 484 type checking beyond ruff's lint scope.

- `aitmpl/security-scanner` — D7 source-audit fail: shells out to `semgrep` + `bandit` + `gitleaks` + ad-hoc grep; per D7 "shelling out to a subprocess is not" trivial. Also D6: would not fit Layer 1 sub-100ms budget. ADR: `catalog/reviews/aitmpl-security-scanner.md`.
- `aitmpl/dependency-checker` — D7 source-audit fail: chains 4 external subprocess invocations (`npm audit`, `npx npm-check-updates`, `safety`, `cargo audit`) with `|| true` suppression. D6: 10+ second npm-check tool incompatible with Layer 1. ADR: `catalog/reviews/aitmpl-dependency-checker.md`.
- `aitmpl/smart-formatting` — D7 source-audit fail: shells out to `prettier`, `black`, `gofmt -w`, `rustfmt`, `php-cs-fixer`. D6: rewrites the file in `PostToolUse`, racing with the agent's diff. D5/D15: overlaps with Layer 1 `fast_gate.py` (format-check) and Layer 3 pre-commit (format-fix). ADR: `catalog/reviews/aitmpl-smart-formatting.md`.
- `aitmpl/run-tests-after-changes` — D7 source-audit fail: shells out to `npm run test:quick`. D6 design: PostToolUse test-running is a CI concern, not a hook concern; the hook also silently swallows all test output (only emits a ✅/⚠️ emoji), defeating the purpose of an in-loop hook. ADR: `catalog/reviews/aitmpl-run-tests-after-changes.md`.
- `aitmpl/change-tracker` — D7 source-audit would pass (shell builtins only: `echo`, `$(date)`, `>>`); rejected on D5/D15 instead — git already tracks every edit and Layer 3 wraps git with pre-commit; adding a parallel `~/.claude/changes.log` audit trail is duplicative and writes outside the user's repo. ADR: `catalog/reviews/aitmpl-change-tracker.md`.
