"""SoAI - MCP utility tool runtime argument validation [backend/mcp/tools/argument_runtime.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from core.runtime.request_context import create_system_context
from core.users.user_id import is_strict_user_id
from mcp.tools.error import MCPToolError

if TYPE_CHECKING:
    from core.runtime.request_context import RequestContext
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("require_authenticated_user_id", "resolve_tool_request_context")


def require_authenticated_user_id(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    tool_name: str,
    message: str | None = None,
) -> int:
    user_id = utility_tools.runtime_sessions.current_user_id()
    if not is_strict_user_id(user_id):
        resolved_message = (
            message
            if isinstance(message, str) and message.strip()
            else f"Authenticated user is required for {tool_name}."
        )
        raise MCPToolError(-32603, resolved_message)
    return int(user_id)


def resolve_tool_request_context(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    tool_name: str,
) -> RequestContext:
    request_context = utility_tools.active_request_context.get(None)
    if request_context is not None:
        return request_context
    return create_system_context(
        f"mcp_{tool_name}",
        user_id=utility_tools.runtime_sessions.current_user_id(),
    )
