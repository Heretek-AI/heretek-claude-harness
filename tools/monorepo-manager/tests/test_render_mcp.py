"""Tests for the .mcp.json renderer."""

from __future__ import annotations

import json

import pytest

from scripts.lib.render_mcp import render_mcp_named


def _server(name: str, **kwargs) -> dict:
    base = {"description": f"{name} MCP", "transport": "stdio", "command": name, "args": []}
    base.update(kwargs)
    return {name: base}


def test_render_mcp_minimal():
    servers = _server("github")
    out = render_mcp_named(servers)
    parsed = json.loads(out)
    assert "mcpServers" in parsed
    assert "github" in parsed["mcpServers"]


def test_render_mcp_includes_multiple_servers():
    servers = {**_server("github"), **_server("sonarqube")}
    parsed = json.loads(render_mcp_named(servers))
    assert set(parsed["mcpServers"].keys()) == {"github", "sonarqube"}


def test_render_mcp_rejects_invalid_name():
    servers = {"BadName": {"description": "x", "transport": "stdio", "command": "x", "args": []}}
    with pytest.raises(ValueError):
        render_mcp_named(servers)


def test_render_mcp_serialises_args_and_env():
    servers = {
        "github": {
            "description": "github",
            "transport": "stdio",
            "command": "github-mcp",
            "args": ["--owner", "Heretek-AI"],
            "env": {"GITHUB_TOKEN": None},
            "timeoutSeconds": 30,
        }
    }
    parsed = json.loads(render_mcp_named(servers))
    g = parsed["mcpServers"]["github"]
    assert g["args"] == ["--owner", "Heretek-AI"]
    assert g["env"] == {"GITHUB_TOKEN": None}
    assert g["timeoutSeconds"] == 30
