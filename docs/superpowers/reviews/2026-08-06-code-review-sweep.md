# Whole-codebase review sweep (2026-08-06)

> Date: 2026-08-06. Sweep: 3 parallel reviewers across
> `catalog/` + `scripts/`, `plugins/` + `plugins/hooks/`, `tests/`.
> Tracking: each P0/P1 finding tracked as a GitHub issue; P2/P3
> captured inline below for triage.

## Methodology

- 3 agents reviewing concurrently against D7, D11 SHA-ride, D15
  hooks-ownership, and general security/correctness.
- Each agent verdict in this sweep reviewed for evidence before
  promotion to "filed-as-issue" status.
- All filenames + line numbers cited are relative to repo root.

---

## P0 — Critical / ship-blocking

### 1. `refresh_pins.py:148-150` — path injection via upstream metadata
- **Severity:** P0 (security, supply-chain integrity)
- **Evidence:** `default_branch = repo_meta.get("default_branch") or "main"`
  reflected verbatim into `/git/ref/heads/{default_branch}` URL.
- **Failure scenario:** catalog `upstream` resolves to attacker-controlled repo (e.g., typo-squat). Attacker sets `default_branch` to an arbitrary ref. `refresh_pins` records that ref's SHA in the catalog → silent dependency swap on next marketplace bump.
- **Fix sketch:** regex-allowlist `^[A-Za-z0-9._/-]+$` on `upstream` and `default_branch` before any URL build. Reject and log otherwise.

### 2. `security_scan.py:70` — `_shallow_clone` upstream injection
- **Severity:** P0 (security)
- **Evidence:** `["git", "clone", "--depth", "1", f"https://github.com/{upstream}.git", "."]` — `upstream` is catalog-controlled, no validation.
- **Failure scenario:** same upstream typo-squat → clone arbitrary repo into `/tmp/scan/`; subsequent steps operate on attacker code (read by `git show`, etc.).
- **Fix sketch:** allowlist `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` on `upstream` before URL build.

### 3. `drift_detector.py:27-29` — `session_id` path traversal
- **Severity:** P0 (security)
- **Evidence:** `SESSION_STATE_DIR / f"{session_id}.json"` writes attacker-controlled session_id into `.heretek/session_state/`.
- **Failure scenario:** malicious stdin payload carries `session_id="../../etc/passwd"` → writes JSON content into arbitrary file in repo tree.
- **Fix sketch:** `re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session_id) or raise ValueError`.

---

## P1 — High-confidence bugs

### 4. `refresh_pins.py:152` — wrong ref pinned on first-party style items
- **Severity:** P1 (correctness, regresses security posture)
- **Evidence:** uses `git/ref/heads/{default_branch}` HEAD instead of latest release tag. Catalog items are pinned to release SHAs by convention.
- **Failure scenario:** `--update-shas` overwrites pinned release SHA with HEAD (possibly unreleased/malicious) and silently bumps marketplace.
- **Fix sketch:** call `_get_latest_release_sha` (already used by `security_scan.py`) instead of HEAD.

### 5. `refresh_pins.py:91` — false-positive license drift when `item.license` missing
- **Severity:** P1 (correctness)
- **Evidence:** `spdx` defaults to `"NOASSERTION"`; `(item.get("license") or "").upper()` → `""`; never equal → drift fires on every missing-license item.
- **Fix sketch:** skip drift if `item.license` is absent, or treat `NOASSERTION` as "unknown, not drift."

### 6. `stale_dep_intercept.py:51` — off-by-one in stale threshold
- **Severity:** P1 (correctness)
- **Evidence:** `return p[1] <= l[1] - 2` fires on exactly 1-minor-behind; docstring says "stale iff >=2 minor behind."
- **Fix sketch:** `return p[1] + 1 < l[1]` (stale iff diff >= 2).

### 7. `security_scan.py:143` — `relative_to` crash when catalog outside repo_root
- **Severity:** P1 (portability, crashes)
- **Evidence:** `str(catalog_path.relative_to(repo_root))` — if catalog supplied as absolute path outside `repo_root`, `ValueError`.
- **Fix sketch:** `try: rel = catalog_path.relative_to(repo_root); except ValueError: rel = Path(os.path.relpath(catalog_path, repo_root))`.

### 8. `security_scan.py:130` / `issue_drafter.py:146` — branch name injection
- **Severity:** P1 (security)
- **Evidence:** `branch = f"security-scan/{item_id}-{new_sha[:12]}"` — `item_id` and `new_sha` uncontrolled; SHA may not be hex if upstream lookups fail (`"0" * 40`).
- **Failure scenario:** catalog item `id: foo/bar` → branch `security-scan/foo/bar-...`; `git checkout -b` semantics shift, may push to nested ref or refuse.
- **Fix sketch:** `item_id` against `^[A-Za-z0-9._-]+$`; SHA against `^[0-9a-f]{40}$`.

### 9. `security_scan.py:166` — hardcoded `git checkout main`
- **Severity:** P1 (portability)
- **Evidence:** returns to `main` after each item — fails if repo default is `master`/`develop`/`trunk`.
- **Fix sketch:** read default branch via `gh repo view --json defaultBranch` or pass from outer config.

### 10. `security_scan.py:222-225` — `/tmp/scan` shared scratch
- **Severity:** P1 (race + symlink attack)
- **Evidence:** `Path("/tmp") / "scan" / f"{plugin_name}-{item.get('id')}-{latest_sha[:12]}"` — collisions across items; predictable path = symlink attack.
- **Fix sketch:** `tempfile.mkdtemp(prefix="scan-", dir=Path("/tmp"))`.

