/**
 * MCP Tools API Client
 *
 * Provides methods for listing and toggling MCP tools via the backend API.
 * All state comes from the server — no localStorage for tool state.
 */

import { api } from './client';

// =============================================================================
// TypeScript Interfaces
// =============================================================================

/** Summary of an MCP tool as returned by GET /mcp/tools */
export interface MCPToolSummary {
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
  outputSchema: Record<string, unknown> | null;
  category: string;
  version: string;
  enabled: boolean;
}

/** Response shape for GET /mcp/tools */
export interface MCPToolsListResponse {
  tools: MCPToolSummary[];
  total: number;
  categories: string[];
}

/** Request body for PUT /mcp/tools/toggle/{name} */
export interface ToolToggleRequest {
  enabled: boolean;
}

/** Response shape for PUT /mcp/tools/toggle/{name} */
export interface ToolToggleResponse {
  name: string;
  enabled: boolean;
  success: boolean;
}

// =============================================================================
// API Methods
// =============================================================================

export const mcpToolsApi = {
  /**
   * Fetch all registered MCP tools.
   * Returns tools with name, description, category, and enabled status.
   */
  listTools: async (): Promise<MCPToolsListResponse> => {
    const response = await api.get<MCPToolsListResponse>('/mcp/tools');
    return response.data;
  },

  /**
   * Toggle a tool's enabled state.
   * @param name - Tool name to toggle
   * @param enabled - New enabled state
   */
  toggleTool: async (name: string, enabled: boolean): Promise<ToolToggleResponse> => {
    const response = await api.put<ToolToggleResponse>(
      `/mcp/tools/toggle/${encodeURIComponent(name)}`,
      { enabled } as ToolToggleRequest
    );
    return response.data;
  },
};

export default mcpToolsApi;
