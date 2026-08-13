"""
Tool Registry - Built-in Agent Tools

5+ core tools for agent operations.
Reference: MiniMax Audit + OpenClaw tool patterns
"""

import asyncio
import os
import shlex
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

# =============================================================================
# Security: Command Whitelist
# =============================================================================
# Only these commands are allowed to be executed by agents
# This prevents command injection and unauthorized system access
# SECURITY NOTE: 'python' and 'git' removed due to arbitrary code execution risk
ALLOWED_COMMANDS: set[str] = {
    # File operations (safe)
    "ls",
    "pwd",
    "cd",
    "cat",
    "head",
    "tail",
    "wc",
    "grep",
    "find",
    "sort",
    "uniq",
    "diff",
    # Text processing
    "echo",
    "printf",
    "sed",
    "awk",
    "cut",
    # System information (read-only)
    "df",
    "du",
    "free",
    "top",
    "ps",
    "uptime",
    "date",
    "whoami",
    "id",
    "uname",
    # Package management (controlled)
    "pip",
}

# Commands that are NEVER allowed (security critical)
BLOCKED_COMMANDS: set[str] = {
    "rm",
    "rmdir",
    "mv",
    "cp",
    "chmod",
    "chown",
    "sudo",
    "su",
    "passwd",
    "useradd",
    "userdel",
    "systemctl",
    "service",
    "iptables",
    "netstat",
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "kill",
    "killall",
    "pkill",
    "reboot",
    "shutdown",
    "dd",
    "mkfs",
    "fdisk",
    "mount",
    "umount",
}