### 11. `plugins/hooks/scripts/fast_gate.py:132-139` — linter internal error blocks Edit
- **Severity:** P1 (operational: linter flake freezes agent)
- **Evidence:** `if result.returncode == 0: return 0\nif ...: print(...)\nreturn 2`. Linters return exit-1 on parse failures, OOM, bad config → DENIES every Edit/Write.
- **Failure scenario:** biome chokes on corrupt config → all subsequent edits blocked; agent loses loop.
- **Fix sketch:** treat returncode ≥ 2 (and/or stderr contains "internal error" markers) as fail-open (exit 0).

### 12. `plugins/hooks/scripts/__pycache__/` — orphan bytecode tracked + no .gitignore
- **Severity:** P1 (build correctness + repo hygiene)
- **Evidence:** directory contains `.cpython-312.pyc`, `.cpython-314.pyc`, `.cpython-315.pyc` (3 Python versions, two of which belong to runtime not in CI). No `.gitignore` line excludes `**/__pycache__/`.
- **Failure scenario:** plugin loads with Python version that doesn't match the compiled `.pyc` → `ImportError: bad magic number` OR silently stale bytecode.
- **Fix sketch:** add `plugins/**/__pycache__/` to `.gitignore`; `git rm -rf --cached` the orphan; document `python -B` or wrapper invocations.

### 13. `plugins/hooks/scripts/install_git_hooks.sh:32-38` — idempotency claim lies
- **Severity:** P1 (UX: re-install always runs)
- **Evidence:** comment says "idempotent" but `--overwrite` re-uses `pre-commit install` unconditionally; never `exit 0` on already-installed.
- **Fix sketch:** detect existing `.git/hooks/pre-commit` symlink and `exit 0` early, or only call `pre-commit install` when state has drifted.

### 14. `quality_gate.py:26-32` (`parse_scope`) — non-validated path becomes cwd
- **Severity:** P1 (UX: silent tool run from wrong dir)
- **Evidence:** any non-empty arg ≠ "diff" is treated as path; no path existence check.
- **Failure scenario:** typo `--diff ` vs `--dit` runs all slow analyzers from `/no/such/dir`.
- **Fix sketch:** validate `arg` is `"" | "diff" | "repo" | <existing-path>`.

---

## P2 — Medium / latent-risk

### 15. `drift_detector.py:188` + `lookup_gate.py` + `stale_dep_intercept.py` — silently swallow JSON errors
- Severity: P2. Hook pipeline hides bugs. Fix: log on `JSONDecodeError`.

### 16. `refresh_pins.py:60-63` — `_github_get` swallows all errors
- Severity: P2. Network failures masquerade as `stars=0` and flood drift table.

### 17. `refresh_pins.py:27` — dead `import yaml`
- Severity: P2 (junk import). Cosmetic.

### 18. `plugins/hooks/scripts/fast_gate.py:115` — `argv_template[1:]` cosmetic only
- Severity: P2. The biome branch uses inline npx; `{}` template never hit.

### 19. `plugins/hooks/scripts/fast_gate.py:23` — unused `from typing import Optional`
- Severity: P2. Dead import.

### 20. `plugins/hooks/hooks/hooks.json` PreToolUse references `${CLAUDE_PROJECT_DIR}/scripts/scanners/ast_grep_scanner.py`
- Severity: P2 (D15 violation). Path outside the plugin tree. Fix: ship scanner inside `plugins/hooks/scripts/scanners/` or use `${CLAUDE_PLUGIN_ROOT}`.

### 21. `plugins/hooks/hooks/hooks.json` PostToolUse — 4 separate matcher entries
- Severity: P2 (schema smell). Should be single entry with hook array.

### 22. `drift_detector.py:131-132` — redundant `len(set) == len(recent_diffs)` clause
- Severity: P3. Minor.

### 23. `counterfactual_diffs_spike.py:54-56` — `+# counterfactual:` annotation breaks unified diff format
- Severity: P2. Annotation inlines a `+` line after another `+`. Move to sidecar.

---

## P3 — Style / nit

### 24. `generate_marketplace.py:58` — `plugin_root=""` yields `"//plugins/foo"`
- Severity: P3 cosmetic.

### 25. `freshness_tokens.py:81` — empty-lines state may print even when not applicable
- Severity: P3 minor.

### 26. `issue_drafter.py:34-39` — search-injection via `title` in `q`
- Severity: P2 (security). Use `params` dict, not f-string.

---

## P3 — tests/CI observations (Agent 3)

### 27. Untracked `tests/fixtures/fast_gate/{good,bad}_sample.{js,py,rs}` + `sample.md`
- Severity: P3. Brittle design — if `create_samples` autouse is removed, tests fail silently without signal.

### 28. `test_run_fails_open_on_time_budget` mutates `fast_gate.subprocess.run`
- Severity: P3. Sequential execution only; would race under pytest-xdist. Add locking if parallelism is added.

### 29. `fast_gate.py:parse_payload` accepts `tool_name` of any type
- Severity: P3. Not covered by tests; not exercised.

### 30. `fast_gate.py:dispatch` capture_output=True → potential `UnicodeDecodeError`
- Severity: P3. Unlikely with ruff/rustfmt/biome but real edge case.

---

## Summary

- **P0**: 3 (path injection × 2, session_id traversal × 1)
- **P1**: 11
- **P2**: 9
- **P3**: 7

Highest-leverage to ship:
1. Allowlist `upstream` + `default_branch` + `item_id` + `session_id` everywhere (closes #1, #2, #3, #8).
2. Switch `refresh_pins.py` from HEAD to release SHA (#4).
3. Fix the false-positive license drift (#5).
4. Fix stale-minor off-by-one (#6).
5. `mkdtemp` for scratch dirs (#10).
