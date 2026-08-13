# Terminal-Bench A/B — `abc1234`

**Trigger:** `push`
**Actor:** test-runner
**Tier:** `quick` (8 tasks)
**Model:** `claude-test` (via `http://localhost`)

## Headline

| Agent | Pass rate | Passed | Failed | Wall-clock | Tokens |
|---|---|---|---|---|---|
| **A — with heretek** | 62.5% | 5/8 | 3/8 | 300s | 12,000 |
| **B — baseline** | 37.5% | 3/8 | 5/8 | 400s | 15,000 |
| **Δ** | **+25%** | **+2** | — | **-100s** | **-3000** |

## Per-task

| Task | A | B | Notes |
|---|---|---|---|
| cancel-async-tasks | ✓ (30s) | ✓ (40s) | both |
| chess-best-move | ✓ (40s) | ✗ (50s) | A wins |
| configure-git-webserver | ✓ (35s) | ✓ (45s) | both |
| constraints-scheduling | ✓ (45s) | ✗ (60s) | A wins |
| count-dataset-tokens | ✓ (25s) | ✓ (35s) | both |
| crack-7z-hash | ✗ (50s) | ✗ (60s) | both fail |
| extract-elf | ✗ (35s) | ✗ (50s) | both fail |
| fix-git | ✗ (40s) | ✗ (60s) | both fail |

## Tasks where heretek helped

- `chess-best-move` (A pass, B fail)
- `constraints-scheduling` (A pass, B fail)

## Tasks where heretek hurt

(none)
