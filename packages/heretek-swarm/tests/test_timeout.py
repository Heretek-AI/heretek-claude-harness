"""Tests for HERETEK_TOOL_TIMEOUT configuration."""

import os
import importlib
from unittest.mock import patch


def test_tool_timeout_default():
    """Test that default timeout is 120 seconds."""
    with patch.dict(os.environ, {}, clear=True):
        # Remove HERETEK_TOOL_TIMEOUT if it exists
        os.environ.pop("HERETEK_TOOL_TIMEOUT", None)

        # Force reimport to pick up the new environment
        import heretek_swarm.validation.agent_messages
        importlib.reload(heretek_swarm.validation.agent_messages)

        assert heretek_swarm.validation.agent_messages.HERETEK_TOOL_TIMEOUT == 120


def test_tool_timeout_custom():
    """Test that custom timeout is respected."""
    with patch.dict(os.environ, {"HERETEK_TOOL_TIMEOUT": "180"}):
        # Force reimport to pick up the new environment
        import heretek_swarm.validation.agent_messages
        importlib.reload(heretek_swarm.validation.agent_messages)

        assert heretek_swarm.validation.agent_messages.HERETEK_TOOL_TIMEOUT == 180


def test_tool_timeout_max_clamp():
    """Test that timeout is clamped to maximum of 300 seconds."""
    with patch.dict(os.environ, {"HERETEK_TOOL_TIMEOUT": "500"}):
        # Force reimport to pick up the new environment
        import heretek_swarm.validation.agent_messages
        importlib.reload(heretek_swarm.validation.agent_messages)

        assert heretek_swarm.validation.agent_messages.HERETEK_TOOL_TIMEOUT == 300


def test_tool_timeout_min_clamp():
    """Test that timeout is clamped to minimum of 1 second."""
    with patch.dict(os.environ, {"HERETEK_TOOL_TIMEOUT": "0"}):
        # Force reimport to pick up the new environment
        import heretek_swarm.validation.agent_messages
        importlib.reload(heretek_swarm.validation.agent_messages)

        assert heretek_swarm.validation.agent_messages.HERETEK_TOOL_TIMEOUT == 1


def test_tool_timeout_negative_clamp():
    """Test that negative timeout is clamped to minimum of 1 second."""
    with patch.dict(os.environ, {"HERETEK_TOOL_TIMEOUT": "-10"}):
        # Force reimport to pick up the new environment
        import heretek_swarm.validation.agent_messages
        importlib.reload(heretek_swarm.validation.agent_messages)

        assert heretek_swarm.validation.agent_messages.HERETEK_TOOL_TIMEOUT == 1


def test_tool_request_default_timeout():
    """Test that ToolRequest uses HERETEK_TOOL_TIMEOUT as default."""
    from heretek_swarm.validation.agent_messages import ToolRequest, HERETEK_TOOL_TIMEOUT

    # Create a tool request without specifying timeout
    request = ToolRequest(
        tool_name="test_tool",
        arguments={},
        sender_id="test_agent"
    )

    # The timeout should be set to the default from environment
    assert request.timeout == HERETEK_TOOL_TIMEOUT


def test_code_execution_request_default_timeout():
    """Test that CodeExecutionRequest uses HERETEK_TOOL_TIMEOUT as default."""
    from heretek_swarm.validation.agent_messages import CodeExecutionRequest, HERETEK_TOOL_TIMEOUT

    # Create a code execution request without specifying timeout
    request = CodeExecutionRequest(
        code="print('hello')",
        sender_id="test_agent"
    )

    # The timeout should be set to the default from environment
    assert request.timeout == HERETEK_TOOL_TIMEOUT
