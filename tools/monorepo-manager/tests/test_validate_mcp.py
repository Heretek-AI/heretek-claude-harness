"""Tests for .mcp.json contract validation."""

from __future__ import annotations

import json
import pathlib

from scripts.lib.validate_mcp import validate_mcp


def _write(tmp_path: pathlib.Path, data: dict) -> str:
    p = tmp_path / ".mcp.json"
    p.write_text(json.dumps(data))
    return str(p)


def test_validate_mcp_accepts_minimal_stdio(tmp_path):
    data = {
        "mcpServers": {
            "github": {
                "description": "Official GitHub MCP",
                "transport": "stdio",
                "command": "github-mcp",
                "args": ["--owner", "Heretek-AI"],
                "timeoutSeconds": 30,
                "retry": 0,
            }
        }
    }
    assert validate_mcp(_write(tmp_path, data)) == []


def test_validate_mcp_rejects_bad_name(tmp_path):
    data = {
        "mcpServers": {
            "BadName": {
                "description": "wrong",
                "transport": "stdio",
                "command": "x",
                "args": [],
            }
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("name" in s.lower() for s in v)


def test_validate_mcp_rejects_missing_command_for_stdio(tmp_path):
    data = {"mcpServers": {"github": {"description": "x", "transport": "stdio", "args": []}}}
    v = validate_mcp(_write(tmp_path, data))
    assert any("command" in s for s in v)


def test_validate_mcp_rejects_bad_env_key(tmp_path):
    data = {
        "mcpServers": {
            "github": {
                "description": "x",
                "transport": "stdio",
                "command": "x",
                "args": [],
                "env": {"lowercase_key": "value"},
            }
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("env" in s.lower() for s in v)


def test_validate_mcp_rejects_plaintext_secret(tmp_path):
    data = {
        "mcpServers": {
            "github": {
                "description": "x",
                "transport": "stdio",
                "command": "x",
                "args": [],
                "env": {"GITHUB_TOKEN": "ghp_actualsecretvalue1234567890"},
            }
        }
    }
    v = validate_mcp(_write(tmp_path, data))
    assert any("plaintext" in s.lower() for s in v)
