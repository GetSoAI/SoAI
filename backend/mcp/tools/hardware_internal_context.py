"""SoAI - MCP hardware internal execution context checks [backend/mcp/tools/hardware_internal_context.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("require_hardware_internal_execute_context",)


def require_hardware_internal_execute_context(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    tool_name: str,
) -> RequestContext:
    request_context = utility_tools.active_request_context.get(None)
    if request_context is None:
        raise MCPToolError(-32603, f"{tool_name} is internal-only and requires a request context.")
    if request_context.agent_mode != "execute":
        raise MCPToolError(-32603, f"{tool_name} requires execute-mode agent context.")
    if request_context.agent_turn_id is None or not request_context.agent_turn_id:
        raise MCPToolError(-32603, f"{tool_name} requires an active agent turn.")
    tool_context = request_context.mcp_tool_context
    if tool_context is None:
        raise MCPToolError(-32603, f"{tool_name} requires selected MCP tool context.")
    if tool_name not in tool_context.tool_map:
        raise MCPToolError(-32603, f"{tool_name} was not selected for this agent turn.")
    return request_context
