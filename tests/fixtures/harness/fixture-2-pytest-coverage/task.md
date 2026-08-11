# Bring src/calc.py to ≥80% coverage

The module `src/calc.py` has a few pure functions but only one test exists in
`tests/test_calc.py`. Add tests so `pytest --cov=src.calc --cov-branch
--cov-fail-under=80` passes when run from the repo root.

Constraints:
- Tests must live in `tests/test_calc.py`.
- Do not modify `src/calc.py`.
- Cover all branches in the existing arithmetic helpers.