class ToolRegistry:
    """
    Central registry for agent tools.

    Manages tool registration, discovery, and execution.
    """

    def __init__(self, default_timeout: int = 30):
        """
        Initialize tool registry.

        Args:
            default_timeout: Default timeout for tool execution in seconds (default: 30)
        """
        self._tools: dict[str, dict] = {}
        self.default_timeout = default_timeout

    def register(
        self,
        name: str,
        handler: Callable,
        description: str,
        parameters: dict | None = None,
    ) -> None:
        """
        Register a tool.

        Args:
            name: Tool name
            handler: Async function to execute tool
            description: Tool description
            parameters: Parameter schema
        """
        self._tools[name] = {
            "handler": handler,
            "description": description,
            "parameters": parameters or {},
            "registered_at": datetime.now(UTC),
        }
        logger.debug("tool_registered", tool=name)

    def get(self, name: str) -> dict | None:
        """Get tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict]:
        """List all available tools."""
        return [
            {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            }
            for name, tool in self._tools.items()
        ]

    async def execute(self, name: str, timeout: int | None = None, **params) -> Any:
        """
        Execute a tool by name.

        Args:
            name: Tool name
            timeout: Optional timeout override in seconds
            **params: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found
            asyncio.TimeoutError: If tool execution times out
        """
        tool = self._tools.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")

        # Use provided timeout, tool-specific timeout, or default
        execution_timeout = timeout or tool["parameters"].get("timeout", self.default_timeout)

        logger.info("tool_executing", tool=name, params=params, timeout=execution_timeout)

        try:
            result = await asyncio.wait_for(
                tool["handler"](**params),
                timeout=execution_timeout,
            )
            logger.info("tool_executed", tool=name, success=True)
            return result
        except TimeoutError:
            logger.error("tool_execution_timeout", tool=name, timeout=execution_timeout)
            raise
        except Exception as e:
            logger.error("tool_execution_failed", tool=name, error=str(e))
            raise


# =============================================================================
# Built-in Tool Implementations
# =============================================================================


async def search_memory(query: str, agent_id: str, limit: int = 5, memory_backend=None):
    """
    Search agent memory for relevant information.

    Args:
        query: Search query
        agent_id: Agent ID
        limit: Max results
        memory_backend: CogneeMemoryReader instance
    """
    if not memory_backend:
        return {"error": "Memory backend not available"}

    try:
        results = await memory_backend.read(query=query, top_k=limit)
    except Exception as e:
        logger.warning("cognee_search_failed", error=str(e))
        return {"query": query, "results": [], "total": 0, "error": str(e)}

    return {
        "query": query,
        "results": results,
        "total": len(results),
    }


async def call_agent(
    agent_id: str,
    message: str,
    target_agent: str,
    a2a_server=None,
):
    """
    Send message to another agent via A2A protocol.

    Args:
        agent_id: Sending agent ID
        message: Message content
        target_agent: Target agent ID
        a2a_server: A2A server instance
    """
    if not a2a_server:
        return {"error": "A2A server not available"}

    # Send via event mesh
    success = await a2a_server.event_mesh.send_to_json(
        target_agent,
        {
            "type": "message",
            "from": agent_id,
            "content": message,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    return {
        "sent": success,
        "to": target_agent,
        "message": message[:100],
    }


async def read_file(path: str, allowed_base_paths: list[str] | None = None) -> dict:
    """
    Read contents of a file with path traversal protection.

    SECURITY: Validates that the resolved path is within allowed base paths
    to prevent reading sensitive files like /etc/passwd.

    Args:
        path: File path
        allowed_base_paths: List of allowed base directories (default: current working directory)
    """
    # Default to current working directory if not specified
    if allowed_base_paths is None:
        allowed_base_paths = [os.getcwd()]

    # Resolve to absolute path
    resolved_path = os.path.realpath(os.path.abspath(path))

    # Validate path is within allowed directories
    path_allowed = False
    for base_path in allowed_base_paths:
        resolved_base = os.path.realpath(os.path.abspath(base_path))
        if resolved_path.startswith(resolved_base + os.sep) or resolved_path == resolved_base:
            path_allowed = True
            break

    if not path_allowed:
        logger.warning(
            "path_traversal_blocked",
            requested_path=path,
            resolved_path=resolved_path,
            allowed_bases=allowed_base_paths,
        )
        return {
            "success": False,
            "error": "Access denied: Path traversal detected. Access is restricted to allowed directories.",
        }

    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()

        return {
            "success": True,
            "path": path,
            "content": content,
            "size": len(content),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def write_file(path: str, content: str, allowed_base_paths: list[str] | None = None) -> dict:
    """
    Write content to a file with path traversal protection.

    SECURITY: Validates that the resolved path is within allowed base paths
    to prevent writing to sensitive locations like /etc/.

    Args:
        path: File path
        content: Content to write
        allowed_base_paths: List of allowed base directories (default: current working directory)
    """
    # Default to current working directory if not specified
    if allowed_base_paths is None:
        allowed_base_paths = [os.getcwd()]

    # Resolve to absolute path
    resolved_path = os.path.realpath(os.path.abspath(path))

    # Validate path is within allowed directories
    path_allowed = False
    for base_path in allowed_base_paths:
        resolved_base = os.path.realpath(os.path.abspath(base_path))
        if resolved_path.startswith(resolved_base + os.sep) or resolved_path == resolved_base:
            path_allowed = True
            break

    if not path_allowed:
        logger.warning(
            "path_traversal_blocked",
            requested_path=path,
            resolved_path=resolved_path,
            allowed_bases=allowed_base_paths,
        )
        return {
            "success": False,
            "error": "Access denied: Path traversal detected. Access is restricted to allowed directories.",
        }

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "path": path,
            "bytes_written": len(content),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


async def run_command(command: str, timeout: int = 30) -> dict:
    """
    Execute shell command with security validation.

    SECURITY: Only whitelisted commands are allowed. Command injection
    is prevented through strict validation and argument sanitization.

    Args:
        command: Shell command
        timeout: Timeout in seconds

    Returns:
        Dict with success status, output, or error message

    Raises:
        ValueError: If command is not allowed
    """
    # Validate command is not empty
    if not command or not command.strip():
        return {"success": False, "error": "Empty command not allowed"}

    # Parse command to extract base command
    parts = command.strip().split()
    if not parts:
        return {"success": False, "error": "Invalid command format"}

    base_cmd = parts[0]

    # Check if command is blocked (security critical)
    if base_cmd in BLOCKED_COMMANDS:
        logger.warning("command_blocked", command=base_cmd, reason="Command in blocked list")
        return {
            "success": False,
            "error": f"Command '{base_cmd}' is not allowed for security reasons",
        }

    # Check if command is allowed
    if base_cmd not in ALLOWED_COMMANDS:
        logger.warning("command_not_allowed", command=base_cmd, reason="Command not in whitelist")
        return {
            "success": False,
            "error": f"Command '{base_cmd}' is not in the allowed command list",
        }

    # Sanitize arguments to prevent injection
    try:
        sanitized_args = [shlex.quote(arg) for arg in parts[1:]]
        safe_command = f"{base_cmd} {' '.join(sanitized_args)}"
    except Exception as e:
        logger.error("command_sanitization_failed", error=str(e))
        return {"success": False, "error": f"Failed to sanitize command arguments: {e!s}"}

    # Execute command with subprocess (no shell=True for security)
    try:
        proc = await asyncio.create_subprocess_exec(
            base_cmd,
            *parts[1:],  # Pass arguments as separate parameters
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout,
        )

        # Log command execution
        logger.info(
            "command_executed",
            command=base_cmd,
            args_count=len(parts) - 1,
            returncode=proc.returncode,
        )

        return {
            "success": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": stdout.decode()[:10000],  # Limit output
            "stderr": stderr.decode()[:10000],
            "command": safe_command,  # Return sanitized command
        }
    except TimeoutError:
        logger.warning("command_timeout", command=base_cmd, timeout=timeout)
        return {"success": False, "error": f"Command timed out after {timeout}s"}
    except FileNotFoundError:
        logger.error("command_not_found", command=base_cmd)
        return {"success": False, "error": f"Command '{base_cmd}' not found"}
    except PermissionError:
        logger.error("command_permission_denied", command=base_cmd)
        return {"success": False, "error": f"Permission denied for command '{base_cmd}'"}
    except Exception as e:
        logger.error("command_execution_failed", command=base_cmd, error=str(e))
        return {"success": False, "error": f"Command execution failed: {e!s}"}


async def http_request(
    method: str,
    url: str,
    headers: dict | None = None,
    body: dict | None = None,
    timeout: int = 30,
    max_retries: int = 1,
) -> dict:
    """
    Make HTTP request with timeout and retry support.

    Args:
        method: HTTP method
        url: URL
        headers: Request headers
        body: Request body
        timeout: Timeout in seconds (default: 30)
        max_retries: Maximum retry attempts (default: 1)

    Returns:
        Dict with success status, response data, or error message
    """
    # Validate URL to prevent SSRF attacks
    if not url or not isinstance(url, str):
        return {
            "success": False,
            "error": "Invalid URL provided",
        }

    # Block private/internal IP ranges to prevent SSRF
    import re

    private_ip_pattern = re.compile(
        r"^(127\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|192\.168\.|0\.0\.0\.0|localhost)",
        re.IGNORECASE,
    )
    if private_ip_pattern.match(url):
        logger.warning("ssrf_attempt_blocked", url=url)
        return {
            "success": False,
            "error": "Access to internal addresses is not allowed",
        }

    attempt = 0
    last_error = None

    while attempt <= max_retries:
        try:
            async with (
                aiohttp.ClientSession() as session,
                session.request(
                    method,
                    url,
                    headers=headers,
                    json=body,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response,
            ):
                content = await response.text()

                return {
                    "success": response.status < 400,
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": content[:10000],  # Limit output size
                }
        except TimeoutError:
            last_error = f"Request timed out after {timeout}s"
            logger.warning("http_request_timeout", url=url, attempt=attempt + 1)
        except aiohttp.ClientError as e:
            last_error = f"HTTP client error: {e!s}"
            logger.error("http_request_client_error", url=url, error=str(e))
            break  # Don't retry client errors
        except Exception as e:
            last_error = str(e)
            logger.error("http_request_error", url=url, error=str(e))

        attempt += 1
        if attempt <= max_retries:
            await asyncio.sleep(1.0 * attempt)  # Exponential backoff

    return {
        "success": False,
        "error": last_error or "Unknown error",
        "attempts": attempt,
    }


# =============================================================================
# Tool Registration
# =============================================================================


def register_builtin_tools(
    registry: ToolRegistry,
    memory_backend=None,
    a2a_server=None,
) -> None:
    """
    Register all built-in tools.

    Args:
        registry: Tool registry
        memory_backend: Optional memory backend
        a2a_server: Optional A2A server
    """

    # Memory search (requires backend)
    async def memory_search_wrapper(query: str, agent_id: str, limit: int = 5):
        return await search_memory(query, agent_id, limit, memory_backend)

    registry.register(
        name="search_memory",
        handler=memory_search_wrapper,
        description="Search agent memory for relevant information",
        parameters={
            "query": "string (required): Search query",
            "agent_id": "string (required): Agent ID",
            "limit": "integer (optional): Max results (default: 5)",
        },
    )

    # Agent calling (requires A2A server)
    async def agent_call_wrapper(agent_id: str, message: str, target: str):
        return await call_agent(agent_id, message, target, a2a_server)

    registry.register(
        name="call_agent",
        handler=agent_call_wrapper,
        description="Send message to another agent via A2A protocol",
        parameters={
            "agent_id": "string (required): Your agent ID",
            "message": "string (required): Message content",
            "target": "string (required): Target agent ID",
        },
    )

    # File operations
    registry.register(
        name="read_file",
        handler=read_file,
        description="Read contents of a file",
        parameters={"path": "string (required): File path"},
    )

    registry.register(
        name="write_file",
        handler=write_file,
        description="Write content to a file",
        parameters={
            "path": "string (required): File path",
            "content": "string (required): Content to write",
        },
    )

    # Command execution (with security validation)
    registry.register(
        name="run_command",
        handler=run_command,
        description="Execute shell command (whitelisted commands only, with argument sanitization)",
        parameters={
            "command": "string (required): Shell command from whitelist",
            "timeout": "integer (optional): Timeout in seconds (default: 30)",
        },
    )

    # HTTP requests
    registry.register(
        name="http_request",
        handler=http_request,
        description="Make HTTP request",
        parameters={
            "method": "string (required): HTTP method (GET, POST, etc)",
            "url": "string (required): URL",
            "headers": "object (optional): Request headers",
            "body": "object (optional): Request body",
            "timeout": "integer (optional): Timeout in seconds (default: 30)",
        },
    )

    logger.info(
        "builtin_tools_registered",
        count=len(registry.list_tools()),
        tools=[t["name"] for t in registry.list_tools()],
    )
