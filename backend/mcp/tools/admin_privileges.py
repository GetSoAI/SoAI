"""SoAI - MCP admin privilege checks [backend/mcp/tools/admin_privileges.py]"""
# SPDX-License-Identifier: LicenseRef-SoAI-Source-1.0

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp.tools.error import MCPToolError
from mcp.tools.user_permission_records import resolve_tool_user_is_admin

if TYPE_CHECKING:
    from mcp.tools.internal_protocols import MCPUtilityToolsProtocol

__all__ = ("require_admin_user",)


async def require_admin_user(
    utility_tools: MCPUtilityToolsProtocol,
    *,
    user_id: int,
    tool_name: str,
) -> None:
    if not await resolve_tool_user_is_admin(utility_tools, user_id=user_id):
        raise MCPToolError(-32603, f"Admin privileges required for {tool_name}.")
