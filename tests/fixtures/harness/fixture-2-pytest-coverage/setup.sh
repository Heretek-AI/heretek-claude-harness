#!/usr/bin/env bash
set -euo pipefail
mkdir -p src tests
cat > src/calc.py <<'EOF'
"""Tiny arithmetic helpers used by the demo CLI."""

def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def multiply(a: float, b: float) -> float:
    return a * b


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError("divide by zero")
    return a / b


def safe_divide(a: float, b: float) -> float | None:
    if b == 0:
        return None
    return a / b


def classify(n: int) -> str:
    if n < 0:
        return "negative"
    if n == 0:
        return "zero"
    if n % 2 == 0:
        return "even"
    return "odd"
EOF
cat > tests/test_calc.py <<'EOF'
from src.calc import add


def test_add_positive() -> None:
    assert add(2, 3) == 5
EOF
cat > pyproject.toml <<'EOF'
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]

[tool.coverage.run]
source = ["src"]

[tool.coverage.report]
fail_under = 80
EOF
git init -q -b main
git add .
git -c user.email=t@t -c user.name=t commit -q -m init
