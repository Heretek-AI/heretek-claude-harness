"""Tests for CLI entry point (__main__.py)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from tier1.__main__ import main


def test_serve_calls_uvicorn(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tier1", "serve", "--host", "127.0.0.1", "--port", "9000"])
    with (
        patch("tier1.__main__.uvicorn.run") as mock_run,
        patch("tier1.__main__.create_app", return_value="app") as mock_app,
        patch("tier1.__main__.get_settings") as mock_settings,
    ):
        mock_settings.return_value.api_host = "0.0.0.0"
        mock_settings.return_value.api_port = 8000
        mock_settings.return_value.dashboard_path = ""
        result = main()
    assert result == 0
    mock_run.assert_called_once()
    mock_app.assert_called_once_with(dashboard_path=None)


def test_serve_with_dashboard_path(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tier1", "serve", "--dashboard-path", "/tmp/dash"])
    with (
        patch("tier1.__main__.uvicorn.run"),
        patch("tier1.__main__.create_app") as mock_app,
        patch("tier1.__main__.get_settings") as mock_settings,
    ):
        mock_settings.return_value.api_host = "0.0.0.0"
        mock_settings.return_value.api_port = 8000
        mock_settings.return_value.dashboard_path = ""
        main()
    mock_app.assert_called_once_with(dashboard_path=Path("/tmp/dash"))


def test_unknown_command_exits(monkeypatch):
    monkeypatch.setattr("sys.argv", ["tier1", "bogus"])
    with patch("tier1.__main__.get_settings"):
        with pytest.raises(SystemExit, match="2"):
            main()
