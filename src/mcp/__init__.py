"""
Model Context Protocol (MCP) Server for Instagram Influencer Marketing.
Provides standard JSON-RPC 2.0 tool endpoints for external agents, Claude, Cursor,
Antigravity, and SaaS integrations.
"""
from src.mcp.server import MCPServer, mcp_server

__all__ = ["MCPServer", "mcp_server"]
