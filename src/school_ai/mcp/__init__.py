"""MCP adapter over application services."""

from school_ai.mcp.client import InProcessMCPClient, MCPClient
from school_ai.mcp.server import SchoolMCPServer, create_mcp_sdk_server

__all__ = [
    "InProcessMCPClient",
    "MCPClient",
    "SchoolMCPServer",
    "create_mcp_sdk_server",
]
