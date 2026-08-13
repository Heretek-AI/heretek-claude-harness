"""Tests for the Phase 1.4 rich / questionary / rich-click integration."""

from __future__ import annotations

from io import StringIO

from heretek_swarm.cli.rich_compat import (
    configure_rich_click,
    console,
    print_consensus_results,
    print_deliberation_results,
    print_startup_banner,
)
from rich.console import Console


class _FakeSwarm:
    """Minimal stand-in for AutonomousSwarm used in display tests."""

    def __init__(self, status: dict[str, str] | None = None) -> None:
        # Use `None` as the default sentinel so callers can pass `{}` to
        # test the empty-status branch (Python's `{} or default` would
        # incorrectly fall back to the default for an empty dict).
        if status is None:
            self._status = {"postgres": "✓ healthy", "redis": "✗ down"}
        else:
            self._status = status

    def get_startup_status(self) -> dict[str, str]:
        return self._status


def test_console_is_rich_console() -> None:
    """The shared console is a rich.console.Console (not stdlib)."""
    assert isinstance(console, Console)


def test_configure_rich_click_sets_command_groups() -> None:
    """configure_rich_click wires up COMMAND_GROUPS for the help output."""
    import rich_click

    configure_rich_click()
    assert "heretek-swarm" in rich_click.COMMAND_GROUPS
    groups = rich_click.COMMAND_GROUPS["heretek-swarm"]
    labels = {g["name"] for g in groups}
    assert {"Core Operations", "Configuration", "Monitoring"} <= labels


def test_print_startup_banner_renders_components() -> None:
    """Startup banner prints all components with status icons."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120)

    import heretek_swarm.cli.rich_compat as rc

    original_console = rc.console
    rc.console = test_console
    try:
        print_startup_banner(_FakeSwarm())
    finally:
        rc.console = original_console

    output = buf.getvalue()
    assert "postgres" in output
    assert "redis" in output
    assert "✓" in output
    assert "✗" in output


def test_print_startup_banner_handles_empty_status() -> None:
    """Empty status dict produces no output, no error."""
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120)
    import heretek_swarm.cli.rich_compat as rc

    original_console = rc.console
    rc.console = test_console
    try:
        print_startup_banner(_FakeSwarm(status={}))
    finally:
        rc.console = original_console
    assert buf.getvalue() == ""


def test_print_deliberation_results_handles_all_three_agents() -> None:
    """Deliberation table renders alpha, beta, charlie rows."""
    results = {
        "alpha": {"analyses": [{"analysis": "Proceed"}]},
        "beta": {"analyses": [{"analysis": "Approve with caveat"}]},
        "charlie": {"analyses": [{"analysis": "Reject: too risky"}]},
    }
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120)
    import heretek_swarm.cli.rich_compat as rc

    original_console = rc.console
    rc.console = test_console
    try:
        print_deliberation_results(results)
    finally:
        rc.console = original_console
    out = buf.getvalue()
    assert "ALPHA" in out
    assert "BETA" in out
    assert "CHARLIE" in out
    assert "Proceed" in out
    assert "Reject" in out


def test_print_deliberation_results_handles_errors() -> None:
    """An agent with an 'error' key renders as an error row."""
    results = {"alpha": {"error": "timeout"}}
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120)
    import heretek_swarm.cli.rich_compat as rc

    original_console = rc.console
    rc.console = test_console
    try:
        print_deliberation_results(results)
    finally:
        rc.console = original_console
    assert "timeout" in buf.getvalue()


def test_print_consensus_results_includes_decision_and_breakdown() -> None:
    """Consensus output includes decision, confidence, and vote breakdown."""
    results = {
        "consensus_id": "abc-123",
        "decision": "approve",
        "confidence": 0.87,
        "total_rounds": 2,
        "votes": [
            {"agent_id": "alpha", "decision": "approve", "confidence": 0.9, "metadata": {"reasoning": "OK"}},
            {"agent_id": "beta", "decision": "approve", "confidence": 0.85, "metadata": {}},
            {"agent_id": "charlie", "decision": "reject", "confidence": 0.7, "metadata": {"reasoning": "Risk"}},
        ],
        "red_flags": ["red flag A"],
        "reasoning": "First reason; second reason",
    }
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False, width=120)
    import heretek_swarm.cli.rich_compat as rc

    original_console = rc.console
    rc.console = test_console
    try:
        print_consensus_results(results)
    finally:
        rc.console = original_console
    out = buf.getvalue()
    assert "abc-123" in out
    assert "approve" in out
    assert "0.87" in out
    assert "alpha" in out
    assert "charlie" in out
    assert "red flag A" in out
    assert "Breakdown" in out
