"""
Heretek Swarm MCP (Model Context Protocol) Package

Provides MCP server implementation for dynamic tool loading,
external system integration, and agent capability expansion.

Modules:
    server: MCP HTTP server implementation
    registry: Tool registry for MCP tools
    client: Client for connecting to external MCP servers
"""

from heretek_swarm.mcp.registry import MCPServerRegistry, MCPToolRegistry
from heretek_swarm.mcp.server import MCPServer

__all__ = [
    "MCPServer",
    "MCPServerRegistry",
    "MCPToolRegistry",
]

__version__ = "0.2.0"
