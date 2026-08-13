"""
MCP Client for External Server Connections

Provides client for connecting to external MCP servers:
- Connect to remote MCP servers
- Proxy external tools into local registry
- Handle tool call requests to external servers
- Manage server health monitoring
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog

from heretek_swarm.mcp.registry import (
    MCPServerRegistry,
    MCPToolMetadata,
    MCPToolRegistry,
    ToolProviderType,
)

logger = structlog.get_logger("mcp.client")

# =============================================================================
# Error Messages (Constants)
# =============================================================================

CLIENT_NOT_CONNECTED = "Client not connected"


class MCPClient:
    """
    Client for connecting to external MCP servers.

    Manages connections to remote MCP servers and proxies
    their tools into the local registry.
    """

    def __init__(
        self,
        server_id: str,
        base_url: str,
        auth_token: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """
        Initialize MCP client.

        Args:
            server_id: Unique server identifier
            base_url: Server base URL
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
        """
        self._server_id = server_id
        self._base_url = base_url.rstrip("/")
        self._auth_token = auth_token
        self._timeout = timeout
        self._http_client: httpx.AsyncClient | None = None
        self._connected = False

    @property
    def server_id(self) -> str:
        """Get server ID."""
        return self._server_id

    @property
    def base_url(self) -> str:
        """Get base URL."""
        return self._base_url

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._connected

    async def connect(self) -> bool:
        """
        Connect to the MCP server.

        Returns:
            True if connection successful
        """
        try:
            self._http_client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._get_headers(),
            )

            # Verify connection with info endpoint
            response = await self._http_client.get("/mcp/info")
            response.raise_for_status()

            self._connected = True
            logger.info("mcp_client_connected", server_id=self._server_id)
            return True

        except Exception as e:
            logger.error(
                "mcp_client_connection_failed",
                server_id=self._server_id,
                error=str(e),
            )
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        self._connected = False
        logger.info("mcp_client_disconnected", server_id=self._server_id)

    async def list_tools(self) -> list[dict[str, Any]]:
        """
        List tools from the remote server.

        Returns:
            List of tool definitions
        """
        if not self._http_client:
            raise RuntimeError(CLIENT_NOT_CONNECTED)

        try:
            response = await self._http_client.get("/mcp/tools")
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])

        except Exception as e:
            logger.error(
                "mcp_client_list_tools_failed",
                server_id=self._server_id,
                error=str(e),
            )
            raise

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Call a tool on the remote server.

        Args:
            tool_name: Tool name to invoke
            arguments: Tool arguments
            context: Optional context

        Returns:
            Tool invocation result
        """
        if not self._http_client:
            raise RuntimeError(CLIENT_NOT_CONNECTED)

        try:
            response = await self._http_client.post(
                "/mcp/tools/call",
                json={
                    "name": tool_name,
                    "arguments": arguments,
                    "context": context,
                },
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(
                "mcp_client_call_tool_failed",
                server_id=self._server_id,
                tool_name=tool_name,
                error=str(e),
            )
            raise

    async def get_tool_details(self, tool_name: str) -> dict[str, Any]:
        """
        Get details for a specific tool.

        Args:
            tool_name: Tool name

        Returns:
            Tool details
        """
        if not self._http_client:
            raise RuntimeError(CLIENT_NOT_CONNECTED)

        try:
            response = await self._http_client.get(f"/mcp/tools/{tool_name}")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(
                "mcp_client_get_tool_failed",
                server_id=self._server_id,
                tool_name=tool_name,
                error=str(e),
            )
            raise

    async def health_check(self) -> dict[str, Any]:
        """
        Check remote server health.

        Returns:
            Health status
        """
        if not self._http_client:
            raise RuntimeError(CLIENT_NOT_CONNECTED)

        try:
            response = await self._http_client.get("/mcp/health")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(
                "mcp_client_health_check_failed",
                server_id=self._server_id,
                error=str(e),
            )
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers including auth."""
        headers = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers


class MCPClientManager:
    """
    Manager for MCP client connections.

    Manages multiple external MCP server connections
    and proxies their tools into a local registry.
    """

    def __init__(self, local_registry: MCPToolRegistry) -> None:
        """
        Initialize client manager.

        Args:
            local_registry: Local tool registry to proxy tools into
        """
        self._local_registry = local_registry
        self._server_registry = MCPServerRegistry()
        self._clients: dict[str, MCPClient] = {}
        self._proxied_tools: dict[str, str] = {}  # tool_name -> server_id

    @property
    def server_registry(self) -> MCPServerRegistry:
        """Get server registry."""
        return self._server_registry

    async def connect_server(
        self,
        server_id: str,
        name: str,
        base_url: str,
        auth_token: str | None = None,
        proxy_tools: bool = True,
    ) -> bool:
        """
        Connect to an external MCP server.

        Args:
            server_id: Unique server identifier
            name: Human-readable server name
            base_url: Server base URL
            auth_token: Optional authentication token
            proxy_tools: Whether to proxy server tools

        Returns:
            True if connection successful
        """
        if server_id in self._clients:
            logger.warning("mcp_server_already_connected", server_id=server_id)
            return False

        # Register server
        self._server_registry.register_server(
            server_id=server_id,
            name=name,
            base_url=base_url,
            auth_token=auth_token,
        )

        # Create and connect client
        client = MCPClient(
            server_id=server_id,
            base_url=base_url,
            auth_token=auth_token,
        )

        if await client.connect():
            self._clients[server_id] = client
            self._server_registry.set_client(server_id, client)
            self._server_registry.update_server_status(server_id, "connected")

            # Proxy tools if requested
            if proxy_tools:
                await self._proxy_server_tools(server_id)

            logger.info("mcp_external_server_connected", server_id=server_id)
            return True

        self._server_registry.update_server_status(
            server_id,
            "connection_failed",
        )
        return False

    async def disconnect_server(self, server_id: str) -> bool:
        """
        Disconnect from an MCP server.

        Args:
            server_id: Server identifier

        Returns:
            True if disconnected
        """
        if server_id not in self._clients:
            return False

        client = self._clients[server_id]
        await client.disconnect()

        # Unregister proxied tools
        tools_to_remove = [
            tool_name for tool_name, srv_id in self._proxied_tools.items() if srv_id == server_id
        ]
        for tool_name in tools_to_remove:
            self._local_registry.unregister_tool(tool_name)
            self._proxied_tools.pop(tool_name)

        self._clients.pop(server_id)
        self._server_registry.unregister_server(server_id)

        logger.info("mcp_external_server_disconnected", server_id=server_id)
        return True

    async def _proxy_server_tools(self, server_id: str) -> None:
        """
        Proxy tools from a remote server to local registry.

        Args:
            server_id: Server to proxy tools from
        """
        client = self._clients.get(server_id)
        if not client:
            return

        try:
            remote_tools = await client.list_tools()

            for tool_def in remote_tools:
                tool_name = tool_def["name"]

                # Create proxy handler
                async def create_proxy_handler(
                    srv_id: str,
                    tool_nm: str,
                ):
                    async def proxy_handler(
                        arguments: dict[str, Any],
                        context: dict[str, Any] | None = None,
                    ):
                        result = await self._clients[srv_id].call_tool(
                            tool_nm,
                            arguments,
                            context,
                        )
                        return result.get("result", result)

                    return proxy_handler

                handler = await create_proxy_handler(server_id, tool_name)

                # Create metadata
                metadata = MCPToolMetadata(
                    name=tool_name,
                    description=tool_def.get("description", ""),
                    input_schema=tool_def.get("inputSchema", {}),
                    output_schema=tool_def.get("outputSchema"),
                    category=tool_def.get("category", "external"),
                    version=tool_def.get("version", "1.0.0"),
                    provider=ToolProviderType.PROXIED,
                    server_id=server_id,
                    tags=tool_def.get("tags", []),
                )

                self._local_registry.register_tool(metadata, handler)
                self._proxied_tools[tool_name] = server_id

                logger.debug(
                    "mcp_tool_proxied",
                    tool_name=tool_name,
                    server_id=server_id,
                )

        except Exception as e:
            logger.error(
                "mcp_tool_proxy_failed",
                server_id=server_id,
                error=str(e),
            )

    async def get_server_health(self, server_id: str) -> dict[str, Any]:
        """
        Get health status of a server.

        Args:
            server_id: Server identifier

        Returns:
            Health status
        """
        client = self._clients.get(server_id)
        if not client:
            return {"status": "not_connected"}

        return await client.health_check()

    def list_servers(self) -> list[dict[str, Any]]:
        """List all connected servers."""
        return self._server_registry.list_servers()

    def list_proxied_tools(self, server_id: str | None = None) -> list[str]:
        """
        List proxied tool names.

        Args:
            server_id: Optional server filter

        Returns:
            List of tool names
        """
        if server_id:
            return [name for name, srv_id in self._proxied_tools.items() if srv_id == server_id]
        return list(self._proxied_tools.keys())
