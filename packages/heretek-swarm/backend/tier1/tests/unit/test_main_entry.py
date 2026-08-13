"""Tests for CLI entry point (__main__.py) — Task 6 coverage lift."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tier1.__main__ import main


def _settings(api_host="0.0.0.0", api_port=8000, dashboard_path=""):
    """Build a mock settings object with the three attributes __main__ reads."""
    s = patch("tier1.__main__.get_settings").start()
    s.return_value.api_host = api_host
    s.return_value.api_port = api_port
    s.return_value.dashboard_path = dashboard_path
    return s


def test_main_serve_invokes_uvicorn(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["tier1", "serve", "--host", "127.0.0.1", "--port", "9000", "--reload"]
    )
    with (
        patch("tier1.__main__.uvicorn.run") as mock_run,
        patch("tier1.__main__.create_app", return_value="app") as mock_app,
    ):
        _settings(api_host="0.0.0.0", api_port=8000, dashboard_path="")
        result = main()
    assert result == 0
    mock_app.assert_called_once_with(dashboard_path=None)
    # First positional arg is the app, then host/port/reload kwargs.
    args, kwargs = mock_run.call_args
    assert args[0] == "app"
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9000
    assert kwargs["reload"] is True


def test_main_uses_settings_host_port_when_no_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "serve"])
    with (
        patch("tier1.__main__.uvicorn.run") as mock_run,
        patch("tier1.__main__.create_app", return_value="app"),
    ):
        _settings(api_host="1.1.1.1", api_port=5555, dashboard_path="")
        main()
    args, kwargs = mock_run.call_args
    assert kwargs["host"] == "1.1.1.1"
    assert kwargs["port"] == 5555
    assert kwargs["reload"] is False


def test_main_overrides_settings_with_args(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "serve", "--host", "1.2.3.4", "--port", "9000"])
    with (
        patch("tier1.__main__.uvicorn.run") as mock_run,
        patch("tier1.__main__.create_app", return_value="app"),
    ):
        _settings(api_host="0.0.0.0", api_port=8000, dashboard_path="")
        main()
    args, kwargs = mock_run.call_args
    assert kwargs["host"] == "1.2.3.4"
    assert kwargs["port"] == 9000


def test_main_uses_arg_dashboard_path_when_provided(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "serve", "--dashboard-path", "/tmp/arg"])
    with (
        patch("tier1.__main__.uvicorn.run"),
        patch("tier1.__main__.create_app", return_value="app") as mock_app,
    ):
        # settings has a different dashboard path — arg wins.
        _settings(api_host="0.0.0.0", api_port=8000, dashboard_path="/tmp/settings")
        main()
    mock_app.assert_called_once_with(dashboard_path=Path("/tmp/arg"))


def test_main_uses_settings_dashboard_path_when_arg_absent(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "serve"])
    with (
        patch("tier1.__main__.uvicorn.run"),
        patch("tier1.__main__.create_app", return_value="app") as mock_app,
    ):
        _settings(api_host="0.0.0.0", api_port=8000, dashboard_path="/tmp/from-settings")
        main()
    mock_app.assert_called_once_with(dashboard_path=Path("/tmp/from-settings"))


def test_main_no_dashboard_when_both_unset(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "serve"])
    with (
        patch("tier1.__main__.uvicorn.run"),
        patch("tier1.__main__.create_app", return_value="app") as mock_app,
    ):
        # Falsy/empty dashboard_path from settings → None passed through.
        _settings(api_host="0.0.0.0", api_port=8000, dashboard_path="")
        main()
    mock_app.assert_called_once_with(dashboard_path=None)


def test_main_unknown_command_errors(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "bogus"])
    # argparse calls parser.error → sys.exit(2) → SystemExit.
    with pytest.raises(SystemExit) as excinfo:
        # Patch uvicorn/create_app just to keep the surface tight; main()
        # should never reach them because parser.error fires first.
        with (
            patch("tier1.__main__.uvicorn.run"),
            patch("tier1.__main__.create_app", return_value="app"),
            patch("tier1.__main__.get_settings"),
        ):
            main()
    assert excinfo.value.code == 2


def test_main_returns_zero_on_success(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["tier1", "serve"])
    with (
        patch("tier1.__main__.uvicorn.run"),
        patch("tier1.__main__.create_app", return_value="app"),
    ):
        _settings(api_host="0.0.0.0", api_port=8000, dashboard_path="")
        result = main()
    assert result == 0
