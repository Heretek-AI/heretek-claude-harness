# Terminal-Bench A/B — `abc1234`

**Trigger:** `push`
**Actor:** test-runner
**Tier:** `quick` (8 tasks)
**Model:** `claude-test` (via `http://localhost`)

## Headline

| Agent | Pass rate | Passed | Failed | Wall-clock | Tokens |
|---|---|---|---|---|---|
| **A — with heretek** | 62.5% | 5/8 | 3/8 | 845s | 412,345 |
| **B — baseline** | 50.0% | 4/8 | 4/8 | 887s | 425,645 |
| **Δ** | **+12.5%** | **+1** | — | **-42s** | **-13300** |

## Per-task

| Task | A | B | Notes |
|---|---|---|---|
| tb-001-fix-permissions | ✓ (45s) | ✓ (52s) | both |
| tb-002-edit-json | ✓ (60s) | ✓ (65s) | both |
| tb-003-build-c | ✗ (180s) | ✗ (175s) | both fail |
| tb-004-build-system | ✗ (120s) | ✗ (175s) | both fail |
| tb-005-network-fetch | ✓ (120s) | ✗ (60s) | A wins |
| tb-006-chmod | ✓ (30s) | ✓ (35s) | both |
| tb-007-rotate | ✗ (90s) | ✗ (95s) | both fail |
| tb-008-install | ✓ (200s) | ✗ (195s) | A wins |

## Tasks where heretek helped

- `tb-005-network-fetch` (A pass, B fail)
- `tb-008-install` (A pass, B fail)

## Tasks where heretek hurt

(none)
