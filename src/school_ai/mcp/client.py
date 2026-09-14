"""Harness-facing MCP client boundary."""

from typing import Any, Protocol
from collections.abc import Callable

from school_ai.ai.models import ToolDefinition
from school_ai.mcp.server import SchoolMCPServer


class MCPClient(Protocol):
    @property
    def tool_definitions(self) -> tuple[ToolDefinition, ...]: ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class InProcessMCPClient:
    """First-milestone client using the same boundary without network transport."""

    def __init__(self, server: SchoolMCPServer, after_tool: Callable[[], None] | None = None) -> None:
        self._server = server
        self._after_tool = after_tool

    @property
    def tool_definitions(self) -> tuple[ToolDefinition, ...]:
        return self._server.tool_definitions

    def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            return self._server.call_tool(name, arguments)
        finally:
            if self._after_tool:
                self._after_tool()
